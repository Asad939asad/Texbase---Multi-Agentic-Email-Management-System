"""
po_processor.py
===============
Main entry point for the PO processing pipeline.

Accepts: PDF files (.pdf) and Images (.jpg, .jpeg, .png, .bmp, .tiff, .gif, .webp)

Two-phase pipeline:
  Phase 1 — OCR all content → Gemini thinking analysis (one call, thinking enabled)
  Phase 2 — Page/image-by-page Gemini extraction (one call per page/image)
  Save    — Each discovered schema → separate SQLite table + ChromaDB collection

Usage (CLI):
    python po_processor.py --file /path/to/po.pdf
    python po_processor.py --file /path/to/po_scan.jpg

Usage (Python):
    from po_processor import process_po
    result = process_po('/path/to/po.pdf'))
    result = process_po('/path/to/po_scan.png'))
"""

import os
import argparse
import tempfile

from pypdf            import PdfReader, PdfWriter
from ocr_engine       import ocr_file, IMAGE_EXTENSIONS, _ocr_one_page_pdf
from gemini_session   import POExtractionSession
from db_manager       import get_connection, create_table, insert_rows, update_embedding_id
from vector_store     import get_or_create_collection, embed_and_store

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.join(os.environ.get('WORKSPACE_ROOT', '.'), 'AgenticControl/PO:Quotation')
DB_PATH    = os.path.join(BASE_DIR, 'po_database.db')
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")


# ── Core pipeline ──────────────────────────────────────────────────────────

def process_po(file_path: str) -> dict:
    """
    End-to-end PO processing pipeline — supports PDF and image files.

    Returns
    -------
    dict  {
        "tables_saved": [{"table_name": ..., "rows": N, "embedded": N}, ...],
        "db_path":      ...,
        "chroma_dir":   ...
    }
    """
    file_path   = file_path
    source_file = os.path.basename(file_path)
    ext         = os.path.splitext(file_path)[1].lower()
    is_image    = ext in IMAGE_EXTENSIONS

    if not os.path.isfile(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return {}

    print(f"\n{'='*65}")
    print(f"  PO Processor — {source_file}")
    print(f"  File type   : {'Image' if is_image else 'PDF'}")
    print(f"{'='*65}\n")

    session = POExtractionSession(source_pdf=source_file)

    # ── Phase 1A: OCR content and buffer ──────────────────────────────────
    print("[ PHASE 1 — DOCUMENT ANALYSIS ]")
    print("─" * 65)

    page_texts = {}   # page_num → text (reused in Phase 2)

    if is_image:
        # ── Image path: single OCR call, single "page" ────────────────────
        print(f"  [File type] Image detected — sending directly to OCR.space")
        pages = ocr_file(file_path)   # returns [{"page":1, "text":"..."}]
        for p in pages:
            page_texts[p["page"]] = p["text"]
            session.collect_page(p["page"], p["text"])

    else:
        # ── PDF path: split and OCR page-by-page ─────────────────────────
        reader      = PdfReader(file_path)
        total_pages = len(reader.pages)
        print(f"  [File type] PDF — {total_pages} page(s), processing page by page")

        with tempfile.TemporaryDirectory() as tmp_dir:
            for i, page_obj in enumerate(reader.pages, start=1):
                writer = PdfWriter()
                writer.add_page(page_obj)
                tmp_pdf = os.path.join(tmp_dir, f"page_{i}.pdf")
                with open(tmp_pdf, "wb") as f:
                    writer.write(f)

                print(f"  [OCR] Page {i}/{total_pages}…", end="", flush=True)
                text = _ocr_one_page_pdf(tmp_pdf, i)
                if text:
                    print(f" ✓ ({len(text)} chars)")
                    page_texts[i] = text
                    session.collect_page(i, text)
                else:
                    print(" — no text, skipping.")

    if not page_texts:
        print("[!] No text extracted. Aborting.")
        return {}

    # ── Phase 1B: Gemini thinking — define schemas ────────────────────────
    session.analyse_structure()

    # ── Phase 2: Per-page/image row extraction ────────────────────────────
    total = len(page_texts)
    print(f"\n[ PHASE 2 — ROW EXTRACTION ({total} page/image(s)) ]")
    print("─" * 65)

    for page_num in sorted(page_texts.keys()):
        print(f"[Page {page_num}/{total}]", end=" ")
        session.extract_page(page_num, page_texts[page_num])

    # ── Finalise ──────────────────────────────────────────────────────────
    result  = session.finalize()
    schemas = result.get("schemas", [])

    if not any(s["rows"] for s in schemas):
        print("[!] No rows extracted. Nothing to save.")
        return {}

    # ── Save to SQLite + ChromaDB ──────────────────────────────────────────
    print(f"\n[ SAVING TO DATABASE ]")
    print("─" * 65)

    conn         = get_connection(DB_PATH)
    tables_saved = []

    for schema in schemas:
        table_name = schema.get("table_name", "purchase_order")
        columns    = schema.get("columns", [])
        rows       = schema.get("rows", [])

        if not rows:
            print(f"  [{table_name}] 0 rows — skipping.")
            continue

        final_table = create_table(conn, table_name, columns)
        row_ids     = insert_rows(conn, final_table, columns, rows)

        collection = get_or_create_collection(CHROMA_DIR, final_table)
        embedded   = 0
        for row_id, row in zip(row_ids, rows):
            clean_row = {k: v for k, v in row.items() if not k.startswith("__")}
            doc_id    = embed_and_store(collection, row_id, clean_row, source_file, final_table)
            update_embedding_id(conn, final_table, row_id, doc_id)
            embedded += 1

        tables_saved.append({"table_name": final_table, "rows": len(row_ids), "embedded": embedded})
        print(f"  ✓ '{final_table}' — {len(row_ids)} rows, {embedded} embedded.")

    conn.close()

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  Done! {len(tables_saved)} table(s) created for '{source_file}'")
    for t in tables_saved:
        print(f"    • {t['table_name']}: {t['rows']} rows, {t['embedded']} vectors")
    print(f"  DB       : {os.path.abspath(DB_PATH)}")
    print(f"  ChromaDB : {os.path.abspath(CHROMA_DIR)}")
    print(f"{'='*65}\n")

    return {
        "tables_saved": tables_saved,
        "db_path":      os.path.abspath(DB_PATH),
        "chroma_dir":   os.path.abspath(CHROMA_DIR),
    }


# ── CLI entry point ────────────────────────────────────────────────────────

def main():
    result = process_po("AgenticControl/PO:Quotation/Purchase-Order-Sheet.jpg")
    if result:
        print("Pipeline completed successfully.")


if __name__ == "__main__":
    main()
