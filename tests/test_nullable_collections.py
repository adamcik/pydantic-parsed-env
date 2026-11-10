from typing import Annotated

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

import pydantic_parsed_env as parsed


class OptionalSet(parsed.ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="PPE_")
    values: Annotated[set[str] | None, parsed.ParseOptions()] = None


class OptionalAlias(parsed.ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="PPE_")
    values: parsed.Parsed[set[str]] | None = None


@pytest.mark.parametrize(
    "model", [OptionalSet, OptionalAlias], ids=lambda model: model.__name__
)
def test_missing_empty_populated_and_explicit_none(model, monkeypatch):
    monkeypatch.delenv("PPE_VALUES", raising=False)
    assert model().values is None
    monkeypatch.setenv("PPE_VALUES", "")
    assert model().values == set()
    monkeypatch.setenv("PPE_VALUES", "read,write")
    assert model().values == {"read", "write"}
    assert model(values=None).values is None


def test_required_nullable_collection_stays_required(monkeypatch):
    class Required(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        values: Annotated[set[str] | None, parsed.ParseOptions()]

    monkeypatch.delenv("PPE_VALUES", raising=False)
    with pytest.raises(ValidationError, match="Field required"):
        Required()


def test_list_tuple_and_dictionary(monkeypatch):
    class Settings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        items: Annotated[list[int] | None, parsed.ParseOptions()] = None
        ports: Annotated[tuple[int, ...] | None, parsed.ParseOptions()] = None
        rates: Annotated[
            dict[str, float] | None, parsed.ParseOptions(kv_delimiter="=")
        ] = None

    monkeypatch.setenv("PPE_ITEMS", "1,2")
    monkeypatch.setenv("PPE_PORTS", "80,443")
    monkeypatch.setenv("PPE_RATES", "/metrics=0.1,/health=0")
    settings = Settings()
    assert settings.items == [1, 2]
    assert settings.ports == (80, 443)
    assert settings.rates == {"/metrics": 0.1, "/health": 0}
    monkeypatch.setenv("PPE_ITEMS", "")
    monkeypatch.setenv("PPE_PORTS", "")
    monkeypatch.setenv("PPE_RATES", "")
    empty = Settings()
    assert empty.items == []
    assert empty.ports == ()
    assert empty.rates == {}


def test_model_config_none_sentinel(monkeypatch):
    class Settings(OptionalSet):
        model_config = SettingsConfigDict(env_parse_none_str="disabled")

    monkeypatch.setenv("PPE_VALUES", "disabled")
    assert Settings().values is None


def test_configured_dotenv_parses_nullable_collection(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("PPE_VALUES=read,write\n", encoding="utf-8")

    class Settings(OptionalSet):
        model_config = SettingsConfigDict(env_file=env_file)

    monkeypatch.delenv("PPE_VALUES", raising=False)
    assert Settings().values == {"read", "write"}
