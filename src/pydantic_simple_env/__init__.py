"""Simplified Environment Variable Parsing for Pydantic Settings.

This package provides utilities to parse structured data (lists, sets, tuples,
dictionaries) from environment variables using simple, delimited strings
instead of complex JSON.
"""

from importlib.metadata import PackageNotFoundError, version

from ._api import (
    BaseSimpleEnvSettings,
    SimpleEnvConfig,
    SimpleEnvParser,
    SimpleEnvSettingsSource,
    SimpleParsed,
)

try:
    __version__ = version("pydantic-simple-env")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "BaseSimpleEnvSettings",
    "SimpleEnvConfig",
    "SimpleEnvParser",
    "SimpleEnvSettingsSource",
    "SimpleParsed",
    "__version__",
]
