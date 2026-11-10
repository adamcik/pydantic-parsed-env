import os
from typing import Annotated

import pytest
from pydantic import Field, SecretStr
from pydantic_settings import (
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    SettingsError,
)

import pydantic_parsed_env as parsed


class Settings(parsed.ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="PPE_")
    scopes: parsed.Parsed[set[str]] = Field(default_factory=set)
    rates: Annotated[dict[str, float], parsed.ParseOptions(kv_delimiter="=")] = Field(
        default_factory=dict
    )
    pragmas: Annotated[list[str], parsed.ParseOptions(item_delimiter=";")] = Field(
        default_factory=list
    )
    native: list[int] = Field(default_factory=list)
    token: SecretStr = SecretStr("default")


def test_delimiter_collections_and_scalar_secrets(tmp_path):
    values = {
        "PPE_SCOPES": "read,write,read",
        "PPE_RATES": "/metrics=0.1,/health=0",
        "PPE_PRAGMAS": (
            "PRAGMA journal_mode = WAL;PRAGMA table_info('name,with,commas')"
        ),
        "PPE_NATIVE": "[1,2]",
        "PPE_TOKEN": "secret-token",
    }
    for name, value in values.items():
        (tmp_path / name).write_text(value + "\n", encoding="utf-8")
    configured = Settings(_secrets_dir=tmp_path)
    assert configured.scopes == {"read", "write"}
    assert configured.rates == {"/metrics": 0.1, "/health": 0}
    assert configured.pragmas == [
        "PRAGMA journal_mode = WAL",
        "PRAGMA table_info('name,with,commas')",
    ]
    assert configured.native == [1, 2]
    assert configured.token.get_secret_value() == "secret-token"


def test_empty_collections(tmp_path):
    for name in ("PPE_SCOPES", "PPE_RATES", "PPE_PRAGMAS"):
        (tmp_path / name).write_text("\n", encoding="utf-8")
    configured = Settings(_secrets_dir=tmp_path)
    assert configured.scopes == set()
    assert configured.rates == {}
    assert configured.pragmas == []


def test_secret_json_compatibility_is_explicit(tmp_path):
    class Compatible(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        scopes: Annotated[list[str], parsed.ParseOptions(json_compatibility=True)] = (
            Field(default_factory=list)
        )

    (tmp_path / "PPE_SCOPES").write_text('["read","write"]', encoding="utf-8")
    assert Compatible(_secrets_dir=tmp_path).scopes == ["read", "write"]


def test_malformed_dictionary_is_a_settings_error(tmp_path):
    (tmp_path / "PPE_RATES").write_text("/metrics=bad", encoding="utf-8")
    with pytest.raises(SettingsError) as error:
        Settings(_secrets_dir=tmp_path)
    assert isinstance(error.value.__cause__, ValueError)


def test_explicit_directory_prefix_and_case_are_kept(tmp_path):
    fallback = tmp_path / "fallback"
    explicit = tmp_path / "explicit"
    fallback.mkdir()
    explicit.mkdir()
    (fallback / "OTHER_scopes").write_text("fallback", encoding="utf-8")
    (explicit / "OTHER_scopes").write_text("explicit", encoding="utf-8")

    class Configured(Settings):
        model_config = SettingsConfigDict(secrets_dir=fallback)

    assert Configured(
        _secrets_dir=explicit,
        _env_prefix="OTHER_",
        _case_sensitive=True,
    ).scopes == {"explicit"}


def test_application_can_supply_systemd_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("CREDENTIALS_DIRECTORY", str(tmp_path))
    (tmp_path / "PPE_SCOPES").write_text("read,write", encoding="utf-8")
    assert Settings().scopes == set()

    class Credentials(Settings):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls,
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            if file_secret_settings.secrets_dir is None:
                file_secret_settings.secrets_dir = os.environ["CREDENTIALS_DIRECTORY"]
            return super().settings_customise_sources(
                settings_cls,
                init_settings,
                env_settings,
                dotenv_settings,
                file_secret_settings,
            )

    assert Credentials().scopes == {"read", "write"}


def test_dictionaries_keep_source_merging_and_precedence(tmp_path, monkeypatch):
    (tmp_path / "PPE_RATES").write_text("file=0.1,shared=0.2", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("PPE_RATES=dotenv=0.3,shared=0.4\n", encoding="utf-8")
    monkeypatch.setenv("PPE_RATES", "env=0.5,shared=0.6")
    configured = Settings(
        rates={"explicit": 0.7, "shared": 0.8},
        _env_file=env_file,
        _secrets_dir=tmp_path,
    )
    assert configured.rates == {
        "file": 0.1,
        "dotenv": 0.3,
        "env": 0.5,
        "explicit": 0.7,
        "shared": 0.8,
    }


def test_public_secret_source(tmp_path):
    (tmp_path / "PPE_SCOPES").write_text("read,write", encoding="utf-8")
    source = parsed.ParsedSecretsSettingsSource(Settings, secrets_dir=tmp_path)
    assert source() == {"scopes": {"read", "write"}}
