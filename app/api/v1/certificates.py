from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, CertificateStatus
from app.schemas import CertificateResponse, CertificateVerificationResponse
from app.config import settings

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.get(
    "/{certificate_id}",
    response_model=CertificateResponse,
    summary="Get single certificate details and metadata",
)
def get_certificate_detail(
    certificate_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate with ID '{certificate_id}' not found.",
        )

    base_url = str(request.base_url).rstrip("/")
    download_url = (
        f"{base_url}{settings.API_V1_STR}/certificates/{cert.id}/download"
        if cert.status == CertificateStatus.GENERATED
        else None
    )

    return CertificateResponse(
        id=cert.id,
        job_id=cert.job_id,
        recipient_name=cert.recipient_name,
        recipient_email=cert.recipient_email,
        custom_attributes=cert.custom_attributes,
        status=cert.status,
        file_path=cert.file_path,
        file_size=cert.file_size,
        error_reason=cert.error_reason,
        created_at=cert.created_at,
        generated_at=cert.generated_at,
        download_url=download_url,
    )


@router.get(
    "/{certificate_id}/download",
    summary="Download generated certificate PDF file",
)
def download_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
):
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate with ID '{certificate_id}' not found.",
        )

    if cert.status != CertificateStatus.GENERATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Certificate status is '{cert.status}'. "
                + (f"Reason: {cert.error_reason}" if cert.error_reason else "Generation has not finished.")
            ),
        )

    if not cert.file_path or not Path(cert.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate file is missing from server storage.",
        )

    safe_name = "".join(c for c in cert.recipient_name if c.isalnum() or c in ("-", "_", " ")).replace(" ", "_")
    filename = f"Certificate_{safe_name}_{cert.id[:8]}.pdf"

    return FileResponse(
        path=cert.file_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.get(
    "/verify/{certificate_id}",
    response_model=CertificateVerificationResponse,
    summary="Public verification endpoint to authenticate a certificate",
)
def verify_certificate(
    certificate_id: str,
    db: Session = Depends(get_db),
):
    cert = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        return CertificateVerificationResponse(
            certificate_id=certificate_id,
            is_valid=False,
            status=CertificateStatus.FAILED,
            verification_message="No record found for this certificate ID. Certificate is invalid or unrecognized.",
        )

    if cert.status != CertificateStatus.GENERATED:
        return CertificateVerificationResponse(
            certificate_id=certificate_id,
            is_valid=False,
            recipient_name=cert.recipient_name,
            status=cert.status,
            verification_message=f"Certificate is in state '{cert.status}' and has not been officially generated.",
        )

    job = cert.job
    return CertificateVerificationResponse(
        certificate_id=cert.id,
        is_valid=True,
        recipient_name=cert.recipient_name,
        course_title=job.title if job else None,
        issuer_name=job.issuer_name if job else None,
        issue_date=str(job.issue_date) if job and job.issue_date else None,
        status=cert.status,
        generated_at=cert.generated_at,
        verification_message="Official Certificate Verified: This certificate was legitimately issued and registered.",
    )
