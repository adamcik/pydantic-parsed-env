# src/pydantic_parsed_env/_api.py

import inspect
import json
from typing import Annotated, Any, get_origin

from pydantic import BaseModel, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
)
from pydantic_settings.sources import PydanticBaseEnvSettingsSource
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


class ParseConfig(BaseModel):
    """Internal configuration model for `ParseOptions()`.

    Stores delimiter settings.

    Users typically interact with `ParseOptions()` via `Annotated[...]`
    metadata, not this class directly.
    """

    item_delimiter: str = ","
    """Environment delimiter; an unset field uses newlines in secret files."""
    kv_delimiter: str = "="
    """Delimiter for key:value within dict entries."""
    json_compatibility: bool = False
    """Enable JSON-first parsing for JSON-like values before simple parsing."""

    @model_validator(mode="after")
    def check_delimiters(self) -> "ParseConfig":
        """Reject an explicitly ambiguous pair before source defaults are resolved."""
        explicit_pair = {"item_delimiter", "kv_delimiter"} <= self.model_fields_set
        if (
            explicit_pair
            and self.kv_delimiter
            and self.item_delimiter == self.kv_delimiter
        ):
            raise ValueError(
                f"item_delimiter ('{self.item_delimiter}') cannot be the same as "
                f"kv_delimiter ('{self.kv_delimiter}'). "
                "This would create parsing ambiguity.",
            )
        return self


def ParseOptions(  # noqa: N802 # public API name is intentionally PascalCase
    item_delimiter: str | None = None,
    kv_delimiter: str | None = None,
    *,
    json_compatibility: bool = False,
) -> list[ParseConfig]:
    """Return `Annotated[...]` metadata describing simple env parsing rules.

    Annotate fields with `Annotated[T, ParseOptions(...)]` to enable simple
    environment variable parsing.

    Default behaviors:
    - Items are comma-separated in environment and dotenv values, and
      newline-separated in secret files. An explicit item_delimiter applies
      to every source, including an explicit comma.
    - Dictionary keys and values are separated by '=' in every source.
    - Items are always stripped of leading/trailing whitespace.
    - An empty input string (e.g., "", ",,,") for lists/sets/variable tuples
      always results in an empty collection ([], {}, ()).

    Examples:
        - `field: Annotated[list[int], ParseOptions()] =`
          `Field(default_factory=list[int])`
        - `field: Annotated[dict[str, str], ParseOptions(kv_delimiter='=')] =`
          `Field(default_factory=dict[str, str])`

    """
    options: dict[str, str | bool] = {"json_compatibility": json_compatibility}
    if item_delimiter is not None:
        options["item_delimiter"] = item_delimiter
    if kv_delimiter is not None:
        options["kv_delimiter"] = kv_delimiter
    return [ParseConfig.model_validate(options)]


type Parsed[T] = Annotated[T, ParseOptions()]
"""Convenience alias for `Annotated[T, ParseOptions()]`."""


class _ParsedSettingsSource(PydanticBaseEnvSettingsSource):
    """Share decoding while preserving each source's lookup and fallback behavior."""

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
        parsing_config: ParseConfig,
    ) -> object:
        resolved_annotation = self._resolve_annotation(field.annotation)
        origin = get_origin(resolved_annotation)
        parsed_annotation_args = annotation_args(resolved_annotation)

        if self._should_try_json_compatibility(value, parsing_config):
            try:
                return self._parse_json_value(value)
            except ValueError:
                pass

        if origin is dict and not parsing_config.kv_delimiter:
            raise TypeError(
                f"Field '{field_name}' is a Dict and is configured with "
                "ParseOptions(), but no 'kv_delimiter' is specified in "
                "the config. Please use "
                "ParseOptions(kv_delimiter=':') or similar for "
                "dictionaries.",
            )

        if origin is dict:
            # Validate the effective pair only for dictionaries. A sequence may
            # use '=' as its item delimiter without using a key-value delimiter.
            parsing_config = ParseConfig(
                item_delimiter=parsing_config.item_delimiter,
                kv_delimiter=parsing_config.kv_delimiter,
                json_compatibility=parsing_config.json_compatibility,
            )

        try:
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
        except ValueError as error:
            if self._looks_json_like(value) and not parsing_config.json_compatibility:
                raise ValueError(
                    f"{error} Value looks like JSON; "
                    "enable ParseOptions(json_compatibility=True).",
                ) from error
            raise

        raise TypeError(
            f"Field '{field_name}' is configured with ParseOptions() "
            f"but its type hint ({resolved_annotation}) is not a List, Set, "
            "Tuple, or Dict.",
        )

    def _should_try_json_compatibility(
        self,
        value: str,
        parsing_config: ParseConfig,
    ) -> bool:
        if not parsing_config.json_compatibility:
            return False

        return self._looks_json_like(value)

    def _looks_json_like(self, value: str) -> bool:
        stripped = value.strip()
        return (stripped.startswith("{") and stripped.endswith("}")) or (
            stripped.startswith("[") and stripped.endswith("]")
        )

    def _parse_json_value(self, value: str) -> object:
        return json.loads(value)

    def _get_parsing_config(self, field: FieldInfo) -> ParseConfig | None:
        for meta_item in self._iter_metadata_items(field.metadata):
            if isinstance(meta_item, ParseConfig):
                return meta_item

        annotation_metadata = self._annotation_metadata_items(field.annotation)
        for meta_item in self._iter_metadata_items(annotation_metadata):
            if isinstance(meta_item, ParseConfig):
                return meta_item

        metadata_items: list[object] = []
        schema_extra = field.json_schema_extra
        if is_mapping_str_object(schema_extra):
            raw_metadata = schema_extra.get("metadata", [])
            if is_object_list(raw_metadata):
                metadata_items = raw_metadata

        for meta_item in self._iter_metadata_items(metadata_items):
            if isinstance(meta_item, ParseConfig):
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


class ParsedEnvSettingsSource(_ParsedSettingsSource, EnvSettingsSource):
    """Environment source that decodes fields annotated with `ParseOptions`."""


class ParsedDotEnvSettingsSource(_ParsedSettingsSource, DotEnvSettingsSource):
    """`DotEnvSettingsSource` variant with ParseOptions support."""


class ParsedSecretsSettingsSource(_ParsedSettingsSource, SecretsSettingsSource):
    """Secret-file source that uses delimiter decoding for annotated collections."""

    def _get_parsing_config(self, field: FieldInfo) -> ParseConfig | None:
        config = super()._get_parsing_config(field)
        if config is None or "item_delimiter" in config.model_fields_set:
            return config

        # Resolve the source default without mutating shared annotation metadata.
        # The decoder validates dictionary delimiter pairs once the type is known.
        return config.model_copy(update={"item_delimiter": "\n"})


class ParsedEnvSettings(BaseSettings):
    """Enable simple environment parsing for Pydantic settings models.

    parsing via `ParseConfig` annotations, avoiding complex JSON strings.
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],  # noqa: ARG003 - BaseSettings hook signature.
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
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
            _parsed_source(env_settings, EnvSettingsSource, ParsedEnvSettingsSource),
            _parsed_source(
                dotenv_settings, DotEnvSettingsSource, ParsedDotEnvSettingsSource
            ),
            _parsed_source(
                file_secret_settings,
                SecretsSettingsSource,
                ParsedSecretsSettingsSource,
            ),
        )


def _parsed_source(
    source: PydanticBaseSettingsSource,
    original_type: type[PydanticBaseSettingsSource],
    parsed_type: type[PydanticBaseSettingsSource],
) -> PydanticBaseSettingsSource:
    if type(source) is not original_type:
        return source

    # Public constructor options differ across supported pydantic-settings versions.
    # Rebuild through that constructor, not by cloning private instance state.
    options: dict[str, Any] = {
        name: getattr(source, name)
        for name in inspect.signature(original_type).parameters
        if name != "settings_cls" and not name.startswith("_")
    }
    return parsed_type(source.settings_cls, **options)
