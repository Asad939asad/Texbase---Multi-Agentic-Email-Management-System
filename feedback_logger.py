import sqlite3
import json
from datetime import datetime
import os
from pathlib import Path

DB_PATH = Path("feedback_log.db")
JSON_PATH = Path("feedback_log.json")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Expanded schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            section TEXT,
            feedback TEXT,
            user_input TEXT,
            agent_response TEXT,
            parameter_name TEXT,
            prediction_summary TEXT,
            tone_requested TEXT,
            draft_length_chars INTEGER,
            pipeline_stage TEXT,
            recipient_hint TEXT,
            predicted_price REAL,
            actual_price REAL,
            price_delta REAL,
            item_description TEXT,
            correction_note TEXT,
            flagged_excerpt TEXT,
            user_comment TEXT
        )
    ''')
    conn.commit()
    conn.close()

def log_feedback(section, feedback, user_input, agent_response, **kwargs):
    timestamp = datetime.now().isoformat()
    
    # Truncate agent response to 500 chars as requested
    res_str = str(agent_response or "")
    truncated_response = (res_str[:497] + "...") if len(res_str) > 500 else res_str

    fields = {
        "timestamp": timestamp,
        "section": section,
        "feedback": feedback,
        "user_input": user_input,
        "agent_response": truncated_response,
        "parameter_name": kwargs.get("parameter_name"),
        "prediction_summary": kwargs.get("prediction_summary"),
        "tone_requested": kwargs.get("tone_requested"),
        "draft_length_chars": kwargs.get("draft_length_chars"),
        "pipeline_stage": kwargs.get("pipeline_stage"),
        "recipient_hint": kwargs.get("recipient_hint"),
        "predicted_price": kwargs.get("predicted_price"),
        "actual_price": kwargs.get("actual_price"),
        "price_delta": kwargs.get("price_delta"),
        "item_description": kwargs.get("item_description"),
        "correction_note": kwargs.get("correction_note"),
        "flagged_excerpt": kwargs.get("flagged_excerpt"),
        "user_comment": kwargs.get("user_comment")
    }

    # Log to SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    placeholders = ", ".join(["?"] * len(fields))
    columns = ", ".join(fields.keys())
    values = tuple(fields.values())
    
    cursor.execute(f"INSERT INTO feedback_log ({columns}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()
    
    # Log to JSONL
    with open(JSON_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(fields) + "\n")

def get_all_logs():
    if not DB_PATH.exists(): return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM feedback_log')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_logs_by_section(section):
    if not DB_PATH.exists(): return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM feedback_log WHERE section = ?', (section,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_negative_logs():
    if not DB_PATH.exists(): return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM feedback_log WHERE feedback IN ('bad', 'partial')")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

if __name__ == "__main__":
    init_db()
    print("Upgraded Feedback logger initialized.")
