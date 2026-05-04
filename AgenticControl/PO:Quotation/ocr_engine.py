"""
ocr_engine.py
=============
Extracts text from PO documents using the OCR.space API.

Supported input formats:
  - PDF  (.pdf) — split page-by-page to bypass free-tier 3-page limit
  - Images (.jpg, .jpeg, .png, .bmp, .tiff, .tif, .gif, .webp) — sent directly

Public API
----------
  ocr_file(file_path: str) -> list[dict]
    Universal entry point. Auto-detects PDF vs image.
    Returns: [{"page": 1, "text": "..."}, {"page": 2, "text": "..."}, ...]

  ocr_pdf_pages(file_path)   — PDF-specific (used internally by po_processor)
  ocr_image_file(file_path)  — Image-specific (single page result)
"""

import os
import time
import tempfile
import mimetypes
import requests
from pypdf import PdfReader, PdfWriter

# ── Configuration ──────────────────────────────────────────────────────────
OCR_API_KEY  = "helloworld"                        # Replace with paid key for production
OCR_URL_POST = "https://api.ocr.space/parse/image"
RETRY_DELAY  = 2   # seconds between retries on network failure

# Supported image extensions → MIME types recognised by OCR.space
IMAGE_EXTENSIONS = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".bmp":  "image/bmp",
    ".tiff": "image/tiff",
    ".tif":  "image/tiff",
    ".gif":  "image/gif",
    ".webp": "image/webp",
}


# ── Shared OCR call helper ──────────────────────────────────────────────────

def _ocr_post(file_path: str, file_name: str, mime_type: str,
              filetype_hint: str, page_label: str) -> str:
    """
    POST a file to OCR.space and return extracted text.
    Retries up to 2 times on network errors.
    """
    payload = {
        "apikey":            OCR_API_KEY,
        "isTable":           "true",
        "scale":             "true",
        "language":          "eng",
        "filetype":          filetype_hint,    # "PDF", "JPG", "PNG", etc.
        "OCREngine":         "2",              # Engine 2 — best for structured data
        "detectOrientation": "true",
    }

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    files = {"file": (file_name, file_bytes, mime_type)}

    result = {}
    for attempt in range(1, 3):
        try:
            response = requests.post(
                OCR_URL_POST,
                data=payload,
                files=files,
                timeout=60,
            )
            response.raise_for_status()
            result = response.json()
            break
        except requests.exceptions.RequestException as e:
            print(f"  [OCR] {page_label} attempt {attempt} failed: {e}")
            if attempt < 2:
                time.sleep(RETRY_DELAY)
            else:
                return ""

    if result.get("IsErroredOnProcessing"):
        err = result.get("ErrorMessage", ["Unknown error"])
        print(f"  [OCR] {page_label} API error: {err}")
        return ""

    parsed = result.get("ParsedResults", [])
    if not parsed:
        return ""

    return parsed[0].get("ParsedText", "").strip()


# ── PDF support ─────────────────────────────────────────────────────────────

def _ocr_one_page_pdf(page_pdf_path: str, page_num: int) -> str:
    """Send a single-page PDF to OCR.space."""
    return _ocr_post(
        file_path=page_pdf_path,
        file_name=f"page_{page_num}.pdf",
        mime_type="application/pdf",
        filetype_hint="PDF",
        page_label=f"Page {page_num}",
    )


def ocr_pdf_pages(file_path: str) -> list:
    """
    Extract text from every page of a PDF.

    Splits the PDF into individual 1-page temp PDFs and calls OCR.space
    once per page — avoids the free-tier 3-page-per-request limit.

    Returns
    -------
    list[dict]  [{"page": 1, "text": "..."}, ...]
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")

    reader      = PdfReader(file_path)
    total_pages = len(reader.pages)
    print(f"[OCR] PDF: {os.path.basename(file_path)} ({total_pages} page(s))")

    pages = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        for i, page in enumerate(reader.pages, start=1):
            writer = PdfWriter()
            writer.add_page(page)
            tmp_pdf = os.path.join(tmp_dir, f"page_{i}.pdf")
            with open(tmp_pdf, "wb") as f:
                writer.write(f)

            print(f"  [OCR] Page {i}/{total_pages}…", end="", flush=True)
            text = _ocr_one_page_pdf(tmp_pdf, i)

            if text:
                pages.append({"page": i, "text": text})
                print(f" ✓ ({len(text)} chars)")
            else:
                print(" — no text")

    print(f"[OCR] Done. {len(pages)}/{total_pages} page(s) extracted.")
    return pages


# ── Image support ───────────────────────────────────────────────────────────

def ocr_image_file(file_path: str) -> list:
    """
    Extract text from a single image file.

    Supports: JPG, JPEG, PNG, BMP, TIFF, TIF, GIF, WEBP

    Returns
    -------
    list[dict]  [{"page": 1, "text": "..."}]  — always a single-item list
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Image not found: {file_path}")

    ext      = os.path.splitext(file_path)[1].lower()
    mime     = IMAGE_EXTENSIONS.get(ext)
    if not mime:
        raise ValueError(
            f"Unsupported image format: '{ext}'. "
            f"Supported: {', '.join(IMAGE_EXTENSIONS)}"
        )

    # OCR.space filetype hint — use "JPG" for JPEG variants, else uppercase ext
    filetype_hint = "JPG" if ext in (".jpg", ".jpeg") else ext.lstrip(".").upper()
    fname         = os.path.basename(file_path)

    print(f"[OCR] Image: {fname} ({ext})")
    print(f"  [OCR] Sending to OCR.space…", end="", flush=True)

    text = _ocr_post(
        file_path=file_path,
        file_name=fname,
        mime_type=mime,
        filetype_hint=filetype_hint,
        page_label="Image",
    )

    if text:
        print(f" ✓ ({len(text)} chars)")
        return [{"page": 1, "text": text}]
    else:
        print(" — no text extracted")
        return []


# ── Universal entry point ───────────────────────────────────────────────────

def ocr_file(file_path: str) -> list:
    """
    Auto-detect file type and extract text.

    Parameters
    ----------
    file_path : str — absolute path to a PDF or image file

    Returns
    -------
    list[dict]  [{"page": N, "text": "..."}, ...]
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return ocr_pdf_pages(file_path)
    elif ext in IMAGE_EXTENSIONS:
        return ocr_image_file(file_path)
    else:
        raise ValueError(
            f"Unsupported file type: '{ext}'. "
            f"Supported: .pdf, {', '.join(IMAGE_EXTENSIONS)}"
        )
