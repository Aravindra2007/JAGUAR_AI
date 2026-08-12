"""
Document/image ingestion for Jaguar AI's "read this and help me with
it" upload feature (/upload in app.py).

Supported today:
    .txt, .md            -> read directly
    .pdf                  -> PyPDF2 text extraction
    .docx                 -> python-docx paragraph extraction
    .png/.jpg/.jpeg/.bmp  -> OCR via pytesseract, IF Tesseract OCR is
                             installed on the machine; otherwise we
                             still store the image and tell the model
                             it received an image it can't read text
                             from yet, rather than failing the upload.

Every extractor is defensive: a broken/unsupported file never crashes
the upload endpoint, it just returns a short explanatory string that
gets shown to the user and (optionally) handed to the LLM.
"""

from __future__ import annotations

import os

MAX_EXTRACT_CHARS = 12000

TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".log", ".json"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


def _truncate(text: str) -> str:
    text = (text or "").strip()
    if len(text) > MAX_EXTRACT_CHARS:
        return text[:MAX_EXTRACT_CHARS] + "\n\n[...truncated]"
    return text


def _extract_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read(MAX_EXTRACT_CHARS)


def _extract_pdf(path: str) -> str:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return "(PDF reading requires PyPDF2 - run: pip install PyPDF2)"

    try:
        reader = PdfReader(path)
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)
    except Exception as e:
        return f"(Could not read this PDF: {e})"


def _extract_docx(path: str) -> str:
    try:
        import docx
    except ImportError:
        return "(Word reading requires python-docx - run: pip install python-docx)"

    try:
        document = docx.Document(path)
        return "\n".join(p.text for p in document.paragraphs)
    except Exception as e:
        return f"(Could not read this Word document: {e})"


def _extract_image(path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return (
            "(Image received. Text extraction from images needs "
            "pytesseract + Pillow, and the Tesseract OCR engine "
            "installed on this machine. Install with: "
            "pip install pytesseract pillow, then install Tesseract "
            "itself from https://github.com/tesseract-ocr/tesseract.)"
        )

    try:
        text = pytesseract.image_to_string(Image.open(path))
        text = text.strip()
        if not text:
            return "(No readable text found in this image via OCR.)"
        return text
    except Exception as e:
        return f"(Could not OCR this image: {e})"


def extract_text(path: str) -> str:
    """Best-effort text extraction for any supported upload."""
    if not os.path.isfile(path):
        return "(File not found.)"

    ext = os.path.splitext(path)[1].lower()

    if ext in TEXT_EXTENSIONS:
        raw = _extract_txt(path)
    elif ext in PDF_EXTENSIONS:
        raw = _extract_pdf(path)
    elif ext in DOCX_EXTENSIONS:
        raw = _extract_docx(path)
    elif ext in IMAGE_EXTENSIONS:
        raw = _extract_image(path)
    else:
        raw = f"(Unsupported file type '{ext}'. Supported: text, PDF, DOCX, and common image formats.)"

    return _truncate(raw)


def build_attachment_context(filename: str, extracted_text: str) -> str:
    """The block that gets prepended to the user's next message so the
    LLM sees what was uploaded."""
    return f"[Attached file: {filename}]\n{extracted_text}"
