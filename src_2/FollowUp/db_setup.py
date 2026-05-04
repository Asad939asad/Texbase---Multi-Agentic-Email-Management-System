#!/usr/bin/python3
"""
db_setup.py — FollowUp Agent
==============================
Creates / migrates email_inbox.db with two tables:
  inbox  — all received emails
  sent   — drafted and sent replies

Run once, or import get_conn() from other modules.
"""

from __future__ import annotations
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'email_inbox.db')

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS inbox (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      TEXT    UNIQUE,          -- Email Message-ID header (dedup key)
    sender          TEXT,                    -- From address
    subject         TEXT,
    body            TEXT,                    -- Full email body text
    received_at     TEXT,                    -- ISO datetime
    thread_id       TEXT,                    -- Groups replies together
    processed       INTEGER DEFAULT 0,       -- 0=new, 1=routed
    routing_plan    TEXT,                    -- JSON: LLM routing decision
    routing_result  TEXT,                    -- JSON: assembled DB query results
    reply_draft     TEXT,                    -- Draft reply email body
    status          TEXT    DEFAULT 'new',   -- new/routed/replied/ignored
    label           TEXT    DEFAULT 'new',   -- new / routed / replied / ignored (human-readable tag)
    created_at      TEXT    DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sent (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    inbox_id    INTEGER,                     -- FK → inbox.id (NULL for cold outreach)
    to_address  TEXT,
    subject     TEXT,
    body        TEXT,
    original_email_body TEXT,                -- The base email this response was generated for
    sent_at     TEXT,                        -- NULL = still a draft
    status      TEXT    DEFAULT 'routed',    -- routed/sent/approved
    created_at  TEXT    DEFAULT (datetime('now')),
    FOREIGN KEY (inbox_id) REFERENCES inbox(id)
);
"""


def get_conn() -> sqlite3.Connection:
    """Return a connection to email_inbox.db (creates file + schema if needed)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.close()
    print(f"[DB] email_inbox.db ready at {DB_PATH}")


if __name__ == "__main__":
    init_db()
