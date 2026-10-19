# Historical NEXORA project plan

> This is a prior progress snapshot and includes authentication/registration claims that have since changed. Current plan and stage status are in [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md); current acceptance evidence is in [docs/TRACEABILITY.md](docs/TRACEABILITY.md). Retained for history, not release status.

Updated 2026-10-16. Status tracks this local implementation and actual checks; it is not a production certification.

## Completed in this batch

- Audited existing single React app/FastAPI app and found self-selected bootstrap admin registration, full employee-directory exposure, four legacy roles, no ownership profile route, stateless logout, and no initial-admin utility.
- Disabled public registration. Added interactive Super Admin bootstrap, admin-only role-scoped account invitations, 48-hour hashed one-time activation tokens, inactive accounts until activation, short-lived bearer login, login throttling, persistent logout revocation and password-change revocation.
- Introduced eight roles, department assignments, employee-to-user links, restricted directory projection (off by default), employee self-profile/name update, department-scoped manager queries, and role-aware dashboard metrics.
- Added administrator UI for role-limited invitations and one-time token display, plus the invitee activation form. Removed public self-registration from the sign-in screen.
- Tested the interactive Super Admin bootstrap on an isolated SQLite database; confirmed password hashing, audit creation, and refusal to provision a second active Super Admin.
- Expanded leave into a persistent policy workflow: HR-managed leave types and annual allocations, optional holiday calendar, weekend/holiday-aware day calculation, half-days, per-year balances, pending/used/remaining display data, comments on decisions, and cancellation with future-approved balance restoration.
- Approval and cancellation transitions use conditional database updates so duplicate decisions cannot double-deduct or double-restore leave. Existing leave requests are preserved and remain policy-less until HR handles them deliberately.
- Replaced physical deletion with employee/department archive behavior.
- Added additive migrations through revision 0003 and migration tests preserving legacy employee/user/leave-request rows.
- Reworked login UI to remove public registration and introduced role-aware navigation visibility without relying on client role checks for backend security.
- Added `SECURITY_REVIEW.md` and `FEATURE_MATRIX.md`; updated setup and implementation limitations.

## Implemented, needs broader verification

- Employee CRUD/archive, department archive, attendance check-in/out, overlap-safe leave request and review.
- No function is considered complete for every level in the master specification; payroll, recruitment, performance, learning, expense/assets, notifications, and reporting remain out of scope/unimplemented.

## Next actions

1. Add profile linking/department assignment workflow for existing legacy accounts and employee records; invited employees must be linked at creation, but legacy records remain unlinked until an HR operator maps them.
2. Expand distinct role dashboards and model manager-to-direct-report relationships; recruiter/payroll role screens explicitly report their domain modules as unavailable rather than showing fabricated metrics.
3. Expand leave rules with carry-forward/accrual configuration and add workflow features one at a time, with business-specific tests: attendance corrections, payroll, recruitment, performance/goals, training, notifications, reports, exports, settings.
4. Move backend routes/services into modules and adopt shared/distributed rate limiting before multi-worker production.
5. Add accessibility and browser end-to-end tests, test deployment on PostgreSQL, provide a recovery drill and test the interactive Super Admin utility manually in a disposable DB.

## Checks most recently executed

- Frontend tests: 4 API-client tests passed.
- Frontend ESLint: passed.
- Frontend TypeScript production build: passed.
- Backend API/migration/bootstrap/leave workflow tests: 14 passed (one Starlette/httpx deprecation warning from the current test-client stack).
- Frontend tests: 4 passed; ESLint and TypeScript/Vite production build passed.
- Alembic migration was tested on temporary copies only. Do not apply migrations to local `backend/users.db` without first making and verifying a backup.
