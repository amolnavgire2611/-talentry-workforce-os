"""Provision the initial Super Admin from a trusted local terminal.

Run after ``alembic upgrade head``. Never expose this command as an HTTP endpoint.
"""

import getpass
import re
import sys

from sqlalchemy import func

import models
from database import SessionLocal
from security import hash_password


def main() -> int:
    if not sys.stdin.isatty():
        print("Run this command from an interactive terminal.", file=sys.stderr)
        return 2
    email = input("Super Admin email: ").strip().lower()
    name = input("Full name: ").strip()
    if len(name) < 2 or len(name) > 100 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        print("Enter a valid email and a name of at least two characters.", file=sys.stderr)
        return 2
    db = SessionLocal()
    try:
        organizations = db.query(models.Organization).filter_by(active=True).order_by(models.Organization.id).limit(2).all()
        if len(organizations) != 1:
            print("Bootstrap requires exactly one active organization; apply the organization migration first.", file=sys.stderr)
            return 1
        organization_id = organizations[0].id
        db.info["organization_id"] = organization_id
        if db.query(models.User.id).filter_by(role="Super Admin", active=True).first():
            print("An active Super Admin already exists; bootstrap is disabled.", file=sys.stderr)
            return 1
        password = getpass.getpass("New password (minimum 12 characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if len(password) < 12 or len(password) > 128 or password != confirmation:
            print("Passwords must match and be 12–128 characters long.", file=sys.stderr)
            return 2
        user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
        if user is None:
            user = models.User(name=name, email=email, role="Super Admin", active=True,
                               hashed_password=hash_password(password), organization_id=organization_id)
            db.add(user)
        else:
            user.name = name
            user.role = "Super Admin"
            user.active = True
            user.hashed_password = hash_password(password)
        db.flush()
        db.add(models.AuditLog(organization_id=organization_id, actor_id=user.id, action="bootstrap.super_admin_provisioned",
                               entity_type="user", entity_id=str(user.id),
                               details={"role": "Super Admin"}))
        db.commit()
        print(f"Super Admin account provisioned for {email}.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
