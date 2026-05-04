"""
local_llm_session.py (formerly gemini_session.py)
=================================================
Two-phase session for PO extraction using the local Qwen model.
"""

import json
import re
import time
import requests

# ── Configuration ──────────────────────────────────────────────────────────
LOCAL_API_URL = "http://127.0.0.1:8003/generate"
CALL_DELAY    = 1    # seconds between local API calls

# ── Prompt templates ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert document analyst specialising in Purchase Orders, Quotations,
and commercial trade documents.

Your task is to read raw OCR text from a scanned/digital PO document and:
1. THINK carefully about the structure of the data — there may be multiple,
   distinct table-like structures on different pages (e.g., a product line-items
   table, a charges/fees breakdown, a packaging summary, a currency summary).
2. Extract ALL commercial data into structured JSON rows assigned to the correct
   schema.

Key rule: do NOT merge fundamentally different structures into one table.
If the document contains two separate grids with different columns, define
two separate schemas.
"""

ANALYSIS_PROMPT = """\
Below is the COMPLETE OCR text of a {total_pages}-page PO document.

Think carefully and deeply about this document. Identify:
- How many distinct table/grid structures exist across all pages?
- What are the exact column names for each structure?
- What short snake_case name best identifies each structure?
- What product(s) or material(s) is this document about? Provide a concise
  product description (e.g. "50% Hydrogen Peroxide, textile bleaching grade",
  "30s Carded Cotton Yarn", "Reactive Dyes — Red MF-3B, Blue MF-2G").

Then define a schema blueprint. Return ONLY valid JSON (no markdown fences):
{{
  "document_summary": "One sentence describing the overall PO document.",
  "product_description": "Concise description of the product(s) / material(s) in this document.",
  "schemas": [
    {{
      "schema_id": "lines",
      "table_name": "acme_po_line_items",
      "description": "Main product line items with qty and price",
      "product_description": "Cotton Yarn 30s Carded, Lahore supplier",
      "columns": ["item_no", "description", "quantity", "unit", "unit_price", "total"]
    }},
    {{
      "schema_id": "charges",
      "table_name": "acme_po_charges",
      "description": "Additional charges and fees",
      "product_description": "",
      "columns": ["charge_type", "amount", "currency"]
    }}
  ]
}}

Rules:
- Use only lowercase, digits, and underscores in table_name and column names.
- Extract ONLY commercial data (skip addresses, legal text, signatures).
- If the whole document has a single uniform structure, define just one schema.
- table_name should be unique and descriptive enough to identify this PO.
- product_description: describe what goods are being purchased — be specific
  (include grade, count, specification if visible in the document).

FULL DOCUMENT OCR TEXT:
\"\"\"
{full_text}
\"\"\"
"""

EXTRACTION_PROMPT = """\
This is PAGE {page_num} of the same PO document.

The document analysis identified these schemas:
{schema_summary}

Extract every data row from this page. For each row, identify which schema_id
it belongs to. Skip rows that are headers, footers, or non-data text.

If a row contains a product name, material grade, specification, or item
description not already in the defined columns, capture it in a field called
"product_description" within that row.

Return ONLY valid JSON (no markdown fences):
{{
  "extractions": [
    {{
      "schema_id": "lines",
      "rows": [
        {{"item_no": "1", "description": "Cotton Yarn 30s", "quantity": "500",
          "product_description": "30s Carded Cotton Yarn, Ring Spun", ...}},
        ...
      ]
    }},
    {{
      "schema_id": "charges",
      "rows": [
        {{"charge_type": "Freight", "amount": "1200", "currency": "USD",
          "product_description": ""}},
        ...
      ]
    }}
  ]
}}

If a schema has no rows on this page, omit it from extractions entirely.

PAGE {page_num} OCR TEXT:
\"\"\"
{text}
\"\"\"
"""

TABLE_NAME_PROMPT = """\
The document has been fully extracted based on these schemas:
{schema_summary}

Generate a short prefix (2-4 words, snake_case) that uniquely identifies THIS PO document, 
to be prepended to each table name.

Example: if the PO is from Alpha Mills for cotton yarn, return: "alpha_mills_cotton"

Return ONLY the prefix string — nothing else. Do not use quotes or markdown.
"""

# ── Helpers ────────────────────────────────────────────────────────────────

def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    return raw.strip()


def _parse_json(raw: str) -> dict:
    cleaned = _strip_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    print(f"  [LocalModel] WARNING: could not parse JSON response.")
    return {}


def _sanitize(name: str) -> str:
    """Make a safe snake_case SQL identifier."""
    name = name.strip().lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name[:60] or "po_table"


def _call_local_api(system_prompt: str, query: str, max_tokens: int = 2000) -> str:
    """Invoke the local FastAPI endpoint."""
    try:
        response = requests.post(
            LOCAL_API_URL,
            json={
                "system_prompt": system_prompt,
                "query": query,
                "max_new_tokens": max_tokens
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        print(f"  [LocalModel] API Error: {e}")
        return ""

# ── Session class ──────────────────────────────────────────────────────────

class POExtractionSession:
    def __init__(self, source_pdf: str):
        self.source_pdf      = source_pdf
        self._buffered_pages = []   
        self._schemas        = {}   
        self._call_count     = 0
        self._analysed       = False

    def _sleep_between_calls(self):
        if self._call_count > 0:
            time.sleep(CALL_DELAY)
        self._call_count += 1

    # ── Phase 1 ──────────────────────────────────────────────────────────

    def collect_page(self, page_num: int, text: str):
        if text.strip():
            self._buffered_pages.append((page_num, text))

    def analyse_structure(self):
        if not self._buffered_pages:
            print("[LocalModel] No buffered pages to analyse.")
            return

        total_pages = len(self._buffered_pages)
        full_text   = "\n\n".join(
            f"--- PAGE {pn} ---\n{txt}"
            for pn, txt in self._buffered_pages
        )

        print(f"\n[LocalModel] Phase 1 — Document Structure Analysis")
        print(f"  Total pages buffered: {total_pages}")
        print(f"  Total OCR chars: {len(full_text)}")
        print(f"  Sending to local model API at {LOCAL_API_URL}…", flush=True)

        prompt = ANALYSIS_PROMPT.format(
            total_pages=total_pages,
            full_text=full_text,
        )

        self._sleep_between_calls()
        ai_text = _call_local_api(SYSTEM_PROMPT, prompt, max_tokens=2000)

        parsed = _parse_json(ai_text)
        if not parsed or "schemas" not in parsed:
            print("  [LocalModel] Could not parse schema blueprint — using fallback single schema.")
            self._schemas["default"] = {
                "table_name": "purchase_order",
                "columns": [],
                "rows": [],
            }
            self._analysed = True
            return

        doc_summary      = parsed.get("document_summary", "")
        doc_product_desc = parsed.get("product_description", "")
        print(f"\n  Document summary     : {doc_summary}")
        if doc_product_desc:
            print(f"  Product description  : {doc_product_desc}")
        print(f"  Schemas detected     : {len(parsed['schemas'])}")

        for s in parsed["schemas"]:
            sid       = _sanitize(s.get("schema_id", "schema"))
            name      = _sanitize(s.get("table_name", f"po_{sid}"))
            cols      = [_sanitize(c) for c in s.get("columns", [])]
            desc      = s.get("description", "")
            prod_desc = s.get("product_description", "") or doc_product_desc
            print(f"    → [{sid}] '{name}' — {desc}")
            print(f"       Columns            : {cols}")
            if prod_desc:
                print(f"       Product description: {prod_desc}")
            self._schemas[sid] = {
                "table_name":          name,
                "columns":             cols,
                "rows":                [],
                "product_description": prod_desc,
            }

        self._analysed = True

    # ── Phase 2 ──────────────────────────────────────────────────────────

    def extract_page(self, page_num: int, text: str):
        if not text.strip():
            print(f"  [LocalModel] Page {page_num}: empty — skipped.")
            return
        if not self._analysed:
            raise RuntimeError("Call analyse_structure() before extract_page().")

        schema_lines = []
        for sid, s in self._schemas.items():
            schema_lines.append(
                f'  schema_id="{sid}" | table="{s["table_name"]}" | columns={s["columns"]}'
            )
        schema_summary = "\n".join(schema_lines)

        prompt = EXTRACTION_PROMPT.format(
            page_num=page_num,
            schema_summary=schema_summary,
            text=text,
        )

        print(f"  [LocalModel] Page {page_num} extraction… ", end="", flush=True)
        self._sleep_between_calls()
        ai_text = _call_local_api(SYSTEM_PROMPT, prompt, max_tokens=2000)

        parsed = _parse_json(ai_text)
        if not parsed:
            print("could not parse.")
            return

        total_rows = 0
        for extraction in parsed.get("extractions", []):
            sid      = _sanitize(extraction.get("schema_id", ""))
            new_rows = extraction.get("rows", [])

            if sid not in self._schemas:
                print(f"\n  [LocalModel] New schema '{sid}' discovered on page {page_num} — adding.")
                all_cols = set()
                for r in new_rows:
                    all_cols.update(r.keys())
                self._schemas[sid] = {
                    "table_name": _sanitize(f"po_{sid}"),
                    "columns":    [_sanitize(c) for c in all_cols],
                    "rows":       [],
                }

            for row in new_rows:
                row["__source_pdf__"]       = self.source_pdf
                row["__page__"]             = str(page_num)
                schema_prod_desc = self._schemas[sid].get("product_description", "")
                if "product_description" not in row or not row["product_description"]:
                    row["product_description"] = schema_prod_desc
            self._schemas[sid]["rows"].extend(new_rows)
            total_rows += len(new_rows)

        print(f"{total_rows} row(s) across {len(parsed.get('extractions', []))} schema(s).")

    # ── Finalize ──────────────────────────────────────────────────────────

    def finalize(self) -> dict:
        total_rows = sum(len(s["rows"]) for s in self._schemas.values())
        if total_rows == 0:
            return {"schemas": list(self._schemas.values())}

        print("  [LocalModel] Generating PO identifier prefix…", end="", flush=True)
        self._sleep_between_calls()
        
        schema_lines = []
        for sid, s in self._schemas.items():
            schema_lines.append(f'- {s["table_name"]}')
        schema_summary = "\n".join(schema_lines)
        
        prompt = TABLE_NAME_PROMPT.format(schema_summary=schema_summary)
        raw_prefix = _call_local_api(SYSTEM_PROMPT, prompt, max_tokens=100).strip().split("\n")[0]
        
        # Add a timestamp to ensure uniqueness for every upload
        timestamp = time.strftime("%m%d_%H%M")
        prefix     = f"{_sanitize(raw_prefix)[:20]}_{timestamp}"
        print(f" '{prefix}'")

        for sid, schema in self._schemas.items():
            current = schema["table_name"]
            if not current.startswith(prefix):
                schema["table_name"] = _sanitize(f"{prefix}_{current}")[:60]

            if "product_description" not in schema["columns"]:
                schema["columns"].append("product_description")

        print(f"\n[LocalModel] Extraction complete.")
        for sid, s in self._schemas.items():
            prod_desc = s.get("product_description", "")
            print(f"  [{sid}] '{s['table_name']}' — {len(s['rows'])} row(s), cols: {s['columns']}")
            if prod_desc:
                print(f"         Product desc : {prod_desc}")

        return {"schemas": list(self._schemas.values())}
