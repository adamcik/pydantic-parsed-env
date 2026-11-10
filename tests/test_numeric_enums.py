from enum import IntEnum
from http import HTTPStatus
from typing import Annotated

import pytest
from pydantic import Field
from pydantic_settings import SettingsConfigDict, SettingsError

import pydantic_parsed_env as parsed


class Level(IntEnum):
    INFO = 20
    WARNING = 30


class Settings(parsed.ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="PPE_")
    statuses: parsed.Parsed[tuple[HTTPStatus, ...]] = ()
    levels: Annotated[dict[str, Level], parsed.ParseOptions(kv_delimiter="=")] = Field(
        default_factory=dict,
    )


def test_numbers_and_names(monkeypatch):
    monkeypatch.setenv("PPE_STATUSES", "429,bad_gateway")
    monkeypatch.setenv("PPE_LEVELS", "access_denied=20,invalid_state=warning")
    configured = Settings()
    assert configured.statuses == (HTTPStatus.TOO_MANY_REQUESTS, HTTPStatus.BAD_GATEWAY)
    assert configured.levels == {
        "access_denied": Level.INFO,
        "invalid_state": Level.WARNING,
    }


@pytest.mark.parametrize("raw", ["999", "not_a_status", "429,,502", "429.0", "0x1ad"])
def test_invalid_integer_enums(monkeypatch, raw):
    monkeypatch.setenv("PPE_STATUSES", raw)
    with pytest.raises(SettingsError):
        Settings()


def test_integer_enum_dictionary_keys(monkeypatch):
    class KeySettings(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="PPE_")
        labels: Annotated[
            dict[HTTPStatus, str], parsed.ParseOptions(kv_delimiter="=")
        ] = Field(
            default_factory=dict,
        )

    monkeypatch.setenv("PPE_LABELS", "429=retry,502=reset")
    assert KeySettings().labels == {
        HTTPStatus.TOO_MANY_REQUESTS: "retry",
        HTTPStatus.BAD_GATEWAY: "reset",
    }
