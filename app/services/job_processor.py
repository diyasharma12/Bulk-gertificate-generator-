import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app import database
from app.models import Job, Certificate, JobStatus, CertificateStatus
from app.config import settings
from app.services.generator import generate_certificate_pdf

logger = logging.getLogger(__name__)


def process_job(job_id: str, db: Optional[Session] = None) -> None:
    """
    Background worker task to process certificate generation for all recipients in a job.
    
    Fault-tolerant:
    - Isolates each certificate generation in a try-except block.
    - An error on one recipient does NOT halt generation for other recipients.
    - Continuously updates processed_count, success_count, and failure_count in the DB.
    - Sets final job status to COMPLETED, PARTIALLY_COMPLETED, or FAILED.
    """
    close_db = False
    if db is None:
        db = database.SessionLocal()
        close_db = True

    try:
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            logger.error(f"Job {job_id} not found for background processing.")
            return

        job.status = JobStatus.PROCESSING
        db.commit()

        # Fetch all pending certificates for this job
        certificates = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.PENDING,
            )
            .all()
        )

        job_storage_dir = settings.STORAGE_DIR / str(job.id)
        job_storage_dir.mkdir(parents=True, exist_ok=True)

        for cert in certificates:
            try:
                # Check for test simulation hook
                if cert.custom_attributes and cert.custom_attributes.get("simulate_failure"):
                    raise RuntimeError("Simulated failure for testing error resilience")

                # Validate recipient name sanity
                if not cert.recipient_name or not cert.recipient_name.strip():
                    raise ValueError("Recipient name is empty or invalid")

                output_path = job_storage_dir / f"{cert.id}.pdf"

                generate_certificate_pdf(
                    output_path=output_path,
                    certificate_id=cert.id,
                    recipient_name=cert.recipient_name,
                    recipient_email=cert.recipient_email,
                    title=job.title,
                    issuer_name=job.issuer_name,
                    issue_date=job.issue_date,
                    description=job.description,
                    custom_attributes=cert.custom_attributes,
                )

                if not output_path.exists() or output_path.stat().st_size == 0:
                    raise IOError("Generated certificate file is missing or zero bytes")

                cert.status = CertificateStatus.GENERATED
                cert.file_path = str(output_path.resolve())
                cert.file_size = output_path.stat().st_size
                cert.generated_at = datetime.utcnow()
                cert.error_reason = None

                job.success_count += 1

            except Exception as e:
                logger.warning(
                    f"Failed to generate certificate for recipient {cert.recipient_name} ({cert.id}): {e}"
                )
                cert.status = CertificateStatus.FAILED
                cert.error_reason = str(e)
                job.failure_count += 1

            job.processed_count += 1
            # Commit after each recipient to reflect real-time progress
            db.commit()

        # Update final job state
        if job.failure_count == 0 and job.success_count > 0:
            job.status = JobStatus.COMPLETED
        elif job.success_count > 0 and job.failure_count > 0:
            job.status = JobStatus.PARTIALLY_COMPLETED
        elif job.success_count == 0 and job.failure_count > 0:
            job.status = JobStatus.FAILED
        else:
            job.status = JobStatus.COMPLETED

        job.completed_at = datetime.utcnow()
        db.commit()
        logger.info(
            f"Job {job_id} completed: total={job.total_count}, "
            f"success={job.success_count}, failures={job.failure_count}, status={job.status}"
        )

    except Exception as e:
        logger.exception(f"Unexpected fatal error while processing job {job_id}: {e}")
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = f"Fatal job execution error: {str(e)}"
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        if close_db:
            db.close()
