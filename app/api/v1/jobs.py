import io
import zipfile
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Job, Certificate, JobStatus, CertificateStatus
from app.schemas import (
    JobCreateRequest,
    JobCreatedResponse,
    JobProgressResponse,
    JobDetailResponse,
    CertificateResponse,
)
from app.services.job_processor import process_job
from app.config import settings

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a bulk certificate generation job",
    description=(
        "Accepts a certificate generation request with a list of recipients. "
        "Validates input, initializes tracking records, and queues background processing."
    ),
)
def create_generation_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    if len(payload.recipients) > settings.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch size exceeds maximum allowed of {settings.MAX_BATCH_SIZE} recipients.",
        )

    # 1. Create the parent Job record
    job = Job(
        title=payload.title,
        issuer_name=payload.issuer_name,
        issue_date=payload.issue_date,
        description=payload.description,
        status=JobStatus.PENDING,
        total_count=len(payload.recipients),
        processed_count=0,
        success_count=0,
        failure_count=0,
    )
    db.add(job)
    db.flush()  # Obtain job.id before creating certificates

    # 2. Create pending Certificate records
    for recipient in payload.recipients:
        cert = Certificate(
            job_id=job.id,
            recipient_name=recipient.recipient_name,
            recipient_email=recipient.recipient_email,
            custom_attributes=recipient.custom_attributes,
            status=CertificateStatus.PENDING,
        )
        db.add(cert)

    db.commit()
    db.refresh(job)

    # 3. Dispatch processing as a background task
    background_tasks.add_task(process_job, job.id)

    base_url = str(request.base_url).rstrip("/")
    status_url = f"{base_url}{settings.API_V1_STR}/jobs/{job.id}"

    return JobCreatedResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count,
        message="Bulk certificate generation job queued successfully.",
        status_url=status_url,
    )


@router.get(
    "",
    response_model=List[JobProgressResponse],
    summary="List all certificate generation jobs",
)
def list_generation_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    request: Request = None,
    db: Session = Depends(get_db),
):
    jobs = db.query(Job).order_by(Job.created_at.desc()).offset(skip).limit(limit).all()
    base_url = str(request.base_url).rstrip("/") if request else ""

    results = []
    for job in jobs:
        progress = (
            round((job.processed_count / job.total_count) * 100.0, 1)
            if job.total_count > 0
            else 0.0
        )
        download_all_url = (
            f"{base_url}{settings.API_V1_STR}/jobs/{job.id}/download-all"
            if job.success_count > 0
            else None
        )
        results.append(
            JobProgressResponse(
                id=job.id,
                title=job.title,
                issuer_name=job.issuer_name,
                issue_date=job.issue_date,
                description=job.description,
                status=job.status,
                total_count=job.total_count,
                processed_count=job.processed_count,
                success_count=job.success_count,
                failure_count=job.failure_count,
                progress_percentage=progress,
                created_at=job.created_at,
                updated_at=job.updated_at,
                completed_at=job.completed_at,
                error_message=job.error_message,
                download_all_url=download_all_url,
            )
        )
    return results


@router.get(
    "/{job_id}",
    response_model=JobDetailResponse,
    summary="Get job progress, status, and recipient certificate details",
)
def get_job_detail(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    base_url = str(request.base_url).rstrip("/")
    progress = (
        round((job.processed_count / job.total_count) * 100.0, 1)
        if job.total_count > 0
        else 0.0
    )

    cert_responses = []
    for cert in job.certificates:
        download_url = (
            f"{base_url}{settings.API_V1_STR}/certificates/{cert.id}/download"
            if cert.status == CertificateStatus.GENERATED
            else None
        )
        cert_responses.append(
            CertificateResponse(
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
        )

    download_all_url = (
        f"{base_url}{settings.API_V1_STR}/jobs/{job.id}/download-all"
        if job.success_count > 0
        else None
    )

    return JobDetailResponse(
        id=job.id,
        title=job.title,
        issuer_name=job.issuer_name,
        issue_date=job.issue_date,
        description=job.description,
        status=job.status,
        total_count=job.total_count,
        processed_count=job.processed_count,
        success_count=job.success_count,
        failure_count=job.failure_count,
        progress_percentage=progress,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        download_all_url=download_all_url,
        certificates=cert_responses,
    )


@router.get(
    "/{job_id}/download-all",
    summary="Download all successfully generated certificates in a ZIP archive",
)
def download_all_certificates(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with ID '{job_id}' not found.",
        )

    generated_certs = (
        db.query(Certificate)
        .filter(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.GENERATED,
        )
        .all()
    )

    if not generated_certs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No certificates have been successfully generated for this job yet.",
        )

    # Create ZIP archive in the job's storage directory
    job_dir = settings.STORAGE_DIR / str(job.id)
    job_dir.mkdir(parents=True, exist_ok=True)
    zip_path = job_dir / "certificates_bundle.zip"

    # Sanitize title for filename
    clean_title = "".join(c for c in job.title if c.isalnum() or c in (" ", "-", "_")).strip()
    clean_title = clean_title.replace(" ", "_") or "certificates"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for cert in generated_certs:
            if cert.file_path and Path(cert.file_path).exists():
                # Format friendly filename inside the zip: "John_Doe_<cert_id>.pdf"
                safe_name = "".join(c for c in cert.recipient_name if c.isalnum() or c in ("-", "_", " ")).replace(" ", "_")
                arcname = f"{safe_name}_{cert.id[:8]}.pdf"
                zip_file.write(cert.file_path, arcname=arcname)

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"{clean_title}_certificates.zip",
    )
