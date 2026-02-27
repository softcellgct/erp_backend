"""Backward-compat shim — use `core.security` in new code."""
from core.security import create_access_token, decode_token  # noqa: F401
