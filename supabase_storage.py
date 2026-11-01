
"""Supabase Cloud Storage for Jaguar AI."""

import os
import uuid
import mimetypes
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client
from werkzeug.utils import secure_filename

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
BUCKET_NAME = os.getenv("SUPABASE_BUCKET", "jaguar-uploads")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError("Supabase credentials are missing.")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)

DOCUMENT_EXTENSIONS = {
    ".pdf", ".txt", ".csv", ".docx",
    ".xlsx", ".json", ".png", ".jpg", ".jpeg"
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp"
}

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
MAX_PROFILE_SIZE = 5 * 1024 * 1024


class StorageError(Exception):
    pass


def upload_file(user_id, file, folder="uploads"):
    if folder not in {"uploads", "profiles"}:
        raise StorageError("Invalid storage folder.")

    filename = secure_filename(file.filename or "")
    extension = Path(filename).suffix.lower()

    if not filename:
        raise StorageError("Invalid filename.")

    allowed = (
        IMAGE_EXTENSIONS
        if folder == "profiles"
        else DOCUMENT_EXTENSIONS
    )

    if extension not in allowed:
        raise StorageError("Unsupported file type.")

    file.stream.seek(0, 2)
    size = file.stream.tell()
    file.stream.seek(0)

    max_size = (
        MAX_PROFILE_SIZE
        if folder == "profiles"
        else MAX_DOCUMENT_SIZE
    )

    if size == 0 or size > max_size:
        raise StorageError("Invalid file size.")

    content = file.stream.read()

    cloud_path = (
        f"users/{user_id}/{folder}/"
        f"{uuid.uuid4().hex}{extension}"
    )

    content_type = (
        mimetypes.guess_type(filename)[0]
        or "application/octet-stream"
    )

    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=cloud_path,
            file=content,
            file_options={
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "false"
            }
        )

        return cloud_path

    except Exception as exc:
        raise StorageError("Supabase upload failed.") from exc


def get_file_url(cloud_path, expires_in=3600):
    """Generate a temporary URL for a private file."""

    try:
        result = (
            supabase.storage
            .from_(BUCKET_NAME)
            .create_signed_url(cloud_path, expires_in)
        )

        return (
            result.get("signedURL")
            or result.get("signedUrl")
        )

    except Exception as exc:
        raise StorageError("Could not generate download URL.") from exc


def delete_file(cloud_path):
    """Delete an object from Supabase."""

    try:
        supabase.storage.from_(BUCKET_NAME).remove(
            [cloud_path]
        )
    except Exception as exc:
        raise StorageError("Cloud deletion failed.") from exc


def download_file(cloud_path):
    """Download a private file."""

    try:
        return supabase.storage.from_(BUCKET_NAME).download(
            cloud_path
        )
    except Exception as exc:
        raise StorageError("Cloud download failed.") from exc
