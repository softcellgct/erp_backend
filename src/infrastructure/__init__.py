"""
MinIO / S3-compatible object storage client.

Usage:
    from infrastructure.storage import minio_client, ensure_bucket
"""

from fastapi import HTTPException
from minio import Minio
from minio.error import S3Error

from core.config import settings
from core.logging import logger

# Strip protocol prefix — Minio client expects bare host:port
_endpoint = settings.minio_endpoint.replace("http://", "").replace("https://", "")

minio_client = Minio(
    _endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure,
)


def ensure_bucket(bucket_name: str) -> None:
    try:
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            logger.info(f"Bucket '{bucket_name}' created.")
        else:
            logger.info(f"Bucket '{bucket_name}' exists.")
    except S3Error as exc:
        raise HTTPException(500, detail=f"Storage error: {exc}")
