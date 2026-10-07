# Bulk Certificate Generator API

A high-performance, fault-tolerant backend REST API built with **FastAPI**, **SQLAlchemy**, and **ReportLab** that accepts bulk certificate generation requests for hundreds or thousands of recipients, processes them asynchronously, tracks real-time progress, and allows individual or bulk ZIP retrieval of certificates.

---

## Table of Contents

1. [Features](#features)
2. [Architecture & Design Decisions](#architecture--design-decisions)
3. [Database Schema](#database-schema)
4. [Prerequisites & Setup](#prerequisites--setup)
5. [Running the Application](#running-the-application)
6. [Running the Test Suite](#running-the-test-suite)
7. [API Documentation & Usage](#api-documentation--usage)
   - [Interactive Swagger UI](#interactive-swagger-ui)
   - [1. Submit Bulk Generation Job](#1-submit-bulk-generation-job)
   - [2. Track Job Progress](#2-track-job-progress)
   - [3. List All Jobs](#3-list-all-jobs)
   - [4. Download Single Certificate](#4-download-single-certificate)
   - [5. Download All Certificates as ZIP](#5-download-all-certificates-as-zip)
   - [6. Public Certificate Verification](#6-public-certificate-verification)
8. [Failure Handling & Fault Isolation](#failure-handling--fault-isolation)
9. [Interview Q&A / Design Justifications](#interview-qa--design-justifications)

---

## Features

- **Bulk Asynchronous Processing:** Accepts large recipient batches in a single `POST` request and responds immediately with `202 Accepted` and a job tracking URL.
- **Per-Certificate Fault Isolation:** A rendering error or bad data on one recipient does **not** abort generation for other recipients in the same batch.
- **Detailed Progress & Status Tracking:** Real-time visibility into `total_count`, `processed_count`, `success_count`, `failure_count`, and completion percentage (`0.0%` to `100.0%`).
- **High-Resolution Vector Certificates:** Produces publication-grade landscape PDF certificates with double gold-and-navy borders, personalized typography, decorative official seals, and custom attributes.
- **Dynamic Verification QR Code:** Every certificate embeds an authenticatable QR code and unique UUID that resolves to a public verification endpoint (`/api/v1/certificates/verify/{certificate_id}`).
- **Batch Export:** Download all generated certificates for an event in a single ZIP bundle.
- **Production-Ready Pydantic Validation:** Comprehensive validation for emails, names, character limits, and non-empty strings.
- **100% Test Coverage:** 21 automated unit and integration tests covering all critical paths, validations, failure cases, and retrieval endpoints.

---

## Architecture & Design Decisions

### 1. Framework: FastAPI
- **Why FastAPI?** Native asynchronous request handling, automatic request validation via Pydantic v2, high throughput, and automatic interactive OpenAPI/Swagger documentation (`/docs`).

### 2. Processing Strategy: Asynchronous Background Processing
- **Decision:** When a client submits a generation request with dozens or hundreds of recipients, generating PDFs synchronously in the HTTP request loop would cause client timeouts, lock server worker threads, and degrade UX.
- **Implementation:** The request handler validates the payload, creates a `Job` record with status `PENDING`, creates associated `Certificate` records, and registers `process_job(job.id)` as a background task via FastAPI's `BackgroundTasks`. The client immediately receives `202 Accepted` with a tracking URL.
- **Production Scalability Evolution:** For high-scale distributed deployments, the background worker interface (`process_job`) is decoupled such that it can effortlessly be offloaded to a distributed task queue like **Celery + Redis** or **RQ** without changing API endpoints or database contracts.

### 3. Database: Relational Database (SQLAlchemy)
- **Default:** SQLite (`sqlite:///./bulk_certs.db`) for zero-dependency local setup.
- **Flexibility:** Configurable via `DATABASE_URL` environment variable to connect to **PostgreSQL** or **MySQL** without code changes (`DATABASE_URL=postgresql://user:pass@host/dbname`).

### 4. Storage Strategy
- Generated PDFs are stored in an organized hierarchy: `storage/certificates/<job_id>/<certificate_id>.pdf`.
- In production, local storage can be abstracted behind an S3/GCS object storage service adapter with pre-signed download URLs.

---

## Database Schema

```
+----------------------------------------------------+
|                       jobs                         |
+----------------------------------------------------+
| id (PK, UUID)                                      |
| title (VARCHAR)                                    |
| issuer_name (VARCHAR)                              |
| issue_date (DATE)                                  |
| description (TEXT)                                 |
| status (ENUM: PENDING, PROCESSING, COMPLETED,      |
|               PARTIALLY_COMPLETED, FAILED)         |
| total_count (INT)                                  |
| processed_count (INT)                              |
| success_count (INT)                                |
| failure_count (INT)                                |
| error_message (TEXT)                               |
| created_at, updated_at, completed_at (DATETIME)   |
+----------------------------------------------------+
                          | 1
                          |
                          | N
+----------------------------------------------------+
|                   certificates                     |
+----------------------------------------------------+
| id (PK, UUID - Certificate Verification ID)        |
| job_id (FK -> jobs.id, ON DELETE CASCADE)          |
| recipient_name (VARCHAR)                           |
| recipient_email (VARCHAR)                          |
| custom_attributes (JSON)                           |
| status (ENUM: PENDING, GENERATED, FAILED)          |
| file_path (VARCHAR)                                |
| file_size (INT)                                    |
| error_reason (TEXT)                                |
| created_at, generated_at (DATETIME)                |
+----------------------------------------------------+
```

---

## Prerequisites & Setup

- **Python 3.9+**
- macOS, Linux, or Windows

### Step 1: Clone / Navigate to Project Directory
```bash
cd /Users/diyar/.gemini/antigravity/scratch/bulk-certificate-generator
```

### Step 2: Create and Activate Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate    # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Running the Application

### Start the FastAPI Server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will initialize the database tables on startup and listen on `http://127.0.0.1:8000`.

---

## Running the Test Suite

Run the full automated test suite (21 unit & integration tests) with pytest:

```bash
pytest -v
```

All tests execute in-memory with isolated temporary schemas and clean up generated test files automatically.

---

## API Documentation & Usage

### Interactive Swagger UI
Open your browser and navigate to:
**`http://127.0.0.1:8000/docs`**

You will see interactive API documentation allowing you to submit requests and test endpoints directly.

---

### 1. Submit Bulk Generation Job
Submits a list of recipients for bulk certificate generation.

**Endpoint:** `POST /api/v1/jobs`  
**Status Code:** `202 Accepted`

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Agentic AI & LLM Systems Bootcamp",
    "issuer_name": "Google DeepMind Academy",
    "issue_date": "2026-10-06",
    "description": "For demonstrating exceptional mastery of multi-agent workflows.",
    "recipients": [
      {
        "recipient_name": "Ada Lovelace",
        "recipient_email": "ada@analytical.org",
        "custom_attributes": {"Grade": "Distinction", "Track": "AI Systems"}
      },
      {
        "recipient_name": "Alan Turing",
        "recipient_email": "alan@turing.ac.uk",
        "custom_attributes": {"Grade": "High Honors", "Track": "Cryptography"}
      }
    ]
  }'
```

**Response (`202 Accepted`):**
```json
{
  "job_id": "a92e2390-d4cf-4235-968b-871408803a6e",
  "status": "PENDING",
  "total_count": 2,
  "message": "Bulk certificate generation job queued successfully.",
  "status_url": "http://127.0.0.1:8000/api/v1/jobs/a92e2390-d4cf-4235-968b-871408803a6e"
}
```

---

### 2. Track Job Progress
Poll this endpoint to monitor real-time progress and retrieve recipient-level statuses.

**Endpoint:** `GET /api/v1/jobs/{job_id}`  
**Status Code:** `200 OK`

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/jobs/a92e2390-d4cf-4235-968b-871408803a6e"
```

**Response (`200 OK`):**
```json
{
  "id": "a92e2390-d4cf-4235-968b-871408803a6e",
  "title": "Agentic AI & LLM Systems Bootcamp",
  "issuer_name": "Google DeepMind Academy",
  "issue_date": "2026-10-06",
  "status": "COMPLETED",
  "total_count": 2,
  "processed_count": 2,
  "success_count": 2,
  "failure_count": 0,
  "progress_percentage": 100.0,
  "created_at": "2026-10-06T16:30:00.000000",
  "completed_at": "2026-10-06T16:30:01.200000",
  "download_all_url": "http://127.0.0.1:8000/api/v1/jobs/a92e2390-d4cf-4235-968b-871408803a6e/download-all",
  "certificates": [
    {
      "id": "27d6dcf2-f28a-40a2-b2d9-138b301c4021",
      "recipient_name": "Ada Lovelace",
      "recipient_email": "ada@analytical.org",
      "status": "GENERATED",
      "download_url": "http://127.0.0.1:8000/api/v1/certificates/27d6dcf2-f28a-40a2-b2d9-138b301c4021/download",
      "error_reason": null
    }
  ]
}
```

---

### 3. List All Jobs
List historical generation jobs with pagination and progress summary.

**Endpoint:** `GET /api/v1/jobs?skip=0&limit=20`

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/jobs"
```

---

### 4. Download Single Certificate
Retrieve the generated PDF for an individual recipient.

**Endpoint:** `GET /api/v1/certificates/{certificate_id}/download`

```bash
curl -O -J "http://127.0.0.1:8000/api/v1/certificates/27d6dcf2-f28a-40a2-b2d9-138b301c4021/download"
```

---

### 5. Download All Certificates as ZIP
Download an archive containing every certificate successfully generated for a job.

**Endpoint:** `GET /api/v1/jobs/{job_id}/download-all`

```bash
curl -O -J "http://127.0.0.1:8000/api/v1/jobs/a92e2390-d4cf-4235-968b-871408803a6e/download-all"
```

---

### 6. Public Certificate Verification
Authenticates a certificate ID and returns verification details.

**Endpoint:** `GET /api/v1/certificates/verify/{certificate_id}`

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/certificates/verify/27d6dcf2-f28a-40a2-b2d9-138b301c4021"
```

**Response (`200 OK`):**
```json
{
  "certificate_id": "27d6dcf2-f28a-40a2-b2d9-138b301c4021",
  "is_valid": true,
  "recipient_name": "Ada Lovelace",
  "course_title": "Agentic AI & LLM Systems Bootcamp",
  "issuer_name": "Google DeepMind Academy",
  "issue_date": "2026-10-06",
  "status": "GENERATED",
  "verification_message": "Official Certificate Verified: This certificate was legitimately issued and registered."
}
```

---

## Interactive Demo Script

An automated demonstration script (`demo_client.py`) is provided:

```bash
# Terminal 1: Run the server
./venv/bin/uvicorn app.main:app --port 8000

# Terminal 2: Run the demo client
./venv/bin/python demo_client.py
```

The script will submit a batch, poll status until complete, download a sample PDF, download the ZIP archive, and perform verification.

---

## Failure Handling & Fault Isolation

1. **Per-Recipient Fault Isolation:**
   In `app/services/job_processor.py`, certificate generation for each recipient is executed within an isolated `try...except` block. If recipient 2 fails (e.g. disk write failure, unexpected format error, or corrupt input), recipient 2 is marked `status = FAILED` with a diagnostic `error_reason`, while recipients 1, 3, and 4 proceed and complete successfully.
2. **Granular Job Status:**
   - `COMPLETED`: All recipient certificates were generated successfully.
   - `PARTIALLY_COMPLETED`: Some certificates succeeded, while others failed.
   - `FAILED`: All certificates failed or an unrecoverable fatal error occurred.
3. **Pydantic Pre-Validation:**
   Requests with malformed emails, empty names, or blank titles are rejected at the API gateway layer with `422 Unprocessable Entity` before any database records or generation processes are initiated.

---

## Interview Q&A / Design Justifications

### Q1: Why use background tasks instead of synchronous generation?
> **Answer:** Generating PDFs is a CPU- and I/O-intensive task. Generating 100 certificates could take 5-10 seconds. In a synchronous request, this would block the HTTP connection, risk gateway timeouts (such as NGINX 504), and lock application workers. By returning `202 Accepted` immediately, the client receives non-blocking feedback and can poll or subscribe to status updates.

### Q2: How would you scale this to 100,000 certificates per hour?
> **Answer:**
> 1. **Message Broker / Task Queue:** Replace FastAPI `BackgroundTasks` with **Celery** or **Argo Workflows** backed by **RabbitMQ/Redis**.
> 2. **Worker Pool Concurrency:** Scale worker containers horizontally using Kubernetes HPA based on queue depth.
> 3. **Batch DB Writes:** In the current implementation, we commit per certificate to provide real-time status. At 100k scale, we would buffer status updates in Redis and flush bulk updates to PostgreSQL every $N$ records or seconds.
> 4. **Cloud Object Storage:** Replace local filesystem storage with Amazon S3 or Google Cloud Storage, serving downloads via pre-signed URLs or CDN.

### Q3: How do you prevent partial state or database corruption on server crash?
> **Answer:** When a worker starts, the job is marked `PROCESSING`. Each certificate record is individually committed as `GENERATED` or `FAILED`. If a worker pod crashes mid-batch, an automated reconciliation cron or heartbeat can find jobs stuck in `PROCESSING` whose worker has died, and re-enqueue only the certificates still marked `PENDING`.

### Q4: Why ReportLab over headless Chrome / HTML-to-PDF?
> **Answer:** Headless Chrome (Playwright/Puppeteer) or WeasyPrint requires heavy browser binaries or native system libraries (`libcairo`, `libpango`). ReportLab is pure Python/C-accelerated, lightweight, uses minimal memory, produces genuine vector PDFs (sharp at any zoom level), and runs reliably in any containerized environment without system-level font/cairo dependencies.
# Bulk-gertificate-generator-
