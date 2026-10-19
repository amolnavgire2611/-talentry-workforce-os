from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import models
from application import create_app
from database import Base


BOOTSTRAP_KEY = "test-bootstrap-key-with-more-than-32-characters"
TEST_SECRET = "test-secret-key-that-is-long-enough"


def empty_app(tmp_path, bootstrap_key=BOOTSTRAP_KEY):
    database_path = tmp_path / "admin-bootstrap.sqlite3"
    app = create_app(
        f"sqlite:///{database_path}",
        secret_key=TEST_SECRET,
        admin_bootstrap_token=bootstrap_key,
    )
    Base.metadata.create_all(app.state.engine)
    with Session(app.state.engine) as db:
        db.add(models.Organization(name="NEXORA", slug="nexora"))
        db.commit()
    return app


def admin_payload(**changes):
    payload = {
        "name": "Initial Administrator",
        "email": "admin@example.com",
        "password": "long-and-unique-password",
        "setup_token": BOOTSTRAP_KEY,
    }
    payload.update(changes)
    return payload


def test_first_admin_setup_key_is_required_and_registration_is_one_time(tmp_path):
    app = empty_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/api/auth/admin-registration-status").json() == {"available": True}
        assert client.post("/api/auth/register-admin", json=admin_payload(setup_token="x" * 48)).status_code == 403
        assert client.post("/api/auth/register-admin", json=admin_payload(role="Employee")).status_code == 422

        created = client.post("/api/auth/register-admin", json=admin_payload())
        assert created.status_code == 201, created.text
        assert created.json()["user"]["role"] == "Super Admin"
        assert "hashed_password" not in created.json()["user"]
        assert client.get("/api/auth/admin-registration-status").json() == {"available": False}
        assert client.post("/api/auth/register-admin", json=admin_payload(email="second@example.com")).status_code == 409

    with Session(app.state.engine) as db:
        admins = db.query(models.User).filter_by(role="Super Admin", active=True).all()
        assert len(admins) == 1
        event = db.query(models.AuditLog).filter_by(action="auth.first_super_admin_registered").one()
        assert event.actor_id is None
        assert event.entity_id == str(admins[0].id)


def test_first_admin_setup_requires_operator_configuration_and_unique_email(tmp_path):
    app = empty_app(tmp_path, bootstrap_key="too-short")
    with TestClient(app) as client:
        assert client.get("/api/auth/admin-registration-status").json() == {"available": False}
        unconfigured = client.post("/api/auth/register-admin", json=admin_payload())
        assert unconfigured.status_code == 503
        assert client.post("/api/auth/register", json={
            "name": "Existing Employee",
            "email": "admin@example.com",
            "password": "long-enough-employee-password",
        }).status_code == 201

    configured_app = create_app(
        f"sqlite:///{tmp_path / 'configured.sqlite3'}",
        secret_key=TEST_SECRET,
        admin_bootstrap_token=BOOTSTRAP_KEY,
    )
    Base.metadata.create_all(configured_app.state.engine)
    with Session(configured_app.state.engine) as db:
        db.add(models.Organization(name="NEXORA", slug="nexora"))
        db.commit()
    with TestClient(configured_app) as client:
        assert client.post("/api/auth/register", json={
            "name": "Existing Employee",
            "email": "admin@example.com",
            "password": "long-enough-employee-password",
        }).status_code == 201
        duplicate = client.post("/api/auth/register-admin", json=admin_payload())
        assert duplicate.status_code == 409
        assert client.get("/api/auth/admin-registration-status").json() == {"available": True}


def test_concurrent_first_admin_requests_create_exactly_one_account(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'concurrent-admin-bootstrap.sqlite3'}"
    apps = [
        create_app(database_url, secret_key=TEST_SECRET, admin_bootstrap_token=BOOTSTRAP_KEY)
        for _ in range(2)
    ]
    Base.metadata.create_all(apps[0].state.engine)
    with Session(apps[0].state.engine) as db:
        db.add(models.Organization(name="NEXORA", slug="nexora"))
        db.commit()
    barrier = Barrier(2)
    with TestClient(apps[0]) as first, TestClient(apps[1]) as second:
        def register(client, email):
            barrier.wait()
            return client.post("/api/auth/register-admin", json=admin_payload(email=email)).status_code

        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(
                lambda values: register(*values),
                [(first, "first@example.com"), (second, "second@example.com")],
            ))

    assert sorted(outcomes) == [201, 409]
    with Session(apps[0].state.engine) as db:
        assert db.query(models.User).filter_by(role="Super Admin", active=True).count() == 1


def test_inactive_super_admin_record_still_closes_first_admin_registration(tmp_path):
    app = empty_app(tmp_path)
    with Session(app.state.engine) as db:
        db.info["organization_id"] = 1
        db.add(models.User(
            name="Previously Registered Admin",
            email="former-admin@example.com",
            role="Super Admin",
            active=False,
            hashed_password="existing-hash",
        ))
        db.commit()

    with TestClient(app) as client:
        assert client.get("/api/auth/admin-registration-status").json() == {"available": False}
        assert client.post("/api/auth/register-admin", json=admin_payload()).status_code == 409

