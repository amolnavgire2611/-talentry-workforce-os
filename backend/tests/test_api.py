from datetime import date, datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import models
from application import create_app
from database import Base
from security import hash_password


def admin_login(client):
    return client.post("/api/auth/login", json={
        "email": "root@example.com", "password": "test-super-admin-password",
    })


def register(client, email, **extra):
    admin_headers = bearer(admin_login(client))
    count = client.get("/api/users?limit=100", headers=admin_headers).json()["total"]
    departments_response = client.get("/api/departments?limit=100", headers=admin_headers)
    departments = departments_response.json()["items"]
    department = next((item for item in departments if item["name"] == "People"), None)
    if department is None:
        department = client.post("/api/departments", headers=admin_headers, json={"name": "People"}).json()
    policies = client.get("/api/leave-types", headers=admin_headers).json()
    if not policies:
        client.post("/api/leave-types", headers=admin_headers, json={
            "name": "Annual", "annual_allowance_days": 20, "description": "Annual leave",
        })
    employee = client.post("/api/employees", headers=admin_headers, json={
        "employee_code": f"INV-{count}", "name": "Test Person", "department": department["name"], "role": "Staff",
    })
    invite = client.post("/api/users/invitations", headers=admin_headers, json={
        "name": "Test Person", "email": email, "role": "Employee",
        **({"employee_id": employee.json()["id"]} if employee.status_code == 201 else {}),
    })
    if invite.status_code != 201:
        return invite
    return client.post("/api/auth/register-invited", json={
        "invitation_token": invite.json()["invitation_token"], "password": "strong-password-123",
    })


def bearer(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_public_registration_creates_employee_account_and_rejects_role_escalation(client):
    registered = client.post("/api/auth/register", json={
        "name": "First Person", "email": "  FIRST@example.com ", "password": "strong-password-123",
    })
    assert registered.status_code == 201, registered.text
    assert registered.json()["user"]["role"] == "Employee"
    assert registered.json()["user"]["email"] == "first@example.com"
    assert "hashed_password" not in registered.json()["user"]
    assert client.get("/api/auth/me", headers=bearer(registered)).json()["name"] == "First Person"
    assert client.post("/api/auth/register", json={
        "name": "Escalation", "email": "escalation@example.com", "password": "strong-password-123",
        "role": "Super Admin",
    }).status_code == 422
    assert client.post("/api/register", json={
        "name": "Alias User", "email": "alias@example.com", "password": "strong-password-123",
    }).status_code == 201
    assert client.post("/api/auth/register", json={
        "name": "Duplicate", "email": "FIRST@example.com", "password": "strong-password-123",
    }).status_code == 409


def test_auth_me_logout_and_inactive_token_rejection(client):
    signed_up = admin_login(client)
    headers = bearer(signed_up)
    assert client.get("/api/auth/me").status_code == 401
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["role"] == "Super Admin"
    assert "hashed_password" not in me.json()

    assert client.post("/api/auth/activate", json={
        "invitation_token": "a" * 48, "password": "another-strong-password-123",
    }).status_code == 400

    login = signed_up
    assert login.status_code == 200
    assert login.json()["expires_in"] <= 3600
    logout_headers = {
        **headers,
        "Origin": "http://localhost:5173",
        "X-CSRF-Token": login.json()["csrf_token"],
    }
    assert client.post("/api/auth/logout", headers=logout_headers).status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401

    updated = client.patch("/api/users/1", json={"active": False}, headers= bearer(admin_login(client)))
    assert updated.status_code == 409  # Cannot deactivate the only Super Admin.


def test_refresh_session_cookie_rotation_and_replay_revocation(client):
    login = admin_login(client)
    assert login.status_code == 200
    assert login.json()["csrf_token"]
    cookie_header = login.headers["set-cookie"].lower()
    assert "nexora_refresh=" in cookie_header
    assert "httponly" in cookie_header
    assert "samesite=strict" in cookie_header
    assert "path=/api/auth" in cookie_header
    original_cookie = login.cookies.get("nexora_refresh")
    original_access = login.json()["access_token"]

    rotated = client.post("/api/auth/refresh", headers={
        "Origin": "http://localhost:5173",
        "X-CSRF-Token": login.json()["csrf_token"],
    })
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["access_token"] != original_access
    assert rotated.json()["csrf_token"] != login.json()["csrf_token"]
    assert rotated.cookies.get("nexora_refresh") != original_cookie

    client.cookies.set("nexora_refresh", original_cookie, path="/api/auth")
    replay = client.post("/api/auth/refresh", headers={
        "Origin": "http://localhost:5173",
        "X-CSRF-Token": rotated.json()["csrf_token"],
    })
    assert replay.status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {rotated.json()['access_token']}"}).status_code == 401


def test_refresh_requires_allowed_origin_and_matching_csrf(client):
    login = admin_login(client)
    assert client.post("/api/auth/refresh", headers={
        "X-CSRF-Token": login.json()["csrf_token"],
    }).status_code == 403
    assert client.post("/api/auth/refresh", headers={
        "Origin": "https://attacker.example",
        "X-CSRF-Token": login.json()["csrf_token"],
    }).status_code == 403
    assert client.post("/api/auth/refresh", headers={
        "Origin": "http://localhost:5173",
    }).status_code == 403
    assert client.post("/api/auth/refresh", headers={
        "Origin": "http://localhost:5173",
        "X-CSRF-Token": "wrong-token",
    }).status_code == 403
    assert client.post("/api/auth/refresh", headers={
        "Origin": "http://localhost:5173",
        "X-CSRF-Token": login.json()["csrf_token"],
    }).status_code == 200


def test_session_inventory_revocation_and_user_isolation(client):
    first_login = admin_login(client)
    second_login = admin_login(client)
    first_headers = bearer(first_login)
    second_headers = bearer(second_login)

    listed = client.get("/api/auth/sessions", headers=first_headers)
    assert listed.status_code == 200
    first_session = next(session for session in listed.json() if session["current"])
    second_session = next(session for session in listed.json() if session["id"] != first_session["id"])

    employee = client.post("/api/auth/register", json={
        "name": "Isolated Employee", "email": "isolated@example.com", "password": "strong-password-123",
    })
    employee_headers = bearer(employee)
    assert client.delete(f"/api/auth/sessions/{second_session['id']}", headers=employee_headers).status_code == 404

    revoked = client.delete(f"/api/auth/sessions/{first_session['id']}", headers=second_headers)
    assert revoked.status_code == 204
    assert client.get("/api/auth/me", headers=first_headers).status_code == 401
    assert client.get("/api/auth/me", headers=second_headers).status_code == 200

    all_revoked = client.delete("/api/auth/sessions", headers=second_headers)
    assert all_revoked.status_code == 204
    assert client.get("/api/auth/me", headers=second_headers).status_code == 401


def test_deactivation_revokes_refresh_sessions_even_if_account_is_reactivated(client):
    employee = client.post("/api/auth/register", json={
        "name": "Lifecycle Employee", "email": "lifecycle@example.com", "password": "strong-password-123",
    })
    headers = bearer(employee)
    admin_headers = bearer(admin_login(client))
    deactivated = client.patch(f"/api/users/{employee.json()['user']['id']}",
                               json={"active": False}, headers=admin_headers)
    assert deactivated.status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    reactivated = client.patch(f"/api/users/{employee.json()['user']['id']}",
                              json={"active": True}, headers=admin_headers)
    assert reactivated.status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_employee_write_roles_and_admin_workflows(client):
    admin = admin_login(client)
    employee = register(client, "employee@example.com")
    employee_headers = bearer(employee)
    admin_headers = bearer(admin)

    assert client.get("/api/employees").status_code == 401
    assert client.post("/api/employees", json={
        "employee_code": "E-100", "name": "Example", "department": "People", "role": "Staff",
    }, headers=employee_headers).status_code == 403

    department = client.get("/api/departments?limit=100", headers=admin_headers).json()["items"]
    assert any(item["name"] == "People" for item in department)
    created = client.post("/api/employees", json={
        "employee_code": "E-100", "name": "Example", "department": "People", "role": "Staff",
    }, headers=admin_headers)
    assert created.status_code == 201, created.text
    assert client.get("/api/employees", headers=employee_headers).status_code == 403

    start = date.today() + timedelta(days=2)
    leave = client.post("/api/leave-requests", json={
        "start_date": start.isoformat(), "end_date": (start + timedelta(days=1)).isoformat(),
        "leave_type_id": client.get("/api/leave-types", headers=admin_headers).json()[0]["id"],
        "reason": "Family commitment",
    }, headers=employee_headers)
    assert leave.status_code == 201, leave.text
    assert leave.json()["status"] == "Pending"
    approved = client.post(f"/api/leave-requests/{leave.json()['id']}/review", json={"decision": "Approved"}, headers=admin_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "Approved"

    clock_in = client.post("/api/attendance/clock-in", headers=employee_headers)
    assert clock_in.status_code == 201, clock_in.text
    assert client.post("/api/attendance/clock-in", headers=employee_headers).status_code == 409
    assert client.post("/api/attendance/clock-out", headers=employee_headers).status_code == 200
    dashboard = client.get("/api/dashboard", headers=employee_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["scope"] == "personal"
    assert dashboard.json()["employee_count"] is None

    audit = client.get("/api/audit-logs", headers=admin_headers)
    assert audit.status_code == 200
    assert audit.json()["total"] >= 6


def test_employee_profile_edit_does_not_mutate_leave_balances(client):
    admin_headers = bearer(admin_login(client))
    admin_id = client.get("/api/auth/me", headers=admin_headers).json()["id"]
    employee = client.post("/api/employees", headers=admin_headers, json={
        "employee_code": "EDIT-1", "name": "Before Edit", "department": "People", "role": "Analyst",
    })
    assert employee.status_code == 201, employee.text
    leave_type = client.post("/api/leave-types", headers=admin_headers, json={
        "name": "Annual", "annual_allowance_days": 20,
    })
    assert leave_type.status_code == 201, leave_type.text

    with Session(client.app.state.engine) as db:
        db.info["organization_id"] = 1
        row = db.get(models.Employee, employee.json()["id"])
        row.user_id = admin_id
        db.add(models.LeaveBalance(
            user_id=admin_id, leave_type_id=leave_type.json()["id"], year=2026,
            allocated_days=20, used_days=5,
        ))
        db.commit()

    updated = client.put(f"/api/employees/{employee.json()['id']}", headers=admin_headers, json={
        "employee_code": "EDIT-1", "name": "After Edit", "department": "People", "role": "Analyst",
        "status": "Active",
    })
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "After Edit"

    with Session(client.app.state.engine) as db:
        balance = db.query(models.LeaveBalance).one()
        assert balance.allocated_days == 20
        assert balance.used_days == 5


def test_employee_private_contacts_and_append_only_employment_history(client):
    admin_headers = bearer(admin_login(client))
    employee_account = register(client, "profile-owner@example.com")
    owner_headers = bearer(employee_account)
    employee = client.get("/api/employees/me", headers=owner_headers)
    assert employee.status_code == 200, employee.text
    employee_id = employee.json()["id"]

    assert client.get("/api/employees/me/contact", headers=owner_headers).json() is None
    saved_contact = client.put("/api/employees/me/contact", headers=owner_headers, json={
        "personal_email": "person@example.com", "phone": "+1 555 123 4567",
        "alternate_phone": None, "address_line": "12 North Street", "city": "Springfield",
        "region": "IL", "postal_code": "62701", "country": "US",
    })
    assert saved_contact.status_code == 200, saved_contact.text
    assert saved_contact.json()["personal_email"] == "person@example.com"
    assert client.get(f"/api/employees/{employee_id}/contact", headers=admin_headers).json()["phone"] == "+1 555 123 4567"
    assert client.put("/api/employees/me/contact", headers=owner_headers, json={
        "personal_email": None, "phone": None, "alternate_phone": None,
    }).status_code == 422
    assert client.put("/api/employees/me/contact", headers=owner_headers, json={
        "personal_email": "invalid-email", "phone": "123",
    }).status_code == 422

    emergency = client.post("/api/employees/me/emergency-contacts", headers=owner_headers, json={
        "name": "A. Contact", "relationship": "Sibling", "phone": "+1 555 222 3333", "priority": 1,
    })
    assert emergency.status_code == 201, emergency.text
    contact_id = emergency.json()["id"]
    assert client.get("/api/employees/me/emergency-contacts", headers=owner_headers).json()[0]["id"] == contact_id
    updated_emergency = client.put(f"/api/emergency-contacts/{contact_id}", headers=owner_headers, json={
        "name": "B. Contact", "relationship": "Sibling", "phone": "+1 555 222 3334", "priority": 2,
    })
    assert updated_emergency.status_code == 200, updated_emergency.text
    assert updated_emergency.json()["name"] == "B. Contact"

    other_account = register(client, "another-profile-owner@example.com")
    other_headers = bearer(other_account)
    assert client.get(f"/api/employees/{employee_id}/contact", headers=other_headers).status_code == 403
    assert client.get(f"/api/employees/{employee_id}/emergency-contacts", headers=other_headers).status_code == 403
    assert client.put(f"/api/emergency-contacts/{contact_id}", headers=other_headers, json={
        "name": "Intruder", "relationship": "Other", "phone": "+1 555 777 8888", "priority": 1,
    }).status_code == 403

    people_department = next(item for item in client.get("/api/departments?limit=100", headers=admin_headers).json()["items"]
                             if item["name"] == "People")
    manager_invite = client.post("/api/users/invitations", headers=admin_headers, json={
        "name": "People Manager", "email": "people-manager@example.com", "role": "Department Manager",
        "department_id": people_department["id"],
    })
    manager_registration = client.post("/api/auth/register-invited", json={
        "invitation_token": manager_invite.json()["invitation_token"], "password": "people-manager-password-123",
    })
    manager_headers = bearer(manager_registration)
    assert client.get(f"/api/employees/{employee_id}/contact", headers=manager_headers).status_code == 403
    assert client.get(f"/api/employees/{employee_id}/employment-history", headers=manager_headers).status_code == 403

    initial_history = client.get("/api/employees/me/employment-history", headers=owner_headers)
    assert initial_history.status_code == 200, initial_history.text
    assert [event["event_type"] for event in initial_history.json()] == ["hire"]
    changed_position = client.put(f"/api/employees/{employee_id}", headers=admin_headers, json={
        "employee_code": employee.json()["employee_code"], "name": employee.json()["name"],
        "department": "People", "role": "Team Lead", "status": "Active",
        "branch_id": None, "designation_id": None, "job_grade_id": None, "reporting_manager_id": None,
    })
    assert changed_position.status_code == 200, changed_position.text
    status_change = client.patch(f"/api/employees/{employee_id}/status", headers=admin_headers, json={"status": "On leave"})
    assert status_change.status_code == 200, status_change.text
    history = client.get(f"/api/employees/{employee_id}/employment-history", headers=admin_headers)
    assert history.status_code == 200, history.text
    assert [event["event_type"] for event in history.json()] == ["status_change", "assignment_change", "hire"]
    assert history.json()[0]["employment_status"] == "On leave"
    assert client.delete(f"/api/emergency-contacts/{contact_id}", headers=owner_headers).status_code == 204
    assert client.get("/api/employees/me/emergency-contacts", headers=owner_headers).json() == []


def test_organization_admin_can_manage_only_scoped_accounts_and_structure(client):
    super_admin_headers = bearer(admin_login(client))
    invitation = client.post("/api/users/invitations", headers=super_admin_headers, json={
        "name": "Organization Admin", "email": "org-admin@example.com", "role": "Organization Admin",
    })
    assert invitation.status_code == 201, invitation.text
    registration = client.post("/api/auth/register-invited", json={
        "invitation_token": invitation.json()["invitation_token"],
        "password": "organization-admin-password-123",
    })
    assert registration.status_code == 201, registration.text
    org_admin_headers = bearer(registration)

    created_department = client.post("/api/departments", headers=org_admin_headers, json={"name": "Research"})
    assert created_department.status_code == 201, created_department.text
    branch = client.post("/api/branches", headers=org_admin_headers, json={
        "code": "HQ", "name": "Head Office", "address": "Main campus",
    })
    designation = client.post("/api/designations", headers=org_admin_headers, json={"name": "Analyst"})
    grade = client.post("/api/job-grades", headers=org_admin_headers, json={
        "code": "G1", "name": "Grade 1", "rank": 1,
    })
    assert branch.status_code == 201, branch.text
    assert designation.status_code == 201, designation.text
    assert grade.status_code == 201, grade.text
    assert client.post("/api/branches", headers=org_admin_headers, json={
        "code": "HQ-2", "name": "head office",
    }).status_code == 409
    employee = client.post("/api/employees", headers=org_admin_headers, json={
        "employee_code": "ORG-EMP-1", "name": "Research Employee", "department": "Research", "role": "Analyst",
        "branch_id": branch.json()["id"], "designation_id": designation.json()["id"],
        "job_grade_id": grade.json()["id"],
    })
    assert employee.status_code == 201, employee.text
    assert employee.json()["branch_id"] == branch.json()["id"]
    assert employee.json()["designation_id"] == designation.json()["id"]
    assert employee.json()["job_grade_id"] == grade.json()["id"]
    assert client.get(f"/api/employees/{employee.json()['id']}/contact", headers=org_admin_headers).status_code == 403
    assert client.get(f"/api/employees/{employee.json()['id']}/employment-history", headers=org_admin_headers).status_code == 403
    subordinate = client.post("/api/employees", headers=org_admin_headers, json={
        "employee_code": "ORG-EMP-2", "name": "Second Employee", "department": "Research", "role": "Associate",
        "reporting_manager_id": employee.json()["id"],
    })
    assert subordinate.status_code == 201, subordinate.text
    cycle = client.put(f"/api/employees/{employee.json()['id']}", headers=super_admin_headers, json={
        "employee_code": "ORG-EMP-1", "name": "Research Employee", "department": "Research", "role": "Analyst",
        "branch_id": branch.json()["id"], "designation_id": designation.json()["id"],
        "job_grade_id": grade.json()["id"], "reporting_manager_id": subordinate.json()["id"],
    })
    assert cycle.status_code == 422
    assert client.delete(f"/api/designations/{designation.json()['id']}", headers=org_admin_headers).status_code == 204
    inactive_assignment = client.post("/api/employees", headers=org_admin_headers, json={
        "employee_code": "ORG-EMP-ARCHIVE", "name": "Archived Assignment", "department": "Research", "role": "Analyst",
        "designation_id": designation.json()["id"],
    })
    assert inactive_assignment.status_code == 422
    org_profile = client.get("/api/organization", headers=org_admin_headers)
    assert org_profile.status_code == 200
    renamed = client.patch("/api/organization", headers=org_admin_headers, json={"name": "NEXORA Research"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "NEXORA Research"

    assert client.post("/api/users/invitations", headers=org_admin_headers, json={
        "name": "New HR Manager", "email": "blocked-hr@example.com", "role": "HR Manager",
    }).status_code == 403
    assert client.post("/api/users/invitations", headers=org_admin_headers, json={
        "name": "Another Org Admin", "email": "blocked-admin@example.com", "role": "Organization Admin",
    }).status_code == 403
    super_admin_id = client.get("/api/auth/me", headers=super_admin_headers).json()["id"]
    assert client.patch(f"/api/users/{super_admin_id}", headers=org_admin_headers, json={"active": False}).status_code == 403

    with Session(client.app.state.engine) as db:
        second_organization = models.Organization(name="Second Organization", slug="second-organization")
        db.add(second_organization)
        db.flush()
        second_org_id = second_organization.id
        db.commit()
    with Session(client.app.state.engine) as db:
        db.info["organization_id"] = second_org_id
        second_user = models.User(
            name="Second Org User", email="second-org-user@example.com", role="Employee", active=True,
            hashed_password=hash_password("second-org-user-password"),
        )
        db.add(second_user)
        db.flush()
        second_user_id = second_user.id
        second_branch = models.Branch(code="HQ", name="Head Office")
        db.add(second_branch)
        db.flush()
        second_branch_id = second_branch.id
        db.commit()

    cross_org_employee = client.post("/api/employees", headers=org_admin_headers, json={
        "employee_code": "ORG-EMP-3", "name": "Cross Scope", "department": "Research", "role": "Analyst",
        "branch_id": second_branch_id,
    })
    assert cross_org_employee.status_code == 422

    accounts = client.get("/api/users?limit=100", headers=org_admin_headers)
    assert accounts.status_code == 200
    assert all(row["id"] != second_user_id for row in accounts.json()["items"])
    assert client.patch(f"/api/users/{second_user_id}", headers=org_admin_headers, json={"active": False}).status_code == 404


def test_leave_dates_and_employee_data_are_validated(client):
    admin = admin_login(client)
    employee = register(client, "person@example.com")
    headers = bearer(employee)
    invalid = client.post("/api/leave-requests", json={
        "start_date": "2026-10-17", "end_date": "2026-10-16", "reason": "Wrong dates",
    }, headers=headers)
    assert invalid.status_code == 422
    assert client.patch("/api/employees/2/status", json={"status": "Active"}, headers=headers).status_code == 403
    assert client.patch("/api/employees/2/status", json={"status": "Unknown"}, headers=bearer(admin)).status_code == 422


def test_dashboard_metrics_filters_password_change_and_leave_overlap(client):
    admin = admin_login(client)
    employee = register(client, "employee@example.com")
    admin_headers = bearer(admin)
    employee_headers = bearer(employee)

    client.post("/api/employees", headers=admin_headers, json={
        "employee_code": "E-200", "name": "Active Person", "department": "People", "role": "Analyst", "status": "Active",
    })
    client.post("/api/employees", headers=admin_headers, json={
        "employee_code": "E-201", "name": "On Leave Person", "department": "Finance", "role": "Analyst", "status": "On leave",
    })
    filtered = client.get("/api/employees?search=Active&status=Active", headers=admin_headers)
    assert filtered.status_code == 200
    assert [item["employee_code"] for item in filtered.json()] == ["E-200"]

    dashboard = client.get("/api/dashboard", headers=admin_headers).json()
    assert dashboard["employee_count"] == 3
    assert dashboard["active_employee_count"] == 2
    assert dashboard["employees_on_leave_count"] == 1

    start = date.today() + timedelta(days=10)
    while start.weekday() >= 5:  # skip weekends so the request contains working days
        start += timedelta(days=1)
    end = start + timedelta(days=1)
    while end.weekday() >= 5:  # ensure the end date is also a weekday
        end += timedelta(days=1)
    payload = {"start_date": start.isoformat(), "end_date": end.isoformat(), "reason": "Family event"}
    payload["leave_type_id"] = client.get("/api/leave-types", headers=admin_headers).json()[0]["id"]
    assert client.post("/api/leave-requests", json=payload, headers=employee_headers).status_code == 201
    assert client.post("/api/leave-requests", json=payload, headers=employee_headers).status_code == 409

    second_session = client.post("/api/auth/login", json={
        "email": "employee@example.com", "password": "strong-password-123",
    })
    changed = client.post("/api/auth/password", headers=employee_headers, json={
        "current_password": "strong-password-123", "new_password": "new-strong-password-456",
    })
    assert changed.status_code == 204
    assert client.get("/api/auth/me", headers=employee_headers).status_code == 401
    assert client.get("/api/auth/me", headers=bearer(second_session)).status_code == 401
    assert client.post("/api/auth/login", json={
        "email": "employee@example.com", "password": "new-strong-password-456",
    }).status_code == 200


def test_organization_membership_drives_authorization_and_can_be_revoked(client):
    admin_headers = bearer(admin_login(client))
    employee = register(client, "membership.employee@example.com")
    employee_headers = bearer(employee)
    employee_user_id = employee.json()["user"]["id"]

    memberships = client.get("/api/organization-memberships?limit=100", headers=admin_headers)
    assert memberships.status_code == 200, memberships.text
    assert memberships.json()["total"] == 2
    member_row = next(row for row in memberships.json()["items"] if row["user_id"] == employee_user_id)
    assert member_row["role"] == "Employee"
    assert member_row["active"] is True

    changed = client.patch(f"/api/users/{employee_user_id}", headers=admin_headers, json={"role": "Recruiter"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "Recruiter"
    with Session(client.app.state.engine) as db:
        db.info["organization_id"] = 1
        account = db.get(models.User, employee_user_id)
        membership = db.query(models.OrganizationMembership).filter_by(user_id=employee_user_id).one()
        # The membership is the role source even if a legacy account column drifts.
        account.role = "Employee"
        db.commit()

    me = client.get("/api/auth/me", headers=employee_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "Recruiter"
    with Session(client.app.state.engine) as db:
        db.info["organization_id"] = 1
        membership = db.query(models.OrganizationMembership).filter_by(user_id=employee_user_id).one()
        membership.active = False
        db.commit()
    assert client.get("/api/auth/me", headers=employee_headers).status_code == 401


def test_employee_cannot_access_cross_employee_directory_or_profile_ids(client):
    admin_headers = bearer(admin_login(client))
    first_account = register(client, "first.employee@example.com")
    second_account = register(client, "second.employee@example.com")
    first_headers = bearer(first_account)
    second_headers = bearer(second_account)

    first_profile = client.get("/api/employees/me", headers=first_headers)
    second_profile = client.get("/api/employees/me", headers=second_headers)
    assert first_profile.status_code == 200
    assert second_profile.status_code == 200
    assert first_profile.json()["id"] != second_profile.json()["id"]
    assert client.get(f"/api/employees/{second_profile.json()['id']}", headers=first_headers).status_code == 403
    assert client.get("/api/employees/directory", headers=first_headers).status_code == 403
    assert client.get("/api/employees?user_id=2", headers=first_headers).status_code == 403
    assert client.patch(f"/api/employees/{second_profile.json()['id']}/status", json={"status": "Inactive"}, headers=first_headers).status_code == 403

    invite = client.post("/api/users/invitations", headers=admin_headers, json={
        "name": "Third Person", "email": "third@example.com", "role": "Employee",
        "employee_id": first_profile.json()["id"],
    })
    assert invite.status_code == 409


def test_role_boundaries_and_department_manager_scope(client):
    admin_headers = bearer(admin_login(client))
    operations = client.post("/api/departments", headers=admin_headers, json={"name": "Operations"}).json()
    client.post("/api/departments", headers=admin_headers, json={"name": "People"})
    people = client.get("/api/departments?limit=100", headers=admin_headers).json()["items"]
    people_department = next(item for item in people if item["name"] == "People")

    employee = client.post("/api/employees", headers=admin_headers, json={
        "employee_code": "OPS-1", "name": "Operations Staff", "department": "Operations", "role": "Analyst",
    }).json()
    outside_employee = client.post("/api/employees", headers=admin_headers, json={
        "employee_code": "PEOPLE-1", "name": "People Staff", "department": "People", "role": "Partner",
    }).json()
    invite = client.post("/api/users/invitations", headers=admin_headers, json={
        "name": "Operations Manager", "email": "manager@example.com", "role": "Department Manager",
        "department_id": operations["id"],
    })
    assert invite.status_code == 201, invite.text
    manager_login = client.post("/api/auth/register-invited", json={
        "invitation_token": invite.json()["invitation_token"], "password": "manager-strong-password-789",
    })
    manager_headers = bearer(manager_login)
    assert manager_login.status_code == 201
    scoped_records = client.get("/api/employees", headers=manager_headers).json()
    assert [row["employee_code"] for row in scoped_records] == ["OPS-1"]
    assert client.get(f"/api/employees/{employee['id']}", headers=manager_headers).status_code == 200
    assert client.get(f"/api/employees/{outside_employee['id']}", headers=manager_headers).status_code == 403
    assert client.get(f"/api/departments?limit=10", headers=manager_headers).json()["total"] == 1

    recruiter_invite = client.post("/api/users/invitations", headers=admin_headers, json={
        "name": "Recruiter", "email": "recruiter@example.com", "role": "Recruiter",
    })
    recruiter_headers = bearer(client.post("/api/auth/register-invited", json={
        "invitation_token": recruiter_invite.json()["invitation_token"], "password": "recruiter-strong-password",
    }))
    assert client.post("/api/departments", headers=recruiter_headers, json={"name": "Forbidden"}).status_code == 403
    assert client.get("/api/audit-logs", headers=recruiter_headers).status_code == 403
    assert client.patch("/api/users/2", headers=recruiter_headers, json={"role": "Super Admin"}).status_code == 403
    assert client.get(f"/api/departments?department_id={people_department['id']}", headers=manager_headers).status_code == 200


def test_invitation_code_completes_registration_once_and_compatibility_route_remains(client):
    headers = bearer(admin_login(client))
    response = client.post("/api/departments", headers=headers, json={"name": "Support"})
    assert response.status_code == 201
    department = response.json()
    invite = client.post("/api/users/invitations", headers=headers, json={
        "name": "Support Manager", "email": "support.manager@example.com", "role": "Department Manager",
        "department_id": department["id"],
    })
    assert invite.status_code == 201
    account = invite.json()["user"]
    assert account["active"] is False
    assert account["registration_pending"] is True
    assert client.post("/api/auth/login", json={
        "email": account["email"], "password": "some-unset-password",
    }).status_code == 401
    registration = {"invitation_token": invite.json()["invitation_token"], "password": "one-time-registration-password"}
    completed = client.post("/api/auth/register-invited", json=registration)
    assert completed.status_code == 201, completed.text
    assert completed.json()["message"] == "Registration complete. You are now signed in."
    assert completed.json()["user"]["role"] == "Department Manager"
    assert client.get("/api/auth/me", headers=bearer(completed)).status_code == 200
    assert client.post("/api/auth/activate", json=registration).status_code == 400
    assert client.post("/api/auth/register-invited", json={**registration, "role": "Super Admin"}).status_code == 422
    openapi_paths = client.get("/openapi.json").json()["paths"]
    assert "/api/auth/register-invited" in openapi_paths
    assert "/api/auth/activate" not in openapi_paths
    operation_ids = [operation["operationId"] for path in openapi_paths.values() for operation in path.values()]
    assert len(operation_ids) == len(set(operation_ids))


def test_pending_registration_code_can_be_reissued_and_cannot_be_reactivated(client):
    headers = bearer(admin_login(client))
    department = client.post("/api/departments", headers=headers, json={"name": "Reissue"}).json()
    invite = client.post("/api/users/invitations", headers=headers, json={
        "name": "Pending Person", "email": "pending@example.com", "role": "Department Manager",
        "department_id": department["id"],
    })
    assert invite.status_code == 201, invite.text
    user_id = invite.json()["user"]["id"]
    account_list = client.get("/api/users?limit=100", headers=headers)
    assert account_list.status_code == 200
    listed = next(row for row in account_list.json()["items"] if row["id"] == user_id)
    assert listed["registration_pending"] is True
    assert client.patch(f"/api/users/{user_id}", headers=headers, json={"active": True}).status_code == 409

    with Session(client.app.state.engine) as db:
        db.info["organization_id"] = 1
        pending_invitation = db.query(models.Invitation).filter_by(user_id=user_id).one()
        pending_invitation.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

    reissued = client.post(f"/api/users/{user_id}/invitation", headers=headers)
    assert reissued.status_code == 200, reissued.text
    assert reissued.json()["invitation_token"] != invite.json()["invitation_token"]
    old_code = {"invitation_token": invite.json()["invitation_token"], "password": "valid-registration-password"}
    new_code = {"invitation_token": reissued.json()["invitation_token"], "password": "valid-registration-password"}
    assert client.post("/api/auth/register-invited", json=old_code).status_code == 400
    completed = client.post("/api/auth/register-invited", json=new_code)
    assert completed.status_code == 201, completed.text
    assert completed.json()["user"]["registration_pending"] is False
    assert client.post(f"/api/users/{user_id}/invitation", headers=headers).status_code == 409


def test_concurrent_registration_code_use_only_completes_once(client):
    headers = bearer(admin_login(client))
    department = client.post("/api/departments", headers=headers, json={"name": "Concurrent Registration"}).json()
    invite = client.post("/api/users/invitations", headers=headers, json={
        "name": "Concurrent Person", "email": "concurrent-registration@example.com", "role": "Department Manager",
        "department_id": department["id"],
    })
    assert invite.status_code == 201, invite.text
    token = invite.json()["invitation_token"]
    second_app = create_app(
        str(client.app.state.engine.url),
        secret_key="test-secret-key-that-is-long-enough",
    )
    barrier = Barrier(2)
    with TestClient(second_app) as second_client:
        def complete(client_instance):
            barrier.wait()
            return client_instance.post("/api/auth/register-invited", json={
                "invitation_token": token, "password": "concurrent-registration-password",
            }).status_code

        with ThreadPoolExecutor(max_workers=2) as workers:
            outcomes = list(workers.map(complete, [client, second_client]))
    assert sorted(outcomes) == [201, 400]


def test_enabled_directory_returns_only_approved_fields(tmp_path):
    app = create_app(
        f"sqlite:///{tmp_path / 'directory.sqlite3'}",
        secret_key="test-secret-key-that-is-long-enough",
        employee_directory_enabled=True,
    )
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
        db.add(models.Department(name="Design", active=True))
        db.add(models.Employee(employee_code="NX-1", name="Public Name", department="Design",
                               role="Designer", status="Active"))
        db.commit()
    with TestClient(app) as enabled_client:
        headers = bearer(admin_login(enabled_client))
        invite = enabled_client.post("/api/users/invitations", headers=headers, json={
            "name": "Directory User", "email": "directory.user@example.com", "role": "Employee", "employee_id": 1,
        })
        employee = enabled_client.post("/api/auth/register-invited", json={
            "invitation_token": invite.json()["invitation_token"], "password": "directory-user-password-123",
        })
        response = enabled_client.get("/api/employees/directory", headers=bearer(employee))
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"] == [{
            "id": 1, "employee_code": "NX-1", "name": "Public Name",
            "department": "Design", "role": "Designer", "status": "Active",
        }]
        assert enabled_client.get("/api/employees", headers=bearer(employee)).status_code == 403


def test_leave_balance_deduction_working_days_half_days_and_policy_permissions(client):
    admin_headers = bearer(admin_login(client))
    employee = register(client, "leave.balance@example.com")
    employee_headers = bearer(employee)
    policy_response = client.post("/api/leave-types", headers=admin_headers, json={
        "name": "Personal", "description": "Personal leave", "annual_allowance_days": 2, "paid": True,
    })
    assert policy_response.status_code == 201, policy_response.text
    policy_id = policy_response.json()["id"]
    assert client.post("/api/leave-types", headers=employee_headers, json={
        "name": "Unauthorized", "annual_allowance_days": 10,
    }).status_code == 403

    friday = date(2026, 11, 6)
    monday = date(2026, 11, 9)
    assert client.post("/api/holidays", headers=admin_headers, json={
        "holiday_date": monday.isoformat(), "name": "Configured Holiday",
    }).status_code == 201
    request = client.post("/api/leave-requests", headers=employee_headers, json={
        "start_date": friday.isoformat(), "end_date": monday.isoformat(),
        "leave_type_id": policy_id, "reason": "Personal commitment",
    })
    assert request.status_code == 201, request.text
    assert request.json()["days_requested"] == "1.00"
    balance_rows = client.get("/api/leave-balances?year=2026", headers=employee_headers).json()
    assert next(row for row in balance_rows if row["leave_type"] == "Personal")["pending_days"] == "1.00"

    approved = client.post(f"/api/leave-requests/{request.json()['id']}/review", headers=admin_headers, json={"decision": "Approved"})
    assert approved.status_code == 200, approved.text
    balance_rows = client.get("/api/leave-balances?year=2026", headers=employee_headers).json()
    assert next(row for row in balance_rows if row["leave_type"] == "Personal")["used_days"] == "1.00"
    assert client.post(f"/api/leave-requests/{request.json()['id']}/review", headers=admin_headers, json={"decision": "Approved"}).status_code == 409

    next_day = date(2026, 11, 10)
    half_day = client.post("/api/leave-requests", headers=employee_headers, json={
        "start_date": next_day.isoformat(), "end_date": next_day.isoformat(),
        "leave_type_id": policy_id, "half_day": True, "reason": "Appointment",
    })
    assert half_day.status_code == 201, half_day.text
    approved_half = client.post(f"/api/leave-requests/{half_day.json()['id']}/review", headers=admin_headers, json={"decision": "Approved"})
    assert approved_half.status_code == 200
    balance = next(row for row in client.get("/api/leave-balances?year=2026", headers=employee_headers).json() if row["leave_type"] == "Personal")
    assert balance["used_days"] == "1.50"
    assert balance["remaining_days"] == "0.50"

    exhausted = client.post("/api/leave-requests", headers=employee_headers, json={
        "start_date": date(2026, 11, 11).isoformat(), "end_date": date(2026, 11, 11).isoformat(),
        "leave_type_id": policy_id, "reason": "Need one full day",
    })
    assert exhausted.status_code == 201
    refused = client.post(f"/api/leave-requests/{exhausted.json()['id']}/review", headers=admin_headers, json={"decision": "Approved"})
    assert refused.status_code == 409
    balance_rows = client.get("/api/leave-balances?year=2026", headers=employee_headers).json()
    assert next(row for row in balance_rows if row["leave_type"] == "Personal")["used_days"] == "1.50"

    future = client.post("/api/leave-requests", headers=employee_headers, json={
        "start_date": date(2026, 12, 1).isoformat(), "end_date": date(2026, 12, 1).isoformat(),
        "leave_type_id": policy_id, "half_day": True, "reason": "Future appointment",
    })
    assert future.status_code == 201
    assert client.post(f"/api/leave-requests/{future.json()['id']}/review", headers=admin_headers,
                       json={"decision": "Approved", "comment": "Approved by manager"}).status_code == 200
    before_cancel = next(row for row in client.get("/api/leave-balances?year=2026", headers=employee_headers).json() if row["leave_type"] == "Personal")
    assert before_cancel["used_days"] == "2.00"
    cancelled = client.post(f"/api/leave-requests/{future.json()['id']}/cancel", headers=employee_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "Cancelled"
    assert cancelled.json()["review_comment"] == "Approved by manager"
    after_cancel = next(row for row in client.get("/api/leave-balances?year=2026", headers=employee_headers).json() if row["leave_type"] == "Personal")
    assert after_cancel["used_days"] == "1.50"


def test_leave_requests_reject_non_workdays_and_cross_year_ranges(client):
    admin_headers = bearer(admin_login(client))
    employee_headers = bearer(register(client, "date.rules@example.com"))
    policy_id = client.get("/api/leave-types", headers=admin_headers).json()[0]["id"]
    weekend = client.post("/api/leave-requests", headers=employee_headers, json={
        "start_date": "2026-11-07", "end_date": "2026-11-08", "leave_type_id": policy_id,
        "reason": "Weekend only",
    })
    assert weekend.status_code == 422
    cross_year = client.post("/api/leave-requests", headers=employee_headers, json={
        "start_date": "2026-12-31", "end_date": "2027-01-01", "leave_type_id": policy_id,
        "reason": "Across years",
    })
    assert cross_year.status_code == 422


def test_half_day_on_weekend_is_rejected(client):
    admin_headers = bearer(admin_login(client))
    employee_headers = bearer(register(client, "weekend.half@example.com"))
    policy_id = client.get("/api/leave-types", headers=admin_headers).json()[0]["id"]
    response = client.post("/api/leave-requests", headers=employee_headers, json={
        "start_date": "2026-11-07", "end_date": "2026-11-07", "leave_type_id": policy_id,
        "half_day": True, "reason": "Weekend request",
    })
    assert response.status_code == 422


# Expected module catalog seeded from DEFAULT_MODULES (application.py).
ALL_MODULE_KEYS = [
    "overview", "employees", "departments", "organization", "attendance",
    "leave", "users", "payroll", "recruitment", "performance", "learning",
    "notifications", "reports", "settings", "module-access",
]
# Modules whose default_granted list includes the Employee role.
EMPLOYEE_MODULE_KEYS = [
    "overview", "employees", "attendance", "leave", "payroll",
    "performance", "learning", "notifications", "settings",
]


def test_my_permissions_returns_full_catalog_for_super_admin(client):
    response = client.get("/api/my-permissions", headers=bearer(admin_login(client)))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert sorted(payload["accessible_modules"]) == sorted(ALL_MODULE_KEYS)
    assert sorted(module["module_key"] for module in payload["modules"]) == sorted(ALL_MODULE_KEYS)


def test_my_permissions_returns_role_subset_for_employee(client):
    employee_headers = bearer(register(client, "menu.subset@example.com"))
    response = client.get("/api/my-permissions", headers=employee_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert sorted(payload["accessible_modules"]) == sorted(EMPLOYEE_MODULE_KEYS)
    # The module catalog itself stays complete; only accessible_modules filters.
    assert sorted(module["module_key"] for module in payload["modules"]) == sorted(ALL_MODULE_KEYS)
    # Employee must never see administrative modules in their menu.
    assert "module-access" not in payload["accessible_modules"]
    assert "users" not in payload["accessible_modules"]


def test_modules_catalog_is_listable_without_super_admin(client):
    """GET /api/modules must serve the full catalog to any authenticated user."""
    employee_headers = bearer(register(client, "menu.catalog@example.com"))
    response = client.get("/api/modules", headers=employee_headers)
    assert response.status_code == 200, response.text
    modules = response.json()
    assert sorted(module["module_key"] for module in modules) == sorted(ALL_MODULE_KEYS)
    # Each module exposes role permission rows so the UI can render access control.
    module_access = next(module for module in modules if module["module_key"] == "module-access")
    granted_roles = {perm["role"] for perm in module_access["permissions"] if perm["granted"]}
    assert granted_roles == {"Super Admin"}
    assert client.get("/api/modules").status_code == 401


def test_module_seed_persists_across_request_sessions(client):
    """Seeded catalog must survive session close; get_db never commits."""
    assert client.get("/api/my-permissions", headers=bearer(admin_login(client))).status_code == 200
    with Session(client.app.state.engine) as db:
        assert db.query(models.Module).count() == len(ALL_MODULE_KEYS)
        assert db.query(models.RoleModulePermission).count() == len(ALL_MODULE_KEYS) * 9  # ALL_ROLES has 9 roles.
    # A second request must not duplicate the seed.
    assert client.get("/api/my-permissions", headers=bearer(admin_login(client))).status_code == 200
    with Session(client.app.state.engine) as db:
        assert db.query(models.Module).count() == len(ALL_MODULE_KEYS)
