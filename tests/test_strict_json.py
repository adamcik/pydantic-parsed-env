from typing import Annotated

import pytest
from pydantic import Field
from pydantic_settings import SettingsConfigDict, SettingsError

import pydantic_parsed_env as parsed


@pytest.mark.parametrize(
    "raw", ['["read","write"]', "[]", "{}", '{"read":true}', " [broken] "]
)
@pytest.mark.parametrize("dotenv", [False, True], ids=["environment", "dotenv"])
def test_json_looking_strings_are_rejected(raw, dotenv, tmp_path, monkeypatch):
    env_file = tmp_path / ".env"

    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(
            env_prefix="PPE_", env_file=env_file if dotenv else None
        )
        values: parsed.Parsed[list[str]] = Field(default_factory=list)

    monkeypatch.delenv("PPE_VALUES", raising=False)
    if dotenv:
        env_file.write_text(f"PPE_VALUES='{raw}'\n", encoding="utf-8")
    else:
        monkeypatch.setenv("PPE_VALUES", raw)
    with pytest.raises(SettingsError) as error:
        Settings()
    assert isinstance(error.value.__cause__, ValueError)
    assert "json_compatibility=True" in str(error.value.__cause__)


def test_compatibility_remains_explicit_and_native_json_is_unchanged(monkeypatch):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        compatible: Annotated[
            list[str], parsed.ParseOptions(json_compatibility=True)
        ] = Field(default_factory=list)
        native: list[str] = Field(default_factory=list)

    monkeypatch.setenv("PPE_COMPATIBLE", '["read","write"]')
    monkeypatch.setenv("PPE_NATIVE", '["read","write"]')
    configured = Settings()
    assert configured.compatible == ["read", "write"]
    assert configured.native == ["read", "write"]
