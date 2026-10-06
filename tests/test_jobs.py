import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Job, Certificate, JobStatus, CertificateStatus
from app.services.job_processor import process_job


def test_create_generation_job_success(client: TestClient):
    """Test successful creation and queuing of a bulk certificate generation job."""
    payload = {
        "title": "Full-Stack AI Engineering",
        "issuer_name": "Google Developers Group",
        "description": "Graduation Certificate for 2026 cohort.",
        "recipients": [
            {"recipient_name": "Alice Smith", "recipient_email": "alice@example.com"},
            {"recipient_name": "Bob Jones", "recipient_email": "bob@example.com"},
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()

    assert "job_id" in data
    assert data["status"] == "PENDING"
    assert data["total_count"] == 2
    assert f"/api/v1/jobs/{data['job_id']}" in data["status_url"]


def test_input_validation_empty_recipients(client: TestClient):
    """Test validation fails when recipient list is empty."""
    payload = {
        "title": "Python Bootcamp",
        "issuer_name": "Codecademy",
        "recipients": [],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_input_validation_invalid_email(client: TestClient):
    """Test validation fails on malformed recipient email."""
    payload = {
        "title": "Python Bootcamp",
        "issuer_name": "Codecademy",
        "recipients": [
            {"recipient_name": "Charlie Brown", "recipient_email": "not-an-email"},
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422
    err_msg = str(response.json()["detail"])
    assert "Invalid email address" in err_msg


def test_input_validation_blank_name(client: TestClient):
    """Test validation fails when recipient name is only spaces."""
    payload = {
        "title": "Python Bootcamp",
        "issuer_name": "Codecademy",
        "recipients": [
            {"recipient_name": "   ", "recipient_email": "charlie@example.com"},
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422
    err_msg = str(response.json()["detail"])
    assert "cannot be empty or whitespace only" in err_msg


def test_input_validation_blank_title(client: TestClient):
    """Test validation fails when job title is blank."""
    payload = {
        "title": "   ",
        "issuer_name": "Codecademy",
        "recipients": [
            {"recipient_name": "Charlie Brown", "recipient_email": "charlie@example.com"},
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == 422


def test_job_processing_and_progress_tracking(client: TestClient, db_session: Session):
    """Test end-to-end processing and progress tracking for a multi-recipient job."""
    payload = {
        "title": "Cloud Architecture Masterclass",
        "issuer_name": "Cloud Native Foundation",
        "recipients": [
            {"recipient_name": "David Miller", "recipient_email": "david@cloud.org"},
            {"recipient_name": "Eva Rostova", "recipient_email": "eva@cloud.org"},
            {"recipient_name": "Frank Castle", "recipient_email": "frank@cloud.org"},
        ],
    }

    create_res = client.post("/api/v1/jobs", json=payload)
    assert create_res.status_code == 202
    job_id = create_res.json()["job_id"]

    # Execute processing worker
    process_job(job_id)

    # Check job status and recipient details
    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == 200
    job_data = status_res.json()

    assert job_data["status"] == "COMPLETED"
    assert job_data["total_count"] == 3
    assert job_data["processed_count"] == 3
    assert job_data["success_count"] == 3
    assert job_data["failure_count"] == 0
    assert job_data["progress_percentage"] == 100.0
    assert job_data["completed_at"] is not None
    assert job_data["download_all_url"] is not None

    certs = job_data["certificates"]
    assert len(certs) == 3
    for cert in certs:
        assert cert["status"] == "GENERATED"
        assert cert["file_path"] is not None
        assert cert["file_size"] > 0
        assert cert["download_url"] is not None
        assert cert["error_reason"] is None


def test_individual_certificate_failure_does_not_halt_batch(client: TestClient, db_session: Session):
    """
    Critical Requirement Test:
    A failure while generating one certificate should NOT prevent other valid certificates
    in the same job from being generated.
    """
    payload = {
        "title": "Resilience and Fault Tolerance",
        "issuer_name": "Reliability Engineering Org",
        "recipients": [
            {
                "recipient_name": "Grace Hopper",
                "recipient_email": "grace@navy.mil",
            },
            {
                "recipient_name": "Faulty Recipient",
                "recipient_email": "faulty@broken.org",
                "custom_attributes": {"simulate_failure": True},
            },
            {
                "recipient_name": "Linus Torvalds",
                "recipient_email": "linus@kernel.org",
            },
        ],
    }

    create_res = client.post("/api/v1/jobs", json=payload)
    assert create_res.status_code == 202
    job_id = create_res.json()["job_id"]

    # Execute processor
    process_job(job_id)

    # Fetch status
    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == 200
    job_data = status_res.json()

    # The overall job should be PARTIALLY_COMPLETED
    assert job_data["status"] == "PARTIALLY_COMPLETED"
    assert job_data["total_count"] == 3
    assert job_data["processed_count"] == 3
    assert job_data["success_count"] == 2
    assert job_data["failure_count"] == 1
    assert job_data["progress_percentage"] == 100.0

    certs = {c["recipient_name"]: c for c in job_data["certificates"]}

    # Grace Hopper and Linus Torvalds succeeded despite the middle recipient failure
    assert certs["Grace Hopper"]["status"] == "GENERATED"
    assert certs["Grace Hopper"]["download_url"] is not None

    assert certs["Linus Torvalds"]["status"] == "GENERATED"
    assert certs["Linus Torvalds"]["download_url"] is not None

    # Faulty recipient is recorded as FAILED with descriptive error
    assert certs["Faulty Recipient"]["status"] == "FAILED"
    assert "Simulated failure" in certs["Faulty Recipient"]["error_reason"]
    assert certs["Faulty Recipient"]["download_url"] is None


def test_list_jobs_endpoint(client: TestClient):
    """Test listing generation jobs with pagination and summary stats."""
    payload = {
        "title": "Web3 Seminar",
        "issuer_name": "Tech Hub",
        "recipients": [{"recipient_name": "User 1", "recipient_email": "u1@tech.com"}],
    }
    client.post("/api/v1/jobs", json=payload)

    res = client.get("/api/v1/jobs?skip=0&limit=10")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert "progress_percentage" in items[0]


def test_get_nonexistent_job_returns_404(client: TestClient):
    """Test requesting an invalid job ID returns 404."""
    res = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


def test_batch_size_limit_exceeded(client: TestClient, monkeypatch):
    """Test that submitting more recipients than MAX_BATCH_SIZE is rejected."""
    from app.config import settings

    monkeypatch.setattr(settings, "MAX_BATCH_SIZE", 2)
    payload = {
        "title": "Large Batch Test",
        "issuer_name": "Org",
        "recipients": [
            {"recipient_name": f"User {i}", "recipient_email": f"u{i}@test.com"}
            for i in range(3)
        ],
    }
    res = client.post("/api/v1/jobs", json=payload)
    assert res.status_code == 400
    assert "Batch size exceeds maximum allowed" in res.json()["detail"]


def test_job_processor_all_failed(client: TestClient):
    """Test job status transitions to FAILED when all recipients fail."""
    payload = {
        "title": "All Fail Job",
        "issuer_name": "Test Org",
        "recipients": [
            {
                "recipient_name": "Fail 1",
                "recipient_email": "f1@test.com",
                "custom_attributes": {"simulate_failure": True},
            },
            {
                "recipient_name": "Fail 2",
                "recipient_email": "f2@test.com",
                "custom_attributes": {"simulate_failure": True},
            },
        ],
    }
    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]

    status_res = client.get(f"/api/v1/jobs/{job_id}")
    job_data = status_res.json()
    assert job_data["status"] == "FAILED"
    assert job_data["success_count"] == 0
    assert job_data["failure_count"] == 2

