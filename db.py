"""
Jaguar AI — MySQL persistence layer.

Everything the product needs to remember across restarts lives here:
  - users            (login accounts)
  - chat_history      (every typed + spoken exchange, per user)
  - uploaded_files     (docs/images the user handed Jaguar to read)

Connection settings come from environment variables so the same code
runs in dev and production without editing source:

    JAGUAR_DB_HOST      default: localhost
    JAGUAR_DB_PORT      default: 3306
    JAGUAR_DB_USER      default: root
    JAGUAR_DB_PASSWORD  default: "" (empty)
    JAGUAR_DB_NAME      default: jaguar_ai

A `.env` file (see .env.example) is the easiest way to set these; the
app loads it automatically via python-dotenv if present.

Uses PyMySQL so there's no compiled C extension to install (works the
same on Windows/macOS/Linux, unlike mysqlclient).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import pymysql
import pymysql.cursors
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


DB_CONFIG = {
    "host": os.getenv("JAGUAR_DB_HOST", "localhost"),
    "port": int(os.getenv("JAGUAR_DB_PORT", "3306")),
    "user": os.getenv("JAGUAR_DB_USER", "root"),
    "password": os.getenv("JAGUAR_DB_PASSWORD", "Harsha@89191"),
    "database": os.getenv("JAGUAR_DB_NAME", "jaguar_ai"),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}


class DBError(Exception):
    """Raised when a database operation fails."""


def _connect(with_db: bool = True):
    cfg = dict(DB_CONFIG)
    if not with_db:
        cfg.pop("database", None)
    return pymysql.connect(**cfg)


@contextmanager
def get_cursor(commit: bool = False):
    """Context manager yielding a DictCursor. Commits on success if
    `commit=True`, always closes the connection."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------
# Schema
# ---------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(80)  NOT NULL UNIQUE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    full_name       VARCHAR(150) DEFAULT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'student',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at   DATETIME     DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS chat_history (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    role_label      VARCHAR(40)  DEFAULT NULL,
    user_message    MEDIUMTEXT   NOT NULL,
    assistant_reply MEDIUMTEXT   NOT NULL,
    source          VARCHAR(10)  NOT NULL DEFAULT 'typed',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_chat_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_chat_user_time (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS uploaded_files (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    filename        VARCHAR(255) NOT NULL,
    filepath        VARCHAR(500) NOT NULL,
    filetype        VARCHAR(50)  DEFAULT NULL,
    extracted_text  MEDIUMTEXT   DEFAULT NULL,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_upload_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_upload_user_time (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""


def init_db() -> None:
    """Create the database (if missing) and all tables. Safe to call
    on every app startup — every statement is IF NOT EXISTS."""
    db_name = DB_CONFIG["database"]

    conn = _connect(with_db=False)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()

    conn = _connect()
    try:
        with conn.cursor() as cur:
            for statement in SCHEMA.strip().split(";"):
                statement = statement.strip()
                if statement:
                    cur.execute(statement)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------
# Users / auth
# ---------------------------------------------------------------

def create_user(username: str, email: str, password: str,
                 full_name: str = "", role: str = "student") -> Dict[str, Any]:
    username = (username or "").strip()
    email = (email or "").strip().lower()

    if not username or not email or not password:
        raise DBError("Username, email, and password are all required.")
    if len(password) < 6:
        raise DBError("Password must be at least 6 characters.")

    password_hash = generate_password_hash(password)

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM users WHERE username=%s OR email=%s", (username, email))
        if cur.fetchone():
            raise DBError("That username or email is already registered.")

        cur.execute(
            "INSERT INTO users (username, email, full_name, password_hash, role) "
            "VALUES (%s, %s, %s, %s, %s)",
            (username, email, full_name.strip(), password_hash, role),
        )
        user_id = cur.lastrowid

    return get_user_by_id(user_id)


def verify_login(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
    identifier = (username_or_email or "").strip()
    with get_cursor(commit=True) as cur:
        cur.execute(
            "SELECT * FROM users WHERE username=%s OR email=%s",
            (identifier, identifier.lower()),
        )
        user = cur.fetchone()
        if not user:
            return None
        if not check_password_hash(user["password_hash"], password or ""):
            return None

        cur.execute(
            "UPDATE users SET last_login_at=%s WHERE id=%s",
            (datetime.now(), user["id"]),
        )
    return user


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        return cur.fetchone()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        return cur.fetchone()


# ---------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------

def save_chat_message(user_id: int, user_message: str, assistant_reply: str,
                       role_label: str = "", source: str = "typed") -> None:
    if not user_id:
        return
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO chat_history (user_id, role_label, user_message, assistant_reply, source) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, role_label, user_message, assistant_reply, source),
        )


def get_recent_chat(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    if not user_id:
        return []
    with get_cursor() as cur:
        cur.execute(
            "SELECT user_message, assistant_reply, source, created_at FROM chat_history "
            "WHERE user_id=%s ORDER BY id DESC LIMIT %s",
            (user_id, limit),
        )
        rows = cur.fetchall()
    return list(reversed(rows))


def clear_chat_history(user_id: int) -> None:
    if not user_id:
        return
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM chat_history WHERE user_id=%s", (user_id,))


# ---------------------------------------------------------------
# Uploaded files
# ---------------------------------------------------------------

def save_uploaded_file(user_id: int, filename: str, filepath: str,
                        filetype: str = "", extracted_text: str = "") -> int:
    with get_cursor(commit=True) as cur:
        cur.execute(
            "INSERT INTO uploaded_files (user_id, filename, filepath, filetype, extracted_text) "
            "VALUES (%s, %s, %s, %s, %s)",
            (user_id, filename, filepath, filetype, (extracted_text or "")[:200000]),
        )
        return cur.lastrowid


def get_uploaded_files(user_id: int, limit: int = 25) -> List[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, filename, filetype, created_at FROM uploaded_files "
            "WHERE user_id=%s ORDER BY id DESC LIMIT %s",
            (user_id, limit),
        )
        return cur.fetchall()
