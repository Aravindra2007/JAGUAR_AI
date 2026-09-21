"""Firebase persistence for Jaguar AI."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class DBError(Exception):
    """Raised when a Firebase persistence operation fails."""


_firestore_client = None


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
            raise DBError("FIREBASE_CREDENTIALS_JSON is not valid service-account JSON.") from exc
    if credentials_path:
        if not os.path.isfile(credentials_path):
            raise DBError(f"Firebase credentials file was not found: {credentials_path}")
        return credentials.Certificate(credentials_path)
    raise DBError(
        "Firebase credentials are missing. Copy .env.example to .env and set "
        "FIREBASE_CREDENTIALS_PATH to your service-account JSON file."
    )


def _client():
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
        firebase_admin.initialize_app(_credential(), options)
    _firestore_client = firestore.client()
    return _firestore_client


def init_firebase() -> None:
    """Initialize Firebase and verify that Firestore is available."""
    next(iter(_client().collection("users").limit(1).stream()), None)


def init_db() -> None:
    """Compatibility entry point retained for the existing app startup path."""
    init_firebase()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _user_ref(user_id: str):
    return _client().collection("users").document(str(user_id))


def _user_from_snapshot(snapshot) -> Optional[Dict[str, Any]]:
    if not snapshot.exists:
        return None
    row = snapshot.to_dict() or {}
    row["id"] = snapshot.id
    return row


def _find_user(field: str, value: str) -> Optional[Dict[str, Any]]:
    snapshots = _client().collection("users").where(
        filter=firestore.FieldFilter(field, "==", value)
    ).limit(1).stream()
    snapshot = next(iter(snapshots), None)
    return _user_from_snapshot(snapshot) if snapshot else None


# Users / auth

def create_user(username: str, email: str, password: str,
                full_name: str = "", role: str = "student") -> Dict[str, Any]:
    username = (username or "").strip()
    email = (email or "").strip().lower()
    if not username or not email or not password:
        raise DBError("Username, email, and password are all required.")
    if len(password) < 6:
        raise DBError("Password must be at least 6 characters.")
    if _find_user("username", username) or _find_user("email", email):
        raise DBError("That username or email is already registered.")

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
    }
    _user_ref(user_id).set({key: value for key, value in row.items() if key != "id"})
    return row


def verify_login(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
    identifier = (username_or_email or "").strip()
    user = _find_user("username", identifier) or _find_user("email", identifier.lower())
    if not user or not check_password_hash(user.get("password_hash", ""), password or ""):
        return None
    last_login_at = _now()
    _user_ref(user["id"]).update({"last_login_at": last_login_at})
    user["last_login_at"] = last_login_at
    return user


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    return _user_from_snapshot(_user_ref(str(user_id)).get())


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    return _find_user("username", username)


# Chat history

def save_chat_message(user_id: str, user_message: str, assistant_reply: str,
                      role_label: str = "", source: str = "typed") -> None:
    if not user_id:
        return
    _client().collection("chat_history").document(uuid.uuid4().hex).set({
        "user_id": str(user_id),
        "role_label": role_label,
        "user_message": user_message,
        "assistant_reply": assistant_reply,
        "source": source,
        "created_at": _now(),
    })


def get_recent_chat(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    if not user_id:
        return []
    snapshots = (_client().collection("chat_history")
                 .where(filter=firestore.FieldFilter("user_id", "==", str(user_id)))
                 .order_by("created_at", direction=firestore.Query.DESCENDING)
                 .limit(limit).stream())
    rows = [snapshot.to_dict() for snapshot in snapshots]
    return list(reversed(rows))


def clear_chat_history(user_id: str) -> None:
    if not user_id:
        return
    snapshots = _client().collection("chat_history").where(
        filter=firestore.FieldFilter("user_id", "==", str(user_id))
    ).stream()
    batch = _client().batch()
    for snapshot in snapshots:
        batch.delete(snapshot.reference)
    batch.commit()


# Uploaded files

def save_uploaded_file(user_id: str, filename: str, filepath: str,
                       filetype: str = "", extracted_text: str = "") -> str:
    file_id = uuid.uuid4().hex
    _client().collection("uploaded_files").document(file_id).set({
        "user_id": str(user_id),
        "filename": filename,
        "filepath": filepath,
        "filetype": filetype,
        "extracted_text": (extracted_text or "")[:200000],
        "created_at": _now(),
    })
    return file_id


def get_uploaded_files(user_id: str, limit: int = 25) -> List[Dict[str, Any]]:
    snapshots = (_client().collection("uploaded_files")
                 .where(filter=firestore.FieldFilter("user_id", "==", str(user_id)))
                 .order_by("created_at", direction=firestore.Query.DESCENDING)
                 .limit(limit).stream())
    return [{"id": snapshot.id, **snapshot.to_dict()} for snapshot in snapshots]
