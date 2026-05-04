"""
db_manager.py
=============
Handles all SQLite operations for the PO tool.

Tables are created dynamically based on the schema Gemini infers from the PO.
Every table always includes: id, embedding_id, source_pdf, created_at — plus
whatever product/price columns Gemini identifies.

Public API
----------
  get_connection(db_path)  -> sqlite3.Connection
  create_table(conn, table_name, columns)
  insert_rows(conn, table_name, columns, rows) -> list[int]   (row ids)
  update_embedding_id(conn, table_name, row_id, embedding_id)
"""

import sqlite3
import re
import datetime


# ── Helpers ────────────────────────────────────────────────────────────────

def _sanitize_name(name: str) -> str:
    """Convert an arbitrary string into a safe SQL identifier."""
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)   # replace non-alnum with _
    name = re.sub(r"_+", "_", name)            # collapse repeated _
    name = name.strip("_")
    if name and name[0].isdigit():
        name = "col_" + name                   # SQL identifiers can't start with digit
    return name or "col"


# ── Connection ─────────────────────────────────────────────────────────────

def get_connection(db_path: str) -> sqlite3.Connection:
    """Open (or create) the SQLite database and return the connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row        # enable column access by name
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ── Schema ─────────────────────────────────────────────────────────────────

def create_table(conn: sqlite3.Connection,
                 table_name: str,
                 columns: list) -> str:
    """
    Create a table for the PO if it does not already exist.

    Parameters
    ----------
    conn       : open SQLite connection
    table_name : Gemini-generated snake_case name (will be sanitized)
    columns    : list of column name strings inferred by Gemini

    Returns
    -------
    str — the final sanitized table name used
    """
    safe_table = _sanitize_name(table_name)

    # Reserved system columns — always present
    system_cols = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "source_pdf TEXT",
        "embedding_id TEXT",
        "created_at TEXT",
    ]

    # User-data columns (all stored as TEXT; numeric types handled in Python)
    sanitized_cols = [_sanitize_name(c) for c in columns]
    # Deduplicate while preserving order
    seen = set()
    unique_cols = []
    for c in sanitized_cols:
        if c not in seen and c not in {"id", "source_pdf", "embedding_id", "created_at"}:
            seen.add(c)
            unique_cols.append(c)

    data_col_defs = [f'"{c}" TEXT' for c in unique_cols]
    all_col_defs  = system_cols + data_col_defs

    ddl = f'CREATE TABLE IF NOT EXISTS "{safe_table}" ({", ".join(all_col_defs)})'

    conn.execute(ddl)
    conn.commit()

    print(f"[DB] Table ready: '{safe_table}' with columns: {unique_cols}")
    return safe_table


# ── Insert ─────────────────────────────────────────────────────────────────

def insert_rows(conn: sqlite3.Connection,
                table_name: str,
                columns: list,
                rows: list) -> list:
    """
    Insert extracted PO rows into the table.

    Parameters
    ----------
    conn       : open SQLite connection
    table_name : sanitized table name (as returned by create_table)
    columns    : list of column names matching the table (user-data cols only)
    rows       : list of dicts — each dict is one PO line item

    Returns
    -------
    list[int]  — the rowids of every inserted row
    """
    if not rows:
        return []

    safe_table = _sanitize_name(table_name)
    safe_cols  = [_sanitize_name(c) for c in columns
                  if _sanitize_name(c) not in {"id", "source_pdf", "embedding_id", "created_at"}]

    now = datetime.datetime.utcnow().isoformat()
    inserted_ids = []

    for row in rows:
        values = [str(row.get(c, "")).strip() for c in safe_cols]

        placeholders = ", ".join(["?"] * (len(safe_cols) + 2))   # +2 for source_pdf, created_at
        col_list     = ", ".join([f'"{c}"' for c in safe_cols] + ['"source_pdf"', '"created_at"'])

        sql = f'INSERT INTO "{safe_table}" ({col_list}) VALUES ({placeholders})'
        cur = conn.execute(sql, values + [row.get("__source_pdf__", ""), now])
        inserted_ids.append(cur.lastrowid)

    conn.commit()
    print(f"[DB] Inserted {len(inserted_ids)} row(s) into '{safe_table}'.')
    return inserted_ids


# ── Update embedding id ─────────────────────────────────────────────────────

def update_embedding_id(conn: sqlite3.Connection,
                        table_name: str,
                        row_id: int,
                        embedding_id: str):
    """Stamp a row with its ChromaDB document ID after embedding."""
    safe_table = _sanitize_name(table_name)
    conn.execute(
        f'UPDATE "{safe_table}" SET embedding_id = ? WHERE id = ?',
        (embedding_id, row_id)
    )
    conn.commit()
