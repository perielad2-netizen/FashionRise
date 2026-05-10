import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("ENVIRONMENT", "production")

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
