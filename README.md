# pydantic-simple-env

Parse common collection settings from simple env strings instead of JSON.

If you want `ALLOWED_HOSTS=api.local,worker.local` (not
`ALLOWED_HOSTS=["api.local","worker.local"]`), this package is for you.

## Why

`pydantic-settings` is excellent, but for structured values it commonly expects
JSON in environment variables.

That can be verbose and brittle in shell scripts, Docker env files, and ops
tooling.

`pydantic-simple-env` adds a lightweight parser for common collection types so
env vars stay readable:

- `APP_HOSTS=api.local,worker.local`
- `APP_FEATURE_FLAGS=true,false,true`
- `APP_PORTS=http:80,https:443`

## Install

```bash
pip install pydantic-simple-env
```

Requires Python 3.13+.

## Happy path

Use `BaseSimpleEnvSettings` and annotate only the fields you want to parse with
simple delimiters.

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
        SimpleEnvParser(kv_delimiter=":"),
    ] = Field(default_factory=dict[str, int])


# APP_HOSTS="api.local, worker.local"
# APP_PORTS="http:80,https:443"
settings = Settings()

assert settings.hosts == ["api.local", "worker.local"]
assert settings.ports == {"http": 80, "https": 443}
```

## What gets parsed

`SimpleEnvParser(...)` applies to these field types:

- `list[T]`
- `set[T]`
- `tuple[T, ...]` and fixed tuples like `tuple[str, int]`
- `dict[K, V]` (requires `kv_delimiter`)

Supported element conversion:

- `str`, `int`, `float`, `bool` (`true` / `false`)
- `Enum` / `StrEnum`
- `Literal[...]`
- `Union[...]` of supported scalar types

Fields without `SimpleEnvParser(...)` keep normal `pydantic-settings` behavior
(including JSON parsing for complex values).

## API

- `BaseSimpleEnvSettings`: `BaseSettings` subclass wiring in the custom env
  source.
- `SimpleParsed[T]`: shorthand for `Annotated[T, SimpleEnvParser()]`.
- `SimpleEnvParser(...)`: annotation metadata factory for delimiter-based
  parsing.

## Why a base class is required

Today, custom parsing is installed via `settings_customise_sources`, so you need
to inherit from `BaseSimpleEnvSettings`.

In other words: using `SimpleEnvParser(...)` annotations alone is not enough;
the custom source must be part of the settings source chain.

If `pydantic-settings` gains a cleaner extension point for field-local env
parsing without source customization, this package may support that path in the
future.

## Error behavior

At the settings integration layer, parsing errors are raised as
`pydantic_settings.SettingsError` (matching upstream source behavior).

Detailed parser failure context is kept in `SettingsError.__cause__`.

## Limits

- Complex nested model elements (for example `list[MyModel]`) are not supported
  by simple string parsing.
- Applying `SimpleEnvParser(...)` to non-collection fields is a type error.

## Development

Default (no Nix required):

```bash
uv sync
uv run ruff check .
uv run ruff format .
uv run pyright .
uv run pytest -q
```

If you use Nix, a dev shell plus formatting/check wiring is already provided:

```bash
nix develop
nix fmt
nix flake check
```

CI runs the same Nix commands (`nix fmt` and `nix flake check`) using
Determinate Nix + Magic Nix Cache.

## License

Apache-2.0.
