# Implementation Plan and Progress

Updated 2026-10-16. This is an execution plan, not a claim that the platform is finished. Track individual requirements in [TRACEABILITY.md](TRACEABILITY.md); module scope is defined in [REQUIREMENTS.md](REQUIREMENTS.md).

## Stage gates

Every stage ends with focused pytest/API authorization and migration tests; frontend unit/component tests; backend lint/type checks; frontend lint/type/build; and manual/browser checks appropriate to the change. Playwright, PostgreSQL integration, accessibility and load checks become gates when those harnesses/modules are introduced. No production stage is marked verified from SQLite-only evidence.

## Stage 1 — Repository audit, requirements, architecture and design system

**Status: Complete.** Audit, requirements, architecture, role matrix, traceability, design-system inventory, and current-baseline references are recorded.

- [x] Inspect source, dependency manifests, migrations, tests, API routes, models and existing docs; exclude local secrets, venv/node_modules and database contents from dumps.
- [x] Record current capability and defects without claiming unimplemented modules.
- [x] Create requirements, architecture, role/permission matrix, plan and traceability checklist.
- [x] Inventory current CSS tokens/components and document accessible design-system decisions in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).
- [x] Mark root FEATURE_MATRIX/PROJECT_PLAN/SECURITY_REVIEW as historical and point current acceptance evidence to the audited baseline.

## Stage 2 — Database foundation, authentication, authorization and organization scoping

**Status: Partial baseline exists; target stage not complete.**

- [x] Existing additive Alembic base and local backup/restore instructions.
- [x] Existing active-account checks, password hashing, access JWT, token revocation, role dependencies, Employee registration, initial-admin mechanisms, invitation API, and some IDOR/department checks.
- [x] Add focused tests for employee/first-admin registration, concurrency closure, duplicate-email and setup-key behavior.
- [x] Harden the environment-key-gated first-admin UI path; bootstrap closes after any Super Admin row exists (including inactive accounts), and operator key removal is documented. The current local `.env` has no bootstrap key configured.
- [x] Complete invited-account registration UI; pending accounts can reissue an expired/lost registration code, cannot be prematurely reactivated, and show a distinct pending state. The old activation route is hidden from OpenAPI but retained as a compatibility alias.
- [x] Add short-lived access tokens with configured issuer/audience validation, rotating HttpOnly refresh sessions, CSRF/origin checks, session inventory/revocation, and session revocation on password change/deactivation. Focused API and frontend client tests cover these flows.
- [x] Add Organization and non-null organization IDs to tenant-owned tables; assign all existing records to the seeded NEXORA organization by the owner's approved mapping.
- [x] Apply authenticated organization filters to ORM reads and bulk writes; reject mismatched tenant writes; use organization-local uniqueness for employee codes, departments, leave types and holidays.
- [x] Verify migration data preservation, foreign keys and API isolation between two organizations using temporary SQLite databases; back up and migrate the live SQLite database to `0005_organization_scope`.
- [x] Add a limited Organization Admin role for own-tenant organization profile, departments, employee creation and scoped account administration; preserve all existing role assignments.
- [x] Add unique per-organization memberships, backfill current users with their existing role/department/active state, require an active membership at login and on each session request, and keep account role/department updates synchronized. Expose a tenant-scoped membership list.
- [ ] Move throttling to shared Redis/gateway or document single-process enforcement; add reset-password workflow and optional MFA extension points.
- [ ] Add multi-organization membership provisioning, organization selection/switching, secure organization onboarding, and composite tenant-aware foreign keys; verify PostgreSQL behavior and review raw SQL paths. Current users remain bound to their existing primary organization.
- [ ] Implement permission definitions and remaining target roles (HR Executive, Payroll Officer, Finance Officer); review legacy-role mapping without privilege expansion.
- [ ] Define v1 error envelope and `/api/v1` routers while old routes delegate to same secured services.

## Stage 3 — Employee lifecycle, departments, organization and onboarding

**Status: Partial existing Employee/Department CRUD plus scoped profile data and history; target stage not complete.**

- [x] Add the base Organization record and tenant keys for current business/security tables.
- [x] Add current-organization profile read/update and a scoped Organization Admin UI/API for departments, employee creation and safe user administration.
- [x] Add Branch, Designation and JobGrade catalogs with tenant-local uniqueness, CRUD APIs, archival and organization-structure UI.
- [x] Add optional branch, designation, grade and reporting-manager assignments to employee records; validate tenant references and reject reporting cycles.
- [x] Add tenant-scoped employee contact and emergency-contact APIs/UI; employee and HR access is owner/role checked, and private values are excluded from audit payloads.
- [x] Record hire, position/assignment and employment-status snapshots and expose read-only employment history to employees and authorized HR roles.
- [ ] Add OrganizationMembership, employment contracts, configurable employee fields and private employee documents through additive migrations.
- [ ] Add explicit account-to-employee linking and onboarding templates/tasks, probation, transfers, promotions and offboarding workflows.
- [ ] Split HR module into router/service/repository/schema files.
- [x] Remove duplicate self-profile GET route and assert unique OpenAPI operation IDs.
- [x] Fix employee update/leave-balance cross-domain defect and add regression coverage.
- [x] Keep employee search and pagination in organization/department scope; add the first role-aware employee profile panel for private details and history.
- [ ] Add configurable sorting, scoped export, full HR/manager/Employee pages and an explicit account-to-employee linking/empty-state workflow.
- [x] Verify cross-tenant user/employee/audit list and IDOR negatives plus tenant-local uniqueness and legacy migration preservation.
- [ ] Verify team IDOR negatives, UI forms and end-to-end onboarding.

## Stage 4 — Attendance, leave, schedules and reusable approvals

**Status: Partial clock events, leave policies/balances and single-stage decisions exist; target stage not complete.**

- [ ] Add AttendanceCorrection, Shift, Roster, timesheet/overtime, schedule/holiday/calendar rules and approval history.
- [ ] Extract reusable versioned ApprovalWorkflow/Stage/Instance/Action engine with separation-of-duty and replay protection.
- [ ] Extend leave with configured accrual, carry-forward, expiry, multi-stage approval and team calendar; keep jurisdictional rules configurable.
- [ ] Add correction/roster/timesheet UI, approval inbox, notification events, timezone edge-case tests and manager team-scope tests.

## Stage 5 — Payroll, compensation, payslips, expenses and finance permissions

**Status: Not implemented.**

- [ ] Define jurisdiction-specific configurable rule packages; no invented tax/statutory assumptions.
- [ ] Implement salary effective history, payroll period/run/validation/reconciliation, approval, idempotent finalization and own payslips with strict permissions.
- [ ] Implement expense categories/policies, private receipt uploads, duplicate claims, approvals, reimbursement/payment and finance reports.
- [ ] Implement ledger foundation, chart of accounts, journal entries and period close as separate finance-owned services.
- [ ] Test unauthorized access, deterministic calculations, transaction rollback, duplicate finalization/payment and export scope.

## Stage 6 — Recruitment, performance, learning and documents

**Status: Not implemented.**

- [ ] Recruitment requisitions, openings, candidates, applications, interviews/feedback, offers/approval and idempotent hire conversion.
- [ ] Performance cycles/goals/progress/self-review/manager review with confidential visibility rules.
- [ ] Training/catalog/enrollment/completion/certification and expiry alerts.
- [ ] Private documents, letters/templates, acknowledgements, employee-relations cases, retention and legal holds.
- [ ] Test consent, retention, role scope, file validation, cross-user document IDOR and approval state transitions.

## Stage 7 — Procurement, inventory, assets, projects, accounting and commercial operations

**Status: Not implemented.**

- [ ] Vendor, requisition/approval, purchase order, goods receipt and invoice matching.
- [ ] Products/SKUs, warehouse/location, movement ledger, transfer/adjustment, reorder rules and documented valuation method.
- [ ] Asset register, assignment, maintenance, warranty, return and disposal history.
- [ ] Projects/tasks/milestones/assignments/timesheets/costs/budgets.
- [ ] Customer/supplier/contract/quote/order/service ticket records and workflow/report permissions.
- [ ] Test transaction atomicity, stock valuation, budget reconciliation, tenant boundaries and requester/approver separation.

## Stage 8 — Dashboards, reporting, notifications, search and complete UI

**Status: Basic persisted role-scoped dashboard only; other shared capabilities not implemented.**

- [ ] Role-specific data-driven dashboards; date/department filters and drill-downs.
- [ ] Authorized global search, pending-action inbox, saved filters, notification preferences/read state/reminders.
- [ ] CSV/PDF export jobs with query-level authorization, audit, formula injection prevention and retention.
- [ ] Email adapter with honest disabled/unconfigured/delivered statuses.
- [ ] Complete shared design system, responsive/dark themes, consistent skeleton/errors/empty/access-denied/404 states, keyboard and screen-reader flows.

## Stage 9 — Security review, test completion and operations

**Status: Not production-ready; audit document lists current known gaps.**

- [ ] Automated authorization matrix, migration, rollback, PostgreSQL, browser E2E and nonfunctional tests.
- [ ] Dependency/configuration scan, secret scan, threat review, upload review, privacy/retention review and independent security testing.
- [ ] Dockerfiles/Compose and CI with pinned/locked compatible dependencies; deployment migrations are a dedicated job.
- [ ] Structured logs/request IDs, health/readiness, metrics/alerts, backup restore drill and incident/recovery runbook.
- [ ] Verify performance/no N+1 and load on PostgreSQL; accessibility audit for core workflows.
- [ ] Synchronize all docs/manual/role matrix and publish only evidence-backed feature completion status.

## Current verified activity for this request

- Repository inventory and architecture/security/data review completed; see [AUDIT.md](AUDIT.md).
- Requirements, architecture, role matrix, design-system inventory, plan and traceability are established; module implementation remains in progress.
- Verification: backend `venv/bin/pytest -q` — 30 passed, with one Starlette/httpx deprecation and three SQLite expression-index reflection warnings. Frontend `npm run lint` passes, `npm test -- --run --maxWorkers=1` passes 12 tests, and `npm run build` passes. A mode-0600 backup at `/tmp/nexora-before-memberships-afayj9jo.sqlite3` was verified at revision 0007 and its disposable copy upgraded through `0008_organization_memberships` with integrity `ok`, zero FK violations, 2 users, 3 employees, 2 memberships, and exact role/department/active-state matches. The live database is at `0008_organization_memberships`, integrity `ok`, zero FK violations, 2 users, 3 employees, 2 memberships, zero mapping mismatches, and all existing records remain in NEXORA; `/health` returns `{"status":"ok"}` and the membership route is registered (unauthenticated probe returns 401). Private employee/emergency contact CRUD and hire/assignment/status history remain verified with owner/HR authorization and API/UI tests. Multi-organization provisioning/switching, employment contracts, configurable fields/documents, remaining target roles, permission definitions, password reset, MFA, distributed throttling and PostgreSQL verification remain open.
- Root `FEATURE_MATRIX.md`, `PROJECT_PLAN.md`, and `SECURITY_REVIEW.md` are explicitly historical references; use the linked current docs for acceptance evidence.

## Completion reporting

At each stage end, update the status here and in TRACEABILITY. Report exact commands/outcomes; list failures and external setup; keep unfinished features explicitly unfinished. Overall project completion requires all mandatory acceptance gates in REQUIREMENTS and cannot be inferred from a frontend build or a passing subset of tests.
