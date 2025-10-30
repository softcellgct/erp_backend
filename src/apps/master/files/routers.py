from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Query
from common.s3.services import UploadService
from sqlalchemy.ext.asyncio import AsyncSession

from components.db.db import get_db_session
from components.settings import settings

router = APIRouter(tags=["Files"])

"""
====================================================
# Files API
====================================================
"""

upload_service = UploadService()

# Bucket name should be set separately
MINIO_BUCKET_NAME = settings.minio_bucket


"""
====================================================
# Serve MinIO file with optional download
====================================================
"""


@router.get(
    "/{object_path:path}",
    description="Serve a file from MinIO",
)
async def get_file(
    request: Request,
    object_path: str,
    db: AsyncSession = Depends(get_db_session),
    download: bool = Query(False, description="Set to true to download the file"),
):
    status, response = await upload_service.serve_minio_file(object_path, download)
    if status:
        return response
    raise HTTPException(status_code=404, detail=response)


"""
====================================================
# Create folder in MinIO
====================================================
"""
# @router.post("/folders", name="Files")
# async def create_folder(folder_path: str = Query(..., description="Folder path to create")):
#     status, message = await upload_service.create_folder(folder_path)
#     if status:
#         return {"detail": message}
#     raise HTTPException(status_code=500, detail=message)


"""
====================================================
# Upload files to MinIO
====================================================
"""


@router.post(
    "/upload_files",
    description="Upload files to MinIO",
)
async def upload_files(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    files: list[UploadFile] = File(...),
    folder_path: str = Query(..., description="Folder path to upload the files"),
):
    status, response = await upload_service.save_files_to_minio(files, folder_path)
    if status:
        return {"detail": "Files uploaded successfully", "file_urls": response}
    raise HTTPException(status_code=400, detail=response)


"""
====================================================
# List files in a folder in MinIO
====================================================
"""
# @router.get("/files/{folder_path:path}", name="Files")
# async def list_files(folder_path: str):
#     status, response = await upload_service.list_files(folder_path)
#     if status:
#         return {"current_folder": folder_path, "items": response}
#     raise HTTPException(status_code=500, detail=response)


"""
====================================================
# Delete file or folder in MinIO
====================================================
"""


@router.delete(
    "/{file_path:path}",
    description="Delete a file from MinIO",
)
async def delete_file(
    request: Request,
    file_path: str,
    db: AsyncSession = Depends(get_db_session),
):
    status, message = await upload_service.delete_file(file_path)
    if status:
        return {"detail": message}
    raise HTTPException(status_code=500, detail=message)