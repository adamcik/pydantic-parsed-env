"""Simplified Environment Variable Parsing for Pydantic Settings.

This package provides utilities to parse structured data (lists, sets, tuples,
dictionaries) from environment variables using simple, delimited strings
instead of complex JSON.
"""

from ._api import (
    SimpleEnvConfig,
    SimpleEnvParser,
    BaseSimpleEnvSettings,
    SimpleEnvSettingsSource,
)

__all__ = [
    "SimpleEnvConfig",
    "SimpleEnvParser",
    "BaseSimpleEnvSettings",
    "SimpleEnvSettingsSource",
]
