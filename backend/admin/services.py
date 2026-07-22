"""
admin/services.py
─────────────────────────────────────────────────────────────────────────────
Admin service layer — real Supabase queries for all 5 dashboard modules.

Tables used:
  auth.users                    — via Supabase Admin API (service role)
  conversations                 — (id, user_id, title, created_at)
  messages                      — (id, conversation_id, sender, content, created_at)
  cached_answers                — (id, question, answer, version, created_at)
  device_documents              — (id, product_name, category, subcategory,
                                    document_name, document_type, file_url,
                                    storage_path, is_active)
  document_download_requests    — (id, user_id, guest_session_id, full_name,
                                    email, document_id, document_name,
                                    otp_verified, downloaded, downloaded_at,
                                    created_at)
  user_preferences              — (user_id, last_active, created_at)

Note: Contact requests are email-only (no DB table). The count is always 0
      unless a contact_requests table is created in a future phase.
Note: Query analytics are derived from cached_answers + search_logs.txt file.
"""

import os
import re
from collections import defaultdict
from datetime import datetime, timezone, date

from database.supabase_client import supabase

_LOG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "logs", "search_logs.txt",
)


# ═══════════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _today_iso() -> str:
    return date.today().isoformat()


def _safe_int(val) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _parse_log_lines() -> list[dict]:
    """
    Parse backend/logs/search_logs.txt into a list of dicts.
    Each line format:
      [YYYY-MM-DD HH:MM:SS] SOURCE=x | CONFIDENCE=y | PRODUCT=z | CATEGORY=w | QUESTION=q
    Returns [] on any read error.
    """
    records = []
    if not os.path.exists(_LOG_FILE):
        return records
    pattern = re.compile(
        r"\[(?P<ts>[^\]]+)\]\s+"
        r"SOURCE=(?P<source>[^|]+)\s*\|\s*"
        r"CONFIDENCE=(?P<conf>[^|]+)\s*\|\s*"
        r"PRODUCT=(?P<product>[^|]+)\s*\|\s*"
        r"CATEGORY=(?P<category>[^|]+)\s*\|\s*"
        r"QUESTION=(?P<question>.+)"
    )
    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                m = pattern.match(line.strip())
                if m:
                    records.append({
                        "ts":       m.group("ts").strip(),
                        "source":   m.group("source").strip(),
                        "conf":     m.group("conf").strip(),
                        "product":  m.group("product").strip(),
                        "category": m.group("category").strip(),
                        "question": m.group("question").strip(),
                    })
    except Exception as exc:
        print(f"[admin/services] log parse error: {exc}")
    return records


# ═══════════════════════════════════════════════════════════════════════════
# 1. DASHBOARD STATS
# ═══════════════════════════════════════════════════════════════════════════

def get_dashboard_stats() -> dict:
    """
    Returns overview counts for the dashboard stat cards.

    Queries:
      SELECT COUNT(*) FROM query_logs                                → total_queries
      SELECT COUNT(*) FROM query_logs WHERE DATE(created_at)=today  → today_queries
      SELECT COUNT(*) FROM query_logs WHERE is_guest=true            → guest_users (approx)
      SELECT COUNT(DISTINCT user_id) FROM query_logs WHERE user_id IS NOT NULL → registered_users
      SELECT COUNT(*) FROM document_download_requests WHERE downloaded=true → total_downloads
      SELECT COUNT(*) FROM device_documents WHERE is_active=true    → total_documents
      SELECT COUNT(*) FROM contact_requests                          → contact_requests
    """
    stats = {
        "total_users":        0,
        "registered_users":   0,
        "guest_users":        0,
        "total_queries":      0,
        "today_queries":      0,
        "total_downloads":    0,
        "total_documents":    0,
        "contact_requests":   0,
    }

    try:
        r = supabase.table("query_logs").select("id", count="exact").execute()
        stats["total_queries"] = r.count or 0
    except Exception as e:
        print(f"[admin/stats] total_queries error: {e}")

    try:
        today = _today_iso()
        r = (supabase.table("query_logs")
             .select("id", count="exact")
             .gte("created_at", today)
             .execute())
        stats["today_queries"] = r.count or 0
    except Exception as e:
        print(f"[admin/stats] today_queries error: {e}")

    try:
        r = (supabase.table("query_logs")
             .select("user_id")
             .not_.is_("user_id", "null")
             .execute())
        unique_users = {row["user_id"] for row in (r.data or [])}
        stats["registered_users"] = len(unique_users)
    except Exception as e:
        print(f"[admin/stats] registered_users error: {e}")

    try:
        r = (supabase.table("query_logs")
             .select("id", count="exact")
             .eq("is_guest", True)
             .execute())
        stats["guest_users"] = r.count or 0
    except Exception as e:
        print(f"[admin/stats] guest_users error: {e}")

    try:
        r = (supabase.table("document_download_requests")
             .select("id", count="exact")
             .eq("downloaded", True)
             .execute())
        stats["total_downloads"] = r.count or 0
    except Exception as e:
        print(f"[admin/stats] total_downloads error: {e}")

    try:
        r = (supabase.table("device_documents")
             .select("id", count="exact")
             .eq("is_active", True)
             .execute())
        stats["total_documents"] = r.count or 0
    except Exception as e:
        print(f"[admin/stats] total_documents error: {e}")

    try:
        r = supabase.table("contact_requests").select("id", count="exact").execute()
        stats["contact_requests"] = r.count or 0
    except Exception as e:
        print(f"[admin/stats] contact_requests error: {e}")

    stats["total_users"] = stats["registered_users"] + stats["guest_users"]
    return stats


# ═══════════════════════════════════════════════════════════════════════════
# 2. USERS  — dashboard stat cards
# ═══════════════════════════════════════════════════════════════════════════

def get_users(limit: int = 20, offset: int = 0) -> dict:
    """
    Returns paginated user rows with activity stats.

    Strategy: conversations table is the source of registered users.
    For each unique user_id we compute:
      - total_conversations : COUNT(*) FROM conversations WHERE user_id=x
      - total_queries       : COUNT(*) FROM messages WHERE sender='user'
                              AND conversation_id IN (user's conversations)
      - documents_downloaded: COUNT(*) FROM document_download_requests
                              WHERE user_id=x AND downloaded=true

    user_preferences.last_active is used as "last login" approximation.

    Returns { rows: [...], total: int, limit: int, offset: int }
    """
    rows_out = []

    try:
        # Fetch all unique user_ids from conversations (no direct auth.users access)
        all_r = (supabase.table("conversations")
                 .select("user_id")
                 .not_.is_("user_id", "null")
                 .execute())
        all_user_ids = list({row["user_id"] for row in (all_r.data or [])})
        total = len(all_user_ids)

        # Apply pagination on the Python side (list of UUIDs)
        page_ids = all_user_ids[offset: offset + limit]

        for uid in page_ids:
            row = {"user_id": uid, "email": "—", "signup_date": "—",
                   "last_login": "—", "total_conversations": 0,
                   "total_queries": 0, "documents_downloaded": 0}

            # Conversations count + earliest created_at (signup proxy)
            c_r = (supabase.table("conversations")
                   .select("id, created_at")
                   .eq("user_id", uid)
                   .order("created_at")
                   .execute())
            conv_rows = c_r.data or []
            row["total_conversations"] = len(conv_rows)
            if conv_rows:
                row["signup_date"] = conv_rows[0]["created_at"]

            # Total user messages across all conversations
            conv_ids = [c["id"] for c in conv_rows]
            if conv_ids:
                m_r = (supabase.table("messages")
                       .select("id", count="exact")
                       .eq("sender", "user")
                       .in_("conversation_id", conv_ids)
                       .execute())
                row["total_queries"] = m_r.count or 0

            # Documents downloaded
            d_r = (supabase.table("document_download_requests")
                   .select("id", count="exact")
                   .eq("user_id", uid)
                   .eq("downloaded", True)
                   .execute())
            row["documents_downloaded"] = d_r.count or 0

            # Last active from user_preferences
            try:
                p_r = (supabase.table("user_preferences")
                       .select("last_active")
                       .eq("user_id", uid)
                       .limit(1)
                       .execute())
                if p_r.data:
                    row["last_login"] = p_r.data[0].get("last_active", "—")
            except Exception:
                pass

            rows_out.append(row)

    except Exception as e:
        print(f"[admin/users] error: {e}")
        return {"rows": [], "total": 0, "limit": limit, "offset": offset}

    return {"rows": rows_out, "total": total, "limit": limit, "offset": offset}


def get_users_stats() -> dict:
    """
    Returns 4 dashboard stat cards for the Users tab.

    Cards:
      total_registered  — distinct user_ids in conversations table
      guest_users       — rows in query_logs where is_guest=true (distinct sessions)
      active_today      — distinct user_ids in conversations with created_at >= today
      total_conversations — COUNT(*) FROM conversations

    Returns:
      {
        total_registered:   int,
        guest_users:        int,
        active_today:       int,
        total_conversations: int,
      }
    """
    stats = {
        "total_registered":    0,
        "guest_users":         0,
        "active_today":        0,
        "total_conversations": 0,
    }

    # ── Total registered: distinct non-null user_ids in conversations ───────
    try:
        r = (supabase.table("conversations")
             .select("user_id")
             .not_.is_("user_id", "null")
             .execute())
        stats["total_registered"] = len({row["user_id"] for row in (r.data or [])})
    except Exception as e:
        print(f"[admin/users_stats] total_registered error: {e}")

    # ── Guest users: distinct guest sessions from query_logs ────────────────
    try:
        r = (supabase.table("query_logs")
             .select("id", count="exact")
             .eq("is_guest", True)
             .execute())
        stats["guest_users"] = r.count or 0
    except Exception as e:
        print(f"[admin/users_stats] guest_users error: {e}")

    # ── Active today: distinct user_ids with a conversation started today ───
    try:
        today = _today_iso()
        r = (supabase.table("conversations")
             .select("user_id")
             .not_.is_("user_id", "null")
             .gte("created_at", today)
             .execute())
        stats["active_today"] = len({row["user_id"] for row in (r.data or [])})
    except Exception as e:
        print(f"[admin/users_stats] active_today error: {e}")

    # ── Also check query_logs for today's activity (covers guests too) ──────
    try:
        today = _today_iso()
        r = (supabase.table("query_logs")
             .select("user_id")
             .not_.is_("user_id", "null")
             .gte("created_at", today)
             .execute())
        from_queries = len({row["user_id"] for row in (r.data or [])})
        # Use the larger of the two counts
        stats["active_today"] = max(stats["active_today"], from_queries)
    except Exception as e:
        print(f"[admin/users_stats] active_today (query_logs) error: {e}")

    # ── Total conversations ─────────────────────────────────────────────────
    try:
        r = supabase.table("conversations").select("id", count="exact").execute()
        stats["total_conversations"] = r.count or 0
    except Exception as e:
        print(f"[admin/users_stats] total_conversations error: {e}")

    return stats



# ═══════════════════════════════════════════════════════════════════════════
# 3. QUERY ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

def get_query_analytics(limit: int = 20, offset: int = 0) -> dict:
    """
    Reads from query_logs table.

    DB query:
      SELECT question, intent, answer_source, created_at
      FROM query_logs ORDER BY created_at DESC

    Aggregates in Python: group by (normalised question + intent),
    count occurrences, record latest timestamp and source.

    Returns { rows: [...], total: int, limit: int, offset: int }
    """
    _SOURCE_LABEL = {
        "faiss":                        "Knowledge Base",
        "bm25":                         "Knowledge Base",
        "pdf":                          "Knowledge Base",
        "cache":                        "Cache",
        "wikipedia":                    "Dynamic Search",
        "dynamic_search":               "Dynamic Search",
        "gemini":                       "Gemini",
        "fallback_formatter":           "Medical Formatter",
        "fallback":                     "Fallback",
        "out_of_scope":                 "Fallback",
        "purchase_intent_guard":        "Filtered",
        "sample_report_intent_guard":   "Filtered",
    }

    try:
        r = (supabase.table("query_logs")
             .select("question, intent, answer_source, created_at")
             .order("created_at", desc=True)
             .execute())
        rows = r.data or []
    except Exception as e:
        print(f"[admin/query_analytics] DB error: {e}")
        rows = []

    agg: dict[str, dict] = {}
    for rec in rows:
        q   = (rec.get("question") or "").strip().lower()
        key = q
        if key not in agg:
            agg[key] = {
                "question":      rec.get("question", ""),
                "intent":        rec.get("intent", "unknown"),
                "times_asked":   0,
                "last_asked":    rec.get("created_at", ""),
                "answer_source": rec.get("answer_source", ""),
            }
        agg[key]["times_asked"] += 1
        if rec.get("created_at", "") > agg[key]["last_asked"]:
            agg[key]["last_asked"]    = rec.get("created_at", "")
            agg[key]["answer_source"] = rec.get("answer_source", "")

    rows_out = []
    for data in agg.values():
        src   = data["answer_source"].lower()
        label = _SOURCE_LABEL.get(src, data["answer_source"])
        intent_label = data["intent"].replace("_", " ").title()
        rows_out.append({
            "question":      data["question"],
            "intent":        intent_label,
            "times_asked":   data["times_asked"],
            "last_asked":    data["last_asked"],
            "answer_source": label,
        })

    rows_out.sort(key=lambda x: x["times_asked"], reverse=True)
    total = len(rows_out)
    return {"rows": rows_out[offset: offset + limit],
            "total": total, "limit": limit, "offset": offset}


# ═══════════════════════════════════════════════════════════════════════════
# 4. PRODUCTS  — based on actual chatbot usage via query_logs
# ═══════════════════════════════════════════════════════════════════════════

def get_products(limit: int = 20, offset: int = 0) -> dict:
    """
    Aggregates product query counts from query_logs.matched_product.

    Every question mentioning a product — regardless of intent (general query,
    comparison, specification, features) — increments that product's count
    because analytics_logger always writes matched_product to query_logs.

    Additionally merges search counts from product_search_logs for any product
    not already appearing in query_logs.

    Columns returned: product, total_queries, last_asked

    Top 5 by total_queries, sorted descending.

    Returns { rows: [...], total: int, limit: int, offset: int }
    """
    product_stats: dict[str, dict] = {}

    # ── Primary source: query_logs.matched_product ───────────────────────
    try:
        r = (supabase.table("query_logs")
             .select("matched_product, created_at")
             .not_.is_("matched_product", "null")
             .order("created_at", desc=True)
             .execute())

        for row in (r.data or []):
            prod = (row.get("matched_product") or "").strip()
            if not prod or prod in ("N/A", ""):
                continue
            ts = row.get("created_at", "")
            if prod not in product_stats:
                product_stats[prod] = {"total_queries": 0, "last_asked": ""}
            product_stats[prod]["total_queries"] += 1
            if ts > product_stats[prod]["last_asked"]:
                product_stats[prod]["last_asked"] = ts
    except Exception as e:
        print(f"[admin/products] query_logs error: {e}")

    # ── Secondary source: product_search_logs (fills gaps if query_logs empty) ──
    try:
        r = (supabase.table("product_search_logs")
             .select("product_name, search_count, last_searched")
             .execute())
        for row in (r.data or []):
            p = (row.get("product_name") or "").strip()
            if not p:
                continue
            if p not in product_stats:
                product_stats[p] = {
                    "total_queries": row.get("search_count", 0),
                    "last_asked":    row.get("last_searched", ""),
                }
            # If already in product_stats from query_logs, don't double-count —
            # query_logs is the authoritative source.
    except Exception as e:
        print(f"[admin/products] product_search_logs error: {e}")

    rows_out = []
    for prod, stats in product_stats.items():
        rows_out.append({
            "product":       prod,
            "total_queries": stats["total_queries"],
            "last_asked":    stats["last_asked"] or "—",
        })

    # Sort descending by total_queries, then by most recent last_asked
    rows_out.sort(key=lambda x: (x["total_queries"], x["last_asked"]), reverse=True)

    total = len(rows_out)
    # Always return top 5 for the Products tab display
    top_rows = rows_out[:5]
    page_rows = top_rows[offset: offset + limit]
    return {"rows": page_rows, "total": min(total, 5), "limit": limit, "offset": offset}


def get_all_products(limit: int = 20, offset: int = 0) -> dict:
    """
    Same data pipeline as get_products() but returns the FULL paginated list
    (not capped at 5).  Used for the 'All Products' table below the top-5 section.

    Columns: product, total_queries, last_asked
    Sorted:  total_queries DESC
    """
    product_stats: dict[str, dict] = {}

    try:
        r = (supabase.table("query_logs")
             .select("matched_product, created_at")
             .not_.is_("matched_product", "null")
             .order("created_at", desc=True)
             .execute())
        for row in (r.data or []):
            prod = (row.get("matched_product") or "").strip()
            if not prod or prod in ("N/A", ""):
                continue
            ts = row.get("created_at", "")
            if prod not in product_stats:
                product_stats[prod] = {"total_queries": 0, "last_asked": ""}
            product_stats[prod]["total_queries"] += 1
            if ts > product_stats[prod]["last_asked"]:
                product_stats[prod]["last_asked"] = ts
    except Exception as e:
        print(f"[admin/all_products] query_logs error: {e}")

    try:
        r = (supabase.table("product_search_logs")
             .select("product_name, search_count, last_searched")
             .execute())
        for row in (r.data or []):
            p = (row.get("product_name") or "").strip()
            if not p:
                continue
            if p not in product_stats:
                product_stats[p] = {
                    "total_queries": row.get("search_count", 0),
                    "last_asked":    row.get("last_searched", ""),
                }
    except Exception as e:
        print(f"[admin/all_products] product_search_logs error: {e}")

    rows_out = []
    for prod, stats in product_stats.items():
        rows_out.append({
            "product":       prod,
            "total_queries": stats["total_queries"],
            "last_asked":    stats["last_asked"] or "—",
        })

    rows_out.sort(key=lambda x: (x["total_queries"], x["last_asked"]), reverse=True)
    total = len(rows_out)
    return {"rows": rows_out[offset: offset + limit], "total": total,
            "limit": limit, "offset": offset}


def get_all_products_catalog(limit: int = 20, offset: int = 0) -> dict:
    """
    Returns ALL products from the knowledge base (device_documents table)
    with query analytics merged from query_logs.

    THIS is the source for the "All Products" section in the admin portal —
    NOT just products that have been queried.  Every product in the catalog
    appears here, with zero counts for those never queried.

    Columns:
      - product_name
      - category
      - total_queries       (from query_logs)
      - general_queries     (from query_logs where intent = 'product_query')
      - specification_queries (from query_logs where intent = 'specification_query')
      - feature_queries     (from query_logs where intent = 'feature_query')
      - comparison_queries  (from comparison_logs)
      - last_asked          (most recent query timestamp)

    Returns { rows: [...], total: int, limit: int, offset: int }
    """
    # ── Step 1: Fetch ALL distinct products from device_documents ──────────
    product_catalog: dict[str, dict] = {}
    try:
        r = (supabase.table("device_documents")
             .select("product_name, category")
             .eq("is_active", True)
             .execute())
        for row in (r.data or []):
            prod = (row.get("product_name") or "").strip()
            cat  = (row.get("category") or "Unknown").strip()
            if not prod:
                continue
            if prod not in product_catalog:
                product_catalog[prod] = {
                    "category":              cat,
                    "total_queries":         0,
                    "general_queries":       0,
                    "specification_queries": 0,
                    "feature_queries":       0,
                    "comparison_queries":    0,
                    "last_asked":            "",
                }
    except Exception as e:
        print(f"[admin/products_catalog] device_documents error: {e}")

    # ── Step 2: Aggregate query counts from query_logs by intent ───────────
    try:
        r = (supabase.table("query_logs")
             .select("matched_product, intent, created_at")
             .not_.is_("matched_product", "null")
             .execute())
        for row in (r.data or []):
            prod = (row.get("matched_product") or "").strip()
            if not prod or prod in ("N/A", ""):
                continue
            # Ensure product exists in catalog (some analytics may ref old products)
            if prod not in product_catalog:
                product_catalog[prod] = {
                    "category":              "Unknown",
                    "total_queries":         0,
                    "general_queries":       0,
                    "specification_queries": 0,
                    "feature_queries":       0,
                    "comparison_queries":    0,
                    "last_asked":            "",
                }
            intent = (row.get("intent") or "").lower()
            ts     = row.get("created_at", "")

            product_catalog[prod]["total_queries"] += 1

            if intent == "product_query":
                product_catalog[prod]["general_queries"] += 1
            elif intent == "specification_query":
                product_catalog[prod]["specification_queries"] += 1
            elif intent == "feature_query":
                product_catalog[prod]["feature_queries"] += 1
            elif intent == "comparison_query":
                product_catalog[prod]["comparison_queries"] += 1

            if ts > product_catalog[prod]["last_asked"]:
                product_catalog[prod]["last_asked"] = ts
    except Exception as e:
        print(f"[admin/products_catalog] query_logs aggregation error: {e}")

    # ── Step 3: Merge comparison counts from comparison_logs ──────────────
    try:
        r = supabase.table("comparison_logs").select("products_compared").execute()
        for row in (r.data or []):
            products_str = row.get("products_compared") or ""
            for prod in products_str.split(","):
                prod = prod.strip()
                if prod and prod in product_catalog:
                    product_catalog[prod]["comparison_queries"] += 1
    except Exception as e:
        print(f"[admin/products_catalog] comparison_logs error: {e}")

    # ── Step 4: Build output rows ─────────────────────────────────────────
    rows_out = []
    for prod, stats in product_catalog.items():
        rows_out.append({
            "product_name":           prod,
            "category":               stats["category"],
            "total_queries":          stats["total_queries"],
            "general_queries":        stats["general_queries"],
            "specification_queries":  stats["specification_queries"],
            "feature_queries":        stats["feature_queries"],
            "comparison_queries":     stats["comparison_queries"],
            "last_asked":             stats["last_asked"] or "—",
        })

    # Sort by total_queries DESC (most queried first), then alphabetically
    rows_out.sort(key=lambda x: (-x["total_queries"], x["product_name"]))

    total = len(rows_out)
    return {"rows": rows_out[offset: offset + limit], "total": total,
            "limit": limit, "offset": offset}


# ═══════════════════════════════════════════════════════════════════════════
# 5. DOCUMENTS
# ═══════════════════════════════════════════════════════════════════════════

def get_documents_admin(limit: int = 20, offset: int = 0) -> dict:
    """
    Returns per-document download analytics.

    Source: document_download_requests (downloaded=True rows) joined with
            device_documents for document metadata.

    For each unique document_name:
      - document_name   : name of the document
      - download_count  : total completed downloads
      - unique_users    : distinct user_ids (authenticated) + distinct emails
      - last_download   : most recent downloaded_at timestamp

    Returns { rows: [...], total: int, limit: int, offset: int }
    """
    doc_stats: dict[str, dict] = defaultdict(lambda: {
        "download_count": 0,
        "user_ids":       set(),
        "emails":         set(),
        "last_download":  "",
    })

    try:
        dl_r = (supabase.table("document_download_requests")
                .select("document_name, user_id, email, downloaded_at")
                .eq("downloaded", True)
                .execute())

        for row in (dl_r.data or []):
            name = row.get("document_name", "Unknown")
            doc_stats[name]["download_count"] += 1

            uid = row.get("user_id")
            if uid:
                doc_stats[name]["user_ids"].add(uid)
            email = row.get("email", "")
            if email:
                doc_stats[name]["emails"].add(email)

            dl_at = row.get("downloaded_at", "")
            if dl_at and dl_at > doc_stats[name]["last_download"]:
                doc_stats[name]["last_download"] = dl_at

    except Exception as e:
        print(f"[admin/documents] error: {e}")
        return {"rows": [], "total": 0, "limit": limit, "offset": offset}

    rows_out = []
    for doc_name, stats in doc_stats.items():
        unique = len(stats["user_ids"]) or len(stats["emails"])
        rows_out.append({
            "document_name":  doc_name,
            "download_count": stats["download_count"],
            "unique_users":   unique,
            "last_download":  stats["last_download"] or "—",
        })

    rows_out.sort(key=lambda x: x["download_count"], reverse=True)
    total = len(rows_out)
    return {"rows": rows_out[offset: offset + limit], "total": total,
            "limit": limit, "offset": offset}


# ═══════════════════════════════════════════════════════════════════════════
# DOWNLOADS  — full live table with all tracking columns
# ═══════════════════════════════════════════════════════════════════════════

def get_downloads(limit: int = 20, offset: int = 0) -> dict:
    """
    Returns paginated raw download request list with all tracking columns.

    Columns:
      full_name       — person who requested the download
      email           — their email address
      document_name   — name of the document
      product         — resolved from device_documents via document_id
      download_time   — downloaded_at (when OTP was verified and file served)
      otp_verified    — boolean
      status          — "Completed" if downloaded=true, "Pending OTP" otherwise

    Source: document_download_requests LEFT JOIN device_documents ON document_id

    Ordered: created_at DESC
    """
    try:
        r = (supabase.table("document_download_requests")
             .select(
                 "id, full_name, email, document_id, document_name, "
                 "created_at, downloaded_at, otp_verified, downloaded, "
                 "user_id"
             )
             .order("created_at", desc=True)
             .range(offset, offset + limit - 1)
             .execute())

        total_r = (supabase.table("document_download_requests")
                   .select("id", count="exact")
                   .execute())

        raw_rows = r.data or []

        # Resolve product names from device_documents in one batch call
        doc_ids = list({row["document_id"] for row in raw_rows if row.get("document_id")})
        product_map: dict[str, str] = {}
        if doc_ids:
            try:
                docs_r = (supabase.table("device_documents")
                          .select("id, product_name")
                          .in_("id", doc_ids)
                          .execute())
                for d in (docs_r.data or []):
                    product_map[d["id"]] = d.get("product_name", "—")
            except Exception as e:
                print(f"[admin/downloads] device_documents lookup error: {e}")

        rows_out = []
        for row in raw_rows:
            doc_id  = row.get("document_id") or ""
            product = product_map.get(doc_id, "—")

            # Determine status
            if row.get("downloaded"):
                status_label = "Completed"
            elif row.get("otp_verified"):
                status_label = "OTP Verified"
            else:
                status_label = "Pending OTP"

            rows_out.append({
                "id":            row.get("id", ""),
                "full_name":     row.get("full_name", "—"),
                "email":         row.get("email", "—"),
                "document_name": row.get("document_name", "—"),
                "product":       product,
                "download_time": row.get("downloaded_at") or row.get("created_at", "—"),
                "otp_verified":  bool(row.get("otp_verified", False)),
                "status":        status_label,
            })

        return {"rows": rows_out, "total": total_r.count or 0,
                "limit": limit, "offset": offset}

    except Exception as e:
        print(f"[admin/downloads] error: {e}")
        return {"rows": [], "total": 0, "limit": limit, "offset": offset}


# ═══════════════════════════════════════════════════════════════════════════
# 6. CONTACT REQUESTS  — all form types, all columns
# ═══════════════════════════════════════════════════════════════════════════

def get_contact_requests(limit: int = 20, offset: int = 0) -> dict:
    """
    Reads from contact_requests table.

    Columns: id, name, email, phone, hospital, address,
             message, reason, submission_type, status, created_at
    Ordered: created_at DESC (newest first)
    """
    try:
        r = (supabase.table("contact_requests")
             .select(
                 "id, name, email, phone, hospital, address, "
                 "message, reason, submission_type, status, created_at"
             )
             .order("created_at", desc=True)
             .range(offset, offset + limit - 1)
             .execute())
        total_r = supabase.table("contact_requests").select("id", count="exact").execute()
        return {"rows": r.data or [], "total": total_r.count or 0,
                "limit": limit, "offset": offset}
    except Exception as e:
        print(f"[admin/contact_requests] error (table may not exist yet): {e}")
        return {"rows": [], "total": 0, "limit": limit, "offset": offset}


def update_contact_request_status(request_id: str, status: str) -> dict:
    """
    PATCH a single contact_requests row's status field.
    Valid values: Pending | In Progress | Resolved
    """
    from datetime import datetime, timezone
    valid = {"Pending", "In Progress", "Resolved"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid}")
    try:
        r = (supabase.table("contact_requests")
             .update({
                 "status":     status,
                 "updated_at": datetime.now(timezone.utc).isoformat(),
             })
             .eq("id", request_id)
             .execute())
        if not r.data:
            raise ValueError(f"Contact request {request_id!r} not found.")
        return r.data[0]
    except Exception as e:
        raise RuntimeError(f"Failed to update status: {e}") from e


# ═══════════════════════════════════════════════════════════════════════════
# 7. UNKNOWN QUERIES  — reads from unanswered_queries table
# ═══════════════════════════════════════════════════════════════════════════

def get_unknown_queries(limit: int = 20, offset: int = 0) -> dict:
    """
    Reads from unanswered_queries table (created by unanswered_queries_migration.sql).

    Only healthcare-domain queries that could not be answered are stored here.
    Off-topic queries (weather, sports, movies) are excluded at write-time by
    the healthcare gate in analytics_logger.log_unanswered_query().

    Columns returned per row:
      id, query, user_id, is_guest, times_asked, reason, status,
      first_asked_at, last_asked_at

    Ordered: last_asked_at DESC (most recently asked first)
    """
    try:
        r = (supabase.table("unanswered_queries")
             .select(
                 "id, query, user_id, is_guest, times_asked, "
                 "reason, status, first_asked_at, last_asked_at"
             )
             .order("last_asked_at", desc=True)
             .range(offset, offset + limit - 1)
             .execute())

        total_r = (supabase.table("unanswered_queries")
                   .select("id", count="exact")
                   .execute())

        rows_out = []
        for rec in (r.data or []):
            uid = rec.get("user_id")
            if uid:
                user_label = f"{str(uid)[:8]}…"
            elif rec.get("is_guest"):
                user_label = "Guest"
            else:
                user_label = "Unknown"

            rows_out.append({
                "id":           rec.get("id", ""),
                "query":        rec.get("query", ""),
                "user":         user_label,
                "date":         rec.get("last_asked_at", ""),
                "times_asked":  rec.get("times_asked", 1),
                "reason":       rec.get("reason", "No Knowledge Match"),
                "status":       rec.get("status", "Pending"),
            })

        return {"rows": rows_out, "total": total_r.count or 0,
                "limit": limit, "offset": offset}

    except Exception as e:
        print(f"[admin/unknown_queries] DB error (table may not exist yet): {e}")
        return {"rows": [], "total": 0, "limit": limit, "offset": offset}


def update_unknown_query_status(query_id: str, status: str) -> dict:
    """
    PATCH a single unanswered_queries row's status field.
    Valid values: Pending | Reviewed | Resolved
    """
    from datetime import datetime, timezone
    valid = {"Pending", "Reviewed", "Resolved"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {valid}")
    try:
        r = (supabase.table("unanswered_queries")
             .update({
                 "status":     status,
                 "updated_at": datetime.now(timezone.utc).isoformat(),
             })
             .eq("id", query_id)
             .execute())
        if not r.data:
            raise ValueError(f"Query {query_id!r} not found.")
        return r.data[0]
    except Exception as e:
        raise RuntimeError(f"Failed to update status: {e}") from e


# ═══════════════════════════════════════════════════════════════════════════
# 8. CONVERSATIONS
# ═══════════════════════════════════════════════════════════════════════════

def get_conversations_admin(limit: int = 20, offset: int = 0) -> dict:
    """
    Returns paginated conversations with enriched columns.

    Columns:
      id, user_id, title, created_at (start_time),
      last_activity  — max(created_at) from messages in this conversation,
      total_messages — count of messages,
      user_type      — 'Registered' if user_id present, else 'Guest'

    DB queries:
      SELECT id, user_id, title, created_at FROM conversations ORDER BY created_at DESC
      SELECT conversation_id, COUNT(*), MAX(created_at) FROM messages GROUP BY conversation_id
    """
    try:
        # Fetch paginated conversation rows
        conv_r = (supabase.table("conversations")
                  .select("id, user_id, title, created_at")
                  .order("created_at", desc=True)
                  .range(offset, offset + limit - 1)
                  .execute())
        total_r = supabase.table("conversations").select("id", count="exact").execute()
        convs   = conv_r.data or []
        total   = total_r.count or 0

        if not convs:
            return {"rows": [], "total": 0, "limit": limit, "offset": offset}

        # Fetch message stats for these conversation IDs in one query
        conv_ids = [c["id"] for c in convs]
        msg_r = (supabase.table("messages")
                 .select("conversation_id, created_at")
                 .in_("conversation_id", conv_ids)
                 .execute())
        msg_rows = msg_r.data or []

        # Aggregate: count + last activity per conversation_id
        msg_stats: dict[str, dict] = {}
        for m in msg_rows:
            cid = m["conversation_id"]
            if cid not in msg_stats:
                msg_stats[cid] = {"count": 0, "last": ""}
            msg_stats[cid]["count"] += 1
            if m["created_at"] > msg_stats[cid]["last"]:
                msg_stats[cid]["last"] = m["created_at"]

        rows_out = []
        for c in convs:
            cid   = c["id"]
            stats = msg_stats.get(cid, {"count": 0, "last": c["created_at"]})
            rows_out.append({
                "id":             cid,
                "user_id":        c.get("user_id") or "—",
                "title":          c.get("title") or "Untitled",
                "start_time":     c.get("created_at", "—"),
                "last_activity":  stats["last"] or c.get("created_at", "—"),
                "total_messages": stats["count"],
                "user_type":      "Registered" if c.get("user_id") else "Guest",
            })

        return {"rows": rows_out, "total": total, "limit": limit, "offset": offset}

    except Exception as e:
        print(f"[admin/conversations] error: {e}")
        return {"rows": [], "total": 0, "limit": limit, "offset": offset}


# ═══════════════════════════════════════════════════════════════════════════
# 9. AI ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

def get_ai_analytics() -> dict:
    """
    Reads from query_logs — counts rows by answer_source.

    DB query:
      SELECT answer_source, COUNT(*) FROM query_logs GROUP BY answer_source

    Maps sources to 6 display categories and returns table rows.
    """
    _BUCKET = {
        "faiss":                        "Knowledge Base Responses",
        "bm25":                         "Knowledge Base Responses",
        "pdf":                          "Knowledge Base Responses",
        "cache":                        "Cache Responses",
        "wikipedia":                    "Dynamic Search Responses",
        "dynamic_search":               "Dynamic Search Responses",
        "gemini":                       "Gemini Responses",
        "fallback_formatter":           "Medical Formatter Responses",
        "refiner":                      "Medical Formatter Responses",
        "fallback":                     "Fallback Responses",
        "out_of_scope":                 "Fallback Responses",
        "purchase_intent_guard":        "Fallback Responses",
        "sample_report_intent_guard":   "Fallback Responses",
    }

    counts: dict[str, int] = {
        "Knowledge Base Responses":    0,
        "Cache Responses":             0,
        "Gemini Responses":            0,
        "Dynamic Search Responses":    0,
        "Medical Formatter Responses": 0,
        "Fallback Responses":          0,
    }

    try:
        r = supabase.table("query_logs").select("answer_source").execute()
        for row in (r.data or []):
            src    = (row.get("answer_source") or "").lower().strip()
            bucket = _BUCKET.get(src, "Fallback Responses")
            counts[bucket] += 1
    except Exception as e:
        print(f"[admin/ai_analytics] DB error: {e}")

    total_queries = sum(counts.values())
    rows = [
        {
            "response_type": label,
            "count":         cnt,
            "percentage":    f"{cnt / total_queries * 100:.1f}%" if total_queries else "0%",
        }
        for label, cnt in counts.items()
    ]
    return {"rows": rows, "total_queries": total_queries}

    total_queries = len(logs)
    rows = [
        {
            "response_type": label,
            "count":         cnt,
            "percentage":    f"{cnt / total_queries * 100:.1f}%" if total_queries else "0%",
        }
        for label, cnt in counts.items()
    ]

    return {
        "rows":          rows,
        "total_queries": total_queries,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 10. SYSTEM HEALTH
# ═══════════════════════════════════════════════════════════════════════════

def get_system_health() -> dict:
    """
    Performs live health checks for each subsystem and returns a list of
    rows for table display.

    Checks:
      Supabase DB   — simple SELECT on cached_answers
      FAISS Index   — check vector_db/faiss_index.bin file exists and size > 0
      BM25 Index    — check rank_bm25 package is importable
      Storage       — SELECT on device_documents (storage proxy)
      Gemini API    — check GEMINI_API_KEY_1 env var is set
      Response Time — measure Supabase round-trip in ms
    """
    import time

    _HERE        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _FAISS_PATH  = os.path.join(_HERE, "vector_db", "faiss_index.bin")

    results = []

    # ── Supabase DB ──────────────────────────────────────────────────────
    t0 = time.monotonic()
    try:
        supabase.table("cached_answers").select("id").limit(1).execute()
        ms = round((time.monotonic() - t0) * 1000)
        results.append({
            "service":       "Supabase DB",
            "status":        "Operational",
            "status_code":   "ok",
            "response_time": f"{ms} ms",
            "detail":        "Connection successful",
        })
    except Exception as exc:
        results.append({
            "service":       "Supabase DB",
            "status":        "Degraded",
            "status_code":   "degraded",
            "response_time": "—",
            "detail":        str(exc)[:120],
        })

    # ── FAISS Index ──────────────────────────────────────────────────────
    try:
        size = os.path.getsize(_FAISS_PATH) if os.path.exists(_FAISS_PATH) else 0
        if size > 0:
            results.append({
                "service":       "FAISS Index",
                "status":        "Operational",
                "status_code":   "ok",
                "response_time": "—",
                "detail":        f"Index file: {size // 1024} KB",
            })
        else:
            results.append({
                "service":       "FAISS Index",
                "status":        "Down",
                "status_code":   "down",
                "response_time": "—",
                "detail":        "faiss_index.bin not found or empty",
            })
    except Exception as exc:
        results.append({
            "service":       "FAISS Index",
            "status":        "Down",
            "status_code":   "down",
            "response_time": "—",
            "detail":        str(exc)[:120],
        })

    # ── BM25 ─────────────────────────────────────────────────────────────
    try:
        import rank_bm25  # noqa: F401
        results.append({
            "service":       "BM25 Index",
            "status":        "Operational",
            "status_code":   "ok",
            "response_time": "—",
            "detail":        f"rank_bm25 v{rank_bm25.__version__ if hasattr(rank_bm25, '__version__') else 'loaded'}",
        })
    except Exception as exc:
        results.append({
            "service":       "BM25 Index",
            "status":        "Down",
            "status_code":   "down",
            "response_time": "—",
            "detail":        str(exc)[:120],
        })

    # ── Storage (device_documents proxy) ─────────────────────────────────
    try:
        r = supabase.table("device_documents").select("id", count="exact").execute()
        doc_count = r.count or 0
        results.append({
            "service":       "Storage",
            "status":        "Operational",
            "status_code":   "ok",
            "response_time": "—",
            "detail":        f"{doc_count} documents indexed",
        })
    except Exception as exc:
        results.append({
            "service":       "Storage",
            "status":        "Degraded",
            "status_code":   "degraded",
            "response_time": "—",
            "detail":        str(exc)[:120],
        })

    # ── Gemini API ────────────────────────────────────────────────────────
    gemini_key = os.getenv("GEMINI_API_KEY_1", "")
    if gemini_key:
        results.append({
            "service":       "Gemini API",
            "status":        "Operational",
            "status_code":   "ok",
            "response_time": "—",
            "detail":        "API key configured",
        })
    else:
        results.append({
            "service":       "Gemini API",
            "status":        "Down",
            "status_code":   "down",
            "response_time": "—",
            "detail":        "GEMINI_API_KEY_1 not set",
        })

    # ── Overall response time (re-use Supabase ms from above) ────────────
    supabase_row = next((r for r in results if r["service"] == "Supabase DB"), None)
    db_rt = supabase_row["response_time"] if supabase_row else "—"

    results.append({
        "service":       "Response Time",
        "status":        "Operational" if db_rt != "—" else "Unknown",
        "status_code":   "ok" if db_rt != "—" else "unknown",
        "response_time": db_rt,
        "detail":        "DB round-trip latency",
    })

    overall = "ok" if all(r["status_code"] == "ok" for r in results) else "degraded"
    return {"rows": results, "overall": overall}
