from pathlib import Path

import pytest
from pydantic import Field
from pydantic_settings import (
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

import pydantic_parsed_env as parsed


class Settings(parsed.ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="PPE_")
    values: parsed.Parsed[set[str]] = Field(default_factory=lambda: {"default"})


def test_dotenv_constructor_options(tmp_path: Path):
    default_file = tmp_path / "default.env"
    default_file.write_text("PPE_VALUES=default-file\n", encoding="utf-8")
    override = tmp_path / "override.env"
    override.write_text("PPE_VALUES=café,override\n", encoding="latin-1")

    class Configured(Settings):
        model_config = SettingsConfigDict(env_file=default_file)

    assert Configured(_env_file=override, _env_file_encoding="latin-1").values == {
        "café",
        "override",
    }
    assert Configured(_env_file=None).values == {"default"}


def test_prefix_and_case_constructor_options(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OTHER_values", "read,write")
    monkeypatch.setenv("OTHER_VALUES", "wrong")
    assert Settings(_env_prefix="OTHER_", _case_sensitive=True).values == {
        "read",
        "write",
    }


def test_empty_constructor_option(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PPE_VALUES", "")
    assert Settings(_env_ignore_empty=True).values == {"default"}


def test_none_constructor_option(monkeypatch: pytest.MonkeyPatch):
    class Nullable(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        value: str | None = None

    monkeypatch.setenv("PPE_VALUE", "disabled")
    assert Nullable(_env_parse_none_str="disabled").value is None


def test_nested_constructor_options(monkeypatch: pytest.MonkeyPatch):
    class Nested(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        payload: dict[str, str] = Field(default_factory=dict)

    monkeypatch.setenv("PPE_PAYLOAD__LONG__KEY", "value")
    assert Nested(_env_nested_delimiter="__", _env_nested_max_split=1).payload == {
        "long__key": "value",
    }


def test_prefix_and_case_apply_to_dotenv(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("OTHER_values=read,write\n", encoding="utf-8")
    assert Settings(
        _env_file=env_file,
        _env_prefix="OTHER_",
        _case_sensitive=True,
    ).values == {"read", "write"}


def test_precedence_and_unannotated_secret_json(tmp_path: Path, monkeypatch):
    class Native(Settings):
        native: list[int] = Field(default_factory=list)

    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "PPE_VALUES").write_text("secret", encoding="utf-8")
    (secrets / "PPE_NATIVE").write_text("[1,2]", encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text("PPE_VALUES=dotenv\n", encoding="utf-8")
    options = {"_secrets_dir": secrets, "_env_file": env_file}
    assert Native(_secrets_dir=secrets).values == {"secret"}
    assert Native(**options).values == {"dotenv"}
    assert Native(**options).native == [1, 2]
    monkeypatch.setenv("PPE_VALUES", "environment")
    assert Native(**options).values == {"environment"}
    assert Native(values={"explicit"}, **options).values == {"explicit"}


def test_custom_source_subclasses_are_preserved():
    class CustomSource(EnvSettingsSource):
        def __call__(self) -> dict[str, object]:
            return {"values": {"custom"}}

    class Custom(Settings):
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

    assert Custom().values == {"custom"}
