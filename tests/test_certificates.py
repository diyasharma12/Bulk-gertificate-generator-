import io
import zipfile
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.job_processor import process_job


def test_certificate_detail_and_download(client: TestClient, db_session: Session):
    """Test retrieving certificate metadata and downloading the generated PDF file."""
    payload = {
        "title": "Quantum Computing Fundamentals",
        "issuer_name": "Quantum Lab",
        "recipients": [
            {"recipient_name": "Richard Feynman", "recipient_email": "feynman@caltech.edu"},
        ],
    }

    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]
    process_job(job_id)

    # Get job detail to obtain certificate ID
    job_res = client.get(f"/api/v1/jobs/{job_id}")
    cert_id = job_res.json()["certificates"][0]["id"]

    # 1. Test get certificate detail endpoint
    cert_res = client.get(f"/api/v1/certificates/{cert_id}")
    assert cert_res.status_code == 200
    cert_data = cert_res.json()
    assert cert_data["id"] == cert_id
    assert cert_data["recipient_name"] == "Richard Feynman"
    assert cert_data["status"] == "GENERATED"
    assert cert_data["download_url"] is not None

    # 2. Test downloading the PDF file
    download_res = client.get(f"/api/v1/certificates/{cert_id}/download")
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "application/pdf"
    assert "attachment;" in download_res.headers["content-disposition"]
    # PDF magic bytes
    assert download_res.content.startswith(b"%PDF-")


def test_download_all_certificates_zip(client: TestClient, db_session: Session):
    """Test downloading a ZIP archive containing all certificates generated for a job."""
    payload = {
        "title": "Distributed Systems Bootcamp",
        "issuer_name": "MIT OpenCourseWare",
        "recipients": [
            {"recipient_name": "Leslie Lamport", "recipient_email": "lamport@mit.edu"},
            {"recipient_name": "Barbara Liskov", "recipient_email": "liskov@mit.edu"},
        ],
    }

    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]
    process_job(job_id)

    # Request ZIP bundle
    zip_res = client.get(f"/api/v1/jobs/{job_id}/download-all")
    assert zip_res.status_code == 200
    assert zip_res.headers["content-type"] == "application/zip"
    assert "Distributed_Systems_Bootcamp_certificates.zip" in zip_res.headers["content-disposition"]

    # Inspect ZIP content
    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
        namelist = zf.namelist()
        assert len(namelist) == 2
        # Check files inside zip are PDFs and non-empty
        for fname in namelist:
            assert fname.endswith(".pdf")
            file_data = zf.read(fname)
            assert file_data.startswith(b"%PDF-")


def test_certificate_verification_valid_and_invalid(client: TestClient, db_session: Session):
    """Test public verification endpoint for genuine and fraudulent certificates."""
    payload = {
        "title": "Cybersecurity Specialist",
        "issuer_name": "Defcon Academy",
        "recipients": [
            {"recipient_name": "Ada Lovelace", "recipient_email": "ada@analytical.org"},
        ],
    }

    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]
    process_job(job_id)

    job_res = client.get(f"/api/v1/jobs/{job_id}")
    valid_cert_id = job_res.json()["certificates"][0]["id"]

    # 1. Verify legitimate certificate
    verify_res = client.get(f"/api/v1/certificates/verify/{valid_cert_id}")
    assert verify_res.status_code == 200
    vdata = verify_res.json()
    assert vdata["is_valid"] is True
    assert vdata["recipient_name"] == "Ada Lovelace"
    assert vdata["course_title"] == "Cybersecurity Specialist"
    assert vdata["issuer_name"] == "Defcon Academy"

    # 2. Verify fake/unrecognized certificate ID
    fake_id = "fake-cert-00000000-0000"
    fake_verify_res = client.get(f"/api/v1/certificates/verify/{fake_id}")
    assert fake_verify_res.status_code == 200
    fake_data = fake_verify_res.json()
    assert fake_data["is_valid"] is False
    assert "invalid or unrecognized" in fake_data["verification_message"].lower()


def test_download_nonexistent_certificate_returns_404(client: TestClient):
    """Test downloading a non-existent certificate returns 404."""
    res = client.get("/api/v1/certificates/00000000-0000-0000-0000-000000000000/download")
    assert res.status_code == 404


def test_download_zip_before_generation_returns_400(client: TestClient, db_session: Session):
    """Test downloading all certificates before any are generated returns 400 Bad Request."""
    from app.models import Job, JobStatus

    job = Job(
        title="Unprocessed Job",
        issuer_name="Test Org",
        status=JobStatus.PENDING,
        total_count=1,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    # Directly request download on a job where no certificates are GENERATED yet
    zip_res = client.get(f"/api/v1/jobs/{job.id}/download-all")
    assert zip_res.status_code == 400
    assert "No certificates have been successfully generated" in zip_res.json()["detail"]


def test_download_failed_certificate_returns_400(client: TestClient):
    """Test downloading a certificate that failed generation returns 400 Bad Request."""
    payload = {
        "title": "Failure Download Test",
        "issuer_name": "Test Org",
        "recipients": [
            {
                "recipient_name": "Doomed Recipient",
                "recipient_email": "doomed@test.com",
                "custom_attributes": {"simulate_failure": True},
            },
        ],
    }
    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]
    job_res = client.get(f"/api/v1/jobs/{job_id}")
    cert_id = job_res.json()["certificates"][0]["id"]

    res = client.get(f"/api/v1/certificates/{cert_id}/download")
    assert res.status_code == 400
    assert "Certificate status is 'FAILED'" in res.json()["detail"]


def test_verify_failed_certificate_returns_invalid(client: TestClient):
    """Test public verification returns invalid for a failed certificate."""
    payload = {
        "title": "Failed Cert Verify",
        "issuer_name": "Test Org",
        "recipients": [
            {
                "recipient_name": "Incomplete User",
                "recipient_email": "inc@test.com",
                "custom_attributes": {"simulate_failure": True},
            },
        ],
    }
    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]
    job_res = client.get(f"/api/v1/jobs/{job_id}")
    cert_id = job_res.json()["certificates"][0]["id"]

    verify_res = client.get(f"/api/v1/certificates/verify/{cert_id}")
    assert verify_res.status_code == 200
    vdata = verify_res.json()
    assert vdata["is_valid"] is False
    assert "has not been officially generated" in vdata["verification_message"]


def test_health_and_root_endpoints(client: TestClient):
    """Test API root documentation links and /health endpoint."""
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "documentation" in res_root.json()

    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"


