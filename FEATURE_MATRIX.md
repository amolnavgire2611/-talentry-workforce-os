# Historical feature matrix

> This matrix predates the current Employee registration and environment-key-gated first-admin setup, and its statuses are not current acceptance evidence. Use [docs/TRACEABILITY.md](docs/TRACEABILITY.md) for the audited current baseline and target checklist. The details below are retained as historical context until the next verified feature-matrix refresh.

Status key: **Not implemented**, **Partially implemented**, **Implemented but not tested**, **Implemented and verified**. “Verified” means the focused checks named in the row were actually executed; it does not imply production certification.

| Domain / required feature | Current status | Evidence / limitation |
| --- | --- | --- |
| Authentication: login, JWT expiry validation, current user, active-account check | Implemented and verified | `pytest`: login, unauthenticated 401, activation/account state coverage. |
| Public registration disabled; administrator-controlled account invitation/activation | Implemented and verified | Registration endpoints reject; admin issues inactive account and hashed expiring one-time activation token. |
| Secure Super Admin bootstrap | Implemented and verified | Isolated utility test verifies password hashing, audit entry, and that a second bootstrap is refused. |
| Eight roles; roles never accepted from registration | Implemented and verified | Schema enumerates roles; authorization tests for recruiter and employee privilege escalation. |
| Session logout and password-change revocation | Implemented and verified | Persistent `jti` revocation; old access token rejected. |
| Employee private record authorization and IDOR prevention | Implemented and verified | HR-only full list; employees have linked own-profile route and cross-ID requests return 403. |
| Configurable limited employee directory | Implemented and verified | Disabled by default; an explicit enabled-setting test verifies the approved employment-only projection. |
| Department Manager query scope | Implemented and verified | Employee list/detail/departments constrained to assigned department. Direct-report hierarchy not modeled. |
| HR employee CRUD/profile updates and archival | Partially implemented | Core code/status/archive; personal/contact fields, work email constraints, history, uploads, onboarding/offboarding missing. |
| Employee directory search and count pagination | Implemented but not tested | Search and pagination endpoint exists; tests currently exercise list search, not all page edge cases. |
| Departments: create/update/archive and counts | Partially implemented | Name/description/active; no FK assignments, head, hierarchy, locations or derived employee count. |
| Attendance clock in/out/history | Partially implemented | UTC, duplicate/invalid transitions, scoped history; policies, shifts, breaks, correction approval, holidays and timesheets missing. |
| Leave types, annual balances, holidays and accrual | Partially implemented | HR-managed calendar-year allocations; balances initialize per employee/year on use; weekends and configured holidays are excluded. No automatic accrual, carry-forward, pro-rating, entitlement tiers, or jurisdictional rules. |
| Leave request/overlap/approval/cancellation | Implemented and verified | Policy-linked full/half-day requests, same-year validation, working-day totals, overlap checks, approval-only atomic balance deduction, reviewer comments, future approved leave restoration, department scope, and insufficient-balance rejection. API tests verify these paths. |
| Dashboard: persisted current metrics and role scope | Partially implemented | Counts come from DB; no trend, task, recruiter/payroll data, dates/filters or operational metrics. |
| Payroll/compensation/payslips | Not implemented | No payroll models, API, calculations, exports or UI. |
| Recruitment/applicant tracking | Not implemented | No requisition/candidate/application models, API or UI. |
| Performance and goals | Not implemented | No review cycle, goal or assessment service/API/UI. |
| Learning and development | Not implemented | No training/course/enrollment records or UI. |
| Employee self-service beyond basic profile, attendance and leave | Partially implemented | No documents, payslips, goals, onboarding, announcements, tasks or notifications. |
| Manager self-service beyond assigned department leave/attendance | Partially implemented | No direct-report hierarchy, timesheets, goals, review or team calendars. |
| Expenses, assets, employee relations | Not implemented | No records or workflows. |
| Notifications/announcements/tasks | Not implemented | No persistent notification models or event delivery. |
| Reports, analytics, CSV/PDF exports | Not implemented | No report/export endpoints; export permissions and formula safety not relevant yet. |
| Organization settings and business policy administration | Not implemented | Only environment-based runtime configuration exists. |
| Audit logging | Partially implemented | Auth, profile, employee, department, leave, invitation and account actions; no audit UX, retention controls or complete all-domain coverage. |
| Additive Alembic migration and legacy record preservation | Implemented and verified | Migration test upgrades synthetic legacy SQLite and verifies user/employee content persists. |
| Frontend API client and validation error presentation | Implemented and verified | Vitest covers bearer, 204, 401 cleanup and Pydantic error fields. |
| Role-specific shell/navigation and login | Partially implemented | Navigation filters by role and public signup removed; several role-specific module pages are still not implemented. |
| Responsive design and reduced motion | Implemented but not tested | CSS breakpoints/focus styles exist; no browser/device visual or accessibility suite executed. |
| Backend API tests | Implemented and verified | `pytest -q`: 14 passed, including bootstrap, invitation, token revocation, directory privacy, leave policy/approval/cancellation, role denial, department scope, and additive migration preservation. |
| Frontend unit tests, lint, production build | Implemented and verified | `npm test`: 4 passed; `npm run lint` passed; `npm run build` passed after the latest changes. |
| Browser E2E/security/load/accessibility testing | Not implemented | No Playwright suite or external security review. |

## Required domains not listed above

Job grades, workforce planning, leave-policy management, timesheets/overtime, payroll rules/jurisdictional configuration, recruitment pipeline/scorecards/offers, performance calibration, training certificates, grievances, assets, expenses, notifications, reports, settings, data retention and comprehensive audit administration are **Not implemented** unless explicitly noted above. No fabricated metrics or placeholder navigation is claimed as working.
