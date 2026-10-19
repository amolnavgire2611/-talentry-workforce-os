# Backend API

FastAPI + SQLAlchemy workforce API. This backend uses the existing `backend/users.db` by default. It does **not** run `create_all`, drop tables, reset the database, or run migrations automatically on startup.

## Configuration

From this directory, copy `.env.example` to `.env` and set `NEXORA_SECRET_KEY` to a long random secret. To enable first-Super-Admin registration in the UI, set `ADMIN_BOOTSTRAP_TOKEN` to a private random value of at least 32 characters. Remove it after setup. `DATABASE_URL` is an SQLAlchemy URL; unset uses the absolute path to this `backend/users.db`, independent of the process working directory. Configure `ACCESS_TOKEN_MINUTES`, `REFRESH_SESSION_DAYS`, `TOKEN_ISSUER`, `TOKEN_AUDIENCE`, `CORS_ORIGINS`, and `APP_ENV` as required. Refresh cookies default to `Secure` in production and non-Secure for local development. Production mode refuses the development signing key and secrets shorter than 32 characters. Keep `.env` private and out of version control.

Example PostgreSQL URL: `postgresql+psycopg://user:password@host/database` (install the corresponding DB driver when switching from SQLite).

## Legacy database and migrations

The checked-in legacy SQLite database already has `users` and `employees` tables and contains data. Back it up before any migration. The initial Alembic revision `0001_additive_foundation` introspects those tables, adds only the `users.role` and `users.active` columns when missing, preserves both legacy tables and all rows, and adds the new workflow tables and unique indexes. Revisions `0002`–`0004` add invitation/revocation, leave policies and refresh-session storage. They do not rename, rebuild, truncate, or delete legacy tables. Downgrades are intentionally forward-only/no-op so rollback cannot remove history.

For an existing populated database, run this once from `backend/`:

```sh
alembic upgrade head
```

If an existing deployment already has the equivalent new schema from a separately reviewed manual setup, inspect it first and then stamp only that known-compatible database with `alembic stamp head`; never stamp an unmigrated database. The migration fails rather than silently changing records when duplicate case-insensitive legacy emails or employee codes conflict with new uniqueness indexes. Resolve such conflicts manually after a backup, or adjust and review the migration before applying it.

The app intentionally does not auto-migrate at startup. Do not point tests or experiments at `users.db`.

## Development

From `backend/`:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set NEXORA_SECRET_KEY in .env, then migrate the retained database.
alembic upgrade head
# Optional fallback if you are not using the guarded UI setup: provision the initial Super Admin interactively.
python -m bootstrap_admin
uvicorn main:app --reload
```

`POST /api/auth/register` creates an active Employee account and returns a sign-in token. The first Super Admin can be created through `/api/auth/register-admin` when `ADMIN_BOOTSTRAP_TOKEN` is configured; the route closes permanently once any Super Admin record exists, including an inactive one. `/api/register` remains as a compatibility alias, and `/api/login` remains available for older clients. The UI uses `/api/auth/login`, `/api/auth/register`, `/api/auth/register-invited`, `/api/auth/admin-registration-status`, `/api/auth/register-admin`, `/api/auth/me`, `/api/auth/refresh`, `/api/auth/sessions`, `/api/auth/logout`, and `/api/auth/password`. The hidden `/api/auth/activate` route is retained as a compatibility alias for invitation-code registration. Access tokens are short-lived HS256 JWTs validated for issuer, audience, expiry and type. Refresh requires the `nexora_refresh` HttpOnly cookie, `X-CSRF-Token`, and an allowed `Origin`. Session operations are scoped to the authenticated user. Password change and account deactivation revoke all that user's refresh sessions. Existing users must sign in after migration `0004_refresh_sessions`; app startup does not auto-migrate.

## API overview

- Auth: `POST /api/auth/register`, one-time `POST /api/auth/register-admin`, `GET /api/auth/admin-registration-status`, `POST /api/auth/login`, `POST /api/auth/register-invited`, `POST /api/auth/refresh`, `GET/DELETE /api/auth/sessions`, `GET /api/auth/me`, `POST /api/auth/logout`, `POST /api/auth/password`.
- Provisioning: Super Admin / HR Administrator `POST /api/users/invitations`; invitation code is stored hashed, returned once, expires in 48 hours, and the account remains pending until the invitee completes registration. A pending code may be rotated with `POST /api/users/{id}/invitation`.
- Employees: HR roles can use full `/api/employees` and paginated `/api/employees/directory`; employees cannot list full records and can only use `GET/PUT /api/employees/me` and their own ID after account/profile linking. Employee directory is disabled unless `EMPLOYEE_DIRECTORY_ENABLED=true`, then only a limited approved projection is exposed.
- Departments: authenticated list; HR roles can create/update/archive. Department Managers see only their assigned department.
- Attendance: authenticated clock-in/out and own history; HR/Attendance Administrators can view organization records; Department Managers see linked team records. Daily dates use UTC; shift and holiday rules are not configured.
- Leave: HR roles create and maintain leave types/annual allocations and holidays; employees submit policy-linked full/half-day requests; weekends and configured holidays are excluded; employees see their own calendar-year balances, and managers can review within scope. Approval atomically deducts balance, insufficient balance is rejected, future approved requests can be cancelled with balance restoration, and reviewer comments are recorded. No carry-forward, accrual schedules, partial-year proration, multi-stage approvals, or statutory leave assumptions are configured.
- Dashboard: `/api/dashboard`; returns role-scoped organization, department, attendance, recruitment, payroll, or personal scope. Recruiter/payroll modules have no underlying domain data yet.
- User administration: Super Admin/HR Administrator at `/api/users`; only Super Admin can assign roles. Audit trail: Super Admin only at `/api/audit-logs`.

Registration always assigns the Employee role; it cannot create or promote an administrator. Bootstrap one trusted initial Super Admin through the interactive command after migration; it refuses to create another while an active Super Admin exists. The eight roles are server-enforced. HR Administrators cannot assign roles; only Super Admin may assign non-Super-Admin roles. Existing rows gain safe defaults during migration; the old `HR Admin` label is migrated to `HR Administrator`. A normalized case-insensitive email index protects uniqueness. Department Manager access requires a configured department assignment.

## Tests

Run the API tests from this directory:

```sh
pytest -q
```

Tests use isolated temporary SQLite files and do not touch `users.db`. The migration test creates a legacy schema, runs Alembic, and verifies original user and employee values remain unchanged.
