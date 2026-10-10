"""
Database layer: SQLite storage for personas, scenarios, responses, and evidence.
"""
import json
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
    brand_loyalty     TEXT,
    usage_level       TEXT
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
CREATE TABLE IF NOT EXISTS evidence (
    scenario_id        INTEGER PRIMARY KEY REFERENCES scenarios(scenario_id),
    is_real_event      INTEGER,
    event_summary      TEXT,
    reported_sentiment TEXT,
    stated_vs_actual   TEXT,
    key_findings       TEXT,
    evidence_strength  TEXT,
    sources            TEXT,
    research_notes     TEXT,
    created_at         TEXT
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
            :price_sensitivity, :brand_loyalty, :usage_level)""",
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


def save_evidence(conn, scenario_id, ev):
    """Save the real-world evidence for a scenario, replacing any older check."""
    conn.execute(
        """INSERT OR REPLACE INTO evidence
           (scenario_id, is_real_event, event_summary, reported_sentiment,
            stated_vs_actual, key_findings, evidence_strength, sources,
            research_notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (scenario_id, int(ev["is_real_event"]), ev["event_summary"],
         ev["reported_sentiment"], ev["stated_vs_actual"],
         json.dumps(ev["key_findings"]), ev["evidence_strength"],
         json.dumps(ev["sources"]), ev.get("research_notes", ""),
         datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()


def get_evidence(conn, scenario_id):
    """Return the saved evidence for a scenario, or None if it hasn't been checked."""
    row = conn.execute(
        """SELECT is_real_event, event_summary, reported_sentiment, stated_vs_actual,
                  key_findings, evidence_strength, sources
           FROM evidence WHERE scenario_id = ?""",
        (scenario_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "is_real_event": bool(row[0]),
        "event_summary": row[1],
        "reported_sentiment": row[2],
        "stated_vs_actual": row[3],
        "key_findings": json.loads(row[4]),
        "evidence_strength": row[5],
        "sources": json.loads(row[6]),
    }