from collections.abc import Mapping
from enum import Enum, StrEnum
from types import UnionType
from typing import (
    Literal,
    Protocol,
    TypeGuard,
    Union,
    cast,
    get_args,
    get_origin,
)


class DelimiterConfig(Protocol):
    item_delimiter: str
    kv_delimiter: str


def is_object_list(value: object) -> TypeGuard[list[object]]:
    return isinstance(value, list)


def is_mapping_str_object(value: object) -> TypeGuard[Mapping[str, object]]:
    return isinstance(value, Mapping)


def annotation_args(annotation: object) -> tuple[object, ...]:
    return cast("tuple[object, ...]", get_args(annotation))


def type_name(target_type: object) -> str:
    return getattr(target_type, "__name__", str(target_type))


def parse_single_item_value(
    item_str: str,
    target_type: object,
    *,
    strip_val: bool,
) -> object:
    processed_item_str = item_str.strip() if strip_val else item_str

    if not processed_item_str:
        if get_origin(target_type) in (Union, UnionType) and type(None) in get_args(
            target_type,
        ):
            return None
        if target_type is str:
            return processed_item_str
        raise ValueError(
            f"Empty string cannot be converted to {type_name(target_type)}",
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
                return parse_single_item_value(
                    processed_item_str,
                    arg,
                    strip_val=strip_val,
                )
            except ValueError:
                continue
        raise ValueError(
            f"'{processed_item_str}' could not be parsed as any of {target_type}",
        )

    if origin is Literal:
        if processed_item_str in args:
            return processed_item_str
        raise ValueError(
            f"'{processed_item_str}' is not one of the allowed literal "
            f"values: {list(args)}",
        )

    if isinstance(target_type, type) and issubclass(target_type, (Enum, StrEnum)):
        try:
            return target_type(processed_item_str)
        except ValueError as err:
            for member_name, member in target_type.__members__.items():
                if member_name.lower() == processed_item_str.lower():
                    return member
            raise ValueError(
                f"'{processed_item_str}' is not a valid {target_type.__name__} member.",
            ) from err

    if target_type is bool:
        if processed_item_str.lower() == "true":
            return True
        if processed_item_str.lower() == "false":
            return False
        raise ValueError(f"'{processed_item_str}' is not a valid boolean (true/false).")

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

    target_type_name = type_name(cast("object", target_type))
    raise ValueError(
        f"Unsupported target type for direct string parsing: {target_type_name}. "
        "Expected a primitive (int, float, bool, str), Enum, Literal, or "
        "Union of these.",
    )


def parse_delimited_sequence_values(
    field_name: str,
    raw_parts: list[str],
    target_types_for_elements: list[object],
    collection_type_name: str,
    *,
    strip_item_str: bool,
) -> list[object]:
    parsed_elements: list[object] = []
    for i, part in enumerate(raw_parts):
        current_item_type = target_types_for_elements[i]
        try:
            parsed_elements.append(
                parse_single_item_value(
                    part,
                    current_item_type,
                    strip_val=strip_item_str,
                ),
            )
        except ValueError as e:
            raise ValueError(
                f"Field '{field_name}': Could not parse item '{part}' at "
                f"position {i + 1} into {type_name(current_item_type)} for "
                f"{collection_type_name} from env var: {e}",
            ) from e
    return parsed_elements


def parse_list_or_set_from_env(
    field_name: str,
    collection_type_origin: type[list[object]] | type[set[object]],
    collection_type_args: tuple[object, ...],
    raw_value: str,
    config: DelimiterConfig,
) -> list[object] | set[object]:
    item_type: object = collection_type_args[0] if collection_type_args else str

    if not raw_value.strip():
        if collection_type_origin is list:
            return []
        return set()

    parts = raw_value.split(config.item_delimiter)

    if all(not part.strip() for part in parts):
        if collection_type_origin is list:
            return []
        return set()

    item_target_types_for_elements = [item_type] * len(parts)
    parsed_items = parse_delimited_sequence_values(
        field_name,
        parts,
        item_target_types_for_elements,
        collection_type_origin.__name__.lower(),
        strip_item_str=True,
    )

    if not any(item is not None and item != "" for item in parsed_items):
        if collection_type_origin is list:
            return []
        return set()

    if collection_type_origin is list:
        return parsed_items
    return set(parsed_items)


def parse_fixed_tuple_from_env(
    field_name: str,
    tuple_element_types: tuple[object, ...],
    raw_value: str,
    config: DelimiterConfig,
) -> tuple[object, ...]:
    parts = raw_value.split(config.item_delimiter)

    if len(parts) != len(tuple_element_types):
        raise ValueError(
            f"Field '{field_name}': Expected {len(tuple_element_types)} "
            f"items for fixed-length tuple but got {len(parts)} from '{raw_value}'. "
            "Check for extra/missing delimiters or values.",
        )

    parsed_items = parse_delimited_sequence_values(
        field_name,
        parts,
        list(tuple_element_types),
        "fixed-length tuple",
        strip_item_str=True,
    )
    return tuple(parsed_items)


def parse_variable_tuple_from_env(
    field_name: str,
    tuple_element_types: tuple[object, ...],
    raw_value: str,
    config: DelimiterConfig,
) -> tuple[object, ...]:
    item_type: object = tuple_element_types[0] if tuple_element_types else str

    if not raw_value.strip():
        return ()

    parts = raw_value.split(config.item_delimiter)
    if all(not part.strip() for part in parts):
        return ()

    item_target_types_for_elements = [item_type] * len(parts)
    parsed_items = parse_delimited_sequence_values(
        field_name,
        parts,
        item_target_types_for_elements,
        "variable-length tuple",
        strip_item_str=True,
    )

    if not any(item is not None and item != "" for item in parsed_items):
        return ()

    return tuple(parsed_items)


def parse_dict_from_env(
    field_name: str,
    collection_type_args: tuple[object, ...],
    raw_value: str,
    config: DelimiterConfig,
) -> dict[object, object]:
    key_type = collection_type_args[0] if collection_type_args else str
    value_type = collection_type_args[1] if len(collection_type_args) > 1 else str

    parsed_dict: dict[object, object] = {}
    for kv_pair_str in raw_value.split(config.item_delimiter):
        kv_pair_untrimmed = kv_pair_str
        kv_pair_trimmed = kv_pair_str.strip()

        if not kv_pair_trimmed:
            continue

        kv_parts = kv_pair_trimmed.split(config.kv_delimiter, 1)

        if len(kv_parts) == 2:
            key_s, value_s = kv_parts[0], kv_parts[1]
            try:
                key = parse_single_item_value(key_s, key_type, strip_val=True)
                val = parse_single_item_value(value_s, value_type, strip_val=True)
                parsed_dict[key] = val
            except ValueError as e:
                raise ValueError(
                    f"Field '{field_name}': Could not parse key '{key_s}' "
                    f"as {type_name(key_type)} or value '{value_s}' as "
                    f"{type_name(value_type)} for dict item '{kv_pair_untrimmed}': {e}",
                ) from e
        else:
            raise ValueError(
                f"Field '{field_name}': Dictionary item '{kv_pair_untrimmed}' "
                f"is malformed. Must be in 'key{config.kv_delimiter}value' format.",
            )

    return parsed_dict
