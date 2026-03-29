# pydantic-simple-env

Simple env var parsing for Pydantic Settings without JSON for common collection types.

## Status

Prototype / pre-1st-release.

- API exists in `src/pydantic_simple_env/_api.py`
- Tests exist in `tests/test_settings.py`
- Behavior is still being stabilized

## Why

Pydantic Settings expects JSON for many structured env values (for example `LIST='[1,2,3]'`).
This project aims to support simpler strings like:

- `INT_LIST=1,2,3`
- `FLAGS=on,off,on`
- `PORTS=http:80,https:443`

## Quick start

```bash
uv sync
uv run pytest -q
```

## Usage

```python
from typing import Annotated

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from pydantic_simple_env import BaseSimpleEnvSettings, SimpleEnvParser, SimpleParsed


class Settings(BaseSimpleEnvSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    hosts: SimpleParsed[list[str]] = Field(default_factory=list[str])
    ports: Annotated[
        dict[str, int],
        SimpleEnvParser(item_delimiter=",", kv_delimiter=":"),
    ] = Field(
        default_factory=dict[str, int],
    )


# APP_HOSTS="api.local, worker.local"
# APP_PORTS="http:80,https:443"
cfg = Settings()
assert cfg.hosts == ["api.local", "worker.local"]
assert cfg.ports == {"http": 80, "https": 443}
```

## Current parsing contract

When a field is annotated with `SimpleEnvParser(...)` metadata:

- Supported collection types: `list[T]`, `set[T]`, `tuple[...]`, `dict[K, V]`
- Item whitespace is stripped before conversion
- `list` / `set` / variable-length `tuple[T, ...]`: empty input (`""`, `",,,"`) becomes empty collection
- Fixed-length tuple requires exact item count
- `dict` requires `kv_delimiter` and parses pairs split by `item_delimiter`
- Empty dict pairs are ignored (for example `"a:1,,b:2"`)

Element conversion currently supports:

- `str`, `int`, `float`, `bool` (`true` / `false`)
- `Enum` / `StrEnum`
- `Literal[...]` (string literal matching)
- `Union[...]` of supported types

Fields without `SimpleEnvParser(...)` use normal Pydantic Settings behavior.

Recommended pattern:

- Use `SimpleParsed[T]` for default delimiters (`Annotated[T, SimpleEnvParser()]`)
- Use explicit `Annotated[T, SimpleEnvParser(...)]` for custom delimiters

## Known limits

- Complex nested item types are not supported as direct elements (for example `list[MyModel]`)
- Applying `SimpleEnvParser(...)` to non-collection fields is an error
- API/behavior may change while tests are being normalized

## Dev

```bash
uv sync
uv run pytest -q
```
