import tempfile
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
import app.database as app_db_module
from app.main import app
from app.config import settings

# StaticPool ensures the single in-memory SQLite database is shared across all sessions/threads
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Configure temporary storage directory and monkeypatch SessionLocal for the test session."""
    with tempfile.TemporaryDirectory() as temp_dir:
        original_storage = settings.STORAGE_DIR
        original_session = app_db_module.SessionLocal

        settings.STORAGE_DIR = Path(temp_dir)
        app_db_module.SessionLocal = TestingSessionLocal

        yield

        settings.STORAGE_DIR = original_storage
        app_db_module.SessionLocal = original_session


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure a clean, isolated schema for each test."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a database session for testing."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient configured with dependency overrides for the test database session."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
