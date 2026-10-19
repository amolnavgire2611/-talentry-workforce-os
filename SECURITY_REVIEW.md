# Historical security review (2026-10-16)

> This review predates the current public Employee registration and guarded first-admin registration path. It is not a current certification. Use [docs/AUDIT.md](docs/AUDIT.md), [docs/ROLE_PERMISSION_MATRIX.md](docs/ROLE_PERMISSION_MATRIX.md) and [docs/TRACEABILITY.md](docs/TRACEABILITY.md) for current risks and status.

## Findings addressed in this change

| Finding | Change | Verification |
| --- | --- | --- |
| Public registration could create the first HR admin, then open employee self-registration | Both public registration paths now return 403. An administrator provisions an inactive account and a one-time 48-hour activation token. | API test asserts both registration paths reject requests; tests invitation activation, one-time use and pre-activation sign-in rejection. |
| Any authenticated account could list full employee records | Full employee lists and directory pagination are HR scoped; department managers are filtered by their assigned department. Employees receive 403 from those endpoints by default. | API test verifies employee list, directory, arbitrary user query and cross-profile ID access are denied. |
| Directory returned employee IDs and all operational fields to any account | Employee directory is disabled by default via `EMPLOYEE_DIRECTORY_ENABLED`; if enabled, returns only employee code, name, department, role/designation and status for active rows. | Schema is explicit; disabled-by-default setting is in `.env.example`. |
| Profile URLs did not have ownership semantics | `GET /api/employees/me` is linked to authenticated user; `GET /api/employees/{id}` checks ownership or manager department scope. Self-edit only accepts name. | Tests cover cross-account IDOR and self-profile linkage. |
| Managers could be granted organization-wide data | Department Manager needs an assigned active department. Employee, attendance, leave, and dashboard reads are filtered to that scope. | Test asserts own department appears and another department's profile is denied. |
| Role edits/selection did not model required roles | Eight server roles are enumerated; registration cannot choose role. Super Admin bootstrap uses an interactive local terminal command. | Tests assert recruiter cannot edit user roles or access audit/HR writes. |
| Logout did not invalidate bearer token | JWT `jti` is recorded in `revoked_tokens` and checked on each authenticated request. Password changes revoke the current token too. | Test asserts the old bearer token receives 401 after logout. |
| Guessing could be repeated without throttling | Process-local limiter rejects more than 10 failed attempts per client IP in a rolling minute and logs client address only. | Functional code present; distributed load/concurrency test remains needed. |
| Employee deletion could destroy a record with history | Delete action now archives by setting Inactive; departments are archived rather than physically deleted. | API and audit behavior exercised through the normal workflow tests. |
| Login state rested on frontend profile data | Frontend uses tab-scoped `sessionStorage`, verifies `/api/auth/me`, and clears token on 401. | API-client tests cover bearer header and 401 cleanup. |

## Permission model currently implemented

| Role | Organization employee records | Department data | Attendance | Leave | User admin | Audit logs |
| --- | --- | --- | --- | --- | --- | --- |
| Super Admin | Organization read/write | Organization read/write | Organization read | All requests; approve | Provision, assign all non-Super-Admin roles, activate/deactivate | Read |
| HR Administrator | Organization read/write | Organization read/write | Organization read | All requests; approve | Provision allowed operational roles; activate/deactivate, but not assign roles | No |
| HR Manager | Organization read/write | Organization read/write | Organization read | All requests; approve | No | No |
| Department Manager | Assigned department only | Assigned department only | Assigned linked team only | Assigned department only; approve | No | No |
| Recruiter | No employee/private HR access | No | No | Own requests only | No | No |
| Payroll Administrator | No employee/private HR access | No | Own attendance only | Own requests only | No | No |
| Attendance Administrator | No employee/private HR access | No | Organization read; own clock actions | Own requests only | No | No |
| Employee | Own linked profile; optional minimal directory only if enabled | No organization directory | Own only | Own only | No | No |

There is deliberately no payroll API or payslip endpoint, so payroll roles have no payroll data to view or change yet. No role receives rights to nonexistent modules.

## Bootstrap and deployment risks

- Provision the first Super Admin only after migration using `python -m bootstrap_admin` from `backend/`. It uses hidden terminal password input, fails if an active Super Admin exists, and does not ship a fixed credential.
- Existing legacy users are normalized to HR Administrator only where the old stored role is exactly `HR Admin`; otherwise the safe default is Employee. Use the bootstrap tool to grant a trusted account Super Admin, then review every other role and link existing employee accounts before exposing the service.
- Invitation tokens are returned once from the administrator-only endpoint. The UI must deliver/share them out of band; no email provider is configured. Treat tokens as secrets and send them through a trusted channel.
- Login limiting is in-memory and per-process; it does not provide shared limits across workers or restarts. Use an edge gateway/shared rate-limit store before public deployment.
- Access JWTs are held in `sessionStorage`; JavaScript can read them. Use HTTPS, restrictive CSP, dependency maintenance and XSS prevention. A production HttpOnly refresh-cookie/session service is not configured.
- SQLite migration intentionally adds nullable integer scope links without rebuilding legacy `users`/`employees` on SQLite. Application queries validate assignments. Review/enforce relational constraints in a staged PostgreSQL migration before production.
- `EMPLOYEE_DIRECTORY_ENABLED=true` reveals only the explicitly defined basic business directory projection; keep false unless organization policy approves it.
- No independent penetration test, privacy/legal review, production load test, or deployment configuration review has been performed. Do not claim certification or compliance.
