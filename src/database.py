"""
Database layer: SQLite storage for personas, scenarios, and responses.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

# Database file lives in data/processed/, which is gitignored
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "simulations.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS personas (
    persona_id        INTEGER PRIMARY KEY,
    age_group         TEXT,
    income            TEXT,
    location          TEXT,
    household         TEXT,
    price_sensitivity TEXT,
    brand_loyalty     TEXT
);
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    description  TEXT NOT NULL,
    model        TEXT,
    created_at   TEXT
);
CREATE TABLE IF NOT EXISTS responses (
    response_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id  INTEGER REFERENCES scenarios(scenario_id),
    persona_id   INTEGER REFERENCES personas(persona_id),
    decision     TEXT,
    intent_score INTEGER,
    sentiment    TEXT,
    reason       TEXT
);
"""


def get_connection(db_path=DB_PATH):
    """Open the database and create the tables if they don't exist yet."""
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def save_personas(conn, personas):
    """Save personas, skipping any that are already stored."""
    conn.executemany(
        """INSERT OR IGNORE INTO personas VALUES
           (:id, :age_group, :income, :location, :household,
            :price_sensitivity, :brand_loyalty)""",
        personas,
    )
    conn.commit()


def create_scenario(conn, description, model):
    """Record a new scenario run and return its ID."""
    cur = conn.execute(
        "INSERT INTO scenarios (description, model, created_at) VALUES (?, ?, ?)",
        (description, model, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    return cur.lastrowid


def save_response(conn, scenario_id, r):
    """Save one persona's reaction."""
    conn.execute(
        """INSERT INTO responses
           (scenario_id, persona_id, decision, intent_score, sentiment, reason)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (scenario_id, r["persona_id"], r["decision"], r["intent_score"],
         r["sentiment"], r["reason"]),
    )
    conn.commit()