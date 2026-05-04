#!/usr/bin/python3
"""
vector_store.py — CashFlowCareTaker
=====================================
Persistent vector store backed by SQLite + SentenceTransformer embeddings.

Model: all-MiniLM-L6-v2 (fast, 384-dim, excellent for short text)
Similarity: cosine (numpy dot product on normalised vectors)

Public API
----------
  add_transaction(text, metadata)  — embed + upsert one chunk
  search_similar(query, n=5)       — return n most similar past entries
  count()                          — number of stored vectors
"""

from __future__ import annotations
import os
import json
import sqlite3
import hashlib
import numpy as np
from sentence_transformers import SentenceTransformer

VECTOR_DB_PATH = os.path.join(os.path.dirname(__file__), 'vector_store.db')
MODEL_NAME     = "all-MiniLM-L6-v2"   # ~22MB, downloads once, cached locally

_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS vectors (
    id        TEXT PRIMARY KEY,    -- sha256[:32] of text
    text      TEXT NOT NULL,
    metadata  TEXT,
    embedding BLOB NOT NULL        -- float32 numpy array serialised as bytes
);
"""

# ── Lazy-loaded model (singleton) ─────────────────────────────────────────────
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print("  [VectorDB] Loading sentence-transformer model…", flush=True)
        _model = SentenceTransformer(MODEL_NAME)
        print(f"  [VectorDB] Model '{MODEL_NAME}' ready.", flush=True)
    return _model


def _embed(text: str) -> np.ndarray:
    """Return a normalised float32 embedding vector."""
    vec = _get_model().encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return vec.astype(np.float32)


# ── SQLite helpers ────────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(VECTOR_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════

def add_transaction(text: str, metadata: dict | None = None) -> str:
    """
    Embed and upsert one transaction into the vector store.

    Parameters
    ----------
    text     : human-readable description
    metadata : dict (type, currency, counterparty, date, …)

    Returns
    -------
    doc_id : str
    """
    doc_id = hashlib.sha256(text.encode()).hexdigest()[:32]
    vec    = _embed(text)

    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO vectors (id, text, metadata, embedding) VALUES (?, ?, ?, ?)",
        (doc_id, text, json.dumps(metadata or {}), vec.tobytes()),
    )
    conn.commit()
    conn.close()
    print(f"  [VectorDB] Stored: {text[:70]}… (id={doc_id})")
    return doc_id


def search_similar(query: str, n: int = 5) -> list[dict]:
    """
    Find the n most similar past transactions using cosine similarity.

    Returns
    -------
    list of dicts sorted by distance (ascending — 0 = identical):
      [{text, metadata, distance}, ...]
    """
    conn = _get_conn()
    rows = conn.execute("SELECT id, text, metadata, embedding FROM vectors").fetchall()
    conn.close()

    if not rows:
        return []

    q_vec = _embed(query)   # already normalised

    scored = []
    for row in rows:
        try:
            vec = np.frombuffer(row["embedding"], dtype=np.float32)
            sim = float(np.dot(q_vec, vec))              # cosine (both normalised)
            scored.append({
                "text":     row["text"],
                "metadata": json.loads(row["metadata"] or "{}"),
                "distance": round(1.0 - sim, 4),        # convert → distance
            })
        except Exception:
            continue

    scored.sort(key=lambda x: x["distance"])
    return scored[:n]


def count() -> int:
    """Return number of stored vectors."""
    conn = _get_conn()
    c    = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
    conn.close()
    return c
