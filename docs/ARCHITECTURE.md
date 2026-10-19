# NEXORA Platform Architecture

**Architecture decision:** evolve the existing FastAPI/React application as a modular monolith. Keep one deployable API and one relational database until scale or team boundaries justify separation. Domain modules must remain independently testable and must not share authorization assumptions implicitly.

## 1. Repository audit and starting point

The current checkout is a Vite React/TypeScript frontend plus one FastAPI/SQLAlchemy backend. The current single-page UI is concentrated in `frontend/src/WorkforceApp.tsx`; API routes and business rules are concentrated in `backend/application.py`; models/schemas/security/config are separate files. Alembic revisions `0001`–`0008` provide an additive migration base. The local application defaults to `backend/users.db`; startup does not migrate or create schema.

Existing persisted models include Organization, OrganizationMembership, Branch, Designation, JobGrade, User, Employee, EmployeeContact, EmergencyContact, EmployeeEmploymentHistory, Department, Invitation, RevokedToken, RefreshSession, Attendance, LeaveRequest, LeaveType, LeaveBalance, Holiday and AuditLog. Revision `0005_organization_scope` assigns all legacy rows to NEXORA and adds non-null organization foreign keys; `0006_organization_catalogs` adds tenant catalogs and nullable employee links for branch, designation, grade and reporting manager; `0007_employee_profile_details` adds private contact records and employment snapshots; `0008_organization_memberships` backfills one membership per existing account without changing its role, department assignment or active state. Existing APIs cover authentication, scoped organization profile/membership listing and catalogs, invitations, employees and private employee profile data, departments, attendance, leave, dashboard, user admin and audit reads. Multi-organization provisioning and switching are not implemented.

Existing risks and gaps: frontend role checks are presentation-only (server checks exist for current routes); access tokens remain in `sessionStorage`, login throttling is process-local, password reset/MFA are absent, and only limited Organization Admin workflows are implemented. Broader role coverage is incomplete. The current ORM applies a server-derived organization filter to reads and bulk writes after authentication, and rejects cross-organization ORM writes. Rotating refresh sessions, HttpOnly cookies, CSRF/origin checks, session inventory/revocation, and JWT issuer/audience validation are implemented for the current auth routes. Typed generated API clients, router, shared server-state/form/component libraries, container/CI files and Playwright suite remain absent; the current API module is large. Invitation codes still require manual trusted delivery because email is not implemented. See [TRACEABILITY.md](TRACEABILITY.md).

## 2. Target component structure

Refactor incrementally while retaining imports/compatibility routes until each domain is moved and covered.

```text
backend/
  app/
    main.py                 # app factory, middleware, lifespan
    core/                   # config, logging, errors, pagination
    api/v1/                 # routers and dependency wiring only
    security/               # identity, sessions, permissions, CSRF
    db/                     # engine, session, base, tenant query helpers
    models/                 # domain-owned SQLAlchemy 2.x mappings
    schemas/                # request/response DTOs
    repositories/           # common scoped persistence queries
    services/               # domain transactions and invariants
    workflows/              # approval definitions, instances and transitions
    modules/                # hr, attendance, leave, payroll, recruitment, ...
    tests/                  # unit, API, authorization, migration, integration
  migrations/
frontend/src/
  app/                      # route tree, guards, providers, error boundaries
  api/                      # generated/manual typed contracts and query client
  components/               # accessible design system and shared data patterns
  features/                 # auth, hr, leave, payroll, recruitment, finance, ...
  layouts/                  # role-filtered navigation, shell, profile menu
  lib/                      # schemas, utilities, permission-aware formatting
```

The starting frontend dependencies are React 19, TypeScript 6, Vite 8 and Vitest 5, with React Testing Library and jsdom now supporting the extracted auth feature. The backend pins FastAPI, Pydantic 2, SQLAlchemy 2, Alembic and pytest in `backend/requirements.txt`. No unverified framework/package upgrade is part of this audit. Planned React Router, TanStack Query, React Hook Form/Zod, accessible component library, icon/chart packages and Playwright must be selected as compatible pinned versions, installed, built and tested in an isolated change before adoption. Existing CSS design remains usable during the migration; no wholesale rewrite is required to add domain slices.

## 3. Backend boundaries

- **Routers** validate HTTP input, resolve authenticated principal/dependencies, call services and select response schemas. They contain no multi-step business transaction logic.
- **Services** own workflows, permission-sensitive decisions, validation, transaction boundaries and audit events.
- **Repositories** provide tenant-scoped queries. A repository requires a `Principal` carrying server-derived organization/membership scope; unscoped reads are platform-only APIs with explicit audit.
- **Models** use SQLAlchemy 2.x typed mappings, explicit FK relationships, unique/check constraints and indexes. Domain models include organization and `organization_id` at the root of tenant-owned aggregates.
- **Schemas** are explicit allowlists. Never serialize ORM rows directly for sensitive records; never accept an authoritative user ID, role, organization or approver assignment from a general request DTO.
- **Errors** use a stable safe envelope and request ID. Database details, exception strings, SQL, secrets and personal data are not returned to clients.

## 4. Tenant, identity and authorization model

Identity is resolved from a verified `Principal` assembled from a server-side session. Authorization evaluates global role, tenant membership, permission, record ownership, active department/team assignments and workflow stage. Scope is intersected into the SQL query before loading rows, not checked only after returning a collection.

All current tenant-owned tables carry a non-null `organization_id`; legacy users, employees, departments and workflow/security records map to the seeded NEXORA organization. Each user now needs an active OrganizationMembership in the server-selected organization; current sessions remain bound to the user's primary organization, so this is not yet multi-organization access. Membership role and department values are the authorization source for the current account, and account administration synchronizes those values without changing legacy mappings. SQLAlchemy loader criteria scope tenant-owned reads and bulk writes from the server-derived organization; pending tenant writes must match that organization. Cross-tenant IDs return not found in focused API checks. Employee codes, department names, leave-type names, holiday dates, branch names/codes, designation names and job-grade names/codes are organization-scoped. Employee branch, designation, grade and reporting-manager IDs are checked against the active tenant; reporting cycles are rejected. Private contact and emergency-contact APIs allow the owner and HR Manager, HR Administrator, or Super Admin; Organization Admin and Department Manager cannot read that data. Employment snapshots are exposed to the owner and those HR roles, and are written by application hire, assignment and status workflows. This is a transitional guard around the existing monolithic ORM layer: raw SQL and new modules must use an explicit tenant-aware repository, and multi-organization provisioning/switching and composite tenant-aware relationship constraints remain future work. Super Admin support access across tenants is not implemented.

Roles grant permission bundles, but sensitive functions use explicit permission keys such as `hr.employee.read`, `payroll.run.finalize`, `finance.payment.create`, `recruitment.candidate.read`, `document.case.read`, and `approval.stage.decide`. The matrix is [ROLE_PERMISSION_MATRIX.md](ROLE_PERMISSION_MATRIX.md). Do not turn role names into scattered special cases as new modules arrive.

## 5. Session and authentication lifecycle

Target flow: Argon2id/password policy -> login throttling through a shared store or gateway -> short-lived signed access credential -> opaque high-entropy rotating refresh session in Secure/HttpOnly/SameSite cookie -> CSRF token/origin validation for cookie-authenticated mutations -> server-side hashed refresh/session record -> session list/revoke/logout-all. JWT validation checks configured algorithm, signature, issuer, audience, expiry, subject and token type. Deactivation, password reset and logout revoke sessions immediately. MFA factors can later attach to the same account/session policy.

Current behavior now includes short-lived HS256 access JWTs validated against configured issuer/audience, opaque refresh secrets stored as hashes, rotating HttpOnly/SameSite cookies, a CSRF token plus exact allowed-origin checks on refresh/logout, session listing and revocation, and immediate refresh-session revocation on password change/deactivation. Access JWTs remain in tab `sessionStorage`; the CSRF value is shared in browser `localStorage` so tabs can use the current token. The UI coordinates refresh within a tab and uses Web Locks across tabs when supported. The login throttler remains process-local; password reset and MFA are absent. First-Super-Admin creation is environment-key gated in the login UI or through a local CLI; the UI path requires an operator-managed random `ADMIN_BOOTSTRAP_TOKEN` and closes after the first Super Admin row exists. Live database backup, revision and integrity evidence is recorded in [AUDIT.md](AUDIT.md).

## 6. Database and migration strategy

- PostgreSQL is the production target. SQLite remains for local development and isolated tests, not concurrency/load certification.
- Preserve `backend/users.db`, existing employee IDs, credentials hashes and workflow history. Never reset, drop or point experiments at that file.
- Every schema change is an Alembic revision. Back up, inspect current revision/columns, preflight duplicate/conflicting values, migrate a backup copy, compare row counts/key fields, then apply to the target during a maintenance window. Record the prior revision and verified restore procedure.
- Use expand/backfill/contract for required fields: add nullable column/table/index -> backfill in batches with audit/validation -> deploy code reading both -> enforce NOT NULL/constraints in a later revision. Prefer no destructive downgrade; restore from verified backup for data loss.
- Revisions `0005_organization_scope` and `0006_organization_catalogs` seed NEXORA, map every existing tenant-owned row to it per the owner's instruction, and add non-null foreign keys, tenant-local catalogs, and employee assignment fields. Revision `0007_employee_profile_details` adds empty tenant-scoped contact tables and employment snapshots without inventing contact data or hire dates for legacy employees. Revision `0008_organization_memberships` backfills each current user's existing role/department/state into the current-organization membership. Multi-organization onboarding/switching and PostgreSQL verification remain open. Do not add a tenant selector to public registration; it currently accepts registrations only when exactly one active organization exists.
- Migration tests build disposable legacy schemas matching actual old revisions, run upgrade, assert data preservation, constraints and rollback behavior. Never run tests against `users.db`.

## 7. Shared approval engine

Approvals are domain-neutral state machines with domain record references. A workflow version contains ordered stages, threshold/role/manager approver rules, separation-of-duty rules, optional SLA/escalation and allowed actions. On submit, snapshot the workflow definition into an ApprovalInstance. Each decision uses a conditional transactional transition, records immutable ApprovalAction with actor/comment/time, and updates the owning aggregate through a service. Request-changes returns a versioned draft; resubmission creates the next valid stage history. Payroll finalization, stock/ledger postings and reimbursement payment each have an explicit domain service beyond a generic approval button.

## 8. Data, files, search and reports

- Documents and receipts live in private object storage (local private volume in development; S3-compatible interface in deployment). Persist storage key, size, media type, checksum, scan status and retention metadata, not public URL. Download is an authorized, audited stream or short-lived URL.
- Global search uses a unified authorized-query interface per module; it never indexes fields the caller cannot read. Search results reauthorize on open.
- Reports and exports compose server-side scoped queries. CSV export neutralizes spreadsheet formulas. Exports are permissioned, audited and may be asynchronous; no browser-generated export from unfiltered sensitive data.
- Optional email is an adapter configured by environment. Without credentials, in-app workflows work and delivery status reports “not configured”; no success is fabricated.

## 9. Frontend architecture and design system

The precise current visual and accessibility baseline is recorded in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md). In brief, the current app is light-only and uses DM Sans/Manrope, navy/blue/teal accents, responsive CSS at 1100/760/480px, visible focus outlines, and reduced-motion support. These styles live alongside a large single-page component and have not been verified through browser accessibility testing. New feature work should extract shared patterns incrementally and preserve keyboard access, field labels, announced errors, responsive reflow, and text equivalents for charts.

Use route-level feature modules and protected route layouts for navigation/usability; server APIs remain authoritative. Server state uses a query cache with explicit invalidation; mutations are guarded against double-submit and show field errors. Forms use schemas shared with API contracts where practical. Shared table/filter/pagination, confirmation dialog, toast, skeleton, empty/error/access-denied states and accessible controls are implemented once. Distinct dashboards are data-driven by role permissions, not fake KPI variants.

Visual direction: existing NEXORA navy/indigo/teal foundation with neutral surfaces, responsive sidebar/topbar, design tokens, dark/light themes, keyboard/focus states, reduced motion, contrast checks and mobile layouts. Introduce charting only for persisted, permission-filtered report data. Use an actual router and 404 page when adopted.

## 10. Operational architecture

- FastAPI app factory, one-shot lifespan, connection pool pre-ping, readiness check that verifies DB connectivity and migration state without mutating schema, liveness endpoint independent of DB, bounded request bodies and proxy trust configuration.
- JSON structured logs with request/correlation ID; redact auth headers, cookies, emails where unnecessary, user-supplied secrets and file contents. Audit events remain separate from operational logs.
- Docker Compose provides API + PostgreSQL + frontend reverse proxy for local integration; secrets come from ignored `.env` or deployment secret manager, not Compose defaults in production.
- CI runs formatting/lint/type checks, isolated PostgreSQL and SQLite tests, migration tests, frontend build and browser smoke. Dependency lockfiles and image digests are reviewed; no paid provider is required for core flows.
- Backups are encrypted and tested by restoring into a disposable environment. Deployment steps use immutable images, explicit migration job, health checks, rollback-compatible expand/contract and operator alerting.

## 11. API compatibility and versioning

Target API root is `/api/v1`. Existing unversioned `/api/...` endpoints remain adapters during migration and call the same services/permission checks. A compatibility route is removed only after clients and integration tests use v1. OpenAPI exposes request/response schemas and permission descriptions; no endpoint is considered complete because it appears in OpenAPI alone.

## 12. Quality gates

Each stage updates [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and [TRACEABILITY.md](TRACEABILITY.md). A stage cannot be marked complete until its focused positive/negative tests, migration tests, lint/type checks, production build and applicable manual/browser checks pass. Production readiness additionally requires PostgreSQL migration/restore and security review; passing a local build is insufficient.
