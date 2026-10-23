from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import models
from application import create_app
from database import Base
from security import hash_password


TEST_SECRET = "test-secret-key-that-is-long-enough"


def test_authenticated_reads_and_identifier_routes_are_organization_scoped(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'tenant-scope.sqlite3'}", secret_key=TEST_SECRET)
    Base.metadata.create_all(app.state.engine)

    with Session(app.state.engine) as db:
        first = models.Organization(name="NEXORA", slug="nexora")
        second = models.Organization(name="Another Organization", slug="another")
        db.add_all([first, second])
        db.flush()
        first_id, second_id = first.id, second.id
        db.info["organization_id"] = first_id
        first_admin = models.User(
            name="First Admin", email="first.admin@example.com", role="Super Admin", active=True,
            hashed_password=hash_password("first-admin-password-123"),
        )
        db.add(first_admin)
        db.flush()
        db.add(models.OrganizationMembership(user_id=first_admin.id, role="Super Admin", active=True))
        db.add(models.Department(name="People", active=True))
        first_employee = models.Employee(
            employee_code="NX-1", name="First Employee", department="People", role="Analyst",
        )
        db.add(first_employee)
        db.commit()
        first_employee_id = first_employee.id

    with Session(app.state.engine) as db:
        db.info["organization_id"] = second_id
        second_admin = models.User(
            name="Second Admin", email="second.admin@example.com", role="Super Admin", active=True,
            hashed_password=hash_password("second-admin-password-123"),
        )
        second_employee = models.Employee(
            employee_code="NX-1", name="Second Employee", department="People", role="Analyst",
        )
        db.add_all([second_admin, second_employee, models.Department(name="People", active=True)])
        db.flush()
        second_admin_id, second_employee_id = second_admin.id, second_employee.id
        db.add(models.OrganizationMembership(user_id=second_admin.id, role="Super Admin", active=True))
        db.add(models.AuditLog(
            organization_id=second_id, actor_id=second_admin_id, action="private.event",
            entity_type="test", details={},
        ))
        db.commit()

    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={
            "email": "first.admin@example.com", "password": "first-admin-password-123",
        })
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        employees = client.get("/api/employees", headers=headers)
        assert employees.status_code == 200
        assert [row["id"] for row in employees.json()] == [first_employee_id]
        assert client.get(f"/api/employees/{second_employee_id}", headers=headers).status_code == 404

        users = client.get("/api/users?limit=100", headers=headers)
        assert users.status_code == 200
        assert users.json()["total"] == 1
        assert [row["id"] for row in users.json()["items"]] == [login.json()["user"]["id"]]
        assert client.patch(f"/api/users/{second_admin_id}", headers=headers, json={"active": False}).status_code == 404

        memberships = client.get("/api/organization-memberships?limit=100", headers=headers)
        assert memberships.status_code == 200
        assert memberships.json()["total"] == 1
        assert [row["user_id"] for row in memberships.json()["items"]] == [login.json()["user"]["id"]]

        audit = client.get("/api/audit-logs?limit=100", headers=headers)
        assert audit.status_code == 200
        assert all(row["action"] != "private.event" for row in audit.json()["items"])


def test_employee_can_read_own_payslip_scoped_by_employee_id(tmp_path):
    """Payslip.employee_id references Employee.id (not User.id). An Employee must be able to
    read their own payslip by resolving the employee profile linked to their account.

    Regression guard: before the fix the endpoint filtered `employee_id == user.id`, which
    mixes identifier spaces and returns no payslips to employees.
    """
    app = create_app(f"sqlite:///{tmp_path / 'payslip-scope.sqlite3'}", secret_key=TEST_SECRET)
    Base.metadata.create_all(app.state.engine)

    with Session(app.state.engine) as db:
        org = models.Organization(name="NEXORA", slug="nexora")
        db.add(org)
        db.flush()
        db.info["organization_id"] = org.id

        emp = models.Employee(
            employee_code="NX-1", name="Payroll Employee", department="People", role="Staff",
        )
        db.add(emp)
        db.flush()
        emp_id = emp.id

        user = models.User(
            name="Payroll Employee", email="payroll@example.com", role="Employee", active=True,
            hashed_password=hash_password("payroll-password-123"),
        )
        db.add(user)
        db.flush()
        user_id = user.id

        emp.user_id = user_id
        db.add(models.OrganizationMembership(user_id=user_id, role="Employee", active=True))

        run = models.PayrollRun(
            name="March 2026", period_start=date(2026, 3, 1), period_end=date(2026, 3, 31),
            pay_date=date(2026, 4, 5), status="Calculated", organization_id=org.id,
        )
        db.add(run)
        db.flush()
        db.add(models.Payslip(
            payroll_run_id=run.id, employee_id=emp_id, organization_id=org.id,
            gross_pay=5000, deductions=500, net_pay=4500, payslip_date=date(2026, 4, 5),
            status="Draft",
        ))
        db.commit()

    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={
            "email": "payroll@example.com", "password": "payroll-password-123",
        })
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        payslips = client.get("/api/payroll/payslips", headers=headers)
        assert payslips.status_code == 200, payslips.text
        assert len(payslips.json()) == 1
        assert payslips.json()[0]["employee_id"] == emp_id
