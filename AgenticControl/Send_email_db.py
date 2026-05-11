import sqlite3
import json
import sys
import os
import re
import base64

def approve_and_move_email(email_id):
    # Connect to the source and destination databases
    review_db_path = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsUnderReview/emailsUnderReview.db')
    outbox_db_path = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'Database/EmailsSent/email_to_be_sent.db') # The new database
    
    try:
        # Open connections
        conn_review = sqlite3.connect(review_db_path)
        conn_outbox = sqlite3.connect(outbox_db_path)
        
        cursor_review = conn_review.cursor()
        cursor_outbox = conn_outbox.cursor()

        # 1. Ensure the destination table exists in the new database
        # We use the exact same schema, but change the default status
        cursor_outbox.execute('''
            CREATE TABLE IF NOT EXISTS ready_emails (
                id               INTEGER PRIMARY KEY,
                body_json        TEXT,
                timestamp        DATETIME,
                followup_date    DATETIME,
                status           TEXT DEFAULT 'ready to be sent',
                company_name     TEXT,
                generated_subject TEXT,
                company_email    TEXT,
                Unique_application_id TEXT
            )
        ''')

        # 2. Fetch the email from the review database
        cursor_review.execute("""
            SELECT id, body_json, timestamp, followup_date, status,
                   company_name, generated_subject, company_email, Unique_application_id
            FROM tracking
            WHERE id = ?
        """, (email_id,))
        
        row = cursor_review.fetchone()

        if not row:
            print(json.dumps({"ok": False, "error": f"Email ID {email_id} not found."}))
            return False

        # Unpack the row data
        (row_id, body_json, timestamp, followup_date, current_status,
         company_name, generated_subject, company_email, unique_app_id) = row
        # 3. Process attachments, links, and clean the body_json payload
        def process_email_attachments(row_id, body_str):
            output_dir = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), f'metadatatracking/{row_id}')
            os.makedirs(output_dir, exist_ok=True)
            
            try:
                data = json.loads(body_str)
            except Exception:
                data = {}
                
            html_content = data.get("body", {}).get("generated_content", body_str)
            if not isinstance(html_content, str):
                html_content = str(html_content)
            
            img_pattern = re.compile(r'<img[^>]+src="data:image/([^;]+);base64,([^"]+)"[^>]*>')
            images_saved = []
            
            def replacer(match):
                ext = match.group(1)
                b64_data = match.group(2)
                idx = len(images_saved)
                filename = f"image_{idx}.{ext}"
                filepath = os.path.join(output_dir, filename)
                
                try:
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    images_saved.append(filename)
                    # Replace src payload entirely with local path
                    full_tag = match.group(0)
                    original_src = f'data:image/{ext};base64,{b64_data}'
                    return full_tag.replace(original_src, f'file://{filepath}')
                except Exception as e:
                    return match.group(0)

            modified_html = img_pattern.sub(replacer, html_content)
            
            link_pattern = re.compile(r'<a[^>]+href="([^"]+)"')
            links_found = link_pattern.findall(modified_html)
            
            if "body" in data and isinstance(data["body"], dict):
                data["body"]["generated_content"] = modified_html
            else:
                data = modified_html # fallback
                
            final_body_str = json.dumps(data) if isinstance(data, dict) else data
            
            with open(os.path.join(output_dir, 'email_data.json'), "w") as f:
                json.dump({
                    "cleaned_html_body": modified_html,
                    "images_attached": images_saved,
                    "links_found": links_found
                }, f, indent=4)
                
            return final_body_str

        cleaned_body_json = process_email_attachments(row_id, body_json)
        
        # 4. Change status to the new requirement
        new_status = 'ready to be sent'

        # 5. Insert the complete row into the new database
        cursor_outbox.execute("""
            INSERT INTO ready_emails
            (id, body_json, timestamp, followup_date, status,
             company_name, generated_subject, company_email, Unique_application_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (row_id, cleaned_body_json, timestamp, followup_date, new_status,
               company_name, generated_subject, company_email, unique_app_id))

        # 6. Delete the entry from the original database
        cursor_review.execute("DELETE FROM tracking WHERE id = ?", (email_id,))

        # 7. Commit transactions on BOTH databases
        conn_outbox.commit()
        conn_review.commit()
        
        print(json.dumps({"ok": True, "message": f"Success: Email {email_id} has been moved to the outbox."}))
        return True

    except sqlite3.Error as e:
        # If any database error occurs, roll back both databases so data isn't lost
        print(json.dumps({"ok": False, "error": f"Database error occurred: {e}"}))
        if 'conn_outbox' in locals(): conn_outbox.rollback()
        if 'conn_review' in locals(): conn_review.rollback()
        return False
        
    finally:
        # Always close connections to free up the DB locks
        if 'conn_outbox' in locals(): conn_outbox.close()
        if 'conn_review' in locals(): conn_review.close()

if __name__ == '__main__':
    try:
        input_data = sys.stdin.read().strip()
        if input_data:
            payload = json.loads(input_data)
            email_id = payload.get('id')
            if email_id is not None:
                approve_and_move_email(int(email_id))
            else:
                print(json.dumps({"ok": False, "error": "No 'id' provided in input"}))
        else:
            print(json.dumps({"ok": False, "error": "No input provided"}))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))