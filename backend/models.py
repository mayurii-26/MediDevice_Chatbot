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
    name: str
    email: str
    message: str


class ContactResponse(BaseModel):
    message: str
