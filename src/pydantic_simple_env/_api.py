# src/pydantic_simple_env/_api.py

from typing import Annotated, get_origin

from pydantic import BaseModel, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic_settings.sources.types import EnvNoneType

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

    Users typically interact with `SimpleEnvParser()` via `Annotated[...]`
    metadata, not this class directly.
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
    """Return `Annotated[...]` metadata describing simple env parsing rules.

    Annotate fields with `Annotated[T, SimpleEnvParser(...)]` to enable simple
    environment variable parsing.

    Default behaviors (hardcoded within this source's logic):
    - Items are always stripped of leading/trailing whitespace.
    - An empty input string (e.g., "", ",,,") for lists/sets/variable tuples
      always results in an empty collection ([], {}, ()).

    For dictionaries, `kv_delimiter` must be explicitly configured if it's not
    the default empty string.

    Examples:
        - `field: Annotated[list[int], SimpleEnvParser()] =`
          `Field(default_factory=list[int])`
        - `field: Annotated[dict[str, str], SimpleEnvParser(kv_delimiter='=')] =`
          `Field(default_factory=dict[str, str])`

    """
    return [SimpleEnvConfig(item_delimiter=item_delimiter, kv_delimiter=kv_delimiter)]


type SimpleParsed[T] = Annotated[T, SimpleEnvParser()]
"""Convenience alias for the default parser configuration.

Use `SimpleParsed[T]` as shorthand for `Annotated[T, SimpleEnvParser()]`.
For custom delimiters, use explicit `Annotated[T, SimpleEnvParser(...)]`.
"""


class SimpleEnvSettingsSource(EnvSettingsSource):
    """`EnvSettingsSource` subclass implementing simple environment parsing.

    This `EnvSettingsSource` subclass provides the implementation for simple
    variable parsing based on `SimpleEnvConfig` instances found in annotation
    metadata.

    It specifically processes fields annotated with `SimpleEnvConfig` and otherwise
    defers to other sources or Pydantic's default behavior.
    Most users should inherit from `BaseSimpleEnvSettings` instead of
    interacting with this directly.
    """

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: object,
        value_is_complex: bool,  # noqa: FBT001 # inherited method signature
    ) -> object:
        parsing_config = self._get_parsing_config(field)
        if parsing_config is None:
            return super().prepare_field_value(
                field_name, field, value, value_is_complex
            )

        if value is None or isinstance(value, EnvNoneType):
            return value

        if not isinstance(value, str):
            return super().prepare_field_value(
                field_name, field, value, value_is_complex
            )

        return self._parse_simple_env_value(field_name, field, value, parsing_config)

    def _parse_simple_env_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: str,
        parsing_config: SimpleEnvConfig,
    ) -> object:
        resolved_annotation = self._resolve_annotation(field.annotation)
        origin = get_origin(resolved_annotation)
        parsed_annotation_args = annotation_args(resolved_annotation)

        if origin is dict and not parsing_config.kv_delimiter:
            raise TypeError(
                f"Field '{field_name}' is a Dict and is configured with "
                "SimpleEnvParser(), but no 'kv_delimiter' is specified in "
                "the config. Please use "
                "SimpleEnvParser(kv_delimiter=':') or similar for "
                "dictionaries.",
            )

        if origin is list:
            return parse_list_or_set_from_env(
                field_name,
                list,
                parsed_annotation_args,
                value,
                parsing_config,
            )
        if origin is set:
            return parse_list_or_set_from_env(
                field_name,
                set,
                parsed_annotation_args,
                value,
                parsing_config,
            )
        if origin is tuple:
            if parsed_annotation_args and parsed_annotation_args[-1] is Ellipsis:
                return parse_variable_tuple_from_env(
                    field_name,
                    parsed_annotation_args,
                    value,
                    parsing_config,
                )
            return parse_fixed_tuple_from_env(
                field_name,
                parsed_annotation_args,
                value,
                parsing_config,
            )
        if origin is dict:
            return parse_dict_from_env(
                field_name,
                parsed_annotation_args,
                value,
                parsing_config,
            )

        raise TypeError(
            f"Field '{field_name}' is configured with SimpleEnvParser() "
            f"but its type hint ({resolved_annotation}) is not a List, Set, "
            "Tuple, or Dict.",
        )

    def _get_parsing_config(self, field: FieldInfo) -> SimpleEnvConfig | None:
        for meta_item in self._iter_metadata_items(field.metadata):
            if isinstance(meta_item, SimpleEnvConfig):
                return meta_item

        annotation_metadata = self._annotation_metadata_items(field.annotation)
        for meta_item in self._iter_metadata_items(annotation_metadata):
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

    def _annotation_metadata_items(self, annotation: object) -> list[object]:
        flattened: list[object] = []
        queue: list[object] = [annotation]

        while queue:
            current = queue.pop()
            origin = get_origin(current)

            if origin is Annotated:
                args = annotation_args(current)
                if args:
                    queue.append(args[0])
                    flattened.extend(args[1:])
                continue

            if origin is not None and hasattr(origin, "__value__"):
                alias_value = getattr(origin, "__value__", None)
                alias_args = annotation_args(current)
                if alias_value is None:
                    continue

                if alias_args:
                    try:
                        queue.append(
                            alias_value[
                                alias_args[0] if len(alias_args) == 1 else alias_args
                            ],
                        )
                    except TypeError:
                        queue.append(alias_value)
                else:
                    queue.append(alias_value)
                continue

            if hasattr(current, "__value__"):
                alias_value = getattr(current, "__value__", None)
                if alias_value is not None:
                    queue.append(alias_value)

        return flattened

    def _resolve_annotation(self, annotation: object) -> object:
        current = annotation
        seen: set[int] = set()

        while id(current) not in seen:
            seen.add(id(current))
            origin = get_origin(current)

            if origin is Annotated:
                args = annotation_args(current)
                if args:
                    current = args[0]
                    continue
                return current

            if origin is not None and hasattr(origin, "__value__"):
                alias_value = getattr(origin, "__value__", None)
                alias_args = annotation_args(current)
                if alias_value is None:
                    return current

                if alias_args:
                    try:
                        current = alias_value[
                            alias_args[0] if len(alias_args) == 1 else alias_args
                        ]
                    except TypeError:
                        current = alias_value
                else:
                    current = alias_value
                continue

            if hasattr(current, "__value__"):
                alias_value = getattr(current, "__value__", None)
                if alias_value is not None:
                    current = alias_value
                    continue

            return current

        return current

    def _iter_metadata_items(self, items: list[object]) -> list[object]:
        flattened: list[object] = []
        for item in items:
            if is_object_list(item):
                flattened.extend(self._iter_metadata_items(item))
            else:
                flattened.append(item)
        return flattened


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
