"""Answer history persistence repository."""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Optional
from uuid import UUID, uuid4

from legal_platform.modules.vault.models import Permission


SCHEMA = """
CREATE TABLE IF NOT EXISTS answer_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    feedback TEXT,
    note TEXT NOT NULL DEFAULT ''
);
"""


class HistoryRepository:
    """Encapsulates durable storage and retrieval of Q&A answer history."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Create the answer_history table if it does not exist."""
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def save_answer(self, user_id: str, question: str, answer_data: dict[str, Any]) -> str:
        """Persist a generated answer for a user and trim old history over 1000 items."""
        hid = str(uuid4())
        answer_data["history_id"] = hid
        now = time.time()
        payload = json.dumps(answer_data, ensure_ascii=False)
        self.conn.execute(
            "INSERT INTO answer_history (id, user_id, question, answer_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (hid, user_id, question, payload, now),
        )
        self.conn.execute(
            "DELETE FROM answer_history WHERE user_id=? AND id NOT IN (SELECT id FROM answer_history WHERE user_id=? ORDER BY created_at DESC LIMIT 1000)",
            (user_id, user_id),
        )
        self.conn.commit()
        return hid

    def list_history(self, user_id: str, limit: int = 100) -> list[sqlite3.Row]:
        """Fetch latest answer history rows for a given user."""
        cursor = self.conn.execute(
            "SELECT * FROM answer_history WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, max(1, limit)),
        )
        return cursor.fetchall()

    def get_history_item(self, history_id: str, user_id: str) -> Optional[sqlite3.Row]:
        """Fetch a specific answer history item by ID and user ID."""
        cursor = self.conn.execute(
            "SELECT * FROM answer_history WHERE id=? AND user_id=?",
            (history_id, user_id),
        )
        return cursor.fetchone()

    def update_feedback(self, history_id: str, user_id: str, feedback: Optional[str], note: Optional[str] = "") -> None:
        """Update user feedback and optional note on a saved answer."""
        self.conn.execute(
            "UPDATE answer_history SET feedback=?, note=? WHERE id=? AND user_id=?",
            (feedback, str(note or "")[:2000], history_id, user_id),
        )
        self.conn.commit()

    def delete_history_item(self, history_id: str, user_id: str) -> None:
        """Delete a saved answer history entry."""
        self.conn.execute(
            "DELETE FROM answer_history WHERE id=? AND user_id=?",
            (history_id, user_id),
        )
        self.conn.commit()

    @staticmethod
    def is_history_allowed(row: sqlite3.Row, user_id: str, registry: Any, vault: Any) -> bool:
        """Verify that the user still has READ permission to all cited collections."""
        try:
            data = json.loads(row["answer_json"])
        except (json.JSONDecodeError, TypeError, KeyError):
            return False
        for citation in data.get("citations", []):
            try:
                doc_id = UUID(citation["document_id"])
            except (KeyError, ValueError, TypeError):
                continue
            document = registry.get_document(doc_id)
            if not document or not vault.check_permission(document.vault_id, user_id, Permission.READ):
                return False
        return True
