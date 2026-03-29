from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

import pytest

from pydantic_simple_env._api import SimpleEnvConfig
from pydantic_simple_env._parsers import (
    parse_dict_from_env,
    parse_fixed_tuple_from_env,
    parse_list_or_set_from_env,
    parse_single_item_value,
    parse_variable_tuple_from_env,
)


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class SingleItemCase:
    raw: str
    target_type: object
    expected: object
    strip: bool = True


@dataclass(frozen=True)
class CollectionCase:
    field_name: str
    args: tuple[object, ...]
    raw_value: str
    expected: object
    config: SimpleEnvConfig = field(default_factory=SimpleEnvConfig)


@pytest.mark.parametrize(
    "case",
    [
        SingleItemCase("42", int, 42),
        SingleItemCase("3.5", float, 3.5),
        SingleItemCase("true", bool, True),
        SingleItemCase("read", Permission, Permission.READ),
        SingleItemCase("active", Literal["active", "inactive"], "active"),
        SingleItemCase("", str | None, None),
        SingleItemCase(" hello ", str, "hello"),
    ],
)
def test_parse_single_item_value_success(case: SingleItemCase) -> None:
    assert (
        parse_single_item_value(case.raw, case.target_type, strip_val=case.strip)
        == case.expected
    )


@pytest.mark.parametrize(
    "raw,target_type",
    [
        ("nope", bool),
        ("unknown", Permission),
        ("oops", Literal["active", "inactive"]),
    ],
)
def test_parse_single_item_value_fails(raw: str, target_type: object) -> None:
    with pytest.raises(ValueError):
        parse_single_item_value(raw, target_type, strip_val=True)


@pytest.mark.parametrize(
    "case",
    [
        CollectionCase("values", (int,), "1,2,3", [1, 2, 3]),
        CollectionCase("values", (str,), "a,a,b", {"a", "b"}),
        CollectionCase("values", (int,), "", []),
        CollectionCase("values", (int,), ",,,", []),
    ],
)
def test_parse_list_or_set_from_env(case: CollectionCase) -> None:
    collection_origin = list if isinstance(case.expected, list) else set
    assert (
        parse_list_or_set_from_env(
            case.field_name,
            collection_origin,
            case.args,
            case.raw_value,
            case.config,
        )
        == case.expected
    )


def test_parse_fixed_tuple_from_env() -> None:
    config = SimpleEnvConfig()
    assert parse_fixed_tuple_from_env("values", (str, int, bool), "x,2,true", config) == (
        "x",
        2,
        True,
    )


def test_parse_variable_tuple_from_env() -> None:
    config = SimpleEnvConfig()
    assert parse_variable_tuple_from_env("values", (float, ...), "1.2,3.4", config) == (
        1.2,
        3.4,
    )


def test_parse_dict_from_env() -> None:
    config = SimpleEnvConfig(kv_delimiter=":")
    assert parse_dict_from_env("values", (str, int), "a:1,b:2", config) == {
        "a": 1,
        "b": 2,
    }
