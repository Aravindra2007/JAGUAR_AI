import sqlite3
from pathlib import Path


class ConversationMemory:
    def __init__(self):
        Path("memory").mkdir(exist_ok=True)

        self.conn = sqlite3.connect(
            "memory/conversations.db",
            check_same_thread=False
        )

        self.cursor = self.conn.cursor()

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT,
                message TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def save(self, role, message):
        self.cursor.execute(
            """
            INSERT INTO conversations(role, message)
            VALUES (?, ?)
            """,
            (role, message)
        )

        self.conn.commit()

    def last_messages(self, limit=10):
        self.cursor.execute(
            """
            SELECT role, message
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        )

        rows = self.cursor.fetchall()

        rows.reverse()

        return [
            {
                "role": role,
                "content": message
            }
            for role, message in rows
        ]