from fastapi import UploadFile, Response
from minio import S3Error
from components.settings import settings
from minio.commonconfig import CopySource
from components.minio import minio_client

class UploadService:
    MINIO_BUCKET_NAME = settings.minio_bucket
    ALLOWED_EXTENSIONS = {
        "jpeg",
        "jpg",
        "png",
        "webp",
        "pdf",
        "doc",
        "docx",
        "xlsx",
        "csv",
        "svg",
    }
    ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "image/svg+xml",
    }
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

    """
    ====================================================
    # Get files from MinIO with optional download
    ====================================================
    """

    async def serve_minio_file(self, object_path: str, download: bool = False):
        try:
            object_key = (
                object_path[len(self.MINIO_BUCKET_NAME) + 1 :]
                if object_path.startswith(self.MINIO_BUCKET_NAME + "/")
                else object_path
            )

            # Fetch the file from MinIO
            response = minio_client.get_object(
                bucket_name=self.MINIO_BUCKET_NAME, object_name=object_key
            )

            # Reading the file data
            data = response.read()

            # Get content type from MinIO (if available)
            content_type = response.headers.get(
                "Content-Type", "application/octet-stream"
            )

            # Set Content-Disposition header based on the `download` parameter
            disposition = "attachment" if download else "inline"

            # Return the file as a response
            return True, Response(
                content=data,
                media_type=content_type,
                headers={
                    "Content-Disposition": f"{disposition}; filename={object_key.split('/')[-1]}"
                },
            )
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False, "File not found."
            return False, f"Error retrieving file: {str(e)}"

    """
    ====================================================
    # Create a folder in MinIO
    ====================================================
    """

    async def create_folder(self, folder_path: str):
        try:
            dummy_file_key = f"{folder_path}/.placeholder"
            from io import BytesIO

            minio_client.put_object(
                bucket_name=self.MINIO_BUCKET_NAME,
                object_name=dummy_file_key,
                data=BytesIO(b""),  # Placeholder content as a readable object
                length=0,  # Length for empty file
                content_type="application/octet-stream",
            )
            return True, "Folder created successfully"
        except S3Error as e:
            return False, f"Failed to create folder: {str(e)}"

    """
    ====================================================
    # Upload files to MinIO
    ====================================================
    """

    async def save_files_to_minio(self, files: list[UploadFile], folder_path: str):
        try:
            file_urls = []
            for file in files:
                file_extension = file.filename.split(".")[-1].lower()
                if file_extension not in self.ALLOWED_EXTENSIONS:
                    return False, f"Invalid file type for {file.filename}."
                if file.content_type not in self.ALLOWED_MIME_TYPES:
                    return False, f"Invalid MIME type for {file.filename}."
                file.file.seek(0, 2)
                file_size = file.file.tell()
                file.file.seek(0)
                if file_size > self.MAX_FILE_SIZE:
                    return False, f"File size exceeds 5MB limit for {file.filename}."

                file_key = f"{folder_path}/{file.filename}"
                minio_client.put_object(
                    bucket_name=self.MINIO_BUCKET_NAME,
                    object_name=file_key,
                    data=file.file,
                    length=file_size,
                    content_type=file.content_type,
                )
                if file_key.startswith("/"):
                    file_urls.append(f"{file_key}")
                else:
                    file_urls.append(f"/{file_key}")
            return True, file_urls
        except S3Error as e:
            return False, f"Failed to upload files: {str(e)}"

    """
    ====================================================
    # List files in a folder in MinIO
    ====================================================
    """

    async def list_files(self, folder_path: str):
        try:
            items = []
            objects = minio_client.list_objects(
                bucket_name=self.MINIO_BUCKET_NAME,
                prefix=f"{folder_path}",
                recursive=True,
            )
            prefix_length = len(folder_path.rstrip("/")) + 1
            for obj in objects:
                if obj.object_name.endswith("/.placeholder"):
                    continue  # Skip the .placeholder file

                # Ensure only immediate children of the folder are listed
                relative_path = obj.object_name[prefix_length:]
                if "/" in relative_path:
                    continue  # Skip nested files or folders

                item_type = "folder" if obj.object_name.endswith("/") else "file"
                items.append(
                    {
                        "id": obj.etag,
                        "name": obj.object_name.split("/")[-1],
                        "label": obj.object_name.split("/")[-1].split(".")[0],
                        "path": f"/{obj.object_name}",
                        "size": obj.size,
                        "updated_at": obj.last_modified.isoformat(),
                        "type": item_type,
                    }
                )
            return True, items
        except S3Error as e:
            return False, f"Failed to list files: {str(e)}"

    """
    ====================================================
    # Delete file in MinIO
    ====================================================
    """

    async def delete_file(self, file_path: str):
        try:
            object_key = (
                file_path[len(self.MINIO_BUCKET_NAME) + 1 :]
                if file_path.startswith(self.MINIO_BUCKET_NAME + "/")
                else file_path
            )
            try:
                minio_client.stat_object(
                    bucket_name=self.MINIO_BUCKET_NAME, object_name=object_key
                )
                print("happens")
            except S3Error as e:
                if e.code == "NoSuchKey":
                    return True, "File Already deleted or not found."
                raise

            minio_client.remove_object(
                bucket_name=self.MINIO_BUCKET_NAME, object_name=object_key
            )
            return True, "File deleted successfully"
        except S3Error as e:
            return False, f"Failed to delete file: {str(e)}"

    """
    ====================================================
    # Delete folder in MinIO
    ====================================================
    """

    async def delete_folder(self, folder_path: str):
        try:
            objects = minio_client.list_objects(
                bucket_name=self.MINIO_BUCKET_NAME,
                prefix=f"{folder_path}/",
                recursive=True,
            )
            found = False
            for obj in objects:
                found = True
                minio_client.remove_object(
                    bucket_name=self.MINIO_BUCKET_NAME, object_name=obj.object_name
                )

            if not found:
                return False, "Folder not found."

            return True, "Folder deleted successfully"
        except S3Error as e:
            return False, f"Failed to delete folder: {str(e)}"

    """
    ====================================================
    # Rename a folder in MinIO
    ====================================================
    """

    async def rename_folder(self, old_folder_path: str, new_folder_path: str):
        try:
            # Step 1: Check if the old folder exists
            objects = minio_client.list_objects(
                bucket_name=self.MINIO_BUCKET_NAME,
                prefix=f"{old_folder_path}/",
                recursive=True,
            )
            found = False
            for _ in objects:
                found = True
                break

            if not found:
                return False, "Old folder does not exist."

            # Step 2: Copy each object to the new folder
            objects = minio_client.list_objects(
                bucket_name=self.MINIO_BUCKET_NAME,
                prefix=f"{old_folder_path}/",
                recursive=True,
            )
            for obj in objects:
                old_object_key = obj.object_name
                new_object_key = old_object_key.replace(
                    old_folder_path, new_folder_path, 1
                )
                copy_source = CopySource(
                    bucket_name=self.MINIO_BUCKET_NAME, object_name=old_object_key
                )
                minio_client.copy_object(
                    bucket_name=self.MINIO_BUCKET_NAME,
                    object_name=new_object_key,
                    source=copy_source,
                )

                minio_client.remove_object(
                    bucket_name=self.MINIO_BUCKET_NAME, object_name=old_object_key
                )

            return True, "Folder renamed successfully"
        except S3Error as e:
            return False, f"Failed to rename folder: {str(e)}"

    """
    ====================================================
    # Rename a file in MinIO
    ====================================================
    """

    async def rename_file(self, old_file_path: str, new_file_path: str):
        try:
            try:
                minio_client.stat_object(
                    bucket_name=self.MINIO_BUCKET_NAME, object_name=old_file_path
                )
            except S3Error as e:
                if e.code == "NoSuchKey":
                    return False, "File not found."
                raise

            copy_source = CopySource(
                bucket_name=self.MINIO_BUCKET_NAME, object_name=old_file_path
            )
            minio_client.copy_object(
                bucket_name=self.MINIO_BUCKET_NAME,
                object_name=new_file_path,
                source=copy_source,
            )

            minio_client.remove_object(
                bucket_name=self.MINIO_BUCKET_NAME, object_name=old_file_path
            )
            return True, "File renamed successfully"
        except S3Error as e:
            return False, f"Failed to rename file: {str(e)}"