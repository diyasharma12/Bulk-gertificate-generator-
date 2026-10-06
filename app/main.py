from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.api.v1.jobs import router as jobs_router
from app.api.v1.certificates import router as certs_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables and storage directories
    init_db()
    settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Shutdown logic (if any)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Routers
app.include_router(jobs_router, prefix=settings.API_V1_STR)
app.include_router(certs_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Health"])
def root_info():
    """Root endpoint returning API service status and quick links."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "healthy",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
        },
        "endpoints": {
            "submit_job": f"POST {settings.API_V1_STR}/jobs",
            "list_jobs": f"GET {settings.API_V1_STR}/jobs",
            "check_job_status": f"GET {settings.API_V1_STR}/jobs/{{job_id}}",
            "download_all_zip": f"GET {settings.API_V1_STR}/jobs/{{job_id}}/download-all",
            "get_certificate": f"GET {settings.API_V1_STR}/certificates/{{certificate_id}}",
            "download_certificate": f"GET {settings.API_V1_STR}/certificates/{{certificate_id}}/download",
            "verify_certificate": f"GET {settings.API_V1_STR}/certificates/verify/{{certificate_id}}",
        },
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe healthcheck endpoint."""
    return {"status": "ok", "version": settings.VERSION}
