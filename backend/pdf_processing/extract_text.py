"""
pdf_processing/extract_text.py

Extracts raw text from a PDF, either from a local file path or a URL
(Supabase public storage URL).

Returns a list of strings, one per page, preserving page order.
Does NOT clean or embed — that is clean_text.py's job.
"""
import io
import urllib.request
from pypdf import PdfReader


def extract_from_path(file_path: str) -> list[str]:
    """Extract raw text from a local PDF file. Returns one string per page."""
    reader = PdfReader(file_path)
    return [page.extract_text() or "" for page in reader.pages]


def extract_from_url(url: str) -> list[str]:
    """Download a PDF from a URL and extract raw text. Returns one string per page."""
    req = urllib.request.Request(url, headers={"User-Agent": "MediDevice-PDF-Extractor/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read()
    reader = PdfReader(io.BytesIO(data))
    return [page.extract_text() or "" for page in reader.pages]


def extract(source: str) -> list[str]:
    """
    Unified entry point.
    If source starts with http/https, downloads and extracts.
    Otherwise treats it as a local file path.
    """
    if source.startswith(("http://", "https://")):
        return extract_from_url(source)
    return extract_from_path(source)
