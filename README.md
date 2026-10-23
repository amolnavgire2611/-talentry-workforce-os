# NEXORA Workforce OS

NEXORA is a React/TypeScript + FastAPI workforce application. This checkout now has working token-backed sign-in, protected employee and department management, daily attendance, leave requests/approval, account administration, and database-backed dashboard summaries. It is a functional foundation, **not yet the full enterprise HR scope** in the original project brief; see [implemented scope and limitations](#implemented-scope-and-known-limitations).

## Quick start

### Backend

Requires Python 3.12+.

```sh
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `NEXORA_SECRET_KEY` in `backend/.env` to a private random value (32+ characters). Back up `backend/users.db` before migrating. Existing user and employee rows are preserved by the additive migration:

```sh
alembic upgrade head
uvicorn main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive OpenAPI docs are at `/docs` in development. Health probe: `/health`.

### Frontend

Requires Node.js 20.19+ or 22.12+ for the installed Vite version.

```sh
cd frontend
npm ci
npm run dev
```

The default API origin is `http://127.0.0.1:8000`. Set `VITE_API_BASE_URL` in a frontend `.env` to override it. Configure the matching frontend origin in backend `CORS_ORIGINS`.

Anyone can register a standard Employee account from the sign-in screen. To create the first Super Admin in the UI, set a private random `ADMIN_BOOTSTRAP_TOKEN` of at least 32 characters in `backend/.env` and restart the API; the **Create administrator** option appears only while the database has no Super Admin record. Keep the key private and remove it from the environment after setup. The trusted-terminal command `python -m bootstrap_admin` remains available as a fallback. Administrators can also issue one-time invitations for role-specific accounts from the Access & users screen.

## Tests and production build

```sh
# backend
cd backend
pytest -q

# frontend
cd frontend
npm test
npm run lint
npm run build
```

Backend tests use temporary SQLite databases. Migration coverage upgrades a synthetic legacy database and asserts legacy users/employees remain intact. Frontend unit tests cover bearer auth, 204 responses, expired-session cleanup, and readable validation errors.

## Configuration, database, and deployment

- See [backend configuration and migration guidance](backend/README.md) and [backend environment placeholders](backend/.env.example).
- `EMPLOYEE_DIRECTORY_ENABLED=false` by default. If organization policy enables it, employee users see only active employees' name, employee code, department, designation, and status. Full employee records remain HR-authorized.
- Migrations are explicit; application startup never creates or resets schema. Back up the database before upgrades. The initial revision is intentionally forward-only to avoid dropping legacy data.
- SQLite is the development default. For PostgreSQL, configure `DATABASE_URL` using a PostgreSQL SQLAlchemy URL and install a compatible PostgreSQL driver in the backend environment. Validate migrations and backups against a staging copy before production.
- Production must use HTTPS, a private random `NEXORA_SECRET_KEY`, exact `CORS_ORIGINS`, restricted database/file access, routine backups, and a reverse proxy with appropriate request limits. Configure `APP_ENV=production` to reject the development signing key.
- Access bearer tokens are short-lived and held in `sessionStorage`. Refresh credentials are hashed server-side and sent only in an HttpOnly, SameSite cookie. A CSRF token and allowed-origin check protect refresh/logout; sessions can be listed or revoked from Account settings. Password changes and account deactivation revoke refresh sessions. Any successful same-origin script execution can access browser-readable state; use HTTPS, apply a strict Content Security Policy, avoid unsafe HTML and keep dependencies updated.
- Files/uploads and outbound email are not implemented. No tax, payment/bank transfer, statutory payroll, or external HR integrations are claimed.

## Implemented scope and known limitations

| Area | Current state |
| --- | --- |
| Authentication | Employee registration, one-time guarded first-Super-Admin registration, invited-account registration with single-use codes, login, `GET /api/auth/me`, short-lived JWT with issuer/audience validation, rotating HttpOnly refresh sessions, CSRF/origin checks, session inventory/revocation, active-account checks, and password/deactivation revocation. Password reset and MFA are not implemented. |
| Authorization | Employee/department writes require authorized HR roles; employees see their own profile, attendance, and leave only. HR/admin actions are server-checked. Department Managers require a department assignment and are scoped to it; only Super Admin assigns roles. |
| Employees/departments | Persistent list/create/edit/status/delete and server-side search/pagination for employees; create/archive/reactivate departments. Employee records still use a department-name string rather than a relational department FK; permanent employee removal is not appropriate where history must be retained. |
| Attendance | Persistent per-user UTC check-in/out, duplicate/invalid transition protection, own history, HR overview, current-day dashboard count. No configurable shifts, breaks, holidays, correction approvals, or timezone policy. |
| Leave | HR-managed leave categories and annual allocations, optional holidays, weekend/holiday-aware full/half-day requests, employee balance ledger, approval-only atomic deductions, reviewer comments, and future-approved cancellation/restoration. Carry-forward, automatic accrual, proration, multi-stage approval and notifications are not implemented. |
| Dashboard/audit | Counts are computed from stored records; audit entries cover implemented sensitive actions. No fabricated historical trends are shown. |
| Payroll, recruitment, performance, reports, notifications, organization settings, imports/exports | Not implemented yet. The navigation deliberately does not present these as operational modules. |
| Quality | Backend API and migration tests plus API-client unit tests; TypeScript build, ESLint, and backend pytest run as documented. Full browser E2E, accessibility audit, production deployment test, and load/security testing remain outstanding. |

Do not use this application to make payroll, employment, compliance, or performance decisions until the corresponding business policies and modules have been implemented and reviewed for the deployment jurisdiction.
