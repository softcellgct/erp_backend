"""Backward-compat shim — use `core.security` in new code."""
from core.security import hash_password as get_password_hash, verify_password  # noqa: F401