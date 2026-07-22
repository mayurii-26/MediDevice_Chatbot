"""
admin/routes.py
─────────────────────────────────────────────────────────────────────────────
All admin API endpoints under a single FastAPI APIRouter.

Prefix : /admin
Tag    : admin

Auth endpoints (public):
  POST /admin/login
  GET  /admin/me

Dashboard:
  GET  /admin/dashboard/stats

Core modules (all paginated, all protected):
  GET  /admin/users              ?limit=20&offset=0
  GET  /admin/query-analytics    ?limit=20&offset=0
  GET  /admin/products           ?limit=20&offset=0
  GET  /admin/documents          ?limit=20&offset=0

Other (stubs, protected):
  GET  /admin/downloads          ?limit=20&offset=0
  GET  /admin/contact-requests   ?limit=20&offset=0
  GET  /admin/unknown-queries    ?limit=20&offset=0
  GET  /admin/conversations      ?limit=20&offset=0
  GET  /admin/ai-analytics
  GET  /admin/system-health

Every route except /admin/login requires a valid admin JWT via require_admin.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Literal

from .auth import require_admin, validate_admin_credentials, create_admin_token
from . import services

admin_router = APIRouter(prefix="/admin", tags=["admin"])

_PAGE_LIMIT_MAX = 200


# ── Request / Response models ──────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    token:   str
    message: str = "Login successful"


class AdminMeResponse(BaseModel):
    username: str
    role:     str


class ContactStatusUpdate(BaseModel):
    status: Literal["Pending", "In Progress", "Resolved"]


# ── Auth ───────────────────────────────────────────────────────────────────

@admin_router.post(
    "/login",
    response_model=AdminLoginResponse,
    summary="Admin login — returns a signed JWT on success",
)
def admin_login(body: AdminLoginRequest):
    if not validate_admin_credentials(body.username.strip(), body.password.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin username or password.",
        )
    return AdminLoginResponse(token=create_admin_token())


@admin_router.get(
    "/me",
    response_model=AdminMeResponse,
    summary="Return identity of the authenticated admin",
)
def admin_me(admin_payload: dict = Depends(require_admin)):
    return AdminMeResponse(
        username=admin_payload.get("sub", "admin"),
        role=admin_payload.get("role", "admin"),
    )


# ── Dashboard ──────────────────────────────────────────────────────────────

@admin_router.get(
    "/dashboard/stats",
    summary="Dashboard overview stat cards",
)
def dashboard_stats(_admin=Depends(require_admin)):
    """
    Returns:
      total_users, registered_users, guest_users,
      total_queries, today_queries,
      total_downloads, total_documents, contact_requests
    """
    return services.get_dashboard_stats()


# ── Users ──────────────────────────────────────────────────────────────────

@admin_router.get(
    "/users/stats",
    summary="Dashboard stat cards for the Users tab",
)
def users_stats(_admin=Depends(require_admin)):
    """
    Returns 4 stat card values:
      total_registered, guest_users, active_today, total_conversations
    """
    return services.get_users_stats()


@admin_router.get(
    "/users",
    summary="Paginated user list with activity stats",
)
def list_users(
    limit:  int = Query(default=20, ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    """
    Columns: user_id, email, signup_date, last_login,
             total_conversations, total_queries, documents_downloaded
    """
    return services.get_users(limit=limit, offset=offset)


# ── Query Analytics ────────────────────────────────────────────────────────

@admin_router.get(
    "/query-analytics",
    summary="Paginated query analytics from search logs + cached answers",
)
def query_analytics(
    limit:  int = Query(default=20, ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    """
    Columns: question, intent, times_asked, last_asked, answer_source
    Source: backend/logs/search_logs.txt + cached_answers table
    """
    return services.get_query_analytics(limit=limit, offset=offset)


# ── Products ───────────────────────────────────────────────────────────────

@admin_router.get(
    "/products",
    summary="Top-5 product analytics (by total queries)",
)
def list_products(
    limit:  int = Query(default=5,  ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    """
    Returns top-5 products sorted by total_queries DESC.
    Columns: product, total_queries, last_asked
    """
    return services.get_products(limit=limit, offset=offset)


@admin_router.get(
    "/products/all",
    summary="Full paginated product table (all products, all query counts)",
)
def list_all_products(
    limit:  int = Query(default=20, ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    """
    Full paginated product list sorted by total_queries DESC.
    Columns: product, total_queries, last_asked
    """
    return services.get_all_products(limit=limit, offset=offset)


@admin_router.get(
    "/products/catalog",
    summary="Complete product catalog from knowledge base with merged analytics",
)
def list_products_catalog(
    limit:  int = Query(default=20, ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    """
    ALL products from device_documents (the actual knowledge base),
    with query counts merged from analytics tables.
    Products never queried appear with count=0.

    Columns: product_name, category, total_queries, general_queries,
             specification_queries, feature_queries, comparison_queries,
             last_asked

    Sorted: total_queries DESC, then alphabetically.
    """
    return services.get_all_products_catalog(limit=limit, offset=offset)


# ── Documents ─────────────────────────────────────────────────────────────

@admin_router.get(
    "/documents",
    summary="Paginated document download analytics",
)
def list_documents(
    limit:  int = Query(default=20, ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    """
    Columns: document_name, download_count, unique_users, last_download
    Source: document_download_requests (downloaded=True)
    """
    return services.get_documents_admin(limit=limit, offset=offset)


# ── Downloads (raw requests) ───────────────────────────────────────────────

@admin_router.get(
    "/downloads",
    summary="Paginated raw download request list",
)
def list_downloads(
    limit:  int = Query(default=20, ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    return services.get_downloads(limit=limit, offset=offset)


# ── Contact Requests ───────────────────────────────────────────────────────

@admin_router.get(
    "/contact-requests",
    summary="Paginated contact form submissions with status",
)
def list_contact_requests(
    limit:  int = Query(default=20, ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    """
    Columns: id, name, email, phone, hospital, message, reason, status, created_at
    Source: contact_requests table (run contact_requests_migration.sql first)
    """
    return services.get_contact_requests(limit=limit, offset=offset)


@admin_router.patch(
    "/contact-requests/{request_id}/status",
    summary="Update the status of a contact request",
)
def update_contact_status(
    request_id: str,
    body: ContactStatusUpdate,
    _admin=Depends(require_admin),
):
    """
    Updates status to one of: Pending | In Progress | Resolved
    """
    try:
        updated = services.update_contact_request_status(request_id, body.status)
        return {"ok": True, "updated": updated}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))


# ── Unknown Queries ────────────────────────────────────────────────────────

@admin_router.get(
    "/unknown-queries",
    summary="Healthcare queries that could not be answered — from unanswered_queries table",
)
def list_unknown_queries(
    limit:  int = Query(default=20, ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    """
    Columns: id, query, user, date, times_asked, reason, status
    Source: unanswered_queries table (healthcare-only, deduplicated)
    Ordered: last_asked_at DESC
    """
    return services.get_unknown_queries(limit=limit, offset=offset)


class UnknownQueryStatusUpdate(BaseModel):
    status: Literal["Pending", "Reviewed", "Resolved"]


@admin_router.patch(
    "/unknown-queries/{query_id}/status",
    summary="Update triage status of an unanswered query",
)
def update_unknown_query_status(
    query_id: str,
    body: UnknownQueryStatusUpdate,
    _admin=Depends(require_admin),
):
    """
    Updates status to one of: Pending | Reviewed | Resolved
    """
    try:
        updated = services.update_unknown_query_status(query_id, body.status)
        return {"ok": True, "updated": updated}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except RuntimeError as re:
        raise HTTPException(status_code=500, detail=str(re))


# ── Conversations ──────────────────────────────────────────────────────────

@admin_router.get(
    "/conversations",
    summary="Paginated conversation list",
)
def list_conversations(
    limit:  int = Query(default=20, ge=1, le=_PAGE_LIMIT_MAX),
    offset: int = Query(default=0,  ge=0),
    _admin=Depends(require_admin),
):
    return services.get_conversations_admin(limit=limit, offset=offset)


# ── AI Analytics ──────────────────────────────────────────────────────────

@admin_router.get(
    "/ai-analytics",
    summary="Cache entries, query counts, fallback rate",
)
def ai_analytics(_admin=Depends(require_admin)):
    return services.get_ai_analytics()


# ── System Health ─────────────────────────────────────────────────────────

@admin_router.get(
    "/system-health",
    summary="Database connectivity health check",
)
def system_health(_admin=Depends(require_admin)):
    return services.get_system_health()
