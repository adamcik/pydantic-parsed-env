from enum import Enum, StrEnum
from pathlib import Path
from typing import Annotated, Literal

import pytest
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import SettingsConfigDict, SettingsError

from pydantic_parsed_env import (
    ParseConfig,
    Parsed,
    ParsedEnvSettings,
    ParseOptions,
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
    PENDING = "pending"


def test_list_of_ints_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Annotated[list[int], ParseOptions()] = Field(
            default_factory=list[int],
        )

    monkeypatch.setenv("VALUES", "1,2,3,42")
    assert Settings().values == [1, 2, 3, 42]


def test_list_of_strings_semicolon_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Annotated[list[str], ParseOptions(item_delimiter=";")] = Field(
            default_factory=list,
        )

    monkeypatch.setenv("VALUES", "alpha; beta;gamma")
    assert Settings().values == ["alpha", "beta", "gamma"]


def test_mixed_list_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[int | str | float | bool]] = Field(
            default_factory=list[int | str | float | bool],
        )

    monkeypatch.setenv("VALUES", "10, hello, 3.14, true, 20.0")
    assert Settings().values == [10, "hello", 3.14, True, 20.0]


def test_permission_list_enum_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[Permission]] = Field(
            default_factory=list[Permission],
        )

    monkeypatch.setenv("VALUES", "read,write,delete")
    assert Settings().values == [Permission.READ, Permission.WRITE, Permission.DELETE]


def test_literal_list_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[Literal["active", "inactive"]]] = Field(
            default_factory=list[Literal["active", "inactive"]],
        )

    monkeypatch.setenv("VALUES", "active,inactive")
    assert Settings().values == ["active", "inactive"]


def test_set_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Annotated[set[str], ParseOptions(item_delimiter="|")] = Field(
            default_factory=set,
        )

    monkeypatch.setenv("VALUES", "one|two|one")
    assert Settings().values == {"one", "two"}


def test_fixed_tuple_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[tuple[str, int, bool]] = Field(
            default=("", 0, False),
        )

    monkeypatch.setenv("VALUES", "name,123,true")
    assert Settings().values == ("name", 123, True)


def test_variable_tuple_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[tuple[float, ...]] = Field(default=())

    monkeypatch.setenv("VALUES", "1.1,2.2,3.3")
    assert Settings().values == (1.1, 2.2, 3.3)


def test_fixed_tuple_optional_element_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[tuple[str, int | None, int]] = Field(
            default=("", None, 0),
        )

    monkeypatch.setenv("VALUES", "part1,,99")
    assert Settings().values == ("part1", None, 99)


def test_dict_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Annotated[dict[str, str], ParseOptions(kv_delimiter=":")] = Field(
            default_factory=dict,
        )

    monkeypatch.setenv("VALUES", "a:1,b:2")
    assert Settings().values == {"a": "1", "b": "2"}


def test_dict_int_values_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Annotated[dict[str, int], ParseOptions(kv_delimiter="/")] = Field(
            default_factory=dict,
        )

    monkeypatch.setenv("VALUES", "id/123,count/456")
    assert Settings().values == {"id": 123, "count": 456}


def test_mixed_dict_values_success(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Annotated[
            dict[str, str | int | bool],
            ParseOptions(item_delimiter=";", kv_delimiter="="),
        ] = Field(
            default_factory=dict,
        )

    monkeypatch.setenv("VALUES", "str_key=hello;int_key=100;bool_key=true")
    assert Settings().values == {"str_key": "hello", "int_key": 100, "bool_key": True}


def test_default_pydantic_list_json(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: list[str] = Field(default_factory=list)

    monkeypatch.setenv("VALUES", '[" item one ", " item two "]')
    assert Settings().values == [" item one ", " item two "]


def test_default_pydantic_dict_json(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: dict[str, int | None] = Field(default_factory=dict)

    monkeypatch.setenv("VALUES", '{" a ": 1, " b ": null}')
    assert Settings().values == {" a ": 1, " b ": None}


def test_simple_parser_json_list_without_fallback_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[int]] = Field(default_factory=list[int])

    monkeypatch.setenv("VALUES", "[1,2,3]")
    with pytest.raises(SettingsError, match='error parsing value for field "values"'):
        Settings()


def test_simple_parser_json_list_without_fallback_has_hint_in_cause(
    monkeypatch: pytest.MonkeyPatch,
):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[int]] = Field(default_factory=list[int])

    monkeypatch.setenv("VALUES", "[1,2,3]")
    with pytest.raises(SettingsError) as exc_info:
        Settings()

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "ParseOptions(json_compatibility=True)" in str(exc_info.value.__cause__)


def test_simple_parser_json_like_can_still_succeed_without_compatibility(
    monkeypatch: pytest.MonkeyPatch,
):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[str]] = Field(default_factory=list[str])

    monkeypatch.setenv("VALUES", "[1,2]")
    assert Settings().values == ["[1", "2]"]


def test_simple_parser_json_list_with_json_compatibility_succeeds(
    monkeypatch: pytest.MonkeyPatch,
):
    class Settings(ParsedEnvSettings):
        values: Annotated[
            list[int],
            ParseOptions(json_compatibility=True),
        ] = Field(default_factory=list[int])

    monkeypatch.setenv("VALUES", " [1, 2, 3] ")
    assert Settings().values == [1, 2, 3]


def test_simple_parser_json_dict_with_json_compatibility_succeeds(
    monkeypatch: pytest.MonkeyPatch,
):
    class Settings(ParsedEnvSettings):
        values: Annotated[
            dict[str, int],
            ParseOptions(kv_delimiter=":", json_compatibility=True),
        ] = Field(default_factory=dict[str, int])

    monkeypatch.setenv("VALUES", '{"http": 80, "https": 443}')
    assert Settings().values == {"http": 80, "https": 443}


def test_simple_parser_json_like_content_can_still_parse_simply(
    monkeypatch: pytest.MonkeyPatch,
):
    class Settings(ParsedEnvSettings):
        values: Annotated[
            dict[str, str],
            ParseOptions(
                item_delimiter=";",
                kv_delimiter=":",
                json_compatibility=True,
            ),
        ] = Field(default_factory=dict[str, str])

    monkeypatch.setenv("VALUES", "{a:1;b:2}")
    assert Settings().values == {"{a": "1", "b": "2}"}


def test_simple_parser_json_compatibility_prefers_json_when_valid(
    monkeypatch: pytest.MonkeyPatch,
):
    class Settings(ParsedEnvSettings):
        values: Annotated[
            list[str],
            ParseOptions(json_compatibility=True),
        ] = Field(default_factory=list[str])

    monkeypatch.setenv("VALUES", '["a", "b"]')
    assert Settings().values == ["a", "b"]


def test_dict_optional_values(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Annotated[dict[str, int | None], ParseOptions(kv_delimiter=":")] = (
            Field(
                default_factory=dict,
            )
        )

    monkeypatch.setenv("VALUES", "k1:10,k2:,k3:30")
    assert Settings().values == {"k1": 10, "k2": None, "k3": 30}


def test_empty_input_to_empty_list(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[int]] = Field(
            default_factory=list[int],
        )

    monkeypatch.setenv("VALUES", "")
    assert Settings().values == []


def test_only_delimiters_to_empty_list(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[int]] = Field(
            default_factory=list[int],
        )

    monkeypatch.setenv("VALUES", ",,,")
    assert Settings().values == []


def test_empty_input_to_empty_variable_tuple(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[tuple[float, ...]] = Field(default=())

    monkeypatch.setenv("VALUES", "")
    assert Settings().values == ()


def test_conflicting_bool_enum_precedence(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[ConflictingBool | bool]] = Field(
            default_factory=list[ConflictingBool | bool],
        )

    monkeypatch.setenv("VALUES", "true,false,maybe")
    assert Settings().values == [
        ConflictingBool.TRUE,
        ConflictingBool.FALSE,
        ConflictingBool.MAYBE,
    ]


def test_conflicting_bool_literal_precedence(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[StatusLiteral | bool]] = Field(
            default_factory=list[StatusLiteral | bool],
        )

    monkeypatch.setenv("VALUES", "true,false,pending")
    assert Settings().values == [
        StatusLiteral.ENABLED,
        StatusLiteral.DISABLED,
        StatusLiteral.PENDING,
    ]


def test_unsupported_top_level_type_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        value: Parsed[int] = Field(default=0)

    monkeypatch.setenv("VALUE", "42")
    with pytest.raises(TypeError):
        Settings()


def test_list_malformed_item_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[int]] = Field(
            default_factory=list[int],
        )

    monkeypatch.setenv("VALUES", "1,2,bad,4")
    with pytest.raises(SettingsError, match='error parsing value for field "values"'):
        Settings()


def test_list_empty_item_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[int]] = Field(
            default_factory=list[int],
        )

    monkeypatch.setenv("VALUES", "1,,2")
    with pytest.raises(SettingsError, match='error parsing value for field "values"'):
        Settings()


def test_enum_item_invalid_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[Permission]] = Field(
            default_factory=list[Permission],
        )

    monkeypatch.setenv("VALUES", "read,invalid")
    with pytest.raises(SettingsError, match='error parsing value for field "values"'):
        Settings()


def test_literal_item_invalid_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[Literal["active", "inactive"]]] = Field(
            default_factory=list[Literal["active", "inactive"]],
        )

    monkeypatch.setenv("VALUES", "active,unknown")
    with pytest.raises(SettingsError, match='error parsing value for field "values"'):
        Settings()


def test_fixed_tuple_wrong_length_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[tuple[str, int, bool]] = Field(
            default=("", 0, False),
        )

    monkeypatch.setenv("VALUES", "hello,123")
    with pytest.raises(SettingsError, match='error parsing value for field "values"'):
        Settings()


def test_dict_malformed_pair_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Annotated[dict[str, str], ParseOptions(kv_delimiter=":")] = Field(
            default_factory=dict,
        )

    monkeypatch.setenv("VALUES", "k1:v1,broken,k2:v2")
    with pytest.raises(SettingsError, match='error parsing value for field "values"'):
        Settings()


def test_dict_missing_kv_delimiter_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[dict[str, str]] = Field(default_factory=dict)

    monkeypatch.setenv("VALUES", "k1:v1")
    with pytest.raises(TypeError):
        Settings()


def test_dict_empty_pair_is_ignored(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Annotated[dict[str, str], ParseOptions(kv_delimiter=":")] = Field(
            default_factory=dict,
        )

    monkeypatch.setenv("VALUES", "name:Alice,,city:New York")
    assert Settings().values == {"name": "Alice", "city": "New York"}


def test_ambiguous_delimiters_fails_config_validation():
    with pytest.raises(ValueError, match="cannot be the same"):
        ParseConfig(item_delimiter=":", kv_delimiter=":")


def test_dict_key_type_conversion_fails(monkeypatch: pytest.MonkeyPatch):
    class MyKey(int, Enum):
        FOO = 1

    class Settings(ParsedEnvSettings):
        values: Annotated[dict[MyKey, str], ParseOptions(kv_delimiter=":")] = Field(
            default_factory=dict[MyKey, str],
        )

    monkeypatch.setenv("VALUES", "invalid:value")
    with pytest.raises(SettingsError, match='error parsing value for field "values"'):
        Settings()


def test_unsupported_union_root_type_fails(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        value: Parsed[str | list[int]] = Field(default="")

    monkeypatch.setenv("VALUE", "something")
    with pytest.raises(TypeError):
        Settings()


def test_unsupported_complex_type_as_list_item_fails(monkeypatch: pytest.MonkeyPatch):
    class Coordinates(BaseModel):
        x: int
        y: int

    class Settings(ParsedEnvSettings):
        values: Parsed[list[Coordinates]] = Field(
            default_factory=list[Coordinates],
        )

    monkeypatch.setenv("VALUES", "1,2")
    with pytest.raises(
        SettingsError,
        match='error parsing value for field "values"',
    ):
        Settings()


def test_unsupported_complex_type_as_dict_key_fails(monkeypatch: pytest.MonkeyPatch):
    class MyComplexKey(BaseModel):
        id: int

    class Settings(ParsedEnvSettings):
        values: Annotated[
            dict[MyComplexKey, str],
            ParseOptions(kv_delimiter=":"),
        ] = Field(
            default_factory=dict[MyComplexKey, str],
        )

    monkeypatch.setenv("VALUES", "key:value")
    with pytest.raises(
        SettingsError,
        match='error parsing value for field "values"',
    ):
        Settings()


def test_unsupported_complex_type_as_dict_value_fails(monkeypatch: pytest.MonkeyPatch):
    class MyComplexValue(BaseModel):
        data: str

    class Settings(ParsedEnvSettings):
        values: Annotated[
            dict[str, MyComplexValue],
            ParseOptions(kv_delimiter=":"),
        ] = Field(
            default_factory=dict,
        )

    monkeypatch.setenv("VALUES", "key:value")
    with pytest.raises(
        SettingsError,
        match='error parsing value for field "values"',
    ):
        Settings()


def test_settings_error_exposes_parser_detail_in_cause(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[int]] = Field(default_factory=list[int])

    monkeypatch.setenv("VALUES", "1,2,bad")

    with pytest.raises(SettingsError) as exc_info:
        Settings()

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "Could not parse item" in str(exc_info.value.__cause__)


def test_non_simple_field_respects_validation_alias(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        value: str = Field(default="", validation_alias="CUSTOM_NAME")

    monkeypatch.setenv("CUSTOM_NAME", "from_alias")
    assert Settings().value == "from_alias"


def test_non_simple_field_honors_case_insensitive_lookup(
    monkeypatch: pytest.MonkeyPatch,
):
    class Settings(ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="app_")
        value: int = 0

    monkeypatch.setenv("app_value", "42")
    assert Settings().value == 42


def test_non_simple_list_json_uses_default_env_parsing(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="app_")
        values: list[int] = Field(default_factory=list[int])

    monkeypatch.setenv("app_values", "[1,2,3]")
    assert Settings().values == [1, 2, 3]


def test_simple_parser_field_respects_validation_alias(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        values: Parsed[list[int]] = Field(
            default_factory=list[int],
            validation_alias="CUSTOM_VALUES",
        )

    monkeypatch.setenv("CUSTOM_VALUES", "1,2,3")
    assert Settings().values == [1, 2, 3]


def test_non_simple_field_supports_alias_choices(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        value: int = Field(default=0, validation_alias=AliasChoices("A", "B"))

    monkeypatch.setenv("B", "7")
    assert Settings().value == 7


def test_non_simple_field_honors_env_nested_delimiter(monkeypatch: pytest.MonkeyPatch):
    class Settings(ParsedEnvSettings):
        model_config = SettingsConfigDict(
            env_prefix="APP_",
            env_nested_delimiter="__",
        )
        payload: dict[str, int] = Field(default_factory=dict)

    monkeypatch.setenv("APP_PAYLOAD__COUNT", "5")
    assert Settings().payload == {"count": 5}


def test_env_source_precedence_over_dotenv_for_simple_parser(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    env_file = tmp_path / ".env"
    env_file.write_text("VALUES=4,5,6\n", encoding="utf-8")

    class Settings(ParsedEnvSettings):
        model_config = SettingsConfigDict(env_file=str(env_file))
        values: Parsed[list[int]] = Field(default_factory=list[int])

    monkeypatch.setenv("VALUES", "1,2,3")
    assert Settings().values == [1, 2, 3]


def test_dotenv_source_parses_simple_parser_field(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    env_file = tmp_path / ".env"
    env_file.write_text("VALUES=7,8,9\n", encoding="utf-8")

    class Settings(ParsedEnvSettings):
        model_config = SettingsConfigDict(env_file=str(env_file))
        values: Parsed[list[int]] = Field(default_factory=list[int])

    monkeypatch.delenv("VALUES", raising=False)
    assert Settings().values == [7, 8, 9]


def test_dotenv_source_parses_json_compatibility_field(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    env_file = tmp_path / ".env"
    env_file.write_text('VALUES=["x", "y"]\n', encoding="utf-8")

    class Settings(ParsedEnvSettings):
        model_config = SettingsConfigDict(env_file=str(env_file))
        values: Annotated[
            list[str],
            ParseOptions(json_compatibility=True),
        ] = Field(default_factory=list[str])

    monkeypatch.delenv("VALUES", raising=False)
    assert Settings().values == ["x", "y"]


def test_dotenv_source_json_like_without_compatibility_has_hint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    env_file = tmp_path / ".env"
    env_file.write_text("VALUES=[1,2,3]\n", encoding="utf-8")

    class Settings(ParsedEnvSettings):
        model_config = SettingsConfigDict(env_file=str(env_file))
        values: Parsed[list[int]] = Field(default_factory=list[int])

    monkeypatch.delenv("VALUES", raising=False)
    with pytest.raises(SettingsError) as exc_info:
        Settings()

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert "ParseOptions(json_compatibility=True)" in str(exc_info.value.__cause__)
