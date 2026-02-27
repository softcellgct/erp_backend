"""Backward-compat shim — use `infrastructure.storage` in new code."""
from infrastructure.storage import minio_client, ensure_bucket  # noqa: F401
