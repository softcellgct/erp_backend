from fastapi import HTTPException
from minio import Minio
from minio.error import S3Error
from components.settings import settings
from logs.logging import logger

# MinIO Configuration
MINIO_ENDPOINT = settings.minio_endpoint
MINIO_ACCESS_KEY = settings.minio_access_key
MINIO_SECRET_KEY = settings.minio_secret_key
MINIO_SECURE = settings.minio_secure

# Initialize MinIO Client
minio_client = Minio(
    MINIO_ENDPOINT.replace("http://", "").replace(
        "https://", ""
    ),  # Ensure the endpoint is clean
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)


def ensure_bucket(bucket_name):
    try:
        # Check if the bucket already exists
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            logger.info(f"Bucket '{bucket_name}' created successfully.✅")
        else:
            logger.info(f"Bucket '{bucket_name}' already exists.✅")
    except S3Error as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to access or create bucket: {str(e)}"
        )