"""
verify_migration.py
───────────────────
Run this script AFTER executing run_this_in_supabase_sql_editor.sql
in the Supabase Dashboard SQL Editor.

Usage:
    cd C:\\Users\\DELL\\MediDevice_Chatbot
    python verify_migration.py
"""

import os, sys, time, importlib.util, pathlib
sys.path.insert(0, "backend")
os.environ["PYTHONIOENCODING"] = "utf-8"

from dotenv import load_dotenv
load_dotenv()

from database.supabase_client import supabase

# Import analytics_logger directly (avoids importing admin routes needing jose)
_logger_path = pathlib.Path("backend/admin/analytics_logger.py")
_spec = importlib.util.spec_from_file_location("analytics_logger", _logger_path)
_mod  = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
log_unanswered_query = _mod.log_unanswered_query

# Import services directly
_svc_path = pathlib.Path("backend/admin/services.py")
_spec2 = importlib.util.spec_from_file_location("admin_services", _svc_path)
_mod2  = importlib.util.module_from_spec(_spec2)
_spec2.loader.exec_module(_mod2)
get_unknown_queries = _mod2.get_unknown_queries

PASS = "PASS"
FAIL = "FAIL"
results = []


def check(label, ok, detail=""):
    status = PASS if ok else FAIL
    results.append((status, label, detail))
    marker = "[PASS]" if ok else "[FAIL]"
    print(f"  {marker} {label}" + (f"  ->  {detail}" if detail else ""))


print()
print("=" * 62)
print("  MediDevice Migration Verification")
print("=" * 62)

# ── Task 1+2: table exists and PostgREST sees it ──────────────────────────
print()
print("TASK 1+2  Table exists & schema cache live")
try:
    r = supabase.table("unanswered_queries").select("id", count="exact").execute()
    check("unanswered_queries EXISTS", True, f"row count = {r.count or 0}")
    table_exists = True
except Exception as e:
    check("unanswered_queries EXISTS", False, str(e)[:100])
    table_exists = False

# ── Task 3: required columns ──────────────────────────────────────────────
print()
print("TASK 3  Required columns present")
REQUIRED_COLS = [
    "id", "query", "query_normalised", "user_id", "is_guest",
    "times_asked", "reason", "status",
    "first_asked_at", "last_asked_at", "updated_at",
]
if table_exists:
    try:
        supabase.table("unanswered_queries").select(", ".join(REQUIRED_COLS)).limit(1).execute()
        check("All required columns present", True, str(REQUIRED_COLS))
    except Exception as e:
        check("All required columns present", False, str(e)[:120])
else:
    check("All required columns present", False, "table does not exist yet")

# cached_answers.version
try:
    supabase.table("cached_answers").select("id, question, answer, version").limit(1).execute()
    check("cached_answers.version column present", True)
except Exception as e:
    if "version" in str(e):
        check("cached_answers.version column present", False,
              "run PART 3 of SQL migration")
    else:
        check("cached_answers.version column present", False, str(e)[:80])

# ── Task 4: INSERT ────────────────────────────────────────────────────────
print()
print("TASK 4  INSERT test via log_unanswered_query()")
TEST_QUERY = "What is CT Scan used for in diagnostics?"
TEST_NORM  = "what is ct scan used for in diagnostics"

if table_exists:
    # Clean up any previous test row
    try:
        supabase.table("unanswered_queries").delete().eq("query_normalised", TEST_NORM).execute()
    except Exception:
        pass
    time.sleep(0.3)

    log_unanswered_query(
        question=TEST_QUERY,
        answer_source="dynamic_search",
        user_id=None,
        is_guest=True,
        confidence=0.0,
        matched_product=None,
    )
    time.sleep(0.5)

    try:
        r = supabase.table("unanswered_queries") \
            .select("id, query, times_asked, reason, status") \
            .eq("query_normalised", TEST_NORM) \
            .limit(1).execute()
        if r.data:
            row = r.data[0]
            check("INSERT row stored", True,
                  f"times_asked={row['times_asked']} reason={row['reason']!r}")
            check("times_asked = 1", row["times_asked"] == 1,
                  f"actual={row['times_asked']}")
            check("reason = 'Web Search Response'",
                  row["reason"] == "Web Search Response",
                  f"actual={row['reason']!r}")
            check("status = 'Pending'", row["status"] == "Pending",
                  f"actual={row['status']!r}")
        else:
            check("INSERT row stored", False, "row not found after insert")
    except Exception as e:
        check("INSERT row stored", False, str(e)[:100])
else:
    check("INSERT row stored", False, "table does not exist — run SQL migration first")

# ── Task 5: DEDUP UPDATE ──────────────────────────────────────────────────
print()
print("TASK 5  Deduplication UPDATE (same query again)")

if table_exists:
    log_unanswered_query(
        question=TEST_QUERY,
        answer_source="dynamic_search",
        user_id=None,
        is_guest=True,
        confidence=0.0,
        matched_product=None,
    )
    time.sleep(0.5)

    try:
        r = supabase.table("unanswered_queries") \
            .select("id, times_asked") \
            .eq("query_normalised", TEST_NORM).execute()
        rows = r.data or []
        check("No duplicate row created", len(rows) == 1, f"row count = {len(rows)}")
        if rows:
            check("times_asked = 2", rows[0]["times_asked"] == 2,
                  f"actual={rows[0]['times_asked']}")
    except Exception as e:
        check("Dedup update", False, str(e)[:100])
else:
    check("Dedup update", False, "table does not exist")

# ── Task 6: Admin API ─────────────────────────────────────────────────────
print()
print("TASK 6  Admin API  get_unknown_queries()")

try:
    result = get_unknown_queries(limit=10, offset=0)
    row_count = len(result.get("rows", []))
    total     = result.get("total", 0)
    check("get_unknown_queries() returns rows", row_count > 0,
          f"rows={row_count}  total={total}")
    if row_count > 0:
        sample = result["rows"][0]
        print(f"    Sample row:")
        print(f"      query       = {sample['query'][:60]!r}")
        print(f"      user        = {sample['user']!r}")
        print(f"      times_asked = {sample['times_asked']}")
        print(f"      reason      = {sample['reason']!r}")
        print(f"      status      = {sample['status']!r}")
except Exception as e:
    check("get_unknown_queries() returns rows", False, str(e)[:100])

# ── Task 7: KB query NOT stored ───────────────────────────────────────────
print()
print("TASK 7  KB query should NOT be stored (source=faiss)")

if table_exists:
    try:
        before = supabase.table("unanswered_queries") \
            .select("id", count="exact").execute()
        before_count = before.count or 0

        log_unanswered_query(
            question="What are the specifications of PageWriter TC50?",
            answer_source="faiss",
            user_id=None,
            is_guest=True,
            confidence=1.0,
            matched_product="PageWriter TC50",
        )
        time.sleep(0.3)

        after = supabase.table("unanswered_queries") \
            .select("id", count="exact").execute()
        after_count = after.count or 0

        check("faiss query NOT stored", after_count == before_count,
              f"before={before_count}  after={after_count}")
    except Exception as e:
        check("faiss query NOT stored", False, str(e)[:100])
else:
    check("faiss query NOT stored", False, "table does not exist")

# ── Task 8: cached_answers no schema errors ───────────────────────────────
print()
print("TASK 8  cached_answers.version — no schema errors")
try:
    supabase.table("cached_answers").select("id, version").limit(1).execute()
    check("No version column schema error", True)
except Exception as e:
    check("No version column schema error", False, str(e)[:80])

# ── Clean up ──────────────────────────────────────────────────────────────
if table_exists:
    try:
        supabase.table("unanswered_queries").delete() \
            .eq("query_normalised", TEST_NORM).execute()
        print()
        print("  (test row cleaned up)")
    except Exception:
        pass

# ── Summary ────────────────────────────────────────────────────────────────
print()
print("=" * 62)
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
print(f"  RESULT  {passed} passed  /  {failed} failed  /  {len(results)} total")
if failed == 0:
    print("  STATUS  ALL CHECKS PASSED — migration successful")
else:
    print("  STATUS  CHECKS FAILED — action required:")
    for s, label, detail in results:
        if s == FAIL:
            print(f"    FAIL  {label}: {detail}")
    print()
    if not table_exists:
        print("  --> Run  run_this_in_supabase_sql_editor.sql  in Supabase Dashboard")
        print("      URL: https://supabase.com/dashboard/project/mykxoqthaqzimzjviyaq/sql/new")
print("=" * 62)
print()
