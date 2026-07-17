# -*- coding: utf-8 -*-
"""
cleanup_cache.py
------------------------------------------------------------
One-time cache cleanup script.

PURPOSE
-------
The response_refiner.py was rewritten on 2026-07-17 (commit 2cf9ab1).
Cached answers generated BEFORE that date may contain corruption signatures
from the old fallback_formatter.py: concatenated words, leaked raw metadata
labels, or old-style markdown that the new formatter no longer produces.

This script:
  1. Connects to Supabase using the same credentials as the chatbot backend.
  2. Fetches every row in `cached_answers`.
  3. Classifies each row as CORRUPTED or CLEAN using a deterministic set of
     corruption signatures derived from the old formatter output patterns.
  4. In DRY-RUN mode (default): prints a full report -- nothing is deleted.
  5. In LIVE mode (--live flag): deletes only the CORRUPTED rows, then
     prints a summary of what was removed.

SAFETY GUARANTEES
-----------------
  [OK] Only touches the `cached_answers` table.
  [OK] Never deletes rows classified as CLEAN.
  [OK] Never touches `conversations`, `messages`, `device_documents`,
       `user_preferences`, `document_download_requests`,
       or `secure_download_tokens`.
  [OK] Defaults to DRY-RUN -- pass --live to actually delete.
  [OK] Prints every decision with its reason so results are auditable.

USAGE
-----
  # Dry-run (safe, no changes):
  python backend/scripts/cleanup_cache.py

  # Live delete:
  python backend/scripts/cleanup_cache.py --live

Run from the project root (C:\\Users\\DELL\\MediDevice_Chatbot).
"""

import sys
import os
import re
from datetime import datetime, timezone

# -- Make project root importable -------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.join(_SCRIPT_DIR, "..")          # backend/
_PROJECT_ROOT = os.path.join(_BACKEND_DIR, "..")        # project root
sys.path.insert(0, _BACKEND_DIR)
sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from database.supabase_client import supabase

# -- Cutoff datetime --------------------------------------------------------
# The new response_refiner was committed at 2026-07-17 19:15:36 +05:30.
# Converting to UTC: 2026-07-17 13:45:36 UTC.
# We use a slightly conservative cutoff of 2026-07-17 00:00:00 UTC so that
# any entry created on that day is ALSO inspected for corruption, rather
# than blindly trusted because of date alone.
NEW_FORMATTER_CUTOFF = datetime(2026, 7, 17, 0, 0, 0, tzinfo=timezone.utc)


# -- Corruption signatures --------------------------------------------------
#
# These patterns are derived from the OLD fallback_formatter.py behaviour.
# Each entry is a (label, regex) pair.
#
# A row is classified as CORRUPTED if ANY one of these patterns matches the
# cached `answer` text.  The label is printed in the report so you can see
# exactly why a row was flagged.
#
# IMPORTANT: The patterns are intentionally specific so that clean Markdown
# responses (e.g. containing "**Product**" as part of natural prose) are not
# falsely flagged.

_CORRUPTION_SIGNATURES = [
    # -- Old formatter heading style -----------------------------------------
    # Old fallback_formatter emitted the product emoji heading at the top.
    # New response_refiner never emits that exact phrase.
    (
        "old_heading: 'Product Information' with emoji",
        re.compile(
            r"[\U0001F4E6]\s*\*\*Product Information\*\*",
            re.IGNORECASE | re.UNICODE,
        ),
    ),
    # Old formatter: "**Product:** PageWriter TC50"
    # New formatter uses a heading-only style, never "**Product:**" inline.
    (
        "old_field_label: '**Product:**'",
        re.compile(r"\*\*Product:\*\*\s+\S", re.IGNORECASE),
    ),
    # Old formatter: "**Category:** Cardiology"
    (
        "old_field_label: '**Category:**'",
        re.compile(r"\*\*Category:\*\*\s+\S", re.IGNORECASE),
    ),
    # Old formatter: "**Description:**" section heading
    (
        "old_field_label: '**Description:**'",
        re.compile(r"\*\*Description:\*\*", re.IGNORECASE),
    ),
    # Old formatter: "**Key Features:**" section heading
    (
        "old_field_label: '**Key Features:**'",
        re.compile(r"\*\*Key Features:\*\*", re.IGNORECASE),
    ),
    # Old formatter: "**Specifications:**" section heading
    (
        "old_field_label: '**Specifications:**'",
        re.compile(r"\*\*Specifications:\*\*", re.IGNORECASE),
    ),
    # Old formatter: "**Key Specifications:**"
    (
        "old_field_label: '**Key Specifications:**'",
        re.compile(r"\*\*Key Specifications:\*\*", re.IGNORECASE),
    ),
    # -- Raw metadata that leaked from FAISS chunks -------------------------
    # Old formatter sometimes passed raw chunk text straight through.
    # Patterns: "Product Name: XYZ" or "Product Name:XYZ" at line start.
    (
        "raw_metadata_leak: 'Product Name:'",
        re.compile(r"(?m)^Product Name\s*:", re.IGNORECASE),
    ),
    # "Description: some text" at line start (raw chunk field label)
    (
        "raw_metadata_leak: 'Description:'",
        re.compile(r"(?m)^Description\s*:\s*\S", re.IGNORECASE),
    ),
    # "Features:" at line start (not inside a markdown bullet)
    (
        "raw_metadata_leak: 'Features:'",
        re.compile(r"(?m)^Features\s*:\s*$", re.IGNORECASE),
    ),
    # "Specifications:" at line start as a bare label
    (
        "raw_metadata_leak: 'Specifications:'",
        re.compile(r"(?m)^Specifications\s*:\s*$", re.IGNORECASE),
    ),
    # -- Word concatenation -- sign that text was joined without spaces ------
    # Detects runs of lowercase+uppercase or alpha+digit transitions that
    # are implausibly long (> 30 chars) without any space or punctuation.
    # Example: "PageWriterTC50Cardiology12-leadECGMachine"
    (
        "word_concatenation: long run without spaces",
        re.compile(r"[A-Za-z0-9]{30,}"),   # 30+ char alnum run = probably corrupt
    ),
    # -- Fallback / error response text -------------------------------------
    # These are the same fragments checked in cache_service._is_fallback()
    # so any that slipped through the quality gate are cleaned up here too.
    (
        "fallback_text: 'i am a medical device assistant trained on'",
        re.compile(r"i am a medical device assistant trained on", re.IGNORECASE),
    ),
    (
        "fallback_text: 'our ai service is temporarily unavailable'",
        re.compile(r"our ai service is temporarily unavailable", re.IGNORECASE),
    ),
    (
        "fallback_text: 'i could not find relevant information'",
        re.compile(r"i could not find relevant information", re.IGNORECASE),
    ),
    (
        "fallback_text: 'please ask about supported medical devices'",
        re.compile(r"please ask about supported medical devices", re.IGNORECASE),
    ),
    # -- Purchase / OOS intent replies that got cached despite the guard ----
    (
        "intent_reply: purchase_intent",
        re.compile(
            r"pricing and purchasing information is not available through the chatbot",
            re.IGNORECASE,
        ),
    ),
    (
        "intent_reply: out_of_scope",
        re.compile(
            r"this platform is designed only for medical devices",
            re.IGNORECASE,
        ),
    ),
    # -- Sample report intent replies ---------------------------------------
    (
        "intent_reply: sample_report_intent",
        re.compile(
            r"sample reports related information is not available through the chatbot",
            re.IGNORECASE,
        ),
    ),
]


def _classify(row):
    """
    Returns (is_corrupted: bool, reasons: list[str]).

    A row is CORRUPTED if:
      (a) created_at is before NEW_FORMATTER_CUTOFF  AND
          at least one corruption signature matches the answer;
      OR
      (b) a fallback / intent reply signature matches (regardless of date) --
          these should never be in the cache at all.

    A row is CLEAN if none of the above apply.
    """
    answer = row.get("answer") or ""
    created_at_raw = row.get("created_at")

    # -- Parse created_at ---------------------------------------------------
    created_at = None
    if created_at_raw:
        try:
            # Supabase returns ISO strings like "2026-06-12T22:25:47.123456+00:00"
            # Python 3.11+ fromisoformat handles this; for 3.10 we normalise first.
            ts = created_at_raw.replace("Z", "+00:00")
            created_at = datetime.fromisoformat(ts)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
        except Exception:
            created_at = None

    is_old = (created_at is None) or (created_at < NEW_FORMATTER_CUTOFF)

    # -- Always-corrupt signatures (date-independent) -----------------------
    # These are the fallback/intent reply fragments -- if they're in the cache
    # they must go regardless of when they were written.
    ALWAYS_CORRUPT_LABELS = {
        "fallback_text: 'i am a medical device assistant trained on'",
        "fallback_text: 'our ai service is temporarily unavailable'",
        "fallback_text: 'i could not find relevant information'",
        "fallback_text: 'please ask about supported medical devices'",
        "intent_reply: purchase_intent",
        "intent_reply: out_of_scope",
        "intent_reply: sample_report_intent",
    }

    reasons = []
    for label, pattern in _CORRUPTION_SIGNATURES:
        if pattern.search(answer):
            # For date-dependent patterns: only flag if the row is old.
            if label not in ALWAYS_CORRUPT_LABELS and not is_old:
                continue
            reasons.append(label)

    return bool(reasons), reasons


def _format_row(row, reasons):
    """Pretty-print a single row decision."""
    question = row.get("question", "<no question>")[:80]
    answer_preview = (row.get("answer") or "")[:120].replace("\n", " ")
    created_at = row.get("created_at", "unknown date")
    row_id = row.get("id", "???")
    label_list = "\n    ".join(reasons) if reasons else "-"
    return (
        "  ID      : {}\n"
        "  KEY     : {}\n"
        "  DATE    : {}\n"
        "  PREVIEW : {}...\n"
        "  REASONS :\n    {}\n"
    ).format(row_id, question, created_at, answer_preview, label_list)


def main():
    # Force stdout to UTF-8 so emoji in cached answer text doesn't crash
    # the print statements on Windows (cp1252 terminal).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    live_mode = "--live" in sys.argv
    mode_label = "LIVE (deleting)" if live_mode else "DRY-RUN (no changes)"

    print("=" * 70)
    print("  MediDevice Chatbot -- Cache Cleanup Script")
    print("  Mode     : {}".format(mode_label))
    print("  Cutoff   : {}".format(NEW_FORMATTER_CUTOFF.isoformat()))
    print("  Table    : cached_answers only")
    print("=" * 70)
    print()

    # -- Fetch all cached_answers rows --------------------------------------
    print("[INFO] Fetching all cached_answers rows ...")
    try:
        result = (
            supabase.table("cached_answers")
            .select("id, question, answer, created_at")
            .execute()
        )
    except Exception as e:
        print("[ERROR] Failed to fetch cached_answers: {}".format(e))
        sys.exit(1)

    rows = result.data or []
    total = len(rows)
    print("[INFO] Fetched {} row(s).\n".format(total))

    if total == 0:
        print("[INFO] Cache is empty -- nothing to clean up.")
        sys.exit(0)

    # -- Classify each row --------------------------------------------------
    corrupted_rows = []   # list of (row, reasons)
    clean_rows = []       # list of row

    for row in rows:
        is_corrupted, reasons = _classify(row)
        if is_corrupted:
            corrupted_rows.append((row, reasons))
        else:
            clean_rows.append(row)

    # -- Print report -------------------------------------------------------
    print("-" * 70)
    print("  RESULTS SUMMARY")
    print("-" * 70)
    print("  Total rows  : {}".format(total))
    print("  CLEAN       : {}".format(len(clean_rows)))
    print("  CORRUPTED   : {}".format(len(corrupted_rows)))
    print("-" * 70)
    print()

    if corrupted_rows:
        print("-- CORRUPTED ROWS (to be deleted) " + "-" * 36)
        for i, (row, reasons) in enumerate(corrupted_rows, 1):
            print("\n[{}/{}] CORRUPTED".format(i, len(corrupted_rows)))
            print(_format_row(row, reasons))

    if clean_rows:
        print("\n-- CLEAN ROWS (will be kept) " + "-" * 41)
        for i, row in enumerate(clean_rows, 1):
            question = (row.get("question") or "")[:80]
            created_at = row.get("created_at", "unknown")
            print("  [{}] {}  [{}]".format(i, question, created_at))

    print()

    # -- Delete corrupted rows (live mode only) -----------------------------
    if not corrupted_rows:
        print("[INFO] No corrupted rows found. Cache is clean.")
        sys.exit(0)

    if not live_mode:
        print(
            "[DRY-RUN] No changes made.\n"
            "[DRY-RUN] To actually delete the corrupted rows, run:\n"
            "[DRY-RUN]   python backend/scripts/cleanup_cache.py --live\n"
        )
        sys.exit(0)

    # Live delete
    print("[LIVE] Deleting {} corrupted row(s) ...\n".format(len(corrupted_rows)))
    deleted_ids = []
    failed_ids = []

    for row, reasons in corrupted_rows:
        row_id = row.get("id")
        if not row_id:
            print("  [SKIP] Row has no id -- skipping (question={})".format(
                row.get("question", "")[:60]
            ))
            continue
        try:
            supabase.table("cached_answers").delete().eq("id", row_id).execute()
            deleted_ids.append(row_id)
            print("  [DELETED] {}  key={}".format(row_id, row.get("question", "")[:60]))
        except Exception as e:
            failed_ids.append(row_id)
            print("  [ERROR]   {}  -- {}".format(row_id, e))

    print()
    print("=" * 70)
    print("  CLEANUP COMPLETE")
    print("  Deleted  : {}".format(len(deleted_ids)))
    print("  Failed   : {}".format(len(failed_ids)))
    print("  Kept     : {}".format(len(clean_rows)))
    if failed_ids:
        print("\n  WARNING: {} row(s) could not be deleted:".format(len(failed_ids)))
        for fid in failed_ids:
            print("     {}".format(fid))
    print("=" * 70)

    if failed_ids:
        sys.exit(2)


if __name__ == "__main__":
    main()
