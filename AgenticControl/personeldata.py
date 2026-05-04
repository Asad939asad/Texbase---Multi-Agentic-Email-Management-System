import sqlite3
import os
import json
from datetime import datetime
# NOTE: ResumeProcessor is imported lazily inside save_user_profile()
# so that a missing dependency (e.g. PyMuPDF) never blocks the DB save.

# ── Configuration ────────────────────────────────────────────────────────
# You can change this path later. The code will automatically create it.
PERSONNEL_FOLDER = os.path.join(os.environ.get('WORKSPACE_ROOT', os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/personnel_data')
DB_PATH = os.path.join(PERSONNEL_FOLDER, 'personnelDetails.db')

# Ensure the personnel folder exists
os.makedirs(PERSONNEL_FOLDER, exist_ok=True)

# ── 1. Initialize Database ───────────────────────────────────────────────
def init_db():
    """Creates the SQL table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # We use 'email' as the PRIMARY KEY so we don't get duplicate users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            name TEXT,
            location TEXT,
            github_description TEXT,
            languages TEXT,
            cv_file_path TEXT,
            access_token TEXT,
            refresh_token TEXT,
            updated_at TEXT,
            is_registered BOOLEAN
        )
    ''')
    conn.commit()
    conn.close()

# Run initialization immediately when the file loads
init_db()

# ── 2. The Boolean Check Function ────────────────────────────────────────
def check_user_exists(email: str) -> bool:
    """
    Checks if we already have this user's information in our database.
    Returns True if they exist, False otherwise.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_registered FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
    conn.close()
    
    # SQLite stores Booleans as 1 or 0. If we found a result, return True.
    if result and result[0] == 1:
        return True
    return False

# ── 3. The Main Save Function ────────────────────────────────────────────
def save_user_profile(
    email: str,
    name: str,
    location: str,
    github_description: str,
    languages: list,
    cv_file_bytes: bytes,  # The actual file content sent from the frontend
    cv_filename: str,      # The name of the uploaded file (e.g., 'resume.pdf'))
    access_token: str,
    refresh_token: str
):
    """
    Saves or updates the user profile and their Google tokens in the SQL database.
    """
    # 1. Fetch the existing cv_file_path before overwriting
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT cv_file_path FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    old_cv_path = row[0] if row else None
    conn.close()

    # 2. Save the actual CV file into the personnel folder
    cv_file_path = None
    if cv_file_bytes and cv_filename:
        # We add the email to the filename so files don't overwrite each other
        safe_filename = f"{email.replace('@', '_at_')}_{cv_filename}"
        cv_file_path = os.path.join(PERSONNEL_FOLDER, safe_filename)
        
        # If an old CV exists and its name differs, delete the old file to prevent orphans
        if old_cv_path and old_cv_path != cv_file_path and os.path.exists(old_cv_path):
            try:
                os.remove(old_cv_path)
                print(f"🗑️ Deleted old CV: {old_cv_path}")
            except Exception as e:
                print(f"❌ Failed to delete old CV: {e}")
                
        with open(cv_file_path, "wb") as f:
            f.write(cv_file_bytes)
            
    # 2. Prepare data for SQL
    # SQL can't store Python lists directly, so we convert languages to a JSON string
    languages_str = json.dumps(languages)
    updated_at = datetime.utcnow().isoformat()
    is_registered = True  # The boolean flag you requested
    
    # 3. Save to SQL Database using UPSERT
    # "UPSERT" means it will INSERT a new row, but if the email already exists, it will UPDATE it.
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO users (
            email, name, location, github_description, languages, 
            cv_file_path, access_token, refresh_token, updated_at, is_registered
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            name=excluded.name,
            location=excluded.location,
            github_description=excluded.github_description,
            languages=excluded.languages,
            cv_file_path=COALESCE(excluded.cv_file_path, users.cv_file_path),
            access_token=excluded.access_token,
            refresh_token=excluded.refresh_token,
            updated_at=excluded.updated_at,
            is_registered=excluded.is_registered
    ''', (
        email, name, location, github_description, languages_str,
        cv_file_path, access_token, refresh_token, updated_at, is_registered
    ))
    
    conn.commit()
    conn.close()
    
    print(f"✅ User {email} successfully saved to SQL Database!")
    
    # 4. If a new CV was uploaded, process it with the LLM in a background thread.
    #    This ensures save_user_profile returns immediately after the DB save,
    #    allowing the Node.js backend to respond to the frontend without waiting for the LLM.
    if cv_file_path:
        try:
            import threading
            from ResumeProcessor import process_resume  # noqa: PLC0415
            print(f"Processing resume for {email} via LLM...", flush=True)
            
            def run_llm_task():
                try:
                    process_resume(cv_file_path, email)
                except Exception as e:
                    print(f"[WARNING] Background ResumeProcessor failed: {e}")

            # Daemon thread will be killed when the main Node.js process dies,
            # but while Node.js is running, this Python thread will continue.
            # Wait, no... if save_user_cli.py exits, the daemon thread dies!
            # Wait, since save_user_cli.py is what spawns this, if it exits, the thread dies.
            # That's why we don't want save_user_cli to exit if the thread is running!
            
            # Actually, to make it completely non-blocking for Node.js, save_user_cli.py MUST print
            # the JSON response, flush it, and then WAIT for the thread. 
            # Or better yet: Node.js handles the async detach.
            
            t = threading.Thread(target=run_llm_task)
            t.daemon = False # Must NOT be daemon, so python doesn't exit until it finishes
            t.start()
        except ImportError as ie:
            print(f"[WARNING] ResumeProcessor not available (missing dependency?): {ie}")
        except Exception as e:
            print(f"[WARNING] ResumeProcessor failed to start: {e}")


# ── Example Usage ────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     # 1. Checking if a user exists
#     exists = check_user_exists("asadirfan7533@gmail.com")
#     print(f"Does Asad exist? {exists}")
    
#     # 2. Saving a new user
#     save_user_profile(
#         email="asadirfan7533@gmail.com",
#         name="Asad Irfan",
#         location="Topi, Pakistan",
#         github_description="AI student building agentic tools",
#         languages=["Python", "TypeScript", "C++"],
#         cv_file_bytes=b"fake_pdf_data_bytes_here",
#         cv_filename='Asad_CV.pdf'),
#         access_token="ya29.a0AfB...",
#         refresh_token="1//0eXYZ..."
#     )
    
    # 3. Checking again
    # exists_now = check_user_exists("asadirfan939@gmail.com")
    # print(f"Does Asad exist now? {exists_now}")