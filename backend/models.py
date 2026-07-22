"""
models.py
Pydantic models for all FastAPI request and response schemas.
"""
from pydantic import BaseModel
from typing import Optional


class DocumentInfo(BaseModel):
    id: str
    product_name: str
    document_name: str
    document_type: Optional[str] = None
    file_url: str
    storage_path: Optional[str] = None


class ChatRequest(BaseModel):
    question: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    source: str = "faiss"
    matched_product: Optional[str] = None
    matched_category: str = "Unknown"
    conversation_id: Optional[str] = None
    confidence: float = 0.0
    documents: list[DocumentInfo] = []


class ContactRequest(BaseModel):
    name:            str
    email:           str
    message:         str
    phone:           Optional[str] = ""
    hospital:        Optional[str] = ""
    reason:          Optional[str] = "General Inquiry"
    address:         Optional[str] = ""
    submission_type: Optional[str] = "General Support"


class ContactResponse(BaseModel):
    message: str


# ── Download / OTP ──────────────────────────────────────────────────────────

class DownloadRequestBody(BaseModel):
    full_name:        str
    email:            str
    phone:            str
    designation:      str
    country:          str
    document_id:      str
    document_name:    str
    file_url:         str
    user_id:          Optional[str] = None
    guest_session_id: Optional[str] = None


class DownloadRequestResponse(BaseModel):
    request_id: str
    email:      str


class VerifyOtpBody(BaseModel):
    request_id: str
    otp:        str


class VerifyOtpResponse(BaseModel):
    verified:  bool
    serve_url: Optional[str] = None   # /download/serve/{token} — never the raw storage URL


class ResendOtpBody(BaseModel):
    request_id: str


class ResendOtpResponse(BaseModel):
    email: str


# ── User preferences (lightweight, for future personalisation) ──────────────

class UserPreferencesBody(BaseModel):
    preferred_category: Optional[str] = None
    recent_products:    Optional[list[str]] = None
    favorite_products:  Optional[list[str]] = None


class UserPreferencesResponse(BaseModel):
    user_id:            str
    preferred_category: Optional[str] = None
    recent_products:    list[str] = []
    favorite_products:  list[str] = []
    last_active:        Optional[str] = None

