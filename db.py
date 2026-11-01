


"""Firebase Firestore + Supabase Storage persistence for Jaguar AI."""

from __future__ import annotations

import json
import mimetypes
import os
import uuid

from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, firestore

from flask import current_app
from supabase import create_client
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ==========================================================
# ERRORS
# ==========================================================

class DBError(Exception):
    """Raised when a Firebase persistence operation fails."""


class StorageError(Exception):
    """Raised when a Supabase Storage operation fails."""


# ==========================================================
# CLIENTS
# ==========================================================

_firestore_client = None
_supabase_client = None


def _credential():
    credentials_json = (
        os.getenv("FIREBASE_CREDENTIALS_JSON")
        or os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    )

    credentials_path = (
        os.getenv("FIREBASE_CREDENTIALS_PATH")
        or os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE")
    )

    if credentials_json:
        try:
            return credentials.Certificate(json.loads(credentials_json))
        except (json.JSONDecodeError, ValueError) as exc:
            raise DBError(
                "Firebase credentials JSON is invalid."
            ) from exc

    if credentials_path:
        if not os.path.isfile(credentials_path):
            raise DBError(
                "Firebase credentials file was not found."
            )

        return credentials.Certificate(credentials_path)

    raise DBError("Firebase credentials are missing.")


def _client():
    """Initialize and return Firestore client."""

    global _firestore_client

    if _firestore_client is not None:
        return _firestore_client

    try:
        firebase_admin.get_app()

    except ValueError:
        options = {}

        project_id = os.getenv("FIREBASE_PROJECT_ID")

        if project_id:
            options["projectId"] = project_id

        firebase_admin.initialize_app(
            _credential(),
            options
        )

    _firestore_client = firestore.client()

    return _firestore_client


def _storage():
    """Initialize and return Supabase client."""

    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SECRET_KEY")

    if not supabase_url or not supabase_key:
        raise StorageError(
            "Supabase URL or secret key is missing."
        )

    try:
        _supabase_client = create_client(
            supabase_url,
            supabase_key
        )

        return _supabase_client

    except Exception as exc:
        raise StorageError(
            "Could not initialize Supabase."
        ) from exc


def _bucket():
    return os.getenv(
        "SUPABASE_BUCKET",
        "jaguar-uploads"
    )


def init_firebase() -> None:
    """Initialize Firebase and verify Firestore."""

    next(
        iter(
            _client().collection("users").limit(1).stream()
        ),
        None
    )


def init_db() -> None:
    """Compatibility entry point."""

    init_firebase()


def init_storage() -> None:
    """Verify Supabase configuration."""

    _storage()


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_ref(user_id: str):
    return (
        _client()
        .collection("users")
        .document(str(user_id))
    )


def _user_from_snapshot(snapshot) -> Optional[Dict[str, Any]]:

    if not snapshot.exists:
        return None

    row = snapshot.to_dict() or {}
    row["id"] = snapshot.id

    return row


def _find_user(
    field: str,
    value: str
) -> Optional[Dict[str, Any]]:

    snapshots = (
        _client()
        .collection("users")
        .where(
            filter=firestore.FieldFilter(
                field, "==", value
            )
        )
        .limit(1)
        .stream()
    )

    snapshot = next(iter(snapshots), None)

    return (
        _user_from_snapshot(snapshot)
        if snapshot else None
    )


# ==========================================================
# USERS / AUTHENTICATION
# ==========================================================

def create_user(
    username: str,
    email: str,
    password: str,
    full_name: str = "",
    role: str = "student"
) -> Dict[str, Any]:

    username = (username or "").strip()
    email = (email or "").strip().lower()

    if not username or not email or not password:
        raise DBError(
            "Username, email, and password are required."
        )

    if len(password) < 6:
        raise DBError(
            "Password must be at least 6 characters."
        )

    if (
        _find_user("username", username)
        or _find_user("email", email)
    ):
        raise DBError(
            "That username or email is already registered."
        )

    user_id = uuid.uuid4().hex

    row = {
        "id": user_id,
        "username": username,
        "email": email,
        "full_name": (full_name or "").strip(),
        "password_hash": generate_password_hash(password),
        "role": role,
        "created_at": _now(),
        "last_login_at": None,
        "verified": False,
    }

    _user_ref(user_id).set({
        key: value
        for key, value in row.items()
        if key != "id"
    })

    return row


def verify_login(
    username_or_email: str,
    password: str
) -> Optional[Dict[str, Any]]:

    identifier = (username_or_email or "").strip()

    user = (
        _find_user("username", identifier)
        or _find_user("email", identifier.lower())
    )

    if not user or not check_password_hash(
        user.get("password_hash", ""),
        password or ""
    ):
        return None

    last_login_at = _now()

    _user_ref(user["id"]).update({
        "last_login_at": last_login_at
    })

    user["last_login_at"] = last_login_at

    return user


def get_user_by_id(user_id: str):
    return _user_from_snapshot(
        _user_ref(str(user_id)).get()
    )


def get_user_by_username(username: str):
    return _find_user("username", username)


# ==========================================================
# OTP VERIFICATION
# ==========================================================

def save_otp(
    user_id: str,
    otp_code: str,
    expiry_minutes: int = 10
):
    expiry_time = (
        _now() + timedelta(minutes=expiry_minutes)
    )

    _user_ref(user_id).update({
        "otp_code": otp_code,
        "otp_expires_at": expiry_time
    })


def verify_otp(user_id: str, otp_code: str) -> bool:

    user = get_user_by_id(user_id)

    if not user:
        return False

    stored_otp = user.get("otp_code")
    expiry = user.get("otp_expires_at")

    if (
        stored_otp == otp_code
        and expiry
        and expiry > _now()
    ):
        _user_ref(user_id).update({
            "verified": True,
            "otp_code": None,
            "otp_expires_at": None
        })

        return True

    return False


# ==========================================================
# CHAT HISTORY
# ==========================================================

def save_chat_message(
    user_id: str,
    user_message: str,
    assistant_reply: str,
    role_label: str = "",
    source: str = "typed"
) -> None:

    if not user_id:
        return

    _client().collection("chat_history").document(
        uuid.uuid4().hex
    ).set({
        "user_id": str(user_id),
        "role_label": role_label,
        "user_message": user_message,
        "assistant_reply": assistant_reply,
        "source": source,
        "created_at": _now(),
    })


def get_recent_chat(
    user_id: str,
    limit: int = 50
) -> List[Dict[str, Any]]:

    if not user_id:
        return []

    snapshots = (
        _client()
        .collection("chat_history")
        .where(
            filter=firestore.FieldFilter(
                "user_id", "==", str(user_id)
            )
        )
        .order_by(
            "created_at",
            direction=firestore.Query.DESCENDING
        )
        .limit(limit)
        .stream()
    )

    rows = [
        snapshot.to_dict()
        for snapshot in snapshots
    ]

    return list(reversed(rows))


def clear_chat_history(user_id: str) -> None:

    if not user_id:
        return

    collection = _client().collection("chat_history")

    snapshots = collection.where(
        filter=firestore.FieldFilter(
            "user_id", "==", str(user_id)
        )
    ).stream()

    # Firestore batches support at most 500 writes.
    batch = _client().batch()
    count = 0

    for snapshot in snapshots:
        batch.delete(snapshot.reference)
        count += 1

        if count == 450:
            batch.commit()
            batch = _client().batch()
            count = 0

    if count:
        batch.commit()


# ==========================================================
# SUPABASE FILE STORAGE
# ==========================================================

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".csv",
    ".docx",
    ".xlsx",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp"
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp"
}

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
MAX_PROFILE_SIZE = 5 * 1024 * 1024


def _read_upload(
    upload,
    filename: str,
    max_size: int
) -> Tuple[bytes, str, str]:

    """
    Accepts either:
    - Flask FileStorage object
    - Local filepath (backward compatibility)

    Returns file bytes, safe filename and MIME type.
    """

    if hasattr(upload, "stream"):

        filename = (
            getattr(upload, "filename", None)
            or filename
        )

        stream = upload.stream
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(0)

        content = stream.read()

        content_type = (
            getattr(upload, "mimetype", None)
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )

    elif isinstance(upload, (str, os.PathLike)):

        path = Path(upload)

        if not path.is_file():
            raise StorageError("Local upload file not found.")

        filename = filename or path.name

        size = path.stat().st_size

        with open(path, "rb") as f:
            content = f.read()

        content_type = (
            mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )

    else:
        raise StorageError("Invalid upload object.")

    if size <= 0 or size > max_size:
        raise StorageError("File size is invalid or exceeds the limit.")

    safe_name = secure_filename(filename or "")

    if not safe_name:
        raise StorageError("Invalid filename.")

    return content, safe_name, content_type


def upload_to_supabase(
    user_id: str,
    upload,
    folder: str = "uploads",
    filename: str = ""
) -> str:

    """Upload a private file to Supabase Storage."""

    if folder not in {"uploads", "profiles"}:
        raise StorageError("Invalid storage folder.")

    if not get_user_by_id(user_id):
        raise StorageError("Account not found.")

    content, safe_name, content_type = _read_upload(
        upload,
        filename,
        MAX_PROFILE_SIZE
        if folder == "profiles"
        else MAX_DOCUMENT_SIZE
    )

    extension = Path(safe_name).suffix.lower()

    allowed = (
        IMAGE_EXTENSIONS
        if folder == "profiles"
        else DOCUMENT_EXTENSIONS
    )

    if extension not in allowed:
        raise StorageError("Unsupported file extension.")

    if folder == "profiles" and not content_type.startswith("image/"):
        raise StorageError("Profile picture must be an image.")

    cloud_path = (
        f"users/{user_id}/{folder}/"
        f"{uuid.uuid4().hex}{extension}"
    )

    try:
        _storage().storage.from_(_bucket()).upload(
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
        raise StorageError(
            "Supabase cloud upload failed."
        ) from exc


def get_storage_url(
    cloud_path: str,
    expires_in: int = 3600
) -> str:

    """Generate a temporary URL for a private cloud file."""

    try:
        result = (
            _storage()
            .storage
            .from_(_bucket())
            .create_signed_url(
                cloud_path,
                expires_in
            )
        )

        url = (
            result.get("signedURL")
            or result.get("signedUrl")
        )

        if not url:
            raise StorageError(
                "Could not generate download URL."
            )

        return url

    except StorageError:
        raise

    except Exception as exc:
        raise StorageError(
            "Signed URL generation failed."
        ) from exc


def delete_storage_file(cloud_path: str) -> None:

    """Delete a file from private Supabase Storage."""

    try:
        _storage().storage.from_(_bucket()).remove(
            [cloud_path]
        )

    except Exception as exc:
        raise StorageError(
            "Could not delete cloud file."
        ) from exc


def download_storage_file(cloud_path: str) -> bytes:

    """Download a private cloud file."""

    try:
        return (
            _storage()
            .storage
            .from_(_bucket())
            .download(cloud_path)
        )

    except Exception as exc:
        raise StorageError(
            "Cloud file download failed."
        ) from exc


# ==========================================================
# UPLOADED FILES
# ==========================================================

def save_uploaded_file(
    user_id: str,
    filename: str,
    filepath,
    filetype: str = "",
    extracted_text: str = ""
) -> str:

    """
    Upload actual file to Supabase.
    Save its cloud path and metadata in Firestore.

    filepath accepts a Flask FileStorage object
    or an existing local filepath.
    """

    if not get_user_by_id(user_id):
        raise DBError("Account not found.")

    cloud_path = None

    try:

        cloud_path = upload_to_supabase(
            user_id=user_id,
            upload=filepath,
            folder="uploads",
            filename=filename
        )

        file_id = uuid.uuid4().hex

        _client().collection("uploaded_files").document(
            file_id
        ).set({
            "user_id": str(user_id),
            "filename": secure_filename(filename),
            "filepath": cloud_path,
            "filetype": filetype,
            "storage_provider": "supabase",
            "extracted_text": (extracted_text or "")[:200000],
            "created_at": _now(),
        })

        return file_id

    except Exception as exc:

        if cloud_path:
            try:
                delete_storage_file(cloud_path)
            except StorageError:
                pass

        if isinstance(exc, DBError):
            raise

        raise DBError(
            "Uploaded file could not be saved."
        ) from exc


def get_uploaded_files(
    user_id: str,
    limit: int = 25
) -> List[Dict[str, Any]]:

    snapshots = (
        _client()
        .collection("uploaded_files")
        .where(
            filter=firestore.FieldFilter(
                "user_id", "==", str(user_id)
            )
        )
        .order_by(
            "created_at",
            direction=firestore.Query.DESCENDING
        )
        .limit(limit)
        .stream()
    )

    return [
        {"id": snapshot.id, **snapshot.to_dict()}
        for snapshot in snapshots
    ]


def get_uploaded_file_url(
    user_id: str,
    file_id: str,
    expires_in: int = 3600
) -> str:

    """Generate URL only for a file owned by this user."""

    snapshot = (
        _client()
        .collection("uploaded_files")
        .document(file_id)
        .get()
    )

    if not snapshot.exists:
        raise DBError("File not found.")

    row = snapshot.to_dict() or {}

    if row.get("user_id") != str(user_id):
        raise DBError("Access denied.")

    path = row.get("filepath", "")

    if not path.startswith(f"users/{user_id}/uploads/"):
        raise DBError("Invalid file reference.")

    return get_storage_url(path, expires_in)


# ==========================================================
# USER PROFILE MANAGEMENT
# ==========================================================

def update_user_profile(
    user_id: str,
    full_name: str
) -> None:

    full_name = (full_name or "").strip()

    if not full_name or len(full_name) > 100:
        raise DBError(
            "Full name must contain 1–100 characters."
        )

    if not get_user_by_id(user_id):
        raise DBError("Account not found.")

    _user_ref(user_id).update({
        "full_name": full_name,
        "updated_at": _now()
    })


def update_profile_photo(
    user_id: str,
    photo_path
) -> str:
    """
    Upload profile picture to Supabase.
    Save cloud path in Firestore.
    Remove previous Supabase profile picture.
    """

    user_id = str(user_id)

    user = get_user_by_id(user_id)

    if not user:
        raise DBError("Account not found.")

    old_photo = user.get("profile_photo")
    cloud_path = None

    try:
        # Upload actual local file to Supabase.
        cloud_path = upload_to_supabase(
            user_id=user_id,
            upload=photo_path,
            folder="profiles",
            filename=Path(photo_path).name
        )

        # Save Supabase path in Firestore.
        _user_ref(user_id).update({
            "profile_photo": cloud_path,
            "updated_at": _now()
        })

    except Exception as exc:

        # Remove newly uploaded file if Firestore update fails.
        if cloud_path:
            try:
                delete_storage_file(cloud_path)
            except Exception:
                pass

        if isinstance(exc, DBError):
            raise

        raise DBError(
            "Profile picture update failed."
        ) from exc

    # Delete previous profile photo only after successful update.
    if (
        old_photo
        and old_photo.startswith(
            f"users/{user_id}/profiles/"
        )
    ):
        try:
            delete_storage_file(old_photo)
        except Exception:
            pass

    return cloud_path

def get_profile_photo_url(
    user_id: str,
    expires_in: int = 3600
) -> Optional[str]:

    """Get temporary URL for the user's private profile picture."""

    user = get_user_by_id(user_id)

    if not user:
        raise DBError("Account not found.")

    cloud_path = user.get("profile_photo")

    if not cloud_path:
        return None

    if not cloud_path.startswith(
        f"users/{user_id}/profiles/"
    ):
        raise DBError("Invalid profile picture reference.")

    return get_storage_url(cloud_path, expires_in)


# ==========================================================
# PASSWORD MANAGEMENT
# ==========================================================

def change_user_password(
    user_id: str,
    current_password: str,
    new_password: str
) -> None:

    user = get_user_by_id(user_id)

    if not user:
        raise DBError("Account not found.")

    if not check_password_hash(
        user.get("password_hash", ""),
        current_password or ""
    ):
        raise DBError("Current password is incorrect.")

    if len(new_password) < 8:
        raise DBError(
            "New password must be at least 8 characters."
        )

    if check_password_hash(
        user["password_hash"],
        new_password
    ):
        raise DBError(
            "New password must differ from the current password."
        )

    _user_ref(user_id).update({
        "password_hash": generate_password_hash(new_password),
        "password_changed_at": _now()
    })


## ==========================================================
# getting profile photo url for user
## ========================================================
def get_profile_photo_url(cloud_path: str) -> str:
    """Generate a signed URL for a private Supabase profile photo."""

    if not cloud_path:
        return ""

    try:
        result = (
            _storage()
            .storage
            .from_(_bucket())
            .create_signed_url(
                cloud_path,
                3600
            )
        )

        return (
            result.get("signedURL")
            or result.get("signedUrl")
            or ""
        )

    except Exception:
        current_app.logger.exception(
            "Failed to generate profile photo URL"
        )
        return ""