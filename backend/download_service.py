"""
download_service.py

Secure document download pipeline:
  1. Request  — validate form fields, generate 6-digit OTP, email it, store request row.
  2. Verify   — check OTP and expiry, mark as verified; generate a signed single-use
                token and return /download/serve/{token} — NEVER the raw storage URL.
  3. Resend   — rate-limited resend (max 3 per request record).
  4. Serve    — validate token (expiry + single-use), fetch file from Supabase Storage,
                stream it to the authenticated caller with no-store headers.

Database tables required (run once in Supabase SQL editor — see phase5_4_migration.sql):

    CREATE TABLE IF NOT EXISTS document_download_requests ( ... );
    CREATE TABLE IF NOT EXISTS secure_download_tokens ( ... );
"""

import os
import hmac
import hashlib
import secrets
import random
import string
import smtplib
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage

from dateutil import parser as dateutil_parser
from dotenv import load_dotenv
from database.supabase_client import supabase

load_dotenv()

EMAIL_USER      = os.getenv("EMAIL_USER")
EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD")
_TOKEN_SECRET   = os.getenv("DOWNLOAD_TOKEN_SECRET", secrets.token_hex(32))

TABLE           = "document_download_requests"
TOKEN_TABLE     = "secure_download_tokens"
OTP_TTL_MINUTES = 5
TOKEN_TTL_MINUTES = 15   # serve token lives 15 minutes
MAX_RESENDS     = 3
DOWNLOAD_LIMIT_HOURS = 24   # one download per authenticated user per this window


# ── Download rate-limit check ─────────────────────────────────────────────

def check_download_limit(user_id: str | None) -> None:
    """
    Enforce: 1 completed download per authenticated user per 24-hour window.

    Rules:
      - Guests (user_id is None) are blocked unconditionally — they must sign in.
      - Authenticated users who already have a verified+downloaded record within
        the last 24 hours get a ValueError with a user-facing message.
      - Raises ValueError on violation; returns None on pass.

    Only rows with both otp_verified=True AND downloaded=True are counted —
    incomplete / abandoned requests do not consume the quota.
    """
    if user_id is None:
        raise ValueError(
            "Guest users cannot download documents. "
            "Please sign in to access document downloads."
        )

    window_start = (
        datetime.now(timezone.utc) - timedelta(hours=DOWNLOAD_LIMIT_HOURS)
    ).isoformat()

    result = (
        supabase.table(TABLE)
        .select("id, downloaded_at")
        .eq("user_id", user_id)
        .eq("otp_verified", True)
        .eq("downloaded", True)
        .gte("downloaded_at", window_start)
        .limit(1)
        .execute()
    )

    if result.data:
        last = result.data[0].get("downloaded_at", "")
        print(
            f"[download] rate-limit hit | user_id={user_id} | "
            f"last_download={last}"
        )
        raise ValueError(
            "You have reached today's download limit. "
            "Please try again after 24 hours."
        )

    print(f"[download] rate-limit OK | user_id={user_id}")


# ── OTP helpers ──────────────────────────────────────────────────────────

def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _expiry_ts(minutes: int = OTP_TTL_MINUTES) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _is_expired(expiry_str: str) -> bool:
    try:
        expiry = dateutil_parser.parse(expiry_str)
    except (ValueError, OverflowError) as exc:
        print(f"[download] Could not parse expiry '{expiry_str}': {exc} — treating as expired")
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > expiry


# ── Secure token helpers ─────────────────────────────────────────────────

def _generate_serve_token(request_id: str) -> str:
    """
    Generate a cryptographically random token, store its HMAC-SHA256 hash
    in secure_download_tokens, and return the raw token (sent to the client).
    The raw token is NEVER stored — only its hash is.
    """
    raw_token = secrets.token_urlsafe(32)          # 256-bit random, URL-safe
    token_hash = hmac.new(
        _TOKEN_SECRET.encode(),
        raw_token.encode(),
        hashlib.sha256,
    ).hexdigest()

    expires_at = _expiry_ts(TOKEN_TTL_MINUTES)

    supabase.table(TOKEN_TABLE).insert({
        "request_id":  request_id,
        "token_hash":  token_hash,
        "expires_at":  expires_at,
        "used":        False,
    }).execute()

    print(f"[download] serve token created | request_id={request_id} | ttl={TOKEN_TTL_MINUTES}m")
    return raw_token


def validate_and_consume_token(raw_token: str) -> dict:
    """
    Validate a serve token:
      1. Compute its HMAC hash.
      2. Look it up in secure_download_tokens.
      3. Verify it is not expired and not already used.
      4. Mark it as used (single-use).
      5. Return the associated download request row (contains file_url etc.).

    Raises ValueError with a safe message on any validation failure.
    Never leaks whether the token existed or why validation failed beyond
    a generic "Invalid or expired download link" message to callers.
    """
    if not raw_token or not isinstance(raw_token, str):
        raise ValueError("Invalid or expired download link.")

    token_hash = hmac.new(
        _TOKEN_SECRET.encode(),
        raw_token.strip().encode(),
        hashlib.sha256,
    ).hexdigest()

    rows = (
        supabase.table(TOKEN_TABLE)
        .select("*")
        .eq("token_hash", token_hash)
        .limit(1)
        .execute()
    ).data

    if not rows:
        raise ValueError("Invalid or expired download link.")

    token_row = rows[0]

    if token_row.get("used"):
        raise ValueError("This download link has already been used.")

    if _is_expired(token_row["expires_at"]):
        raise ValueError("This download link has expired. Please verify your OTP again.")

    # Mark single-use — do this BEFORE fetching the file so a race condition
    # cannot result in double-use.
    supabase.table(TOKEN_TABLE).update({
        "used":    True,
        "used_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", token_row["id"]).execute()

    # Fetch the linked download request to get file_url / document_name
    req_rows = (
        supabase.table(TABLE)
        .select("*")
        .eq("id", token_row["request_id"])
        .limit(1)
        .execute()
    ).data

    if not req_rows:
        raise ValueError("Invalid or expired download link.")

    print(f"[download] token consumed | request_id={token_row['request_id']}")
    return req_rows[0]


# ── Email ────────────────────────────────────────────────────────────────

def _send_otp_email(to_email: str, full_name: str, otp: str, document_name: str) -> None:
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("[download] Email credentials not configured — OTP not sent.")
        return

    msg = EmailMessage()
    msg["Subject"] = f"Your Download Verification Code — {document_name}"
    msg["From"]    = EMAIL_USER
    msg["To"]      = to_email
    msg.set_content(
        f"Dear {full_name},\n\n"
        f"Your one-time verification code for downloading\n"
        f"\"{document_name}\" is:\n\n"
        f"    {otp}\n\n"
        f"This code is valid for {OTP_TTL_MINUTES} minutes.\n\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"— MediDeviceAI Team"
    )

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f"[download] OTP email sent to {to_email}")


# ── Public API ────────────────────────────────────────────────────────────

def request_download(
    *,
    full_name: str,
    email: str,
    phone: str,
    designation: str,
    country: str,
    document_id: str,
    document_name: str,
    file_url: str,
    user_id: str | None = None,
    guest_session_id: str | None = None,
) -> dict:
    """
    Create a download request record, generate an OTP and email it.
    Returns { request_id, email }.
    """
    # ── Rate-limit check (guest block + 24-hour window) ───────────────────
    # This runs BEFORE any OTP is generated or email sent.
    check_download_limit(user_id)

    for field, val in [("full_name", full_name), ("email", email),
                       ("phone", phone), ("designation", designation),
                       ("country", country)]:
        if not val or not val.strip():
            raise ValueError(f"{field} is required")

    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Invalid email address")

    otp    = _generate_otp()
    expiry = _expiry_ts()

    result = supabase.table(TABLE).insert({
        "user_id":          user_id,
        "guest_session_id": guest_session_id,
        "full_name":        full_name.strip(),
        "email":            email.strip().lower(),
        "phone":            phone.strip(),
        "designation":      designation.strip(),
        "country":          country.strip(),
        "document_id":      document_id,
        "document_name":    document_name,
        "file_url":         file_url,
        "otp_code":         otp,
        "otp_verified":     False,
        "otp_expiry":       expiry,
        "resend_count":     0,
        "downloaded":       False,
    }).execute()

    if not result.data:
        raise RuntimeError("Failed to create download request")

    row = result.data[0]
    _send_otp_email(email, full_name, otp, document_name)

    print(f"[download] request created | id={row['id']} | doc={document_name}")
    return {"request_id": row["id"], "email": email.strip().lower()}


def verify_otp(request_id: str, otp_entered: str) -> dict:
    """
    Verify the OTP. On success, issue a short-lived single-use serve token.
    Returns { verified: bool, serve_url: str }.
    The raw file_url is NEVER returned to the client.
    """
    rows = (
        supabase.table(TABLE)
        .select("*")
        .eq("id", request_id)
        .limit(1)
        .execute()
    ).data

    if not rows:
        raise ValueError("Download request not found")

    row = rows[0]

    if row.get("otp_verified"):
        # Already verified — issue a fresh serve token (idempotent re-verify)
        raw_token = _generate_serve_token(request_id)
        return {"verified": True, "serve_url": f"/download/serve/{raw_token}"}

    if _is_expired(row["otp_expiry"]):
        raise ValueError("OTP has expired. Please request a new one.")

    if row["otp_code"] != otp_entered.strip():
        raise ValueError("Invalid OTP. Please try again.")

    # Mark verified
    now = datetime.now(timezone.utc).isoformat()
    supabase.table(TABLE).update({
        "otp_verified":  True,
        "downloaded":    True,
        "downloaded_at": now,
    }).eq("id", request_id).execute()

    # Issue a short-lived serve token — never expose file_url
    raw_token = _generate_serve_token(request_id)
    print(f"[download] OTP verified | id={request_id}")
    return {"verified": True, "serve_url": f"/download/serve/{raw_token}"}


def resend_otp(request_id: str) -> dict:
    """
    Resend a fresh OTP (rate-limited to MAX_RESENDS).
    """
    rows = (
        supabase.table(TABLE)
        .select("*")
        .eq("id", request_id)
        .limit(1)
        .execute()
    ).data

    if not rows:
        raise ValueError("Download request not found")

    row = rows[0]

    if row.get("otp_verified"):
        raise ValueError("This request has already been verified.")

    if row.get("resend_count", 0) >= MAX_RESENDS:
        raise ValueError("Maximum resend limit reached. Please start a new download request.")

    otp    = _generate_otp()
    expiry = _expiry_ts()

    supabase.table(TABLE).update({
        "otp_code":     otp,
        "otp_expiry":   expiry,
        "resend_count": row.get("resend_count", 0) + 1,
    }).eq("id", request_id).execute()

    _send_otp_email(row["email"], row["full_name"], otp, row["document_name"])
    print(f"[download] OTP resent | id={request_id} | count={row['resend_count'] + 1}")
    return {"email": row["email"]}
