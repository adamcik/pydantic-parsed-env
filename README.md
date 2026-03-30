# pydantic-parsed-env

Parse common collection settings from simple env strings instead of JSON.

If you want `ALLOWED_HOSTS=api.local,worker.local` (not
`ALLOWED_HOSTS=["api.local","worker.local"]`), this package is for you.

## Quickstart

```bash
pip install pydantic-parsed-env
```

Requires Python 3.13+.

```python
from typing import Annotated

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from pydantic_parsed_env import ParseOptions, Parsed, ParsedEnvSettings


class Settings(ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    hosts: Parsed[list[str]] = Field(default_factory=list[str])
    ports: Annotated[
        dict[str, int],
        ParseOptions(kv_delimiter="="),
    ] = Field(default_factory=dict[str, int])


# export APP_HOSTS="api.local, worker.local"
# export APP_PORTS="http=80,https=443"

settings = Settings()

assert settings.hosts == ["api.local", "worker.local"]
assert settings.ports == {"http": 80, "https": 443}
```

In the simple case, you can use `Parsed[dict[str, int]]` and the default
`kv_delimiter=":"`. The example uses `ParseOptions(kv_delimiter="=")` only to
show delimiter override.

## When to use this

Use this package when you want readable delimiter-based env values for
collections.

Use plain `pydantic-settings` JSON parsing when you need nested objects,
nullable collection items, or other complex shapes.

## Why

`pydantic-settings` is excellent, but structured env values commonly use JSON.
That can be verbose and brittle in shell scripts, Docker env files, and ops
tooling.

`pydantic-parsed-env` keeps common collection config short and readable:

- `APP_HOSTS=api.local,worker.local`
- `APP_FEATURE_FLAGS=true,false,true`
- `APP_PORTS=http:80,https:443`

## Core API

- `ParsedEnvSettings`: `BaseSettings` subclass that wires in the custom env
  source.
- `Parsed[T]`: shorthand for `Annotated[T, ParseOptions()]`.
- `ParseOptions(...)`: annotation metadata factory for delimiter-based parsing.

`ParseOptions(...)` metadata alone is not enough. The custom parser is
installed via `settings_customise_sources`, so your settings class must inherit
from `ParsedEnvSettings`.

## Supported parsing

`ParseOptions(...)` applies to:

- `list[T]`
- `set[T]`
- `tuple[T, ...]` and fixed tuples like `tuple[str, int]`
- `dict[K, V]` (uses default `kv_delimiter` set to `:`)

Supported element conversion:

- `str`, `int`, `float`, `bool` (`true` / `false`)
- `Enum` / `StrEnum`
- `Literal[...]`

Fields without `ParseOptions(...)` keep normal `pydantic-settings` behavior,
including JSON parsing for complex values.

## Behavior matrix

| Field type                            | Example input         | Parsed result                |
| ------------------------------------- | --------------------- | ---------------------------- |
| `list[int]`                           | `"1,2,3"`             | `[1, 2, 3]`                  |
| `set[str]`                            | `"a,a,b"`             | `{"a", "b"}`                 |
| `tuple[float, ...]`                   | `"1.2,3.4"`           | `(1.2, 3.4)`                 |
| `tuple[str, int]`                     | `"host,80"`           | `("host", 80)`               |
| `dict[str, int]` + `kv_delimiter=":"` | `"http:80,https:443"` | `{"http": 80, "https": 443}` |

## Empty and malformed input semantics

- For collection fields, unset and `""` map to empty collections:
  - `list[T] -> []`
  - `set[T] -> set()`
  - `tuple[T, ...] -> ()`
  - `dict[K, V] -> {}`

- For required fields without defaults, unset values still follow normal
  `pydantic-settings` required-field behavior.

- `None` is not inferred from empty input by default. If you need nullable
  collection values, use an explicit sentinel convention.

- Parsing is strict for malformed segments:
  - `"a,,b"` is invalid for `list[int]` and similar non-string item types.
  - `"k1:v1,broken,k2:v2"` is invalid for `dict[K, V]`.

- Empty segments are allowed for `str` items:
  - `list[str]`: `"a,,b" -> ["a", "", "b"]`

## Dict parsing rules

- Dict fields require a key-value delimiter, for example
  `ParseOptions(kv_delimiter=":")`.
- Each pair must match `key<kv_delimiter>value`, for example `"k:v"`.
- Whitespace around keys and values is trimmed before conversion.
- Duplicate keys use the last value encountered:
  - `"a:1,a:2" -> {"a": 2}`

## Error behavior

At the settings integration layer, parsing errors are raised as
`pydantic_settings.SettingsError` (matching upstream source behavior).

Detailed parser failure context is preserved in `SettingsError.__cause__`.

## Non-goals and limits

- Complex nested model elements (for example `list[MyModel]`) are not supported
  by simple string parsing.
- Nullable item types inside collections (for example `list[int | None]` or
  `dict[str, bool | None]`) are intentionally out of scope for simple parsing.
  Use standard JSON-based `pydantic-settings` parsing for those shapes.
- Complex item-level unions (including nullable item unions) are not supported
  for simple parsing.
- Applying `ParseOptions(...)` to non-collection fields is a type error.

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
