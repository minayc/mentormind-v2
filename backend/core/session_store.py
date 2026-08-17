"""
session_store.py — SQLite persistence for MentorMind chat sessions.

Saves to the same mentormind.db used by spaced_repetition.py so there
is only one database file to manage.
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = "mentormind.db"


def init_session_db():
    """Create session tables if they don't exist yet."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id   TEXT PRIMARY KEY,
                backend      TEXT    DEFAULT 'groq',
                sources      TEXT    DEFAULT '[]',
                created_at   TEXT,
                last_active  TEXT
            );
 
            CREATE TABLE IF NOT EXISTS chat_messages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT,
                role         TEXT,
                content      TEXT,
                score        REAL,
                feedback     TEXT,
                created_at   TEXT
            );
 
            CREATE TABLE IF NOT EXISTS chat_scores (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id   TEXT,
                score        INTEGER
            );
 
            CREATE TABLE IF NOT EXISTS chat_concepts (
                session_id   TEXT,
                concept      TEXT,
                understood   INTEGER,
                score        REAL,
                attempts     INTEGER,
                PRIMARY KEY (session_id, concept)
            );
        """)


def create_session(session_id: str, backend: str, sources: list):
    """Register a new session in the database."""
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO chat_sessions
               (session_id, backend, sources, created_at, last_active)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, backend, json.dumps(sources), now, now),
        )


def save_turn(
    session_id: str,
    user_msg: str,
    assistant_msg: str,
    score=None,
    feedback=None,
):
    """Persist one full conversation turn (user + assistant) and optional score."""
    now = datetime.now().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT INTO chat_messages
               (session_id, role, content, score, feedback, created_at)
               VALUES (?, 'user', ?, NULL, NULL, ?)""",
            (session_id, user_msg, now),
        )
        conn.execute(
            """INSERT INTO chat_messages
               (session_id, role, content, score, feedback, created_at)
               VALUES (?, 'assistant', ?, ?, ?, ?)""",
            (session_id, assistant_msg, score, feedback, now),
        )
        if score is not None:
            conn.execute(
                "INSERT INTO chat_scores (session_id, score) VALUES (?, ?)",
                (session_id, score),
            )
        conn.execute(
            "UPDATE chat_sessions SET last_active=? WHERE session_id=?",
            (now, session_id),
        )


def save_concept(
    session_id: str,
    concept: str,
    understood: bool,
    score: float,
    attempts: int,
):
    """Upsert a concept's current status for this session."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO chat_concepts
               (session_id, concept, understood, score, attempts)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, concept, 1 if understood else 0, score, attempts),
        )


def list_sessions(limit: int = 20) -> list[dict]:
    """Return the most recent sessions ordered by last activity, newest first."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT s.session_id, s.sources, s.created_at, s.last_active,
                   COUNT(m.id) AS turns
            FROM chat_sessions s
            LEFT JOIN chat_messages m
                   ON m.session_id = s.session_id AND m.role = 'user'
            GROUP BY s.session_id
            ORDER BY s.last_active DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "session_id": r[0],
            "sources":    json.loads(r[1] or "[]"),
            "created_at": r[2],
            "last_active": r[3],
            "turns":      r[4],
        }
        for r in rows
    ]


def delete_session(session_id: str) -> None:
    """Permanently remove a session and all its messages, scores, and concepts."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM chat_messages  WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_scores    WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_concepts  WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_sessions  WHERE session_id=?", (session_id,))


def delete_session(session_id: str) -> None:
    """Permanently remove a session and all its messages, scores, and concepts."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM chat_sessions  WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_messages  WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_scores    WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_concepts  WHERE session_id=?", (session_id,))


def load_session(session_id: str):
    """
    Load a persisted session from the database.
    Returns a dict with keys: backend, sources, messages, scores, concepts.
    Returns None if session_id is not found.
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT backend, sources FROM chat_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if not row:
            return None

        backend, sources_json = row
        sources = json.loads(sources_json)

        raw_messages = conn.execute(
            """SELECT role, content, score, feedback
               FROM chat_messages WHERE session_id=? ORDER BY id""",
            (session_id,),
        ).fetchall()

        scores = [
            r[0]
            for r in conn.execute(
                "SELECT score FROM chat_scores WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        ]

        concepts = [
            {
                "concept":   r[0],
                "understood": bool(r[1]),
                "score":     r[2],
                "attempts":  r[3],
            }
            for r in conn.execute(
                """SELECT concept, understood, score, attempts
                   FROM chat_concepts WHERE session_id=?""",
                (session_id,),
            ).fetchall()
        ]

    return {
        "backend":  backend,
        "sources":  sources,
        "messages": [
            {
                "role":     r[0],
                "content":  r[1],
                "score":    r[2],
                "feedback": r[3],
            }
            for r in raw_messages
        ],
        "scores":   scores,
        "concepts": concepts,
    }