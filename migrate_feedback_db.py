import sqlite3
import os

DB_PATH = "feedback_log.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print("Database does not exist. No migration needed.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get existing columns
    cursor.execute("PRAGMA table_info(feedback_log)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    
    new_cols = [
        ("parameter_name", "TEXT"),
        ("prediction_summary", "TEXT"),
        ("tone_requested", "TEXT"),
        ("draft_length_chars", "INTEGER"),
        ("pipeline_stage", "TEXT"),
        ("recipient_hint", "TEXT"),
        ("predicted_price", "REAL"),
        ("actual_price", "REAL"),
        ("price_delta", "REAL"),
        ("item_description", "TEXT"),
        ("correction_note", "TEXT"),
        ("flagged_excerpt", "TEXT"),
        ("user_comment", "TEXT")
    ]
    
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            print(f"Adding column {col_name}...")
            try:
                cursor.execute(f"ALTER TABLE feedback_log ADD COLUMN {col_name} {col_type}")
            except Exception as e:
                print(f"Failed to add {col_name}: {e}")
    
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
