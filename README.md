# pydantic-parsed-env

Read typed collections from environment variables and credential files without JSON. Use
comma-separated values for single-line environment settings and one entry per line in
credential files, rather than adding application-specific collection parsers.

## Quickstart

Requires Python 3.12+. Install with `pip install pydantic-parsed-env`, or
`pip install .` from a source checkout. These examples describe the 0.2.0 API; for
0.1.0, see its
[versioned README](https://github.com/adamcik/pydantic-parsed-env/blob/v0.1.0/README.md).

Set the environment values:

```bash
export APP_HOSTS="api.local, worker.local"
export APP_PORTS="http=80,https=443"
```

Mark the collection fields you want parsed:

```python
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from pydantic_parsed_env import Parsed, ParsedEnvSettings


class Settings(ParsedEnvSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    hosts: Parsed[list[str]] = Field(default_factory=list[str])
    ports: Parsed[dict[str, int]] = Field(default_factory=dict[str, int])


settings = Settings()

assert settings.hosts == ["api.local", "worker.local"]
assert settings.ports == {"http": 80, "https": 443}
```

`Parsed[T]` is shorthand for `Annotated[T, ParseOptions()]`. Your model must inherit
from `ParsedEnvSettings` to install the parser. Unannotated fields retain normal
Pydantic behavior, including JSON decoding.

## Input formats

| Source                               | Item delimiter | Dictionary key-value delimiter |
| ------------------------------------ | -------------- | ------------------------------ |
| Environment and dotenv               | Comma          | `=`                            |
| Individual secret or credential file | Newline        | `=`                            |

A dotenv or systemd EnvironmentFile supplies environment values in the same comma-based
format as the quickstart, with one `NAME=value` assignment per line. An individual
credential file contains only its value; for example, a file named `APP_PORTS`:

```text
http=80
https=443
```

These delimiters are library conventions, not formats required by systemd.

Use `Annotated` and `ParseOptions` for field-specific delimiters:

```python
from typing import Annotated

from pydantic import Field

from pydantic_parsed_env import ParseOptions, ParsedEnvSettings


class CustomSettings(ParsedEnvSettings):
    paths: Annotated[list[str], ParseOptions(item_delimiter=";")] = Field(
        default_factory=list[str],
    )
```

For example, `PATHS="/etc/a;/etc/b"` produces `["/etc/a", "/etc/b"]`. Explicit
delimiters apply to every source: `ParseOptions(item_delimiter=",")` also keeps
credential files comma-separated. Omitting a delimiter, or passing `None`, selects its
source default. Use `kv_delimiter=":"` to change dictionary pairs to `key:value`.

There is no item-level quoting or escaping. Choose an item delimiter that cannot occur
inside a value, such as `;` between SQL PRAGMA statements supplied in an environment
variable.

## Loading sources

Dotenv files and secret directories are opt-in. Pass `_env_file` or `_secrets_dir` to
your settings constructor, or set `env_file` or `secrets_dir` in `model_config`.
`_env_file=None` disables dotenv loading. Prefix, case, encoding, empty-value, and
nested settings options retain their normal Pydantic meaning.

Priority is constructor values, environment, dotenv, secret files, then defaults.
Dictionaries retain Pydantic's normal source-merging behavior, with higher-priority
sources winning on overlapping keys. Secret contents are not exported into the
environment.

The library does not discover `CREDENTIALS_DIRECTORY` automatically. An application can
opt in by passing it as `_secrets_dir` when constructing settings. Custom source
subclasses are preserved; when overriding `settings_customise_sources`, delegate through
`super()` to retain parsed sources. `ParsedSecretsSettingsSource` is also available for
applications assembling their own source pipeline.

## Supported types

These examples use environment delimiters; credential files use newlines by default:

| Field type          | Example input         | Parsed result                |
| ------------------- | --------------------- | ---------------------------- |
| `list[int]`         | `"1,2,3"`             | `[1, 2, 3]`                  |
| `set[str]`          | `"a,a,b"`             | `{"a", "b"}`                 |
| `tuple[float, ...]` | `"1.2,3.4"`           | `(1.2, 3.4)`                 |
| `tuple[str, int]`   | `"host,80"`           | `("host", 80)`               |
| `dict[str, int]`    | `"http=80,https=443"` | `{"http": 80, "https": 443}` |

Items, keys, and values can be:

- `str`, `int`, `float`, or `bool` (`true` / `false`, case-insensitive).
- Enums by string value or case-insensitive member name. `IntEnum` also accepts decimal
  values, including `HTTPStatus`: `429,502` or `too_many_requests,bad_gateway`.
- String literals such as `Literal["active", "inactive"]`.
- Unions of these types, including nullable items. For example, `list[int | None]`
  parses `1,,3` as `[1, None, 3]`. Union alternatives are tried in order, with `str`
  last.

A field itself can be nullable: `allowed: Parsed[set[str] | None] = None`. The root must
be one collection type, optionally combined with `None`; other root unions and scalar
fields are unsupported. Delimiter parsing does not construct nested containers or model
items such as `list[MyModel]`; use ordinary Pydantic JSON fields for those.

## Empty values and input rules

- Unset fields keep their defaults. Required fields without defaults remain required.
- An empty string produces `[]`, `set()`, `()`, or `{}` for lists, sets, variable-length
  tuples, and dictionaries, even when the field is nullable. Fixed tuples require the
  declared number of items. Whitespace-only or delimiter-only input is also empty for
  variable-size collections.
- Empty input does not mean `None`. Leave a field with a `None` default unset, pass
  `None` directly, or configure `env_parse_none_str` for environment and dotenv values.
- Whitespace around items, keys, and values is trimmed.
- Empty string items are retained: `a,,b` becomes `["a", "", "b"]` for `list[str]`.
  Empty items fail for non-nullable numeric types; nullable items become `None`.
- Dictionary entries split at the first key-value delimiter, so values may contain
  additional `=` characters. Empty entries are ignored; entries without a key-value
  delimiter fail. Duplicate keys use the last value: `a=1,a=2` becomes `{"a": 2}`.

Source parsing errors raise `pydantic_settings.SettingsError`. Parser details in
`__cause__` may contain configuration values or secrets; do not log them unsanitized.
Pydantic still validates the parsed result against the field type and constraints.

## JSON and upgrading to 0.2.0

Parsed fields reject values wrapped in `[...]` or `{...}` by default in every source,
including credential files. This includes malformed JSON-looking input. To accept JSON,
explicitly set `ParseOptions(json_compatibility=True)`; it tries JSON first and falls
back to delimiter parsing. Unannotated fields keep normal Pydantic JSON decoding.

When upgrading from 0.1.0:

- Dictionary pairs now default to `=`, so `Parsed[dict[str, int]]` needs no extra
  options.
- Credential-file collections now use delimiter parsing, with newline-separated items by
  default. Rewrite existing JSON collections or enable compatibility explicitly.
- JSON-looking string collections are rejected rather than silently split into literal
  fragments. Use an empty value instead of `[]` for an empty collection.

## Development

For the development environment:

```bash
uv sync
uv run ruff check .
uv run ruff format .
uv run pyright src
uv run pytest -q
```

Or use Nix:

```bash
nix develop
nix fmt
nix flake check
```

CI uses `nix fmt -- --ci` and `nix flake check`. The latter runs the full suite against
two locked dependency groups: `compat-minimum` tests the declared lower bounds;
`compat-latest` tests current supported 2.x versions. Each check verifies the installed
versions before testing the installed package. Renovate keeps the minimum fixed and
updates the latest group.

Runtime compatibility ranges live in `pyproject.toml`; exact development and check
versions are pinned in `uv.lock` and `flake.lock`.

## Versioning and releases

- Package versions are derived from Git tags via `hatch-vcs`.
- Release tags must use the `vX.Y.Z` form, for example `v0.3.1`.
- The published package version strips the `v` prefix, so `v0.3.1` becomes `0.3.1` on
  PyPI.
- This project follows semantic versioning for its public API. While the package is
  still `0.x`, breaking changes may still land in minor releases.

## License

Apache-2.0.
