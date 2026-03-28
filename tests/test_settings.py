from enum import Enum, StrEnum
from typing import Literal

import pytest

from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict

from pydantic_simple_env import BaseSimpleEnvSettings, SimpleEnvConfig, SimpleEnvParser


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
    PENDING = "pending"


def test_list_of_ints_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[int] = Field(default_factory=list, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "1,2,3,42")
    assert Settings().values == [1, 2, 3, 42]


def test_list_of_strings_semicolon_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[str] = Field(
            default_factory=list, metadata=SimpleEnvParser(item_delimiter=";")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "alpha; beta;gamma")
    assert Settings().values == ["alpha", "beta", "gamma"]


def test_mixed_list_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[int | str | float | bool] = Field(
            default_factory=list, metadata=SimpleEnvParser()
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "10, hello, 3.14, true, 20.0")
    assert Settings().values == [10, "hello", 3.14, True, 20.0]


def test_permission_list_enum_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[Permission] = Field(default_factory=list, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "read,write,delete")
    assert Settings().values == [Permission.READ, Permission.WRITE, Permission.DELETE]


def test_literal_list_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[Literal["active", "inactive"]] = Field(
            default_factory=list, metadata=SimpleEnvParser()
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "active,inactive")
    assert Settings().values == ["active", "inactive"]


def test_set_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: set[str] = Field(
            default_factory=set, metadata=SimpleEnvParser(item_delimiter="|")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "one|two|one")
    assert Settings().values == {"one", "two"}


def test_fixed_tuple_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: tuple[str, int, bool] = Field(
            default=("", 0, False), metadata=SimpleEnvParser()
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "name,123,true")
    assert Settings().values == ("name", 123, True)


def test_variable_tuple_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: tuple[float, ...] = Field(default=(), metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "1.1,2.2,3.3")
    assert Settings().values == (1.1, 2.2, 3.3)


def test_fixed_tuple_optional_element_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: tuple[str, int | None, int] = Field(
            default=("", None, 0), metadata=SimpleEnvParser()
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "part1,,99")
    assert Settings().values == ("part1", None, 99)


def test_dict_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: dict[str, str] = Field(
            default_factory=dict, metadata=SimpleEnvParser(kv_delimiter=":")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "a:1,b:2")
    assert Settings().values == {"a": "1", "b": "2"}


def test_dict_int_values_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: dict[str, int] = Field(
            default_factory=dict, metadata=SimpleEnvParser(kv_delimiter="/")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "id/123,count/456")
    assert Settings().values == {"id": 123, "count": 456}


def test_mixed_dict_values_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: dict[str, str | int | bool] = Field(
            default_factory=dict,
            metadata=SimpleEnvParser(item_delimiter=";", kv_delimiter="="),
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "str_key=hello;int_key=100;bool_key=true")
    assert Settings().values == {"str_key": "hello", "int_key": 100, "bool_key": True}


def test_default_pydantic_list_json(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[str] = Field(default_factory=list)
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", '[" item one ", " item two "]')
    assert Settings().values == [" item one ", " item two "]


def test_default_pydantic_dict_json(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: dict[str, int | None] = Field(default_factory=dict)
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", '{" a ": 1, " b ": null}')
    assert Settings().values == {" a ": 1, " b ": None}


def test_dict_optional_values(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: dict[str, int | None] = Field(
            default_factory=dict, metadata=SimpleEnvParser(kv_delimiter=":")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "k1:10,k2:,k3:30")
    assert Settings().values == {"k1": 10, "k2": None, "k3": 30}


def test_empty_input_to_empty_list(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[int] = Field(default_factory=list, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "")
    assert Settings().values == []


def test_only_delimiters_to_empty_list(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[int] = Field(default_factory=list, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", ",,,")
    assert Settings().values == []


def test_empty_input_to_empty_variable_tuple(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: tuple[float, ...] = Field(default=(), metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "")
    assert Settings().values == ()


def test_conflicting_bool_enum_precedence(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[ConflictingBool | bool] = Field(
            default_factory=list, metadata=SimpleEnvParser()
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "true,false,maybe")
    assert Settings().values == [ConflictingBool.TRUE, ConflictingBool.FALSE, ConflictingBool.MAYBE]


def test_conflicting_bool_literal_precedence(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[StatusLiteral | bool] = Field(
            default_factory=list, metadata=SimpleEnvParser()
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "true,false,pending")
    assert Settings().values == [StatusLiteral.ENABLED, StatusLiteral.DISABLED, StatusLiteral.PENDING]


def test_unsupported_top_level_type_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        value: int = Field(default=0, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUE", "42")
    with pytest.raises(TypeError):
        Settings()


def test_list_malformed_item_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[int] = Field(default_factory=list, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "1,2,bad,4")
    with pytest.raises(ValueError):
        Settings()


def test_list_empty_item_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[int] = Field(default_factory=list, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "1,,2")
    with pytest.raises(ValueError):
        Settings()


def test_enum_item_invalid_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[Permission] = Field(default_factory=list, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "read,invalid")
    with pytest.raises(ValueError):
        Settings()


def test_literal_item_invalid_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: list[Literal["active", "inactive"]] = Field(
            default_factory=list, metadata=SimpleEnvParser()
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "active,unknown")
    with pytest.raises(ValueError):
        Settings()


def test_fixed_tuple_wrong_length_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: tuple[str, int, bool] = Field(
            default=("", 0, False), metadata=SimpleEnvParser()
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "hello,123")
    with pytest.raises(ValueError):
        Settings()


def test_dict_malformed_pair_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: dict[str, str] = Field(
            default_factory=dict, metadata=SimpleEnvParser(kv_delimiter=":")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "k1:v1,broken,k2:v2")
    with pytest.raises(ValueError):
        Settings()


def test_dict_missing_kv_delimiter_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: dict[str, str] = Field(default_factory=dict, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "k1:v1")
    with pytest.raises(TypeError):
        Settings()


def test_dict_empty_pair_is_ignored(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        values: dict[str, str] = Field(
            default_factory=dict, metadata=SimpleEnvParser(kv_delimiter=":")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "name:Alice,,city:New York")
    assert Settings().values == {"name": "Alice", "city": "New York"}


def test_ambiguous_delimiters_fails_config_validation():
    with pytest.raises(ValueError):
        SimpleEnvConfig(item_delimiter=":", kv_delimiter=":")


def test_dict_key_type_conversion_fails(monkeypatch: pytest.MonkeyPatch):
    class MyKey(int, Enum):
        FOO = 1

    class Settings(BaseSimpleEnvSettings):
        values: dict[MyKey, str] = Field(
            default_factory=dict, metadata=SimpleEnvParser(kv_delimiter=":")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "invalid:value")
    with pytest.raises(ValueError):
        Settings()


def test_unsupported_union_root_type_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(BaseSimpleEnvSettings):
        value: str | list[int] = Field(default="", metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUE", "something")
    with pytest.raises(TypeError):
        Settings()


def test_unsupported_complex_type_as_list_item_fails(monkeypatch: pytest.MonkeyPatch):
    class Coordinates(BaseModel):
        x: int
        y: int

    class Settings(BaseSimpleEnvSettings):
        values: list[Coordinates] = Field(default_factory=list, metadata=SimpleEnvParser())
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "1,2")
    with pytest.raises(ValueError):
        Settings()


def test_unsupported_complex_type_as_dict_key_fails(monkeypatch: pytest.MonkeyPatch):
    class MyComplexKey(BaseModel):
        id: int

    class Settings(BaseSimpleEnvSettings):
        values: dict[MyComplexKey, str] = Field(
            default_factory=dict, metadata=SimpleEnvParser(kv_delimiter=":")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "key:value")
    with pytest.raises(ValueError):
        Settings()


def test_unsupported_complex_type_as_dict_value_fails(monkeypatch: pytest.MonkeyPatch):
    class MyComplexValue(BaseModel):
        data: str

    class Settings(BaseSimpleEnvSettings):
        values: dict[str, MyComplexValue] = Field(
            default_factory=dict, metadata=SimpleEnvParser(kv_delimiter=":")
        )
        model_config = SettingsConfigDict(env_prefix="APP_")

    monkeypatch.setenv("APP_VALUES", "key:value")
    with pytest.raises(ValueError):
        Settings()
