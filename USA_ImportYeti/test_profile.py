import sqlite3

# ─── Configuration ──────────────────────────────────────────────
# Replace these with your actual database path and table name
import os
DB_PATH = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'USA_ImportYeti/importyeti_data.db')
TABLE_NAME = "companies"
# ────────────────────────────────────────────────────────────────

def reset_selection():
    conn = None
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Execute the update query
        # This updates every row in the table, setting 'selection' to 0
        query = f"UPDATE {TABLE_NAME} SET selection = 0"
        cursor.execute(query)

        # Commit the transaction to save changes
        conn.commit()

        # Print how many rows were affected
        print(f"✅ Success! {cursor.rowcount} rows have been reset to selection = 0.")

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")

    finally:
        # Always close the connection
        if conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    # Ask for confirmation before running (optional but safe)
    confirm = input(f"Are you sure you want to reset 'selection' to 0 in {TABLE_NAME}? (y/n): ")
    if confirm.lower() == 'y':
        reset_selection()
    else:
        print("Operation cancelled.")