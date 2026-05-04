#!/usr/bin/python3
"""
db_setup.py — CashFlowCareTaker
================================
Creates / migrates the SQLite cashflow.db with 3 tables:
  intakes   — money coming IN
  outtakes  — money going OUT
  conflicts — flagged HIGH-CONFLICT entries (resolved manually)

Run this once before first use, or import `get_conn()` from other modules.
"""

from __future__ import annotations
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'cashflow.db')

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS intakes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    description     TEXT    NOT NULL,
    amount_raw      TEXT,
    amount_usd      REAL,
    amount_pkr      REAL,
    currency        TEXT,
    fx_rate_used    REAL,
    date            TEXT    NOT NULL,
    source          TEXT,
    counterparty    TEXT,
    vector_match    TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outtakes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    description     TEXT    NOT NULL,
    amount_raw      TEXT,
    amount_usd      REAL,
    amount_pkr      REAL,
    currency        TEXT,
    fx_rate_used    REAL,
    date            TEXT    NOT NULL,
    source          TEXT,
    counterparty    TEXT,
    vector_match    TEXT,
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conflicts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    original_input   TEXT,
    candidates_json  TEXT,
    conflict_reason  TEXT,
    status           TEXT    DEFAULT 'pending',
    created_at       TEXT    DEFAULT (datetime('now'))
);
"""


def get_conn() -> sqlite3.Connection:
    """Return a WAL-enabled connection to cashflow.db (creates file if needed)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def init_db() -> None:
    """Create / migrate cashflow.db. Safe to run multiple times."""
    conn = get_conn()
    conn.close()
    print(f"[DB] cashflow.db ready at {DB_PATH}")


if __name__ == "__main__":
    init_db()
