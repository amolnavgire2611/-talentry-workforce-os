import io
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import bootstrap_admin
import models
from database import Base
from security import verify_password


class InteractiveInput(io.StringIO):
    def isatty(self):
        return True


def test_bootstrap_provisions_super_admin_once_with_hashed_password(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'bootstrap.sqlite3'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(models.Organization(name="NEXORA", slug="nexora"))
        db.commit()
    monkeypatch.setattr(bootstrap_admin, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setattr("sys.stdin", InteractiveInput("root@example.com\nRoot User\n"))
    passwords = iter(("strong-bootstrap-password-123", "strong-bootstrap-password-123"))
    monkeypatch.setattr(bootstrap_admin.getpass, "getpass", lambda _prompt: next(passwords))

    assert bootstrap_admin.main() == 0
    with Session(engine) as db:
        root = db.query(models.User).filter_by(email="root@example.com").one()
        assert root.role == "Super Admin"
        assert root.active is True
        assert verify_password("strong-bootstrap-password-123", root.hashed_password)
        assert root.hashed_password != "strong-bootstrap-password-123"
        assert db.query(models.AuditLog).filter_by(action="bootstrap.super_admin_provisioned").count() == 1
    monkeypatch.setattr("sys.stdin", InteractiveInput("root@example.com\nRoot User\n"))
    assert bootstrap_admin.main() == 1
    engine.dispose()
