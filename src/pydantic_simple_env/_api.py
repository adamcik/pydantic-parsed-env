# src/pydantic_simple_env/_api.py

import json
import os
from typing import get_origin

# Import Field from pydantic for metadata argument
from pydantic import BaseModel, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)

from ._parsers import (
    annotation_args,
    is_mapping_str_object,
    is_object_list,
    parse_dict_from_env,
    parse_fixed_tuple_from_env,
    parse_list_or_set_from_env,
    parse_variable_tuple_from_env,
)

# --- 1. Base Configuration Model for Simple Environment Parsing ---


class SimpleEnvConfig(BaseModel):
    """Internal configuration model for `SimpleEnvParser()`.

    Stores delimiter settings.

    Users typically interact with `SimpleEnvParser()` for annotation via
    `Field(metadata=...)`, not this class directly.
    """

    item_delimiter: str = ","
    """Delimiter for items in lists/sets/tuples."""
    kv_delimiter: str = (
        ""  # Default to empty string; forces explicit setting for dicts.
    )
    """Delimiter for key:value within dict entries."""

    @model_validator(mode="after")
    def check_delimiters(self) -> "SimpleEnvConfig":
        """Ensure delimiters are distinct when dictionary parsing is enabled.

        Ensure item_delimiter and kv_delimiter are not the same for dicts,
        if kv_delimiter is provided.
        """
        if self.kv_delimiter and self.item_delimiter == self.kv_delimiter:
            raise ValueError(
                f"item_delimiter ('{self.item_delimiter}') cannot be the same as "
                f"kv_delimiter ('{self.kv_delimiter}'). "
                "This would create parsing ambiguity.",
            )
        return self


# --- Annotation Factory Function ---


def SimpleEnvParser(  # noqa: N802 # public API name is intentionally PascalCase
    item_delimiter: str = ",",
    kv_delimiter: str = "",
) -> list[SimpleEnvConfig]:
    """Return a list containing a `SimpleEnvConfig` instance for `Field(metadata=...)`.

    Annotate fields with `Field(metadata=SimpleEnvParser())` to enable
    simple environment variable parsing.

    Default behaviors (hardcoded within this source's logic):
    - Items are always stripped of leading/trailing whitespace.
    - An empty input string (e.g., "", ",,,") for lists/sets/variable tuples
      always results in an empty collection ([], {}, ()).

    For dictionaries, `kv_delimiter` must be explicitly configured if it's not
    the default empty string.

    Examples:
        - `field: List[int] = Field(metadata=SimpleEnvParser())`
        - `field: Dict[str, str] = Field(metadata=SimpleEnvParser(kv_delimiter='='))`

    """
    # Return a list containing the SimpleEnvConfig instance.
    # Field(metadata=...) expects a heterogeneous list of metadata objects.
    return [SimpleEnvConfig(item_delimiter=item_delimiter, kv_delimiter=kv_delimiter)]


class SimpleEnvSettingsSource(EnvSettingsSource):
    """`EnvSettingsSource` subclass implementing simple environment parsing.

    This `EnvSettingsSource` subclass provides the implementation for simple
    variable parsing based on `SimpleEnvConfig` instances found in
    `Field(metadata=...)`.

    It specifically processes fields annotated with `SimpleEnvConfig` and otherwise
    defers to other sources or Pydantic's default behavior.
    Most users should inherit from `BaseSimpleEnvSettings` instead of
    interacting with this directly.
    """

    def __call__(self) -> dict[str, object]:
        data: dict[str, object] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            env_val_from_source = self._get_env_val(field, field_name)

            if env_val_from_source is None:
                continue

            parsing_config = self._get_parsing_config(field)

            if parsing_config is None:
                data[field_name] = self._parse_default_env_value(
                    field,
                    env_val_from_source,
                )
                continue  # Skip processing by this source

            # --- If we reach here, value IS from env AND has our custom config ---
            value = env_val_from_source  # Raw string from environment

            origin = get_origin(field.annotation)
            parsed_annotation_args = annotation_args(field.annotation)

            if origin is dict and not parsing_config.kv_delimiter:
                raise TypeError(
                    f"Field '{field_name}' is a Dict and is configured with "
                    "SimpleEnvParser(), but no 'kv_delimiter' is specified in "
                    "the config. Please use "
                    "SimpleEnvParser(kv_delimiter=':') or similar for "
                    "dictionaries.",
                )

            if origin is list:
                parsed_value = parse_list_or_set_from_env(
                    field_name,
                    list,
                    parsed_annotation_args,
                    value,
                    parsing_config,
                )
            elif origin is set:
                parsed_value = parse_list_or_set_from_env(
                    field_name,
                    set,
                    parsed_annotation_args,
                    value,
                    parsing_config,
                )
            elif origin is tuple:
                if parsed_annotation_args and parsed_annotation_args[-1] is Ellipsis:
                    parsed_value = parse_variable_tuple_from_env(
                        field_name,
                        parsed_annotation_args,
                        value,
                        parsing_config,
                    )
                else:
                    parsed_value = parse_fixed_tuple_from_env(
                        field_name,
                        parsed_annotation_args,
                        value,
                        parsing_config,
                    )
            elif origin is dict:
                parsed_value = parse_dict_from_env(
                    field_name,
                    parsed_annotation_args,
                    value,
                    parsing_config,
                )
            else:
                raise TypeError(
                    f"Field '{field_name}' is configured with SimpleEnvParser() "
                    f"but its type hint ({field.annotation}) is not a List, Set, "
                    "Tuple, or Dict.",
                )

            data[field_name] = parsed_value

        return data

    def _get_parsing_config(self, field: FieldInfo) -> SimpleEnvConfig | None:
        for meta_item in self._iter_metadata_items(field.metadata):
            if isinstance(meta_item, SimpleEnvConfig):
                return meta_item

        metadata_items: list[object] = []
        schema_extra = field.json_schema_extra
        if is_mapping_str_object(schema_extra):
            raw_metadata = schema_extra.get("metadata", [])
            if is_object_list(raw_metadata):
                metadata_items = raw_metadata

        for meta_item in self._iter_metadata_items(metadata_items):
            if isinstance(meta_item, SimpleEnvConfig):
                return meta_item

        return None

    def _iter_metadata_items(self, items: list[object]) -> list[object]:
        flattened: list[object] = []
        for item in items:
            if is_object_list(item):
                flattened.extend(self._iter_metadata_items(item))
            else:
                flattened.append(item)
        return flattened

    def _parse_default_env_value(self, field: FieldInfo, raw_value: str) -> object:
        origin = get_origin(field.annotation)
        if origin in (list, set, tuple, dict):
            return json.loads(raw_value)
        return raw_value

    def _get_env_val(self, field: FieldInfo, field_name: str) -> str | None:
        env_names = [field.alias] if field.alias else [field_name]
        env_names = [
            f"{self.config.get('env_prefix', '')}{n.upper()}" for n in env_names
        ]

        for env_name in env_names:
            if env_name in os.environ:
                return os.environ[env_name]
        return None


# --- 3. Base Class for Simple Environment Parsing Settings ---


class BaseSimpleEnvSettings(BaseSettings):
    """Enable simple environment parsing for Pydantic settings models.

    parsing via `SimpleEnvConfig` annotations, avoiding complex JSON strings.
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG003 # required by BaseSettings signature
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
        PydanticBaseSettingsSource,
    ]:
        return (
            init_settings,
            SimpleEnvSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )
