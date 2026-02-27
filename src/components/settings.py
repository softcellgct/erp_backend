"""Backward-compat shim — use `from core.config import settings` in new code."""
from core.config import Settings, settings  # noqa: F401
