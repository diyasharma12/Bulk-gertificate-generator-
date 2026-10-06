from pathlib import Path
from datetime import date
import tempfile
import uuid

from app.services.generator import generate_certificate_pdf


def test_generate_certificate_pdf_creates_valid_file():
    """Verify that generate_certificate_pdf creates a non-empty, valid PDF file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = Path(temp_dir) / f"{uuid.uuid4()}.pdf"

        res_path = generate_certificate_pdf(
            output_path=output_file,
            certificate_id=str(uuid.uuid4()),
            recipient_name="Marie Curie",
            recipient_email="marie.curie@radium.org",
            title="Advanced Radiochemistry Fellowship",
            issuer_name="Sorbonne Scientific Institute",
            issue_date=date(2026, 10, 6),
            description="For extraordinary discovery and perseverance.",
            custom_attributes={"Honor": "Summa Cum Laude", "Grade": "A+"},
        )

        assert res_path.exists()
        assert res_path.stat().st_size > 0

        # Verify PDF header magic bytes
        with open(res_path, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"


def test_generate_certificate_pdf_minimal_attributes():
    """Verify certificate generation works without optional description or custom attributes."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = Path(temp_dir) / f"{uuid.uuid4()}.pdf"

        res_path = generate_certificate_pdf(
            output_path=output_file,
            certificate_id=str(uuid.uuid4()),
            recipient_name="Alan Turing",
            recipient_email="alan@turing.ac.uk",
            title="Computational Theory Workshop",
            issuer_name="Cambridge Computing Society",
            issue_date=date.today(),
            description=None,
            custom_attributes=None,
        )

        assert res_path.exists()
        assert res_path.stat().st_size > 0
