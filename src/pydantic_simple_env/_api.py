# src/pydantic_simple_env/_api.py

import os
import json
from types import UnionType
from enum import Enum, StrEnum
from typing import Any, Literal, Union, get_args, get_origin, Mapping, cast

# Import Field from pydantic for metadata argument
from pydantic import BaseModel, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
)


# --- 1. Base Configuration Model for Simple Environment Parsing ---


class SimpleEnvConfig(BaseModel):
    """
    Internal configuration model used by `SimpleEnvParser()` to hold delimiter settings.
    Users typically interact with `SimpleEnvParser()` for annotation via `Field(metadata=...)`,
    not this class directly.
    """

    item_delimiter: str = ","
    """Delimiter for items in lists/sets/tuples."""
    kv_delimiter: str = (
        ""  # Default to empty string; forces explicit setting for dicts.
    )
    """Delimiter for key:value within dict entries."""

    @model_validator(mode="after")
    def check_delimiters(self) -> "SimpleEnvConfig":
        """Ensure item_delimiter and kv_delimiter are not the same for dicts,
        if kv_delimiter is provided."""
        if self.kv_delimiter and self.item_delimiter == self.kv_delimiter:
            raise ValueError(
                f"item_delimiter ('{self.item_delimiter}') cannot be the same as "
                f"kv_delimiter ('{self.kv_delimiter}'). This would create parsing ambiguity."
            )
        return self


# --- Annotation Factory Function ---


def SimpleEnvParser(
    item_delimiter: str = ",", kv_delimiter: str = ""
) -> list[SimpleEnvConfig]:  # Returns a list containing the config instance.
    """
    Returns a list containing a `SimpleEnvConfig` instance, suitable for `Field(metadata=...)`.

    Annotate fields with `Field(metadata=SimpleEnvParser())` to enable simple environment
    variable parsing.

    Default behaviors (hardcoded within this source's logic):
    - Items are always stripped of leading/trailing whitespace.
    - An empty input string (e.g., "", ",,,") for lists/sets/variable tuples
      always results in an empty collection ([], {}, ()).

    For dictionaries, `kv_delimiter` must be explicitly configured if it's not the default empty string.

    Examples:
        - `field: List[int] = Field(metadata=SimpleEnvParser())`
        - `field: Dict[str, str] = Field(metadata=SimpleEnvParser(kv_delimiter='='))`
    """
    # Return a list containing the SimpleEnvConfig instance.
    # Field(metadata=...) expects a list[Any] where you can put various metadata objects.
    return [SimpleEnvConfig(item_delimiter=item_delimiter, kv_delimiter=kv_delimiter)]


# --- 2. The Custom Environment Settings Source Implementation ---


class SimpleEnvSettingsSource(EnvSettingsSource):
    """
    This `EnvSettingsSource` subclass provides the implementation for simple environment
    variable parsing based on `SimpleEnvConfig` instances found in `Field(metadata=...)`.

    It specifically processes fields annotated with `SimpleEnvConfig` and otherwise
    defers to other sources or Pydantic's default behavior.
    Most users should inherit from `BaseSimpleEnvSettings` instead of interacting with this directly.
    """

    def __call__(self) -> dict[str, Any]:
        data: dict[str, Any] = {}

        for field_name, field in self.settings_cls.model_fields.items():
            env_val_from_source = self._get_env_val(field, field_name)

            if env_val_from_source is None:
                continue

            parsing_config = self._get_parsing_config(field)

            if parsing_config is None:
                data[field_name] = self._parse_default_env_value(
                    field, env_val_from_source
                )
                continue  # Skip processing by this source

            # --- If we reach here, value IS from env AND has our custom config ---
            value = env_val_from_source  # Raw string from environment

            if not isinstance(value, str):
                raise TypeError(
                    f"Field '{field_name}' is configured for SimpleEnvParser() "
                    f"but received non-string value type {type(value).__name__} from environment. "
                    f"This source expects string inputs for configured fields."
                )

            origin = get_origin(field.annotation)

            if origin is dict and not parsing_config.kv_delimiter:
                raise TypeError(
                    f"Field '{field_name}' is a Dict and is configured with SimpleEnvParser(), "
                    f"but no 'kv_delimiter' is specified in the config. "
                    f"Please use SimpleEnvParser(kv_delimiter=':') or similar for dictionaries."
                )

            if origin in (list, set):
                parsed_value = self._parse_list_or_set_value(
                    field_name,
                    origin,
                    get_args(field.annotation),
                    value,
                    parsing_config,
                )
            elif origin is tuple:
                if (
                    get_args(field.annotation)
                    and get_args(field.annotation)[-1] is Ellipsis
                ):
                    parsed_value = self._parse_variable_tuple_value(
                        field_name,
                        get_args(field.annotation),
                        value,
                        parsing_config,
                    )
                else:
                    parsed_value = self._parse_fixed_tuple_value(
                        field_name,
                        get_args(field.annotation),
                        value,
                        parsing_config,
                    )
            elif origin is dict:
                parsed_value = self._parse_dict_value(
                    field_name,
                    get_args(field.annotation),
                    value,
                    parsing_config,
                )
            else:
                raise TypeError(
                    f"Field '{field_name}' is configured with SimpleEnvParser() but its "
                    f"type hint ({field.annotation}) is not a List, Set, Tuple, or Dict."
                )

            data[field_name] = parsed_value

        return data

    def _get_parsing_config(self, field: FieldInfo) -> SimpleEnvConfig | None:
        for meta_item in self._iter_metadata_items(field.metadata):
            if isinstance(meta_item, SimpleEnvConfig):
                return meta_item

        metadata_items: list[Any] = []
        schema_extra = field.json_schema_extra
        if isinstance(schema_extra, Mapping):
            raw_metadata = cast(Mapping[str, Any], schema_extra).get("metadata", [])
            if isinstance(raw_metadata, list):
                metadata_items = raw_metadata

        for meta_item in self._iter_metadata_items(metadata_items):
            if isinstance(meta_item, SimpleEnvConfig):
                return meta_item

        return None

    def _iter_metadata_items(self, items: list[Any]) -> list[Any]:
        flattened: list[Any] = []
        for item in items:
            if isinstance(item, list):
                flattened.extend(self._iter_metadata_items(item))
            else:
                flattened.append(item)
        return flattened

    def _parse_default_env_value(self, field: FieldInfo, raw_value: str) -> Any:
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

    def _parse_list_or_set_value(
        self,
        field_name: str,
        collection_type_origin: type[list] | type[set],
        collection_type_args: tuple[Any, ...],
        raw_value: str,
        config: SimpleEnvConfig,
    ) -> list[Any] | set[Any]:
        """Parses a delimited string into a list or set of parsed items."""
        item_type = collection_type_args[0] if collection_type_args else str

        if not raw_value.strip():
            return collection_type_origin([])

        parts = raw_value.split(config.item_delimiter)

        if all(not part.strip() for part in parts):
            return collection_type_origin([])

        item_target_types_for_elements = [item_type] * len(parts)

        parsed_items = self._parse_delimited_sequence_elements(
            field_name,
            parts,  # Pass ALL parts (no pre-filtering)
            item_target_types_for_elements,
            collection_type_origin.__name__.lower(),
            strip_item_str=True,  # Opinion: Always strip
        )

        if not any(item is not None and item != "" for item in parsed_items):
            return collection_type_origin([])

        return collection_type_origin(parsed_items)

    def _parse_fixed_tuple_value(
        self,
        field_name: str,
        tuple_element_types: tuple[Any, ...],
        raw_value: str,
        config: SimpleEnvConfig,
    ) -> tuple[Any, ...]:
        """Parses a delimited string into a fixed-length tuple."""
        parts = raw_value.split(config.item_delimiter)

        if len(parts) != len(tuple_element_types):
            raise ValueError(
                f"Field '{field_name}': Expected {len(tuple_element_types)} "
                f"items for fixed-length tuple but got {len(parts)} from '{raw_value}'. "
                f"Check for extra/missing delimiters or values."
            )

        parsed_items = self._parse_delimited_sequence_elements(
            field_name,
            parts,  # Pass all parts (no pre-filtering)
            list(tuple_element_types),  # Must be a list for item_target_types
            "fixed-length tuple",
            strip_item_str=True,  # Opinion: Always strip
        )
        return tuple(parsed_items)

    def _parse_variable_tuple_value(
        self,
        field_name: str,
        tuple_element_types: tuple[Any, ...],
        raw_value: str,
        config: SimpleEnvConfig,
    ) -> tuple[Any, ...]:
        """Parses a delimited string into a variable-length tuple."""
        item_type = tuple_element_types[0] if tuple_element_types else str

        if not raw_value.strip():
            return tuple([])

        parts = raw_value.split(config.item_delimiter)

        if all(not part.strip() for part in parts):
            return tuple([])

        item_target_types_for_elements = [item_type] * len(parts)

        parsed_items = self._parse_delimited_sequence_elements(
            field_name,
            parts,  # Pass ALL parts (no pre-filtering)
            item_target_types_for_elements,
            "variable-length tuple",
            strip_item_str=True,  # Opinion: Always strip
        )

        if not any(item is not None and item != "" for item in parsed_items):
            return tuple([])

        return tuple(parsed_items)

    def _parse_delimited_sequence_elements(
        self,
        field_name: str,
        raw_parts: list[str],
        target_types_for_elements: list[Any],
        collection_type_name: str,
        strip_item_str: bool,
    ) -> list[Any]:
        """
        Shared helper to parse a list of raw string parts into a list of typed Python objects.
        Applies `strip_item_str` to the item string before parsing.
        Raises ValueError if an item cannot be parsed to its target type.
        """
        parsed_elements = []
        for i, part in enumerate(raw_parts):
            current_item_type = target_types_for_elements[i]
            try:
                parsed_elements.append(
                    self._parse_single_item(part, current_item_type, strip_item_str)
                )
            except ValueError as e:
                raise ValueError(
                    f"Field '{field_name}': Could not parse item '{part}' at "
                    f"position {i + 1} into {self._type_name(current_item_type)} for "
                    f"{collection_type_name} from env var: {e}"
                ) from e
        return parsed_elements

    def _parse_dict_value(
        self,
        field_name: str,
        collection_type_args: tuple[Any, ...],
        raw_value: str,
        config: SimpleEnvConfig,
    ) -> dict[Any, Any]:
        """Parses a delimited string into a dictionary."""
        key_type = collection_type_args[0] if collection_type_args else str
        value_type = collection_type_args[1] if len(collection_type_args) > 1 else str

        parsed_dict = {}
        for kv_pair_str in raw_value.split(config.item_delimiter):
            kv_pair_untrimmed = kv_pair_str
            kv_pair_trimmed = kv_pair_str.strip()

            if not kv_pair_trimmed:
                continue

            kv_parts = kv_pair_trimmed.split(config.kv_delimiter, 1)

            if len(kv_parts) == 2:
                key_s, value_s = kv_parts[0], kv_parts[1]
                try:
                    key = self._parse_single_item(key_s, key_type, strip_val=True)
                    val = self._parse_single_item(value_s, value_type, strip_val=True)
                    parsed_dict[key] = val
                except ValueError as e:
                    raise ValueError(
                        f"Field '{field_name}': Could not parse key '{key_s}' "
                        f"as {self._type_name(key_type)} or value '{value_s}' as "
                        f"{self._type_name(value_type)} for dict item '{kv_pair_untrimmed}': {e}"
                    ) from e
            else:
                raise ValueError(
                    f"Field '{field_name}': Dictionary item '{kv_pair_untrimmed}' "
                    f"is malformed. Must be in 'key{config.kv_delimiter}value' format."
                )

        return parsed_dict

    def _parse_single_item(
        self, item_str: str, target_type: Any, strip_val: bool
    ) -> Any:
        """
        Helper to parse a single string item into the target_type.
        Applies `strip_val` to the item string before parsing.
        Handles primitives, Enums, StrEnums, and Union of Literals.
        Raises ValueError if parsing fails for the target type.
        """
        processed_item_str = item_str.strip() if strip_val else item_str

        if not processed_item_str:
            if get_origin(target_type) in (Union, UnionType) and type(None) in get_args(
                target_type
            ):
                return None
            if target_type is str:
                return processed_item_str
            raise ValueError(
                f"Empty string cannot be converted to {self._type_name(target_type)}"
            )

        origin = get_origin(target_type)
        args = get_args(target_type)

        if origin in (Union, UnionType):
            ordered_args = list(args)
            if len(ordered_args) > 1 and str in ordered_args:
                ordered_args = [arg for arg in ordered_args if arg is not str] + [str]

            for arg in ordered_args:
                if arg is type(None):
                    continue
                try:
                    return self._parse_single_item(processed_item_str, arg, strip_val)
                except ValueError:
                    continue
            raise ValueError(
                f"'{processed_item_str}' could not be parsed as any of {target_type}"
            )

        if origin is Literal:
            if processed_item_str in args:
                return processed_item_str
            raise ValueError(
                f"'{processed_item_str}' is not one of the allowed literal values: {list(args)}"
            )

        if isinstance(target_type, type) and issubclass(target_type, (Enum, StrEnum)):
            try:
                return target_type(processed_item_str)
            except ValueError:
                for member_name, member in target_type.__members__.items():
                    if member_name.lower() == processed_item_str.lower():
                        return member
                raise ValueError(
                    f"'{processed_item_str}' is not a valid {target_type.__name__} member."
                )

        if target_type is bool:
            if processed_item_str.lower() == "true":
                return True
            if processed_item_str.lower() == "false":
                return False
            raise ValueError(
                f"'{processed_item_str}' is not a valid boolean (true/false)."
            )

        if target_type is int:
            try:
                return int(processed_item_str, 0)
            except ValueError:
                raise ValueError(f"'{processed_item_str}' is not a valid integer.")
        if target_type is float:
            try:
                return float(processed_item_str)
            except ValueError:
                raise ValueError(f"'{processed_item_str}' is not a valid float.")
        if target_type is str:
            return processed_item_str

        raise ValueError(
            f"Unsupported target type for direct string parsing: {getattr(target_type, '__name__', str(target_type))}. "
            f"Expected a primitive (int, float, bool, str), Enum, Literal, or Union of these."
        )

    def _type_name(self, target_type: Any) -> str:
        return getattr(target_type, "__name__", str(target_type))


# --- 3. Base Class for Simple Environment Parsing Settings ---


class BaseSimpleEnvSettings(BaseSettings):
    """
    A base class for Pydantic settings models that enables simple environment variable
    parsing via `SimpleEnvConfig` annotations, avoiding complex JSON strings.
    """

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ):
        return (
            init_settings,
            SimpleEnvSettingsSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )
