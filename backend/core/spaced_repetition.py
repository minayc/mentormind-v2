"""
SM-2 spaced repetition engine with SQLite persistence.

Each concept the student discusses gets a "card" that tracks:
  - easiness  : E-factor (starts 2.5, drops when student struggles)
  - interval  : days until next review
  - repetitions: consecutive successful reviews
  - due_date  : ISO date the card is next due

Scoring map: our 1-10 scale → SM-2's 0-5 quality scale.
"""

import sqlite3
from datetime import date, timedelta
from dataclasses import dataclass
from pathlib import Path

DB_PATH = Path("mentormind.db")


#data class

@dataclass
class ConceptCard:
    concept: str
    easiness: float = 2.5
    interval: int = 1
    repetitions: int = 0
    due_date: str = ""
    last_score: int = 0
    attempts: int = 0


#DB init

def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS concept_reviews (
            concept      TEXT    PRIMARY KEY,
            easiness     REAL    DEFAULT 2.5,
            interval_days INTEGER DEFAULT 1,
            repetitions  INTEGER DEFAULT 0,
            due_date     TEXT,
            last_score   INTEGER DEFAULT 0,
            attempts     INTEGER DEFAULT 0,
            updated_at   TEXT
        )
    """)
    conn.commit()
    conn.close()


#SM-2 core

def _score_to_quality(score: int) -> int:
    """Map MentorMind 1-10 score → SM-2 quality 0-5."""
    return max(0, min(5, round((score / 10) * 5)))


def sm2_update(card: ConceptCard, score: int) -> ConceptCard:
    q = _score_to_quality(score)
    card.attempts += 1

    if q < 3:
        # Failed recall — reset streak, review again tomorrow
        card.repetitions = 0
        card.interval = 1
    else:
        # Successful recall — advance interval
        if card.repetitions == 0:
            card.interval = 1
        elif card.repetitions == 1:
            card.interval = 6
        else:
            card.interval = round(card.interval * card.easiness)
        card.repetitions += 1
        # Update easiness factor (never drops below 1.3)
        card.easiness = max(
            1.3,
            card.easiness + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
        )

    card.due_date = (date.today() + timedelta(days=card.interval)).isoformat()
    card.last_score = score
    return card


#DB helpers

def _row_to_card(row: tuple) -> ConceptCard:
    return ConceptCard(
        concept=row[0], easiness=row[1], interval=row[2],
        repetitions=row[3], due_date=row[4] or "",
        last_score=row[5], attempts=row[6]
    )


def _card_to_dict(card: ConceptCard) -> dict:
    return {
        "concept":     card.concept,
        "easiness":    round(card.easiness, 2),
        "interval":    card.interval,
        "repetitions": card.repetitions,
        "due_date":    card.due_date,
        "last_score":  card.last_score,
        "attempts":    card.attempts,
    }


def upsert_concept(concept: str, score: int) -> ConceptCard:
    """Create or update a concept card with a new score using SM-2."""
    key = concept.lower().strip()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT concept, easiness, interval_days, repetitions, due_date, last_score, attempts "
        "FROM concept_reviews WHERE concept = ?", (key,)
    ).fetchone()

    card = _row_to_card(row) if row else ConceptCard(concept=key)
    card = sm2_update(card, score)

    conn.execute("""
        INSERT INTO concept_reviews
            (concept, easiness, interval_days, repetitions, due_date, last_score, attempts, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
        ON CONFLICT(concept) DO UPDATE SET
            easiness      = excluded.easiness,
            interval_days = excluded.interval_days,
            repetitions   = excluded.repetitions,
            due_date      = excluded.due_date,
            last_score    = excluded.last_score,
            attempts      = excluded.attempts,
            updated_at    = excluded.updated_at
    """, (card.concept, card.easiness, card.interval, card.repetitions,
          card.due_date, card.last_score, card.attempts))
    conn.commit()
    conn.close()
    return card


def get_due_concepts() -> list[dict]:
    """Return all concepts due for review today or overdue."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT concept, easiness, interval_days, repetitions, due_date, last_score, attempts
        FROM concept_reviews
        WHERE due_date <= date('now') OR due_date IS NULL
        ORDER BY due_date ASC
    """).fetchall()
    conn.close()
    return [_card_to_dict(_row_to_card(r)) for r in rows]


def delete_concept(concept: str) -> None:
    """Permanently remove a concept card from the database."""
    key = concept.lower().strip()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM concept_reviews WHERE concept = ?", (key,))
    conn.commit()
    conn.close()


def get_all_concepts() -> list[dict]:
    """Return every tracked concept sorted by due date."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT concept, easiness, interval_days, repetitions, due_date, last_score, attempts
        FROM concept_reviews
        ORDER BY due_date ASC
    """).fetchall()
    conn.close()
    return [_card_to_dict(_row_to_card(r)) for r in rows]