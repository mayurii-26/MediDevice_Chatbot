"""
backend/scripts/sync_documents.py

Scans all folders in the `device-documents` Supabase Storage bucket,
derives metadata from folder path + filename, and inserts records into
the `device_documents` table. Skips files that already exist.

Run from project root:
    python backend/scripts/sync_documents.py
"""

import os
import re
import sys
from pathlib import Path

# ── Allow imports from backend/ when run from project root ────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from supabase import create_client

# ── Config ─────────────────────────────────────────────────────────────────
BUCKET       = "device-documents"
TABLE        = "device_documents"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")   # service role needed for storage listing

if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Document-type keywords (checked in order, longer phrases first) ────────
_DOC_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"accessories[_ ]brochure",    "Accessories Brochure"),
    (r"accessories",                "Accessories"),
    (r"quick[_ ]?start[_ ]?guide",  "Quick Start Guide"),
    (r"user[_ ]?guide",             "User Guide"),
    (r"user[_ ]?manual",            "User Manual"),
    (r"service[_ ]?manual",         "Service Manual"),
    (r"installation[_ ]?guide",     "Installation Guide"),
    (r"reference[_ ]?guide",        "Reference Guide"),
    (r"clinical[_ ]?guide",         "Clinical Guide"),
    (r"specification",              "Specifications"),
    (r"datasheet",                  "Datasheet"),
    (r"data[_ ]?sheet",             "Datasheet"),
    (r"white[_ ]?paper",            "White Paper"),
    (r"brochure",                   "Brochure"),
    (r"flyer",                      "Flyer"),
    (r"catalogue",                  "Catalogue"),
    (r"catalog",                    "Catalogue"),
    (r"overview",                   "Overview"),
]


def detect_document_type(stem: str) -> str:
    """Infer document type from the filename stem (no extension)."""
    lower = stem.lower()
    for pattern, label in _DOC_TYPE_PATTERNS:
        if re.search(pattern, lower):
            return label
    return "Brochure"          # safe default


def derive_product_name(stem: str) -> str:
    """
    Strip trailing document-type words and clean up separators.
    e.g. "PageWriter_TC50_Cardiology"     -> "PageWriter TC50"
         "HeartStart_FRx_AED_Accessories_Brochure" -> "HeartStart FRx AED"
    """
    # Collect all doc-type tokens to strip
    type_tokens = set()
    for _, label in _DOC_TYPE_PATTERNS:
        for word in label.split():
            type_tokens.add(word.lower())

    # Replace underscores/hyphens with spaces
    name = re.sub(r"[_\-]+", " ", stem).strip()

    # Remove doc-type words from the end (iteratively)
    changed = True
    while changed:
        changed = False
        words = name.split()
        # strip from the tail as long as the last word is a type token
        while words and words[-1].lower() in type_tokens:
            words.pop()
            changed = True
        name = " ".join(words)

    # Remove trailing category/misc words sometimes appended to filenames
    name = re.sub(
        r"\s+(cardiology|anaesthesia|monitoring|patient|devices?|documents?)\s*$",
        "", name, flags=re.IGNORECASE
    ).strip()

    return name or stem


def public_url(file_path: str) -> str:
    """Return the public URL for a file in the bucket."""
    res = supabase.storage.from_(BUCKET).get_public_url(file_path)
    # SDK returns a plain string
    return res if isinstance(res, str) else res.get("publicUrl", "")


def list_files(prefix: str = "") -> list[dict]:
    """
    Recursively list all files under `prefix` in the bucket.
    Returns list of dicts with keys: name, path, size_bytes.
    """
    files: list[dict] = []
    entries = supabase.storage.from_(BUCKET).list(prefix)

    for entry in entries:
        entry_name = entry.get("name", "")
        full_path  = f"{prefix}/{entry_name}".lstrip("/")

        # Folders have id=None (or metadata=None); files have a size
        metadata = entry.get("metadata") or {}
        size     = metadata.get("size")

        if size is not None:
            # It's a file
            files.append({
                "name":       entry_name,
                "path":       full_path,
                "size_bytes": int(size),
            })
        else:
            # It's a folder — recurse
            files.extend(list_files(full_path))

    return files


def existing_urls() -> set[str]:
    """Fetch all file_url values already in the table."""
    result = supabase.table(TABLE).select("file_url").execute()
    return {row["file_url"] for row in (result.data or [])}


def parse_path(file_path: str) -> tuple[str, str, str]:
    """
    Split a storage path into (category, subcategory, filename).
    Handles 2-level and 3-level folder structures.

    device-documents/
      Category/filename.pdf            -> subcategory = category
      Category/Subcategory/filename.pdf
    """
    parts = [p for p in file_path.split("/") if p]

    if len(parts) >= 3:
        category    = parts[0]
        subcategory = parts[1]
        filename    = parts[-1]
    elif len(parts) == 2:
        category    = parts[0]
        subcategory = parts[0]
        filename    = parts[1]
    else:
        category    = "Unknown"
        subcategory = "Unknown"
        filename    = parts[-1] if parts else file_path

    return category, subcategory, filename


# ── Mode: populate storage_path for existing rows ─────────────────────────

def update_storage_paths() -> None:
    """
    UPDATE_EXISTING_STORAGE_PATHS mode.
    - Scans bucket for every PDF.
    - Matches each file to a DB row via file_url (most reliable key).
    - Sets storage_path where it is currently NULL.
    - Never inserts, never creates duplicates.
    """
    print(f"MODE: UPDATE_EXISTING_STORAGE_PATHS\nScanning bucket: {BUCKET}")
    all_files = list_files()
    pdfs = [f for f in all_files if f["name"].lower().endswith(".pdf")]
    print(f"Found {len(pdfs)} PDF(s) in bucket.\n")

    # Load all rows that have a NULL storage_path, keyed by file_url
    result = (
        supabase.table(TABLE)
        .select("id, file_url, storage_path")
        .execute()
    )
    rows = result.data or []
    total = len(rows)

    # Build lookup: file_url -> row
    url_to_row: dict[str, dict] = {r["file_url"]: r for r in rows}

    updated   = 0
    populated = 0
    errors    = 0

    for f in pdfs:
        url          = public_url(f["path"])
        storage_path = f["path"]          # e.g. "Patient Monitoring Devices/ECG/PageWriter TC50_Cardiology.pdf"

        row = url_to_row.get(url)

        if row is None:
            print(f"  ERROR  no DB row matched for: {f['path']}")
            errors += 1
            continue

        if row.get("storage_path"):
            print(f"  SKIP   already populated: {f['path']}")
            populated += 1
            continue

        supabase.table(TABLE).update(
            {"storage_path": storage_path}
        ).eq("id", row["id"]).execute()

        print(f"  UPDATED  {f['path']}")
        updated += 1

    print(
        f"\nDone."
        f"\n  Total DB records : {total}"
        f"\n  Updated          : {updated}"
        f"\n  Already populated: {populated}"
        f"\n  Errors           : {errors}"
    )


# ── Mode: full import ──────────────────────────────────────────────────────

def main() -> None:
    print(f"Scanning bucket: {BUCKET}")
    all_files = list_files()
    print(f"Found {len(all_files)} file(s) in bucket.\n")

    known_urls = existing_urls()

    inserted = 0
    skipped  = 0

    for f in all_files:
        # Only process PDFs
        if not f["name"].lower().endswith(".pdf"):
            skipped += 1
            continue

        category, subcategory, filename = parse_path(f["path"])
        stem          = Path(filename).stem
        document_name = stem.replace("_", " ").replace("-", " ")
        product_name  = derive_product_name(stem)
        document_type = detect_document_type(stem)
        size_mb       = round(f["size_bytes"] / (1024 * 1024), 3)
        url           = public_url(f["path"])

        if url in known_urls:
            print(f"  SKIP  {f['path']}")
            skipped += 1
            continue

        record = {
            "category":      category,
            "subcategory":   subcategory,
            "product_name":  product_name,
            "document_name": document_name,
            "document_type": document_type,
            "file_size_mb":  size_mb,
            "file_url":      url,
            "is_active":     True,
        }

        supabase.table(TABLE).insert(record).execute()
        known_urls.add(url)   # prevent re-insert within same run
        print(f"  INSERT {f['path']}  →  {product_name} | {document_type}")
        inserted += 1

    print(f"\nDone. Inserted: {inserted}  |  Skipped: {skipped}")


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Pass --update-storage-paths to run the backfill mode.
    # Default (no args) runs the full import mode.
    if "--update-storage-paths" in sys.argv:
        update_storage_paths()
    else:
        main()
