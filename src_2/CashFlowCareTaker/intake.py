#!/usr/bin/python3
"""
intake.py — CashFlowCareTaker  (Layer A)
==========================================
Accepts any of:
  - Plain text string
  - PDF file path   → OCR via ocr_engine.py
  - Image file path → OCR via ocr_engine.py
  - Email body text (same as plain text)

After extracting raw text, performs a semantic search against the vector store
to find similar past transactions.

Public API
----------
  process_input(source: str, input_type: str = "text") -> IntakeResult
    source     : text string, or absolute file path
    input_type : "text" | "pdf" | "image" | "email"

  Returns IntakeResult dict:
    {
      "raw_text":       str,
      "similar_entries": [ {text, metadata, distance}, ... ],
      "source_type":    str,
    }
"""

from __future__ import annotations
import os
import sys

# OCR engine lives in PO:Quotation — add to path
OCR_ENGINE_DIR = "/Volumes/ssd2/TEXBASE/src/PO:Quotation"
sys.path.insert(0, OCR_ENGINE_DIR)
sys.path.insert(0, os.path.dirname(__file__))

from ocr_engine import ocr_file
from vector_store import search_similar

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"}


def _extract_text_from_file(file_path: str) -> str:
    """Route to OCR engine and concatenate all page text."""
    pages = ocr_file(file_path)
    return "\n\n".join(p["text"] for p in pages if p.get("text"))


def process_input(source: str, input_type: str = "auto") -> dict:
    """
    Layer A entry point. Extract raw text from any input format and
    retrieve semantically similar past entries from the vector store.

    Parameters
    ----------
    source     : absolute path to file, or raw text string
    input_type : "auto" | "text" | "email" | "pdf" | "image"

    Returns
    -------
    dict with keys: raw_text, similar_entries, source_type
    """
    raw_text = ""
    source_type = input_type

    # ── Auto-detect file vs text ───────────────────────────────────────────
    if input_type == "auto":
        if os.path.isfile(source):
            ext = os.path.splitext(source)[1].lower()
            source_type = "image" if ext in IMAGE_EXTS else "pdf"
        else:
            source_type = "text"

    # ── Extract text ───────────────────────────────────────────────────────
    if source_type in ("pdf", "image"):
        print(f"[Intake] OCR processing {source_type.upper()}: {os.path.basename(source)}")
        raw_text = _extract_text_from_file(source)
    else:
        # "text" or "email" — passed directly
        raw_text = source.strip()
        print(f"[Intake] Text/email input ({len(raw_text)} chars)")

    if not raw_text:
        print("[Intake] WARNING: No text could be extracted from input.")

    # ── Semantic search ────────────────────────────────────────────────────
    print(f"[Intake] Searching vector DB for similar past entries…")
    similar = search_similar(raw_text, n=5)
    if similar:
        print(f"  Found {len(similar)} similar entry/entries:")
        for h in similar:
            print(f"    [{h['distance']:.3f}] {h['text'][:70]}…")
    else:
        print("  No similar entries found (vector DB may be empty).")

    return {
        "raw_text":        raw_text,
        "similar_entries": similar,
        "source_type":     source_type,
    }
