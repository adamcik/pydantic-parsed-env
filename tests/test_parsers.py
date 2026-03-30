from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

import pytest

from pydantic_parsed_env._api import ParseConfig
from pydantic_parsed_env._parsers import (
    parse_dict_from_env,
    parse_fixed_tuple_from_env,
    parse_list_or_set_from_env,
    parse_single_item_value,
    parse_variable_tuple_from_env,
)


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True, kw_only=True)
class SingleItemCase:
    raw: str
    target_type: object
    expected: object
    strip: bool = True


@dataclass(frozen=True, kw_only=True)
class CollectionCase[T]:
    field_name: str
    args: tuple[object, ...]
    raw_value: str
    expected: list[T] | set[T]
    config: ParseConfig = field(default_factory=ParseConfig)


@pytest.mark.parametrize(
    "case",
    [
        SingleItemCase(
            raw="42",
            target_type=int,
            expected=42,
        ),
        SingleItemCase(
            raw="3.5",
            target_type=float,
            expected=3.5,
        ),
        SingleItemCase(
            raw="true",
            target_type=bool,
            expected=True,
        ),
        SingleItemCase(
            raw="read",
            target_type=Permission,
            expected=Permission.READ,
        ),
        SingleItemCase(
            raw="active",
            target_type=Literal["active", "inactive"],
            expected="active",
        ),
        SingleItemCase(
            raw="",
            target_type=str | None,
            expected=None,
        ),
        SingleItemCase(
            raw=" hello ",
            target_type=str,
            expected="hello",
        ),
    ],
)
def test_parse_single_item_value_success(case: SingleItemCase) -> None:
    actual = parse_single_item_value(case.raw, case.target_type, strip_val=case.strip)
    assert actual == case.expected


@pytest.mark.parametrize(
    ("raw", "target_type"),
    [
        ("nope", bool),
        ("unknown", Permission),
        ("oops", Literal["active", "inactive"]),
    ],
)
def test_parse_single_item_value_fails(raw: str, target_type: object) -> None:
    with pytest.raises(ValueError, match="not"):
        parse_single_item_value(raw, target_type, strip_val=True)


@pytest.mark.parametrize(
    "case",
    [
        CollectionCase[int](
            field_name="values",
            args=(int,),
            raw_value="1,2,3",
            expected=[1, 2, 3],
        ),
        CollectionCase[str](
            field_name="values",
            args=(str,),
            raw_value="a,a,b",
            expected={"a", "b"},
        ),
        CollectionCase[int](
            field_name="values",
            args=(int,),
            raw_value="",
            expected=[],
        ),
        CollectionCase[int](
            field_name="values",
            args=(int,),
            raw_value=",,,",
            expected=[],
        ),
    ],
)
def test_parse_list_or_set_from_env(case: CollectionCase[object]) -> None:
    collection_origin = list if isinstance(case.expected, list) else set
    actual = parse_list_or_set_from_env(
        case.field_name,
        collection_origin,
        case.args,
        case.raw_value,
        case.config,
    )
    assert actual == case.expected


def test_parse_fixed_tuple_from_env() -> None:
    config = ParseConfig()
    actual = parse_fixed_tuple_from_env(
        "values",
        (str, int, bool),
        "x,2,true",
        config,
    )
    assert actual == ("x", 2, True)


def test_parse_variable_tuple_from_env() -> None:
    config = ParseConfig()
    actual = parse_variable_tuple_from_env("values", (float, ...), "1.2,3.4", config)
    assert actual == (1.2, 3.4)


def test_parse_dict_from_env() -> None:
    config = ParseConfig(kv_delimiter=":")
    actual = parse_dict_from_env("values", (str, int), "a:1,b:2", config)
    assert actual == {"a": 1, "b": 2}
