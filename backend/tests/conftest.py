import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import models  # noqa: E402
from application import create_app  # noqa: E402
from database import Base  # noqa: E402
from security import hash_password  # noqa: E402


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    app = create_app(f"sqlite:///{db_path}", secret_key="test-secret-key-that-is-long-enough")
    Base.metadata.create_all(app.state.engine)
    with Session(app.state.engine) as db:
        organization = models.Organization(name="NEXORA", slug="nexora")
        db.add(organization)
        db.flush()
        db.info["organization_id"] = organization.id
        db.add(models.User(name="Test Root", email="root@example.com", role="Super Admin",
                           active=True, hashed_password=hash_password("test-super-admin-password")))
        db.flush()
        root = db.query(models.User).filter_by(email="root@example.com").one()
        db.add(models.OrganizationMembership(user_id=root.id, role="Super Admin", active=True))
        db.commit()
    with TestClient(app) as test_client:
        yield test_client
