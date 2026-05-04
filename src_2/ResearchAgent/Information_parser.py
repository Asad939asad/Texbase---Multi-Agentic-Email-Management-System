"""
Information_parser.py
======================
Reads every PDF from the research_pdf/ folder, extracts as many small,
self-contained news snippets as possible from each PDF using Gemini, and
persists all results in a local SQLite database (news_items.db).

Database schema
---------------
Table: news_items
  id          INTEGER  PRIMARY KEY AUTOINCREMENT
  title       TEXT     Short headline for the news item  (~10 words)
  body        TEXT     The full news snippet             (2-5 sentences)
  category    TEXT     Inferred category tag             (e.g. "Fashion", "Sustainability")
  source_pdf  TEXT     Filename of the PDF it came from
  page_number INTEGER  PDF page the snippet was extracted from (1-indexed)
  created_at  TEXT     ISO-8601 timestamp of extraction

Usage
-----
  python Information_parser.py

Requirements
------------
  pip install pypdf google-genai
"""

import os
import re
import json
import sqlite3
import argparse
import datetime
from pypdf import PdfReader          # pip install pypdf
from google import genai             # pip install google-genai

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_KEY    = "AIzaSyBU69quGl9VhEOPqwNhbAiSUx40QQmk9Nc"
PDF_FOLDER = "/Volumes/ssd2/TEXBASE/src/ResearchAgent/research_pdf"
DB_PATH    = '/Volumes/ssd2/TEXBASE/src/ResearchAgent/news_items.db'))
MODEL      = "gemini-2.5-flash"   # fast, large-context model

client = genai.Client(api_key=API_KEY)

# ---------------------------------------------------------------------------
# Prompt template sent to Gemini for each page/chunk of PDF text
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """\
You are a professional news editor specialising in the textile and fashion industry.

Below is a section of a deep-research report. Your job is to extract as many small,
self-contained news items as possible from this text. 

CRITICAL: The text frequently contains Data Tables and Lists. You MUST NOT ignore them. 
If you encounter tabular data (e.g. imports, exports, percentages, trends), you MUST extract it 
and perfectly format it as a rigorous GitHub-Flavored Markdown table inside your "body" response. 

Each news item must:
  - Have a punchy, concise headline (max 12 words).
  - Have a body containing a Markdown Table (if tabular data is found) OR 2-5 standalone sentences (if text-heavy).
  - Be tagged with one of these categories:
      Fashion Trends | Textile Innovation | Trade & Exports | Manufacturing Tech | Strategy & Business | Data Analytics
  - NOT include any source citations, reference numbers, or URLs.

Return your answer as a valid JSON array (and NOTHING else) with this structure:
[
  {{
    "title": "...",
    "body": "...",
    "category": "..."
  }},
  ...
]

TEXT TO PROCESS:
\"\"\"
{text}
\"\"\"
"""

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def init_db(db_path: str, table_name: str) -> sqlite3.Connection:
    """Create the SQLite database and dynamic table name if they don't exist."""
    conn = sqlite3.connect(db_path)
    
    # Ensure table names are safe from SQL injection
    safe_table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name)
    
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS "{safe_table_name}" (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT    NOT NULL,
            body        TEXT    NOT NULL,
            category    TEXT,
            source_pdf  TEXT,
            page_number INTEGER,
            created_at  TEXT
        )
    """)
    conn.commit()
    return conn


def insert_news_items(conn: sqlite3.Connection,
                      items: list,
                      source_pdf: str,
                      page_number: int,
                      table_name: str) -> int:
    """Insert a list of extracted news items and return the count inserted into dynamically named table."""
    now = datetime.datetime.utcnow().isoformat()
    safe_table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name)
    
    rows = [
        (
            item.get("title", "").strip(),
            item.get("body",  "").strip(),
            item.get("category", "General").strip(),
            source_pdf,
            page_number,
            now,
        )
        for item in items
        if item.get("title") and item.get("body")
    ]
    if rows:
        conn.executemany(
            f'INSERT INTO "{safe_table_name}" (title, body, category, source_pdf, page_number, created_at) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            rows,
        )
        conn.commit()
    return len(rows)

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Strip excessive whitespace from extracted PDF text."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 6000) -> list:
    """
    Split text into chunks of at most max_chars characters, breaking at
    paragraph boundaries so sentences are not split mid-way.
    """
    paragraphs = text.split('\n\n')
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current += "\n\n" + para
    if current.strip():
        chunks.append(current.strip())
    return chunks

# ---------------------------------------------------------------------------
# Gemini extraction
# ---------------------------------------------------------------------------

def extract_news_from_text(text: str) -> list:
    """
    Send a text chunk to Gemini and parse the returned JSON array
    of news items.  Returns an empty list on any failure.
    """
    prompt = EXTRACTION_PROMPT.format(text=text)
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        raw = response.text.strip()

        # Strip markdown code fences if present (```json ... ```)
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$',          '', raw)

        items = json.loads(raw)
        if isinstance(items, list):
            return items
    except json.JSONDecodeError as e:
        print(f"  [!] JSON parse error: {e}")
    except Exception as e:
        print(f"  [!] Gemini API error: {e}")
    return []

# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def process_pdf(pdf_path: str, conn: sqlite3.Connection, table_name: str) -> int:
    """
    Extract text page-by-page from a PDF, call Gemini on each chunk,
    and save all news items.  Returns total number of items saved.
    """
    filename = os.path.basename(pdf_path)
    print(f"\n{'='*60}")
    print(f"  Processing: {filename}")
    print(f"{'='*60}")

    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        print(f"  [!] Could not open PDF: {e}")
        return 0

    total_saved = 0

    for page_num, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        page_text = clean_text(raw_text)

        if len(page_text) < 80:
            print(f"  [Page {page_num}] Skipped (too little text).")
            continue

        # Split page into chunks if it is very long
        chunks = chunk_text(page_text, max_chars=6000)
        print(f"  [Page {page_num}] {len(chunks)} chunk(s) to process...", end="", flush=True)

        page_items = []
        for chunk in chunks:
            items = extract_news_from_text(chunk)
            page_items.extend(items)

        saved = insert_news_items(conn, page_items, filename, page_num, table_name)
        total_saved += saved
        print(f" -> {saved} news item(s) saved.")

    return total_saved


def run(target_file: str = None, table_name: str = "news_items"):
    """Entry point: iterate over all PDFs and populate the database."""
    # Validate folder
    if not os.path.isdir(PDF_FOLDER):
        print(f"[ERROR] PDF folder not found: {PDF_FOLDER}")
        return

    # If --target is supplied, process only that file. Otherwise process full directory.
    if target_file:
        pdf_path = os.path.join(PDF_FOLDER, target_file)
        if not os.path.exists(pdf_path):
            print(f"[ERROR] Target file not found: {pdf_path}")
            return
        pdf_files = [target_file]
    else:
        pdf_files = sorted([
            f for f in os.listdir(PDF_FOLDER)
            if f.lower().endswith(".pdf")
        ])

    if not pdf_files:
        print(f"[INFO] No PDF files found to process.")
        return

    print(f"\nFound {len(pdf_files)} PDF file(s) to process into table -> '{table_name}'")

    # Initialise database dynamically connected to target table
    conn = init_db(DB_PATH, table_name)
    print(f"Database ready: {DB_PATH}")

    grand_total = 0
    now_start = datetime.datetime.now()

    for pdf_file in pdf_files:
        pdf_path  = os.path.join(PDF_FOLDER, pdf_file)
        count     = process_pdf(pdf_path, conn, table_name)
        grand_total += count
        print(f"  Done with {pdf_file}: {count} news item(s) saved.")

    conn.close()

    elapsed = datetime.datetime.now() - now_start
    print(f"\n{'='*60}")
    print(f"  Done!  Total news items saved to DB: {grand_total} in {elapsed.total_seconds():.1f}s.")
    print(f"  Database table '{table_name}' has been updated.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Information Parser")
    parser.add_argument("--target", type=str, help="Specify a single PDF filename inside research_pdf to parse")
    parser.add_argument("--table", type=str, default="news_items", help="Specify the dynamic table name in SQLite to save to")
    args = parser.parse_args()
    
    run(target_file=args.target, table_name=args.table)
