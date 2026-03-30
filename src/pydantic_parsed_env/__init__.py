"""Simplified Environment Variable Parsing for Pydantic Settings.

This package provides utilities to parse structured data (lists, sets, tuples,
dictionaries) from environment variables using simple, delimited strings
instead of complex JSON.
"""

from importlib.metadata import PackageNotFoundError, version

from ._api import (
    ParseConfig,
    Parsed,
    ParsedEnvSettings,
    ParsedEnvSettingsSource,
    ParseOptions,
)

try:
    __version__ = version("pydantic-parsed-env")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "ParseConfig",
    "ParseOptions",
    "Parsed",
    "ParsedEnvSettings",
    "ParsedEnvSettingsSource",
    "__version__",
]
