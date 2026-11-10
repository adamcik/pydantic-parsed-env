import os
from typing import Annotated

import pytest
from pydantic import Field
from pydantic_settings import SettingsConfigDict, SettingsError

import pydantic_parsed_env as parsed


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in os.environ:
        if key.upper().startswith("DEFAULT_"):
            monkeypatch.delenv(key)


class Defaults(parsed.ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="DEFAULT_")
    names: parsed.Parsed[list[str]] = Field(default_factory=list)
    ports: parsed.Parsed[dict[str, int]] = Field(default_factory=dict)


def test_environment_defaults(monkeypatch):
    monkeypatch.setenv("DEFAULT_NAMES", "read,write")
    monkeypatch.setenv("DEFAULT_PORTS", "http=80,https=443")
    configured = Defaults()
    assert configured.names == ["read", "write"]
    assert configured.ports == {"http": 80, "https": 443}


def test_environment_file_defaults(tmp_path):
    env_file = tmp_path / "service.env"
    env_file.write_text(
        "DEFAULT_NAMES=read,write\nDEFAULT_PORTS=http=80,https=443\n",
        encoding="utf-8",
    )
    configured = Defaults(_env_file=env_file)
    assert configured.names == ["read", "write"]
    assert configured.ports == {"http": 80, "https": 443}


def test_credential_file_defaults(tmp_path):
    (tmp_path / "DEFAULT_NAMES").write_text("read\nwrite\n", encoding="utf-8")
    (tmp_path / "DEFAULT_PORTS").write_text("http=80\nhttps=443\n", encoding="utf-8")
    configured = Defaults(_secrets_dir=tmp_path)
    assert configured.names == ["read", "write"]
    assert configured.ports == {"http": 80, "https": 443}


def test_credential_defaults_accept_crlf(tmp_path):
    (tmp_path / "DEFAULT_NAMES").write_bytes(b"read\r\nwrite\r\n")
    (tmp_path / "DEFAULT_PORTS").write_bytes(b"http=80\r\nhttps=443\r\n")
    configured = Defaults(_secrets_dir=tmp_path)
    assert configured.names == ["read", "write"]
    assert configured.ports == {"http": 80, "https": 443}


def test_explicit_comma_overrides_credential_newlines(tmp_path):
    class Explicit(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="DEFAULT_")
        names: Annotated[list[str], parsed.ParseOptions(item_delimiter=",")] = Field(
            default_factory=list,
        )
        ports: Annotated[dict[str, int], parsed.ParseOptions(item_delimiter=",")] = (
            Field(
                default_factory=dict,
            )
        )

    (tmp_path / "DEFAULT_NAMES").write_text("read,write", encoding="utf-8")
    (tmp_path / "DEFAULT_PORTS").write_text("http=80,https=443", encoding="utf-8")
    configured = Explicit(_secrets_dir=tmp_path)
    assert configured.names == ["read", "write"]
    assert configured.ports == {"http": 80, "https": 443}


def test_explicit_key_value_delimiter_keeps_default_item_delimiter(tmp_path):
    class Explicit(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="DEFAULT_")
        ports: Annotated[dict[str, int], parsed.ParseOptions(kv_delimiter=":")] = Field(
            default_factory=dict,
        )

    (tmp_path / "DEFAULT_PORTS").write_text("http:80\nhttps:443", encoding="utf-8")
    assert Explicit(_secrets_dir=tmp_path).ports == {"http": 80, "https": 443}


def test_explicit_delimiters_work_in_every_source(tmp_path, monkeypatch):
    class Explicit(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="DEFAULT_")
        ports: Annotated[
            dict[str, int],
            parsed.ParseOptions(item_delimiter=";", kv_delimiter=":"),
        ] = Field(default_factory=dict)

    raw = "http:80;https:443"
    (tmp_path / "DEFAULT_PORTS").write_text(raw, encoding="utf-8")
    assert Explicit(_secrets_dir=tmp_path).ports == {"http": 80, "https": 443}
    monkeypatch.setenv("DEFAULT_PORTS", raw)
    assert Explicit().ports == {"http": 80, "https": 443}


def test_credential_decoding_does_not_mutate_environment_defaults(
    tmp_path, monkeypatch
):
    (tmp_path / "DEFAULT_NAMES").write_text("read\nwrite", encoding="utf-8")
    assert Defaults(_secrets_dir=tmp_path).names == ["read", "write"]
    monkeypatch.setenv("DEFAULT_NAMES", "env,other")
    assert Defaults(_secrets_dir=tmp_path).names == ["env", "other"]


def test_credential_delimiter_collision_is_rejected(tmp_path):
    class Invalid(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="DEFAULT_")
        ports: Annotated[dict[str, int], parsed.ParseOptions(kv_delimiter="\n")] = (
            Field(
                default_factory=dict,
            )
        )

    (tmp_path / "DEFAULT_PORTS").write_text("http\n80", encoding="utf-8")
    with pytest.raises(SettingsError) as error:
        Invalid(_secrets_dir=tmp_path)
    assert "cannot be the same" in str(error.value.__cause__)


def test_explicit_equal_item_delimiter_for_sequences(tmp_path, monkeypatch):
    class Explicit(parsed.ParsedEnvSettings):
        model_config = SettingsConfigDict(env_prefix="DEFAULT_")
        names: Annotated[list[str], parsed.ParseOptions(item_delimiter="=")] = Field(
            default_factory=list,
        )

    (tmp_path / "DEFAULT_NAMES").write_text("read=write", encoding="utf-8")
    assert Explicit(_secrets_dir=tmp_path).names == ["read", "write"]
    monkeypatch.setenv("DEFAULT_NAMES", "env=other")
    assert Explicit().names == ["env", "other"]
