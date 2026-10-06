"""Interactive Demo Script for Bulk Certificate Generator API.

Run this script to submit a sample batch of certificates, observe status polling,
download generated PDFs, and perform public verification.
"""

import time
import httpx

BASE_URL = "http://127.0.0.1:8000"



def main():
    print("=" * 60)
    print("BULK CERTIFICATE GENERATOR - API DEMO")
    print("=" * 60)

    # 1. Health check
    try:
        health = httpx.get(f"{BASE_URL}/health").json()
        print(f"[*] API Health: {health}")
    except httpx.ConnectError:
        print(f"[!] Server is not running at {BASE_URL}. Start it first using:")
        print("    ./venv/bin/uvicorn app.main:app --port 8000")
        return

    # 2. Submit Bulk Generation Request

    payload = {
        "title": "Agentic AI & Deep Learning Masterclass",
        "issuer_name": "Google DeepMind Academy",
        "description": "For outstanding proficiency in agentic architectures and neural networks.",
        "recipients": [
            {
                "recipient_name": "Ada Lovelace",
                "recipient_email": "ada.lovelace@analytical.org",
                "custom_attributes": {"Grade": "Distinction", "Role": "Lead Architect"},
            },
            {
                "recipient_name": "Alan Turing",
                "recipient_email": "alan.turing@cambridge.ac.uk",
                "custom_attributes": {"Grade": "High Honors", "Track": "Cryptography"},
            },
            {
                "recipient_name": "Katherine Johnson",
                "recipient_email": "katherine.johnson@nasa.gov",
                "custom_attributes": {"Grade": "Summa Cum Laude", "Track": "Orbital Mechanics"},
            },
        ],
    }

    print("\n[+] Submitting bulk certificate generation request...")
    res = httpx.post(f"{BASE_URL}/api/v1/jobs", json=payload)
    if res.status_code != 202:
        print(f"[!] Failed to submit job: {res.text}")
        return

    job_info = res.json()
    job_id = job_info["job_id"]
    print(f"    Job ID: {job_id}")
    print(f"    Initial Status: {job_info['status']}")
    print(f"    Recipients queued: {job_info['total_count']}")

    # 3. Poll for progress
    print("\n[*] Polling job status...")
    while True:
        status_res = httpx.get(f"{BASE_URL}/api/v1/jobs/{job_id}").json()
        status = status_res["status"]
        processed = status_res["processed_count"]
        total = status_res["total_count"]
        pct = status_res["progress_percentage"]
        print(f"    Status: {status} | Processed: {processed}/{total} ({pct}%)")

        if status in ("COMPLETED", "PARTIALLY_COMPLETED", "FAILED"):
            break
        time.sleep(0.5)

    print(f"\n[✓] Job completed with status: {status_res['status']}")
    print(f"    Successful: {status_res['success_count']}")
    print(f"    Failures:   {status_res['failure_count']}")

    # 4. Inspect generated certificates
    certificates = status_res.get("certificates", [])
    if certificates:
        first_cert = certificates[0]
        cert_id = first_cert["id"]
        print(f"\n[+] Verifying certificate for {first_cert['recipient_name']} (ID: {cert_id})...")
        verify_res = httpx.get(f"{BASE_URL}/api/v1/certificates/verify/{cert_id}").json()
        print(f"    Valid: {verify_res['is_valid']}")
        print(f"    Message: {verify_res['verification_message']}")

        # 5. Download individual PDF
        print(f"\n[+] Downloading single certificate PDF...")
        pdf_res = httpx.get(f"{BASE_URL}/api/v1/certificates/{cert_id}/download")
        pdf_filename = f"sample_certificate_{cert_id[:8]}.pdf"
        with open(pdf_filename, "wb") as f:
            f.write(pdf_res.content)
        print(f"    Saved sample certificate to: {pdf_filename} ({len(pdf_res.content)} bytes)")

        # 6. Download ZIP bundle
        if status_res.get("download_all_url"):
            print(f"\n[+] Downloading all certificates ZIP archive...")
            zip_res = httpx.get(f"{BASE_URL}/api/v1/jobs/{job_id}/download-all")
            zip_filename = f"batch_{job_id[:8]}_all_certificates.zip"
            with open(zip_filename, "wb") as f:
                f.write(zip_res.content)
            print(f"    Saved ZIP archive to: {zip_filename} ({len(zip_res.content)} bytes)")

    print("\n" + "=" * 60)
    print("Demo completed successfully! Check the generated files in current folder.")
    print("=" * 60)


if __name__ == "__main__":
    main()
