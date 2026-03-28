from enum import Enum, StrEnum
import os
from typing import Annotated, List, Literal, Any, Set, Tuple, Dict, Union

import pytest

from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict

from pydantic_simple_env import (
    BaseSimpleEnvSettings,
    SimpleEnvConfig,
    SimpleEnvParser,
    SimpleEnvSettingsSource,
)


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"


class ConflictingBool(StrEnum):
    TRUE = "true"
    FALSE = "false"
    MAYBE = "maybe"


class StatusLiteral(StrEnum):
    ENABLED = "true"
    DISABLED = "false"
    PENDING = "false"  # Corrected typo


class AppConfiguration(BaseSimpleEnvSettings):
    # Lists (now using Field(metadata=SimpleEnvParser()) )
    int_list: List[int] = Field(default_factory=list, metadata=SimpleEnvParser())
    """List of integers, comma-separated from ENV. Always stripped, empty input -> []."""
    str_list_semicolon: List[str] = Field(
        default_factory=list, metadata=SimpleEnvParser(item_delimiter=";")
    )
    """List of strings, semicolon-separated from ENV. Always stripped, empty input -> []."""
    mixed_list_comma: List[int | str | float | bool] = Field(
        default_factory=list, metadata=SimpleEnvParser()
    )
    """List of mixed types, comma-separated from ENV. Always stripped, empty input -> []."""
    permission_list: List[Permission] = Field(
        default_factory=list, metadata=SimpleEnvParser()
    )
    """List of Permissions, comma-separated from ENV. Always stripped, empty input -> []."""
    status_list: List[Literal["active", "inactive"]] = Field(
        default_factory=list, metadata=SimpleEnvParser()
    )
    """List of Literals, comma-separated from ENV. Always stripped, empty input -> []."""
    on_off_int_list: List[Literal["on", "off"] | int] = Field(
        default_factory=list, metadata=SimpleEnvParser()
    )
    """List of 'on'/'off' literals or integers, comma-separated from ENV. Always stripped, empty input -> []."""

    # This field relies on default Pydantic List[str] parsing
    no_custom_parsing_str_list: List[str] = Field(default_factory=list)
    """A standard List[str] field. Not custom parsed. Relies on Pydantic's default parsing (e.g., JSON from env)."""

    # Sets
    str_set: Set[str] = Field(
        default_factory=set, metadata=SimpleEnvParser(item_delimiter="|")
    )
    """Set of strings, pipe-separated from ENV. Always stripped, empty input -> {}."""
    bool_set: Set[bool] = Field(default_factory=set, metadata=SimpleEnvParser())
    """Set of booleans, comma-separated from ENV. Always stripped, empty input -> {}."""

    # Tuples
    fixed_tuple_str_int_bool: Tuple[str, int, bool] = Field(
        default=("", 0, False), metadata=SimpleEnvParser()
    )
    """Fixed-length tuple, comma-separated from ENV. Always stripped. Empty input leads to error if length mismatch."""
    variable_tuple_float: Tuple[float, ...] = Field(
        default=(), metadata=SimpleEnvParser()
    )
    """Variable-length tuple of floats, comma-separated from ENV. Always stripped, empty input -> ()." """
    fixed_tuple_str_opt_int: Tuple[str, Union[int, None], int] = Field(
        default=("", None, 0), metadata=SimpleEnvParser()
    )
    """Fixed-length tuple with an optional integer, comma-separated from ENV. Always stripped."""

    # Dictionaries
    str_str_map: Dict[str, str] = Field(
        default_factory=dict, metadata=SimpleEnvParser(kv_delimiter=":")
    )
    """String-to-string map, comma-separated K:V pairs from ENV. Always stripped."""
    str_int_map_slash: Dict[str, int] = Field(
        default_factory=dict, metadata=SimpleEnvParser(kv_delimiter="/")
    )
    """String-to-integer map, slash-separated K/V pairs from ENV. Always stripped."""
    mixed_value_map: Dict[str, str | int | bool] = Field(
        default_factory=dict, metadata=SimpleEnvParser(item_delimiter=";", kv_delimiter="=")
    )
    """Mixed-value map, semicolon-separated K=V pairs from ENV. Always stripped."""

    no_custom_parsing_opt_int_map: Dict[str, Union[int, None]] = Field(default_factory=dict)
    """A standard Dict[str, Optional[int]] field. Not custom parsed. Relies on Pydantic's default parsing (e.g., JSON from env)."""

    dict_with_optional_value: Dict[str, Union[int, None]] = Field(
        default_factory=dict, metadata=SimpleEnvParser(kv_delimiter=":")
    )
    """Dict with optional integer values, comma-separated K:V pairs from ENV. Always stripped."""

    # Corner Cases for Enum/Literal shadowing bool
    conflicting_bool_enum_list: List[ConflictingBool | bool] = Field(
        default_factory=list, metadata=SimpleEnvParser()
    )
    """List of ConflictingBool or bool, from ENV. ConflictingBool takes precedence for "true"/"false"."""
    conflicting_bool_literal_list: List[StatusLiteral | bool] = Field(
        default_factory=list, metadata=SimpleEnvParser()
    )
    """List of StatusLiteral or bool, from ENV. StatusLiteral takes precedence for "true"/"false"."""
    conflicting_bool_list_bool_first: List[bool | ConflictingBool] = Field(
        default_factory=list, metadata=SimpleEnvParser()
    )
    """List of bool or ConflictingBool, from ENV. bool takes precedence for "true"/"false"."""

    # Fields NOT parsed by custom source
    json_data: Dict[str, Any] = {}
    """A standard dictionary field, expecting JSON string from ENV or direct dict."""

    unsupported_type_field: int = Field(default=0, metadata=SimpleEnvParser())
    """
    Example of an unsupported type for SimpleEnvConfig.
    Annotating a non-collection type will result in a TypeError during settings loading.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
    )


# Fixture to manage environment variables using monkeypatch
@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """
    Cleans up all APP_ prefixed environment variables before each test.
    Ensures tests are isolated and don't interfere with each other.
    """
    old_env = {k: os.environ[k] for k in os.environ if k.startswith("APP_")}
    for key in list(os.environ.keys()):
        if key.startswith("APP_"):
            monkeypatch.delenv(key)
    yield
    for k, v in old_env.items():
        monkeypatch.setenv(k, v)


# --- Test Cases for Successful Parsing ---


def test_list_of_ints_success(monkeypatch):
    monkeypatch.setenv("APP_INT_LIST", "1,2,3,42")
    config = AppConfiguration()
    assert config.int_list == [1, 2, 3, 42]
    assert all(isinstance(x, int) for x in config.int_list)


def test_list_of_strings_semicolon_success(monkeypatch):
    monkeypatch.setenv("APP_STR_LIST_SEMICOLON", "alpha; beta;gamma")
    config = AppConfiguration()
    assert config.str_list_semicolon == ["alpha", "beta", "gamma"]
    assert all(isinstance(x, str) for x in config.str_list_semicolon)


def test_mixed_list_success(monkeypatch):
    monkeypatch.setenv("APP_MIXED_LIST_COMMA", "10, hello, 3.14, true, 20.0")
    config = AppConfiguration()
    assert config.mixed_list_comma == [10, "hello", 3.14, True, 20.0]
    assert isinstance(config.mixed_list_comma[0], int)
    assert isinstance(config.mixed_list_comma[1], str)
    assert isinstance(config.mixed_list_comma[2], float)
    assert isinstance(config.mixed_list_comma[3], bool)
    assert isinstance(config.mixed_list_comma[4], float)


def test_permission_list_enum_success(monkeypatch):
    monkeypatch.setenv("APP_PERMISSION_LIST", "read,write,delete")
    config = AppConfiguration()
    assert config.permission_list == [
        Permission.READ,
        Permission.WRITE,
        Permission.DELETE,
    ]
    assert all(isinstance(x, Permission) for x in config.permission_list)


def test_status_list_literal_success(monkeypatch):
    monkeypatch.setenv("APP_STATUS_LIST", "active,inactive")
    config = AppConfiguration()
    assert config.status_list == ["active", "inactive"]
    assert all(isinstance(x, str) for x in config.status_list)


def test_on_off_int_list_union_success(monkeypatch):
    monkeypatch.setenv("APP_ON_OFF_INT_LIST", "on,10,off,20")
    config = AppConfiguration()
    assert config.on_off_int_list == ["on", 10, "off", 20]
    assert isinstance(config.on_off_int_list[0], str)
    assert isinstance(config.on_off_int_list[1], int)


def test_str_set_success(monkeypatch):
    monkeypatch.setenv(
        "APP_STR_SET", "item1|item2|item1"
    )  # Duplicate should be removed by set
    config = AppConfiguration()
    assert config.str_set == {"item1", "item2"}


def test_bool_set_success(monkeypatch):
    monkeypatch.setenv("APP_BOOL_SET", "True, false,TRUE")
    config = AppConfiguration()
    assert config.bool_set == {True, False}


def test_fixed_tuple_success(monkeypatch):
    monkeypatch.setenv("APP_FIXED_TUPLE_STR_INT_BOOL", "test_str,123,true")
    config = AppConfiguration()
    assert config.fixed_tuple_str_int_bool == ("test_str", 123, True)
    assert isinstance(config.fixed_tuple_str_int_bool, tuple)
    assert isinstance(config.fixed_tuple_str_int_bool[0], str)
    assert isinstance(config.fixed_tuple_str_int_bool[1], int)
    assert isinstance(config.fixed_tuple_str_int_bool[2], bool)


def test_variable_tuple_success(monkeypatch):
    monkeypatch.setenv("APP_VARIABLE_TUPLE_FLOAT", "1.1,2.2,3.3")
    config = AppConfiguration()
    assert config.variable_tuple_float == (1.1, 2.2, 3.3)
    assert isinstance(config.variable_tuple_float, tuple)
    assert all(isinstance(x, float) for x in config.variable_tuple_float)


def test_fixed_tuple_optional_element_success(monkeypatch):
    monkeypatch.setenv(
        "APP_FIXED_TUPLE_STR_OPT_INT", "part1,,99"
    )  # Empty string -> None for Optional[int]
    config = AppConfiguration()
    assert config.fixed_tuple_str_opt_int == ("part1", None, 99)
    assert isinstance(config.fixed_tuple_str_opt_int[0], str)
    assert config.fixed_tuple_str_opt_int[1] is None
    assert isinstance(config.fixed_tuple_str_opt_int[2], int)


def test_str_str_map_success(monkeypatch):
    monkeypatch.setenv("APP_STR_STR_MAP", "key1:val1,key2:val2")
    config = AppConfiguration()
    assert config.str_str_map == {"key1": "val1", "key2": "val2"}


def test_str_int_map_slash_success(monkeypatch):
    monkeypatch.setenv("APP_STR_INT_MAP_SLASH", "id/123,count/456")
    config = AppConfiguration()
    assert config.str_int_map_slash == {"id": 123, "count": 456}
    assert isinstance(config.str_int_map_slash["id"], int)


def test_mixed_value_map_success(monkeypatch):
    monkeypatch.setenv(
        "APP_MIXED_VALUE_MAP", "str_key=string_val;int_key=100;bool_key=true"
    )
    config = AppConfiguration()
    assert config.mixed_value_map == {
        "str_key": "string_val",
        "int_key": 100,
        "bool_key": True,
    }
    assert isinstance(config.mixed_value_map["str_key"], str)
    assert isinstance(config.mixed_value_map["int_key"], int)
    assert isinstance(config.mixed_value_map["bool_key"], bool)


def test_json_data_field_not_impacted_by_custom_source(monkeypatch):
    monkeypatch.setenv("APP_JSON_DATA", '{"data":"hello","num":123}')
    config = AppConfiguration()
    assert config.json_data == {"data": "hello", "num": 123}
    assert isinstance(config.json_data, dict)


# --- Numeric Type Tests ---


def test_int_list_numeric_formats(monkeypatch):
    monkeypatch.setenv("APP_INT_LIST", "10,0xFF,0o77,0b1010")
    config = AppConfiguration()
    assert config.int_list == [10, 255, 63, 10]
    assert all(isinstance(x, int) for x in config.int_list)


def test_mixed_list_scientific_notation(monkeypatch):
    monkeypatch.setenv("APP_MIXED_LIST_COMMA", "1.23e-5, 4.5e2, 6.78")
    config = AppConfiguration()
    assert config.mixed_list_comma == [0.0000123, 450.0, 6.78]
    assert all(isinstance(x, float) for x in config.mixed_list_comma)


# --- Stripping Tests ---


def test_no_custom_parsing_str_list_behaves_as_default_pydantic_list(monkeypatch):
    # This field is NOT custom annotated, so Pydantic's default List[str] parsing applies.
    # It will typically expect JSON.
    monkeypatch.setenv("APP_NO_CUSTOM_PARSING_STR_LIST", '[" item one ", " item two "]')
    config = AppConfiguration()
    assert config.no_custom_parsing_str_list == [
        " item one ",
        " item two ",
    ]  # Pydantic default preserves whitespace from JSON
    assert all(isinstance(x, str) for x in config.no_custom_parsing_str_list)


def test_custom_parsed_list_always_strips_whitespace(monkeypatch):
    # This field IS custom annotated, so it always strips due to opinionated default.
    monkeypatch.setenv("APP_STR_LIST_SEMICOLON", " item one ; item two ")
    config = AppConfiguration()
    assert config.str_list_semicolon == ["item one", "item two"]  # Stripped
    assert all(isinstance(x, str) for x in config.str_list_semicolon)


def test_no_custom_parsing_opt_int_map_behaves_as_default_pydantic_dict(monkeypatch):
    # This field is NOT custom annotated.
    monkeypatch.setenv(
        "APP_NO_CUSTOM_PARSING_OPT_INT_MAP",
        '{" key one ": 10, " key two ": null, " key three ": 30}',
    )
    config = AppConfiguration()
    assert config.no_custom_parsing_opt_int_map == {
        " key one ": 10,
        " key two ": None,
        " key three ": 30,
    }
    assert isinstance(config.no_custom_parsing_opt_int_map[" key one "], int)
    assert config.no_custom_parsing_opt_int_map[" key two "] is None
    assert isinstance(config.no_custom_parsing_opt_int_map[" key three "], int)


def test_custom_parsed_map_always_strips_whitespace(monkeypatch):
    monkeypatch.setenv("APP_STR_STR_MAP", " key one : val one , key two : val two ")
    config = AppConfiguration()
    assert config.str_str_map == {"key one": "val one", "key two": "val two"}
    assert all(isinstance(x, str) for x in config.str_str_map.keys())
    assert all(isinstance(x, str) for x in config.str_str_map.values())


# --- Optional/None Value Tests ---


def test_dict_with_optional_value_none_from_empty(monkeypatch):
    monkeypatch.setenv("APP_DICT_WITH_OPTIONAL_VALUE", "key1:10,key2:,key3:30")
    config = AppConfiguration()
    assert config.dict_with_optional_value == {"key1": 10, "key2": None, "key3": 30}
    assert isinstance(config.dict_with_optional_value["key1"], int)
    assert config.dict_with_optional_value["key2"] is None
    assert isinstance(config.dict_with_optional_value["key3"], int)


# --- Empty String To Empty Collection Tests (empty_string_to_empty_collection=True by default) ---


def test_empty_to_empty_str_list_empty_input(monkeypatch):
    monkeypatch.setenv(
        "APP_INT_LIST", ""
    )  # Using int_list which now has empty_string_to_empty_collection=True behavior
    config = AppConfiguration()
    assert config.int_list == []
    assert isinstance(config.int_list, list)


def test_empty_to_empty_str_list_only_delimiters(monkeypatch):
    monkeypatch.setenv("APP_INT_LIST", ",,,")  # Using int_list
    config = AppConfiguration()
    assert config.int_list == []
    assert isinstance(config.int_list, list)


def test_empty_to_empty_int_list_empty_input(monkeypatch):
    monkeypatch.setenv("APP_INT_LIST", "")  # Using int_list
    config = AppConfiguration()
    assert config.int_list == []
    assert isinstance(config.int_list, list)


def test_empty_to_empty_int_list_only_delimiters(monkeypatch):
    monkeypatch.setenv("APP_INT_LIST", ",,")  # Using int_list
    config = AppConfiguration()
    assert config.int_list == []
    assert isinstance(config.int_list, list)


def test_empty_to_empty_var_tuple_empty_input(monkeypatch):
    monkeypatch.setenv("APP_VARIABLE_TUPLE_FLOAT", "")  # Using variable_tuple_float
    config = AppConfiguration()
    assert config.variable_tuple_float == ()
    assert isinstance(config.variable_tuple_float, tuple)


def test_empty_to_empty_var_tuple_only_delimiters(monkeypatch):
    monkeypatch.setenv("APP_VARIABLE_TUPLE_FLOAT", ",,,")  # Using variable_tuple_float
    config = AppConfiguration()
    assert config.variable_tuple_float == ()
    assert isinstance(config.variable_tuple_float, tuple)


# --- Union Precedence and Ambiguity Tests ---


def test_conflicting_bool_enum_list_enum_precedence(monkeypatch):
    monkeypatch.setenv("APP_CONFLICTING_BOOL_ENUM_LIST", "true,false,maybe")
    config = AppConfiguration()
    assert config.conflicting_bool_enum_list == [
        ConflictingBool.TRUE,
        ConflictingBool.FALSE,
        ConflictingBool.MAYBE,
    ]
    assert all(
        isinstance(x, ConflictingBool) for x in config.conflicting_bool_enum_list
    )


def test_conflicting_bool_literal_list_literal_precedence(monkeypatch):
    monkeypatch.setenv("APP_CONFLICTING_BOOL_LITERAL_LIST", "true,false,pending")
    config = AppConfiguration()
    assert config.conflicting_bool_literal_list == [
        StatusLiteral.ENABLED,
        StatusLiteral.DISABLED,
        StatusLiteral.PENDING,
    ]
    assert all(
        isinstance(x, StatusLiteral) for x in config.conflicting_bool_literal_list
    )


def test_conflicting_bool_list_bool_first_bool_precedence(monkeypatch):
    monkeypatch.setenv("APP_CONFLICTING_BOOL_LIST_BOOL_FIRST", "true,false,maybe")
    config = AppConfiguration()
    assert config.conflicting_bool_list_bool_first == [
        ConflictingBool.TRUE,
        ConflictingBool.FALSE,
        ConflictingBool.MAYBE,
    ]
    assert isinstance(config.conflicting_bool_list_bool_first[0], ConflictingBool)
    assert isinstance(config.conflicting_bool_list_bool_first[1], ConflictingBool)
    assert isinstance(config.conflicting_bool_list_bool_first[2], ConflictingBool)


# --- Test Cases for Expected Parsing Failures ---


def test_unsupported_type_annotation_fails(monkeypatch):
    monkeypatch.setenv("APP_UNSUPPORTED_TYPE_FIELD", "42")
    with pytest.raises(TypeError) as excinfo:
        AppConfiguration()
    assert (
        "is configured with SimpleEnvParser() but its type hint"
        in str(excinfo.value)
    )  # Updated error msg check
    assert "not a List, Set, Tuple, or Dict." in str(excinfo.value)


def test_list_of_ints_malformed_item_fails(monkeypatch):
    monkeypatch.setenv("APP_INT_LIST", "1,2,invalid,4")
    with pytest.raises(ValueError) as excinfo:
        AppConfiguration()
    assert "Could not parse item 'invalid' at position 3 into int" in str(excinfo.value)


def test_list_of_ints_empty_part_fails(monkeypatch):
    monkeypatch.setenv(
        "APP_INT_LIST", "1,,2"
    )  # Empty string at index 1 will cause failure for int
    with pytest.raises(ValueError) as excinfo:
        AppConfiguration()
    assert "Empty string cannot be converted to int" in str(excinfo.value)


def test_permission_list_invalid_enum_fails(monkeypatch):
    monkeypatch.setenv("APP_PERMISSION_LIST", "read,invalid,write")
    with pytest.raises(ValueError) as excinfo:
        AppConfiguration()
    assert "'invalid' is not a valid Permission member." in str(excinfo.value)


def test_status_list_invalid_literal_fails(monkeypatch):
    monkeypatch.setenv("APP_STATUS_LIST", "active,unknown")
    with pytest.raises(ValueError) as excinfo:
        AppConfiguration()
    assert "'unknown' is not one of the allowed literal values" in str(excinfo.value)


def test_fixed_tuple_wrong_length_fails(monkeypatch):
    monkeypatch.setenv("APP_FIXED_TUPLE_STR_INT_BOOL", "hello,123")  # Too few items
    with pytest.raises(ValueError) as excinfo:
        AppConfiguration()
    assert "Expected 3 items for fixed-length tuple but got 2" in str(excinfo.value)


def test_fixed_tuple_malformed_item_fails(monkeypatch):
    monkeypatch.setenv(
        "APP_FIXED_TUPLE_STR_INT_BOOL", "hello,not_an_int,true"
    )  # Middle item
    with pytest.raises(ValueError) as excinfo:
        AppConfiguration()
    assert "Could not parse item 'not_an_int' at position 2 into int" in str(
        excinfo.value
    )


def test_variable_tuple_malformed_item_fails(monkeypatch):
    monkeypatch.setenv("APP_VARIABLE_TUPLE_FLOAT", "1.1,not_a_float,3.3")
    with pytest.raises(ValueError) as excinfo:
        AppConfiguration()
    assert "Could not parse item 'not_a_float' at position 2 into float" in str(
        excinfo.value
    )


def test_dict_malformed_kv_pair_fails(monkeypatch):
    monkeypatch.setenv("APP_STR_STR_MAP", "key1:val1,malformed_pair,key2:val2")
    with pytest.raises(ValueError) as excinfo:
        AppConfiguration()
    assert "Dictionary item 'malformed_pair' is malformed." in str(excinfo.value)


def test_dict_key_parse_fails(monkeypatch):
    class MyKey(int, Enum):
        FOO = 1

    class TestAppConfig(AppConfiguration):
        key_enum_map: Annotated[
            Dict[MyKey, str], SimpleEnvParser(kv_delimiter=":")
        ] = {}  # Uses SimpleEnvParser
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_KEY_ENUM_MAP", "invalid_key:value1")
    with pytest.raises(ValueError) as excinfo:
        TestAppConfig()
    assert "'invalid_key' is not a valid MyKey member." in str(excinfo.value)


def test_dict_value_parse_fails(monkeypatch):
    monkeypatch.setenv("APP_STR_INT_MAP_SLASH", "id/not_an_int")
    with pytest.raises(ValueError) as excinfo:
        AppConfiguration()
    assert "Could not parse key 'id' as str or value 'not_an_int' as int" in str(
        excinfo.value
    )


def test_dict_empty_kv_pair_is_ignored(monkeypatch):
    monkeypatch.setenv(
        "APP_STR_STR_MAP", "name:Alice,,city:New York"
    )  # Empty entry at index 1
    config = AppConfiguration()
    assert config.str_str_map == {"name": "Alice", "city": "New York"}
    assert isinstance(config.str_str_map, dict)


# --- New Failure Tests: Ambiguous Delimiters and Complex Types ---


def test_ambiguous_delimiters_fails_config_validation():
    # Attempt to create SimpleEnvConfig with same item_delimiter and kv_delimiter
    with pytest.raises(ValueError) as excinfo:
        SimpleEnvConfig(item_delimiter=":", kv_delimiter=":")
    assert "item_delimiter (':') cannot be the same as kv_delimiter (':')" in str(
        excinfo.value
    )


def test_dict_missing_kv_delimiter_fails(monkeypatch):
    # This tests the explicit TypeError for Dicts if kv_delimiter is not set in SimpleEnvParser()
    class TestConfig(AppConfiguration):
        my_dict: Annotated[
            Dict[str, str], SimpleEnvParser()
        ]  # kv_delimiter defaults to ""

    monkeypatch.setenv("APP_MY_DICT", "key1:value1")
    with pytest.raises(TypeError) as excinfo:
        TestConfig()
    assert (
        "Field 'my_dict' is a Dict and is configured with SimpleEnvParser(),"
        in str(excinfo.value)
    )
    assert "but no 'kv_delimiter' is specified in the config." in str(excinfo.value)


def test_unsupported_complex_type_in_union_fails(monkeypatch):
    class TestConfig(AppConfiguration):
        unsupported_union: Annotated[str | list[int], SimpleEnvParser()]

    monkeypatch.setenv("APP_UNSUPPORTED_UNION", "not_a_list")
    with pytest.raises(TypeError) as excinfo:
        TestConfig()
    assert "is not a List, Set, Tuple, or Dict" in str(
        excinfo.value
    )


def test_unsupported_complex_type_as_item_fails(monkeypatch):
    class Coordinates(BaseModel):
        x: int
        y: int

    class TestConfig(AppConfiguration):
        coords_list: Annotated[list[Coordinates], SimpleEnvParser()]

    monkeypatch.setenv("APP_COORDS_LIST", "1,2")
    with pytest.raises(ValueError) as excinfo:
        TestConfig()
    assert "Unsupported target type for direct string parsing: Coordinates" in str(
        excinfo.value
    )


def test_unsupported_complex_type_as_dict_key_fails(monkeypatch):
    class MyComplexKey(BaseModel):
        id: int

    class TestConfig(AppConfiguration):
        complex_key_map: Annotated[
            dict[MyComplexKey, str], SimpleEnvParser(kv_delimiter=":")
        ]

    monkeypatch.setenv("APP_COMPLEX_KEY_MAP", "key_data:value")
    with pytest.raises(ValueError) as excinfo:
        TestConfig()
    assert "Unsupported target type for direct string parsing: MyComplexKey" in str(
        excinfo.value
    )


def test_unsupported_complex_type_as_dict_value_fails(monkeypatch):
    class MyComplexValue(BaseModel):
        data: str

    class TestConfig(AppConfiguration):
        complex_value_map: Annotated[
            dict[str, MyComplexValue], SimpleEnvParser(kv_delimiter=":")
        ]

    monkeypatch.setenv("APP_COMPLEX_VALUE_MAP", "key:value_data")
    with pytest.raises(ValueError) as excinfo:
        TestConfig()
    assert "Unsupported target type for direct string parsing: MyComplexValue" in str(
        excinfo.value
    )
