# pydantic-parsed-env

Parse common collection settings from simple env strings instead of JSON.

If you want `ALLOWED_HOSTS=api.local,worker.local` (not
`ALLOWED_HOSTS=["api.local","worker.local"]`), this package is for you.

## Quickstart

```bash
pip install pydantic-parsed-env
```

Requires Python 3.12+.

Runtime dependency policy:

- Published runtime dependencies use tested compatibility ranges, not exact pins.
- Supported runtime dependency ranges are declared in the package metadata.
- Exact versions for development are managed separately in the lockfile/tooling.

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

Dictionary fields must specify a key-value delimiter, such as
`ParseOptions(kv_delimiter="=")` or `ParseOptions(kv_delimiter=":")`.
`Parsed[dict[str, int]]` alone does not configure one.

## When to use this

Use this package when you want readable delimiter-based env values for collections.

Use plain `pydantic-settings` JSON parsing when you need nested objects, nullable
collection items, or other complex shapes.

## Why

`pydantic-settings` is excellent, but structured env values commonly use JSON. That can
be verbose and brittle in shell scripts, Docker env files, and ops tooling.

`pydantic-parsed-env` keeps common collection config short and readable:

- `APP_HOSTS=api.local,worker.local`
- `APP_FEATURE_FLAGS=true,false,true`
- `APP_PORTS=http:80,https:443`

## Core API

- `ParsedEnvSettings`: `BaseSettings` subclass that wires in parsed environment, dotenv,
  and secret-file sources.
- `Parsed[T]`: shorthand for `Annotated[T, ParseOptions()]`.
- `ParseOptions(...)`: annotation metadata factory for delimiter-based parsing.
- `ParsedEnvSettingsSource` and `ParsedSecretsSettingsSource`: source classes for
  applications that explicitly assemble their own source pipeline.

`ParseOptions(...)` metadata alone is not enough. The custom parser is installed via
`settings_customise_sources`, so your settings class must inherit from
`ParsedEnvSettings`.

## Settings sources

Parsed fields use the same syntax in environment variables, configured dotenv files, and
secret files. Unannotated fields retain their source's normal behavior. Constructor
overrides such as `_env_file`, `_env_file_encoding`, `_env_prefix`, `_case_sensitive`,
and `_secrets_dir` are preserved. Dotenv loading remains opt-in through `model_config`
or `_env_file`.

Source priority is unchanged: constructor values, environment, dotenv, secret files,
then defaults. Dictionary values retain Pydantic's normal source-merging rules. Custom
source subclasses are preserved rather than replaced.

If you override `settings_customise_sources`, compose with
`super().settings_customise_sources(...)`. Returning the original sources bypasses
parsed decoding. An application may set the supplied secret source's `secrets_dir`
before delegating, for example to read a systemd credentials directory. This library
does not inspect `CREDENTIALS_DIRECTORY` itself.

## Supported parsing

`ParseOptions(...)` applies to:

- `list[T]`
- `set[T]`
- `tuple[T, ...]` and fixed tuples like `tuple[str, int]`
- `dict[K, V]` (requires an explicit `kv_delimiter`)
- Nullable collections, for example `Annotated[set[str] | None, ParseOptions()] = None`

Supported element conversion:

- `str`, `int`, `float`, `bool` (`true` / `false`)
- `Enum` / `StrEnum` values or case-insensitive member names
- `IntEnum` values in decimal notation, including `HTTPStatus` (`429,502`)
- `Literal[...]`

Fields without `ParseOptions(...)` keep normal `pydantic-settings` behavior, including
JSON parsing for complex values.

## Behavior matrix

| Field type                            | Example input         | Parsed result                |
| ------------------------------------- | --------------------- | ---------------------------- |
| `list[int]`                           | `"1,2,3"`             | `[1, 2, 3]`                  |
| `set[str]`                            | `"a,a,b"`             | `{"a", "b"}`                 |
| `tuple[float, ...]`                   | `"1.2,3.4"`           | `(1.2, 3.4)`                 |
| `tuple[str, int]`                     | `"host,80"`           | `("host", 80)`               |
| `dict[str, int]` + `kv_delimiter=":"` | `"http:80,https:443"` | `{"http": 80, "https": 443}` |

## Empty and malformed input semantics

- Unset fields retain their defaults, including `None` for nullable collections.
- An explicit `""` maps to an empty collection, even when the field is nullable:
  - `list[T] -> []`
  - `set[T] -> set()`
  - `tuple[T, ...] -> ()`
  - `dict[K, V] -> {}`

- For required fields without defaults, unset values still follow normal
  `pydantic-settings` required-field behavior.

- `None` is not inferred from empty input. Pass `None` directly, leave a nullable field
  with a `None` default unset, or configure Pydantic's `env_parse_none_str` sentinel for
  environment and dotenv values.

- Parsing is strict for malformed segments:
  - `"a,,b"` is invalid for `list[int]` and similar non-string item types.
  - `"k1:v1,broken,k2:v2"` is invalid for `dict[K, V]`.

- Empty segments are allowed for `str` items:
  - `list[str]`: `"a,,b" -> ["a", "", "b"]`

## JSON compatibility

Parsed fields reject values wrapped in `[...]` or `{...}` by default, including string
collections and malformed JSON-looking values. They are never silently accepted as
delimiter-separated strings. Unannotated fields still use normal Pydantic JSON decoding.

For an intentional transition period, a field may opt into
`ParseOptions(json_compatibility=True)`. This tries JSON first for JSON-looking values
and retains delimiter parsing as its fallback. Leave compatibility disabled when
migrating completely to delimiter syntax.

Delimiters are literal strings: there is no quoting or escaping within a parsed value.
Choose delimiters that cannot occur in the items, such as `;` between SQL PRAGMA
statements containing spaces, commas, or equals signs.

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

Detailed parser failure context is preserved in `SettingsError.__cause__`. That context
can contain configuration values; do not log it without sanitization.

## Non-goals and limits

- Complex nested model elements (for example `list[MyModel]`) are not supported by
  simple string parsing.
- Nullable item types inside collections (for example `list[int | None]` or
  `dict[str, bool | None]`) are intentionally out of scope for simple parsing. Use
  standard JSON-based `pydantic-settings` parsing for those shapes.
- Complex item-level unions (including nullable item unions) are not supported for
  simple parsing.
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

CI runs the same Nix commands (`nix fmt` and `nix flake check`) using Determinate Nix +
Magic Nix Cache.

## Versioning and releases

### 0.2.0 migration

Breaking changes from 0.1.0:

- JSON-looking values in parsed string collections are rejected rather than split into
  literal fragments. Rewrite them with delimiters or explicitly opt into JSON
  compatibility.
- Parsed fields in secret files now use delimiter syntax too. JSON values require
  explicit compatibility, just as they do in environment and dotenv values.

This release also adds nullable root collections and numeric `IntEnum` parsing,
preserves constructor source options, and keeps source precedence unchanged.

- Package versions are derived from Git tags via `hatch-vcs`.
- Release tags must use the `vX.Y.Z` form, for example `v0.3.1`.
- The published package version strips the `v` prefix, so `v0.3.1` becomes `0.3.1` on
  PyPI.
- This project follows semantic versioning for its public API. While the package is
  still `0.x`, breaking changes may still land in minor releases.

## License

Apache-2.0.
