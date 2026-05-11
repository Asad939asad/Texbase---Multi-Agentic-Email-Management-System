import fitz  # PyMuPDF
import json
import sqlite3
import requests
import os
import re
# --- CONFIGURATION ---
LLM_URL = "http://localhost:8003/generate"
ROOT_DIR = os.environ.get('WORKSPACE_ROOT', '.')
DB_PATH = os.path.join(ROOT_DIR, 'Database/personnel_data/ResumeProcessed.db')

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# --- 1. DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Table updated with specific columns for each resume factor
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resumes (
            email TEXT PRIMARY KEY,
            education TEXT,
            hard_skills TEXT,
            soft_skills TEXT,
            summary TEXT,
            projects TEXT,
            languages TEXT,
            contact TEXT,
            github TEXT,
            linkedin TEXT,
            brief_analysis TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# --- 2. PDF TEXT EXTRACTION ---
def extract_text_from_pdf(pdf_path):
    with fitz.open(pdf_path) as doc:
        text = "".join(page.get_text() for page in doc)
    return text

# --- 3. LLM INTERACTION ---
def call_llm(system_prompt, user_query):
    payload = {
        "system_prompt": system_prompt,
        "query": user_query,
        "max_new_tokens": 1000
    }
    response = requests.post(LLM_URL, json=payload)
    if response.status_code == 200:
        return response.json()["response"]
    raise Exception(f"LLM Error: {response.text}")

# --- 4. MAIN PROCESSING LOGIC ---
def process_resume(pdf_path, user_email):
    print(f"🚀 Starting process for: {user_email}")
    
    # Step A: Extract Raw Text
    resume_raw_text = extract_text_from_pdf(pdf_path)
    
    # Step B: LLM Pass 1 - Structured Extraction
    # IMPROVED PROMPT: We give it a strict schema to follow
    extraction_prompt = (
        "You are a precise JSON extractor. Extract resume data into this EXACT JSON format: "
        '{"education": "...", "hard_skills": "...", "soft_skills": "...", "summary": "...", '
        '"projects": "...", "languages": "...", "contact": "...", "github": "...", "linkedin": "..."}. '
        "Return ONLY the raw JSON object. Do not include any markdown or explanation."
    )
    
    try:
        json_raw = call_llm(extraction_prompt, resume_raw_text)
        
        # 1. Clean Markdown and whitespace
        json_raw = re.sub(r"```json|```", "", json_raw).strip()
        
        # 2. Basic JSON Repair: Small models often leave trailing commas or bad quotes
        # This regex helps find the first '{' and last '}' to ignore extra hallucinated text
        match = re.search(r'\{.*\}', json_raw, re.DOTALL)
        if match:
            json_raw = match.group(0)
        
        data = json.loads(json_raw)
        
    except Exception as e:
        print(f"❌ Failed to parse LLM JSON. Raw output was: \n{json_raw[:200]}...")
        print(f"Detailed Error: {e}")
        return

    # Step C: LLM Pass 2 - Brief of Skills Analysis
    analysis_prompt = "Summarize the following candidate's top 3 professional strengths in 3 short sentences."
    # We pass the cleaned data back to the LLM
    brief_analysis = call_llm(analysis_prompt, json.dumps(data))

    # Step D: Save to Database (same as before...)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO resumes (
                email, education, hard_skills, soft_skills, summary, 
                projects, languages, contact, github, linkedin, brief_analysis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_email,
            str(data.get('education', 'n/a')),
            str(data.get('hard_skills', 'n/a')),
            str(data.get('soft_skills', 'n/a')),
            str(data.get('summary', 'n/a')),
            str(data.get('projects', 'n/a')),
            str(data.get('languages', 'n/a')),
            str(data.get('contact', 'n/a')),
            str(data.get('github', 'n/a')),
            str(data.get('linkedin', 'n/a')),
            brief_analysis
        ))
        conn.commit()
        print(f"✅ Successfully saved profile for {user_email}")
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        conn.close()

# if __name__ == "__main__":
#     init_db()
#     ROOT_DIR = os.environ.get('WORKSPACE_ROOT', '.')
#     load_dotenv(dotenv_path=os.path.join(ROOT_DIR, 'backend/.env'))
#     path = os.path.join(ROOT_DIR, 'Database/personnel_data/asadchairman735_at_gmail.com_Asad CV (1).pdf')
#     email = "asadirfan358@gmail.com"
#     if os.path.exists(path):
#         process_resume(path, email)