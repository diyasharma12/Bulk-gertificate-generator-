from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Bulk Certificate Generator API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = (
        "High-performance backend API for bulk certificate generation, "
        "status tracking, and certificate retrieval."
    )
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite:///./bulk_certs.db"

    # Storage
    STORAGE_DIR: Path = Path("./storage/certificates")

    # Server settings
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Verification base URL (used for QR code on certificates)
    VERIFY_BASE_URL: str = "http://localhost:8000/api/v1/certificates/verify"

    # Batch and generation settings
    MAX_BATCH_SIZE: int = 2000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()

# Ensure storage directory exists
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
