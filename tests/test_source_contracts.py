import os
from dataclasses import dataclass
from enum import IntEnum
from http import HTTPStatus
from typing import Annotated

import pytest
from pydantic import Field, ValidationError
from pydantic_settings import (
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
)

import pydantic_parsed_env as parsed


class Level(IntEnum):
    INFO = 20
    WARNING = 30


class SourceSettings(parsed.ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="PPE_")

    values: parsed.Parsed[set[str]] = Field(default_factory=lambda: {"default"})
    native: list[int] = Field(default_factory=list)


class NullableSettings(parsed.ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="PPE_")

    values: Annotated[set[str] | None, parsed.ParseOptions()] = None


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in os.environ:
        if key.upper().startswith(("PPE_", "OTHER_")):
            monkeypatch.delenv(key)


@dataclass(frozen=True, kw_only=True)
class SourceCase:
    id: str


SOURCES = [
    SourceCase(id="environment"),
    SourceCase(id="dotenv"),
    SourceCase(id="secrets"),
]


def source_options(case, tmp_path, monkeypatch, raw):
    if case.id == "environment":
        monkeypatch.setenv("PPE_VALUES", raw)
        return {}
    if case.id == "dotenv":
        env_file = tmp_path / ".env"
        env_file.write_text(f"PPE_VALUES='{raw}'\n", encoding="utf-8")
        return {"_env_file": env_file}
    (tmp_path / "PPE_VALUES").write_text(raw + "\n", encoding="utf-8")
    return {"_secrets_dir": tmp_path}


@pytest.mark.parametrize("case", SOURCES, ids=lambda case: case.id)
def test_delimiters_work_in_every_source(case, tmp_path, monkeypatch):
    options = source_options(case, tmp_path, monkeypatch, "read, write,read")
    assert SourceSettings(**options).values == {"read", "write"}


@pytest.mark.parametrize("case", SOURCES, ids=lambda case: case.id)
@pytest.mark.parametrize(
    "raw", ['["read","write"]', "[]", '{"read":true}', " [broken] "]
)
def test_every_source_rejects_json_looking_string_collections(
    case,
    raw,
    tmp_path,
    monkeypatch,
):
    options = source_options(case, tmp_path, monkeypatch, raw)
    with pytest.raises(SettingsError) as error:
        SourceSettings(**options)
    assert isinstance(error.value.__cause__, ValueError)
    assert "json_compatibility=True" in str(error.value.__cause__)


@pytest.mark.parametrize("case", SOURCES, ids=lambda case: case.id)
@pytest.mark.parametrize("raw", ["", "read,write"])
def test_nullable_collection_distinguishes_empty_from_missing(
    case,
    raw,
    tmp_path,
    monkeypatch,
):
    assert NullableSettings().values is None
    options = source_options(case, tmp_path, monkeypatch, raw)
    assert NullableSettings(**options).values == (
        set() if not raw else {"read", "write"}
    )
    assert NullableSettings(values=None, **options).values is None


def test_nullable_collection_keeps_required_field_validation():
    class Required(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        values: Annotated[set[str] | None, parsed.ParseOptions()]

    with pytest.raises(ValidationError, match="Field required"):
        Required()


def test_optional_collection_alias(monkeypatch):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        values: parsed.Parsed[set[str]] | None = None

    monkeypatch.setenv("PPE_VALUES", "read,write")
    assert Settings().values == {"read", "write"}


def test_nullable_list_tuple_and_dictionary(monkeypatch):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        items: Annotated[list[int] | None, parsed.ParseOptions()] = None
        ports: Annotated[tuple[int, ...] | None, parsed.ParseOptions()] = None
        rates: Annotated[
            dict[str, float] | None,
            parsed.ParseOptions(kv_delimiter="="),
        ] = None

    monkeypatch.setenv("PPE_ITEMS", "1,2")
    monkeypatch.setenv("PPE_PORTS", "80,443")
    monkeypatch.setenv("PPE_RATES", "/metrics=0.1,/health=0")
    configured = Settings()
    assert configured.items == [1, 2]
    assert configured.ports == (80, 443)
    assert configured.rates == {"/metrics": 0.1, "/health": 0}


def test_integer_enums_accept_numbers_and_names(monkeypatch):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        statuses: parsed.Parsed[tuple[HTTPStatus, ...]] = ()
        levels: Annotated[dict[str, Level], parsed.ParseOptions(kv_delimiter="=")] = (
            Field(
                default_factory=dict,
            )
        )

    monkeypatch.setenv("PPE_STATUSES", "429,bad_gateway")
    monkeypatch.setenv("PPE_LEVELS", "access_denied=20,invalid_state=warning")
    configured = Settings()
    assert configured.statuses == (HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.BAD_GATEWAY)
    assert configured.levels == {
        "access_denied": Level.INFO,
        "invalid_state": Level.WARNING,
    }


@pytest.mark.parametrize("raw", ["999", "not_a_status", "429,,502"])
def test_integer_enums_reject_unknown_values(monkeypatch, raw):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        values: parsed.Parsed[tuple[HTTPStatus, ...]] = ()

    monkeypatch.setenv("PPE_VALUES", raw)
    with pytest.raises(SettingsError):
        Settings()


def test_constructor_dotenv_options_and_disable(tmp_path):
    configured_file = tmp_path / "configured.env"
    configured_file.write_text("PPE_VALUES=configured\n", encoding="utf-8")
    override = tmp_path / "override.env"
    override.write_text("PPE_VALUES=caf\xe9,override\n", encoding="latin-1")

    class Settings(SourceSettings):
        model_config = SettingsConfigDict(env_file=configured_file)

    assert Settings(_env_file=override, _env_file_encoding="latin-1").values == {
        "café",
        "override",
    }
    assert Settings(_env_file=None).values == {"default"}


def test_constructor_prefix_and_case_sensitivity(monkeypatch):
    monkeypatch.setenv("OTHER_values", "read,write")
    monkeypatch.setenv("OTHER_VALUES", "wrong")
    assert SourceSettings(_env_prefix="OTHER_", _case_sensitive=True).values == {
        "read",
        "write",
    }


def test_constructor_empty_and_none_options(monkeypatch):
    monkeypatch.setenv("PPE_VALUES", "")
    assert SourceSettings(_env_ignore_empty=True).values == {"default"}
    monkeypatch.setenv("PPE_VALUES", "disabled")
    assert NullableSettings(_env_parse_none_str="disabled").values is None


def test_constructor_nested_options(monkeypatch):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        payload: dict[str, str] = Field(default_factory=dict)

    monkeypatch.setenv("PPE_PAYLOAD__LONG__KEY", "value")
    assert Settings(_env_nested_delimiter="__", _env_nested_max_split=1).payload == {
        "long__key": "value",
    }


def test_source_precedence_and_native_json(tmp_path, monkeypatch):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "PPE_VALUES").write_text("secret", encoding="utf-8")
    (secrets / "PPE_NATIVE").write_text("[1,2]", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("PPE_VALUES=dotenv\n", encoding="utf-8")
    assert SourceSettings(_secrets_dir=secrets).values == {"secret"}
    assert SourceSettings(_secrets_dir=secrets).native == [1, 2]
    options = {"_secrets_dir": secrets, "_env_file": env_file}
    assert SourceSettings(**options).values == {"dotenv"}
    monkeypatch.setenv("PPE_VALUES", "environment")
    assert SourceSettings(**options).values == {"environment"}
    assert SourceSettings(values={"explicit"}, **options).values == {"explicit"}


def test_customize_sources_can_compose_credential_directory(tmp_path):
    class Settings(SourceSettings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls,
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            file_secret_settings.secrets_dir = tmp_path
            return super().settings_customise_sources(
                settings_cls,
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )

    (tmp_path / "PPE_VALUES").write_text("read,write", encoding="utf-8")
    assert Settings().values == {"read", "write"}


def test_secret_json_compatibility_is_explicit(tmp_path):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        values: Annotated[list[str], parsed.ParseOptions(json_compatibility=True)] = (
            Field(
                default_factory=list,
            )
        )

    (tmp_path / "PPE_VALUES").write_text('["read","write"]', encoding="utf-8")
    assert Settings(_secrets_dir=tmp_path).values == ["read", "write"]


@pytest.mark.parametrize("case", SOURCES, ids=lambda case: case.id)
def test_prefix_and_case_options_apply_to_every_source(case, tmp_path, monkeypatch):
    if case.id == "environment":
        monkeypatch.setenv("OTHER_values", "read,write")
        options = {}
    elif case.id == "dotenv":
        env_file = tmp_path / ".env"
        env_file.write_text("OTHER_values=read,write\n", encoding="utf-8")
        options = {"_env_file": env_file}
    else:
        (tmp_path / "OTHER_values").write_text("read,write", encoding="utf-8")
        options = {"_secrets_dir": tmp_path}
    assert SourceSettings(
        _env_prefix="OTHER_",
        _case_sensitive=True,
        **options,
    ).values == {"read", "write"}


def test_source_adaptation_keeps_loaded_snapshots(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("PPE_NATIVE=[1,2]\n", encoding="utf-8")
    monkeypatch.setenv("PPE_VALUES", "before")

    class Settings(SourceSettings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls,
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            monkeypatch.setenv("PPE_VALUES", "after")
            env_file.write_text("PPE_NATIVE=[3,4]\n", encoding="utf-8")
            return super().settings_customise_sources(
                settings_cls,
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )

    configured = Settings(_env_file=env_file)
    assert configured.values == {"before"}
    assert configured.native == [1, 2]


def test_custom_source_subclasses_are_preserved():
    class CustomSource(EnvSettingsSource):
        def __call__(self) -> dict[str, object]:
            return {"values": {"custom"}}

    class Settings(SourceSettings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls,
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return super().settings_customise_sources(
                settings_cls,
                init_settings,
                CustomSource(settings_cls),
                dotenv_settings,
                file_secret_settings,
            )

    assert Settings().values == {"custom"}


def test_public_secret_source_can_be_used_directly(tmp_path):
    (tmp_path / "PPE_VALUES").write_text("read,write", encoding="utf-8")
    source = parsed.ParsedSecretsSettingsSource(SourceSettings, secrets_dir=tmp_path)
    assert source() == {"values": {"read", "write"}}


def test_dictionary_sources_keep_normal_merging(tmp_path, monkeypatch):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        values: Annotated[dict[str, int], parsed.ParseOptions(kv_delimiter="=")] = (
            Field(
                default_factory=dict,
            )
        )

    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "PPE_VALUES").write_text("file=1,shared=2", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("PPE_VALUES=dotenv=3,shared=4\n", encoding="utf-8")
    monkeypatch.setenv("PPE_VALUES", "env=5,shared=6")
    configured = Settings(
        values={"explicit": 7, "shared": 8},
        _env_file=env_file,
        _secrets_dir=secrets,
    )
    assert configured.values == {
        "file": 1,
        "dotenv": 3,
        "env": 5,
        "explicit": 7,
        "shared": 8,
    }


def test_statement_delimiter_preserves_sql_content(monkeypatch):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        values: Annotated[list[str], parsed.ParseOptions(item_delimiter=";")] = Field(
            default_factory=list,
        )

    monkeypatch.setenv(
        "PPE_VALUES",
        "PRAGMA journal_mode = WAL; PRAGMA table_info('name,with,commas')",
    )
    assert Settings().values == [
        "PRAGMA journal_mode = WAL",
        "PRAGMA table_info('name,with,commas')",
    ]
