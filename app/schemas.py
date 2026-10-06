import re
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.models import JobStatus, CertificateStatus


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class RecipientInput(BaseModel):
    recipient_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of the certificate recipient",
        examples=["Ada Lovelace"],
    )
    recipient_email: str = Field(
        ...,
        description="Valid email address of the recipient",
        examples=["ada.lovelace@example.com"],
    )
    custom_attributes: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional recipient-specific key-value attributes (e.g. grade, specialization, rank)",
        examples=[{"grade": "Distinction", "role": "Speaker"}],
    )

    @field_validator("recipient_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Recipient name cannot be empty or whitespace only")
        return trimmed

    @field_validator("recipient_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed or not EMAIL_REGEX.match(trimmed):
            raise ValueError(f"Invalid email address: '{v}'")
        return trimmed.lower()


class JobCreateRequest(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Title of the course, event, or workshop",
        examples=["Advanced Machine Learning Specialization"],
    )
    issuer_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the issuing organization or authority",
        examples=["DeepMind Academy"],
    )
    issue_date: Optional[date] = Field(
        default_factory=date.today,
        description="Date of issuance (defaults to today)",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional certificate description or statement of achievement",
        examples=["In recognition of outstanding completion of the program."],
    )
    recipients: List[RecipientInput] = Field(
        ...,
        min_length=1,
        description="List of recipients to generate certificates for (bulk)",
    )

    @field_validator("title", "issuer_name")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Field cannot be empty or whitespace only")
        return trimmed

    @field_validator("recipients")
    @classmethod
    def validate_recipients_non_empty(cls, v: List[RecipientInput]) -> List[RecipientInput]:
        if not v:
            raise ValueError("Recipients list cannot be empty")
        return v


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    recipient_name: str
    recipient_email: str
    custom_attributes: Optional[Dict[str, Any]] = None
    status: CertificateStatus
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    error_reason: Optional[str] = None
    created_at: datetime
    generated_at: Optional[datetime] = None
    download_url: Optional[str] = None


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus
    total_count: int
    message: str
    status_url: str


class JobProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    issuer_name: str
    issue_date: date
    description: Optional[str] = None
    status: JobStatus
    total_count: int
    processed_count: int
    success_count: int
    failure_count: int
    progress_percentage: float
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    download_all_url: Optional[str] = None


class JobDetailResponse(JobProgressResponse):
    certificates: List[CertificateResponse]


class CertificateVerificationResponse(BaseModel):
    certificate_id: str
    is_valid: bool
    recipient_name: Optional[str] = None
    course_title: Optional[str] = None
    issuer_name: Optional[str] = None
    issue_date: Optional[str] = None
    status: CertificateStatus
    generated_at: Optional[datetime] = None
    verification_message: str
