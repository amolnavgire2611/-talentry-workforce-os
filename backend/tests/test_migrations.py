import sqlite3
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_additive_migration_preserves_legacy_records(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE, hashed_password VARCHAR(255) NOT NULL
        );
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY, employee_code VARCHAR(20) NOT NULL UNIQUE,
            name VARCHAR(100) NOT NULL, department VARCHAR(100) NOT NULL,
            role VARCHAR(100) NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'Active'
        );
        INSERT INTO users (id, name, email, hashed_password)
        VALUES (41, 'Legacy Admin', 'legacy@example.com', 'preserved-hash');
        INSERT INTO employees (id, employee_code, name, department, role, status)
        VALUES (52, 'NX-52', 'Legacy Employee', 'Operations', 'Associate', 'Active');
        """
    )
    connection.commit()
    connection.close()

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["database_url"] = f"sqlite:///{db_path}"
    command.upgrade(config, "0001_additive_foundation")
    interim = create_engine(f"sqlite:///{db_path}")
    with interim.begin() as connection:
        connection.execute(text("UPDATE users SET role = 'HR Admin' WHERE id = 41"))
    interim.dispose()
    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    assert {"organizations", "departments", "branches", "designations", "job_grades", "attendance", "leave_requests", "audit_logs", "invitations", "revoked_tokens", "refresh_sessions", "leave_types", "leave_balances", "holidays", "employee_contacts", "emergency_contacts", "employee_employment_history", "organization_memberships"}.issubset(inspector.get_table_names())
    assert {"role", "active"}.issubset({column["name"] for column in inspector.get_columns("users")})
    assert {"user_id"}.issubset({column["name"] for column in inspector.get_columns("employees")})
    assert {"branch_id", "designation_id", "job_grade_id", "reporting_manager_id"}.issubset(
        {column["name"] for column in inspector.get_columns("employees")}
    )
    assert {"leave_type_id", "half_day", "days_requested", "review_comment"}.issubset(
        {column["name"] for column in inspector.get_columns("leave_requests")}
    )
    with engine.connect() as migrated:
        user = migrated.execute(text("SELECT id, email, hashed_password, role, active FROM users WHERE id = 41")).one()
        employee = migrated.execute(text("SELECT id, employee_code, name FROM employees WHERE id = 52")).one()
        organization = migrated.execute(text("SELECT id, name, slug FROM organizations")).one()
        tenant_ids = {
            table: migrated.execute(text(f"SELECT DISTINCT organization_id FROM {table}")).scalars().all()
            for table in ("users", "employees", "departments", "invitations", "revoked_tokens", "refresh_sessions", "attendance", "leave_requests", "leave_types", "leave_balances", "holidays", "audit_logs", "organization_memberships")
        }
    assert user == (41, "legacy@example.com", "preserved-hash", "HR Administrator", 1)
    assert employee == (52, "NX-52", "Legacy Employee")
    with engine.connect() as migrated:
        employee_assignment = migrated.execute(text(
            "SELECT branch_id, designation_id, job_grade_id, reporting_manager_id FROM employees WHERE id = 52"
        )).one()
    assert employee_assignment == (None, None, None, None)
    assert organization == (1, "NEXORA", "nexora")
    assert all(values in ([], [1]) for values in tenant_ids.values())
    assert tenant_ids["users"] == [1]
    assert tenant_ids["employees"] == [1]
    assert tenant_ids["organization_memberships"] == [1]
    with engine.connect() as migrated:
        membership = migrated.execute(text(
            "SELECT organization_id, user_id, role, active FROM organization_memberships WHERE user_id = 41"
        )).one()
        assert migrated.execute(text("SELECT count(*) FROM organization_memberships")).scalar_one() == 1
    assert membership == (1, 41, "HR Administrator", 1)
    for table in ("employee_contacts", "emergency_contacts", "employee_employment_history"):
        organization_column = next(column for column in inspect(engine).get_columns(table) if column["name"] == "organization_id")
        assert organization_column["nullable"] is False
        assert any(foreign_key["referred_table"] == "organizations" for foreign_key in inspect(engine).get_foreign_keys(table))
    membership_organization_column = next(column for column in inspect(engine).get_columns("organization_memberships") if column["name"] == "organization_id")
    assert membership_organization_column["nullable"] is False
    assert any(foreign_key["referred_table"] == "organizations" for foreign_key in inspect(engine).get_foreign_keys("organization_memberships"))
    with engine.connect() as migrated:
        assert migrated.execute(text("SELECT count(*) FROM employee_employment_history")).scalar_one() == 0
    for table in tenant_ids:
        organization_column = next(column for column in inspect(engine).get_columns(table) if column["name"] == "organization_id")
        assert organization_column["nullable"] is False
        assert any(foreign_key["referred_table"] == "organizations" for foreign_key in inspect(engine).get_foreign_keys(table))
    for table in ("branches", "designations", "job_grades"):
        organization_column = next(column for column in inspect(engine).get_columns(table) if column["name"] == "organization_id")
        assert organization_column["nullable"] is False
        assert any(foreign_key["referred_table"] == "organizations" for foreign_key in inspect(engine).get_foreign_keys(table))
    assert {"organization_id", "employee_code"} == set(next(
        constraint["column_names"] for constraint in inspect(engine).get_unique_constraints("employees")
        if constraint["name"] == "uq_employees_org_employee_code"
    ))
    assert {"organization_id", "holiday_date"} == set(next(
        constraint["column_names"] for constraint in inspect(engine).get_unique_constraints("holidays")
        if constraint["name"] == "uq_holidays_org_date"
    ))
    with engine.begin() as migrated:
        migrated.execute(text("INSERT INTO organizations (id, name, slug) VALUES (2, 'Second', 'second')"))
        migrated.execute(text(
            "INSERT INTO employees (id, employee_code, name, department, role, status, organization_id) "
            "VALUES (53, 'NX-52', 'Second Tenant Employee', 'Operations', 'Associate', 'Active', 2)"
        ))
        migrated.execute(text(
            "INSERT INTO departments (name, active, organization_id) VALUES ('Operations', 1, 1), ('operations', 1, 2)"
        ))
        migrated.execute(text(
            "INSERT INTO leave_types (name, annual_allowance_days, paid, active, organization_id) "
            "VALUES ('Annual', 20, 1, 1, 1), ('annual', 20, 1, 1, 2)"
        ))
        migrated.execute(text(
            "INSERT INTO holidays (holiday_date, name, active, organization_id) "
            "VALUES ('2026-01-01', 'New Year', 1, 1), ('2026-01-01', 'New Year', 1, 2)"
        ))
    with engine.connect() as migrated:
        # Regression for 0016: SQLite must never end up with PostgreSQL-only
        # now() column defaults anywhere in the final schema.
        leftover = migrated.execute(text(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND sql LIKE '%now()%'"
        )).scalars().all()
        assert leftover == []
    with engine.begin() as migrated:
        # The login flow seeds the catalog with server-generated timestamps;
        # these inserts failed before 0016 with "unknown function: now()".
        migrated.execute(text(
            "INSERT INTO modules (module_key, name, description, active, organization_id) "
            "VALUES ('regression', 'Regression', NULL, 1, 1)"
        ))
        module_created_at = migrated.execute(text(
            "SELECT created_at FROM modules WHERE module_key = 'regression'"
        )).scalar_one()
        assert module_created_at is not None
        datetime.fromisoformat(module_created_at)
        module_id = migrated.execute(text(
            "SELECT id FROM modules WHERE module_key = 'regression'"
        )).scalar_one()
        migrated.execute(text(
            "INSERT INTO role_module_permissions (organization_id, module_id, role, granted) "
            "VALUES (1, :module_id, 'Employee', 1)"
        ), {"module_id": module_id})
        perm_created_at = migrated.execute(text(
            "SELECT created_at FROM role_module_permissions WHERE module_id = :module_id"
        ), {"module_id": module_id}).scalar_one()
        datetime.fromisoformat(perm_created_at)
    engine.dispose()
