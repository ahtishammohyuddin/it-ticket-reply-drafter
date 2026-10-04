"""Request and response models. These are the API contract."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    password_login = "password_login"
    access_request = "access_request"
    email = "email"
    network_vpn = "network_vpn"
    hardware = "hardware"
    software = "software"
    security = "security"
    other = "other"


class Priority(str, Enum):
    P1 = "P1"  # business stopped or security incident
    P2 = "P2"  # one person fully blocked
    P3 = "P3"  # degraded, a workaround exists
    P4 = "P4"  # request or question


class Tone(str, Enum):
    concise = "concise"
    detailed = "detailed"
    escalation = "escalation"


class TicketIn(BaseModel):
    subject: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=5, max_length=4000)
    customer_name: str | None = Field(default=None, max_length=80)


class Analysis(BaseModel):
    category: Category
    priority: Priority
    summary: str
    needs_escalation: bool
    escalation_reasons: list[str] = []


class Draft(BaseModel):
    tone: Tone
    subject: str
    body: str
    kb_ids: list[str] = []
    flags: list[str] = []     # guardrail findings for this draft
    blocked: bool = False     # true when a finding is serious enough to stop approval


class KBSource(BaseModel):
    id: str
    title: str
    score: float


class Redaction(BaseModel):
    type: str
    count: int


class DraftResponse(BaseModel):
    request_id: str
    analysis: Analysis
    drafts: list[Draft]
    kb_sources: list[KBSource]
    redactions: list[Redaction]
    redacted_ticket: str
    signals: list[str]
    provider: str
    model: str
    latency_ms: int
