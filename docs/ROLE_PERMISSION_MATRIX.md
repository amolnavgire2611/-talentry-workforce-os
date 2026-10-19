# Role and Permission Matrix

This is the **target** policy for the nine required roles. Every permission is enforced by the API and scoped to the user's organization and, where applicable, branch/team/owned record. A visible UI action never grants authority by itself. The audited current implementation is summarized at the end.

## Permission vocabulary

- **Platform**: cross-organization administration, limited to Super Admin and fully audited.
- **Org**: records in the active organization only.
- **Team**: assigned department/team and configured reporting scope only.
- **Own**: authenticated user's own records resolved from the server-side session.
- **Assigned**: a specific object or workflow assigned to the user.
- **—**: no access. Read access does not imply write, export, download, or approval access.

## Target module permissions

| Module / action | Super Admin | Organization Admin | HR Manager | HR Executive | Department Manager | Payroll Officer | Recruiter | Finance Officer | Employee |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Platform organizations and support tooling | Platform | — | — | — | — | — | — | — | — |
| Organization settings, users and membership | Platform | Org | — | — | — | — | — | — | — |
| Role/permission definitions | Platform (controlled) | Org assignments within policy | — | — | — | — | — | — | — |
| Employee directory basic projection | Authorized Org | Authorized Org | Authorized Org | Assigned HR Org | Team | Minimal payroll-linked identity | Recruiting contact only | Finance-linked identity | Approved opt-in projection only |
| Employee profile/contact/history | Platform with audit | Org | Org | Assigned HR fields | Team-limited fields | Payroll-required fields only | — | — | Own permitted fields |
| Employee documents/cases | Platform with audit | Org by policy | HR-authorized | Assigned HR scope | — | — | — | — | Own approved docs only |
| Onboarding/offboarding | Platform with audit | Org | Org | Assigned cases | Assigned tasks only | — | Hired-candidate handoff only | — | Own checklist/status |
| Attendance/team schedules | Platform with audit | Org | Org | Assigned HR view | Team | Payroll input projection only | — | — | Own |
| Attendance corrections | Platform with audit | Org | Org | Assigned HR workflow | Team approval scope | — | — | — | Own request only |
| Leave policy/calendar | Platform with audit | Org | Org | Assigned HR scope | Read team policy | — | — | — | Read applicable policy |
| Leave requests/balances | Org | Org | Org | Assigned HR workflow | Team approvals | Payroll-approved aggregate only | — | — | Own |
| Approvals | Platform oversight | Org workflows | HR stages | Assigned HR stages | Assigned team stage | Payroll stages | Recruitment stages | Finance/procurement stages | Own submission/resubmission |
| Salary/compensation/payroll runs | Platform controlled, audited | No implicit read; explicit break-glass only | — | — | — | Org payroll scope | — | Ledger summaries only | Own payslips only |
| Recruitment/candidates/interviews/offers | Platform audited | Org administration only | HR/recruiting permission if assigned | Assigned HR workflow | Assigned interviewer feedback only | — | Org recruitment scope | — | — |
| Performance reviews/goals | Platform audited | Org policy administration | Org | Assigned HR workflow | Team assigned reviews | — | — | — | Own goals/self-review |
| Learning/training | Platform audited | Org | Org | Assigned workflow | Team | — | — | Budget totals only | Own enrollment/certificates |
| Expenses/receipts/reimbursement | Platform audited | Org policy/user administration | HR claim data only where assigned | Assigned HR claims only | Team approval, no finance settlement | — | — | Org finance settlement/reports | Own claim/receipt |
| General ledger/AP/AR/budgets | Platform audited | Org membership only | — | — | — | Payroll journal interface only | — | Org finance scope | — |
| Procurement/vendors/POs | Platform audited | Org membership only | — | Team requisition/request only | Payroll-linked purchase data only | — | — | Org finance/procurement scope | Own requisition |
| Inventory/assets/projects/operations | Platform audited | Org settings only | Employee asset view only | Assigned HR view | Team/project assignment | — | — | Cost/budget view only | Own assignment/requests |
| Audit records | Platform | Own-org security/admin events | HR events in scope | Assigned HR events | Team workflow events | Payroll events | Recruitment events | Finance events | Own security events only |
| Notifications/search/reports/exports | Same source scope; export audited | Same source scope | Same source scope | Assigned scope | Team scope | Payroll scope | Recruiting scope | Finance scope | Own scope |

### Separation-of-duty rules

1. Requesters cannot approve their own request where the workflow requires separation of duties.
2. A Payroll Officer may prepare/reconcile payroll but finalization requires the configured independent approver. Finance payment roles cannot change payroll permissions.
3. Organization Admin manages only its own tenant; it cannot create a user in or query another tenant.
4. HR Executive receives only explicit HR permissions; it is not an alias for Organization Admin or Super Admin.
5. Department Manager scope comes from active server-side assignments, not a department ID supplied by the request.
6. Recruiter cannot read compensation, general HR documents or unrelated employee cases.
7. Finance Officer cannot read medical, employee-relations or unrestricted HR documents.
8. Super Admin cross-tenant access requires a privileged action reason and audit event; routine employee operations should use tenant roles.
9. CSV/PDF export and file download are distinct permissions and reapply the same row/field filters as the UI.

## Current implementation (baseline, not target)

The checked-out app currently recognizes `Super Admin`, `Organization Admin`, `HR Administrator`, `HR Manager`, `Department Manager`, `Recruiter`, `Payroll Administrator`, `Attendance Administrator`, and `Employee`. Organization and tenant keys exist, and all current records belong to NEXORA. Each current user has a membership row with the same role, department assignment and active state; login/session validation requires an active membership, and the membership is the runtime role source. Multi-organization provisioning and switching are not implemented, and no legacy role was remapped. **Organization Admin** has limited tenant-scoped organization, department/catalog, employee-creation and user-invitation APIs; HR Executive, Payroll Officer and Finance Officer are not yet implemented.

| Current role | Current code capabilities |
| --- | --- |
| Super Admin | HR employee/department/leave management; employee private contact and employment history access; organization attendance; user invitations, registration-code reissue, account deactivation/reactivation and role assignment; audit API. |
| Organization Admin | Own-organization profile; department, branch, designation and job-grade catalogs; employee listing/creation and basic profile; user listing; invitations for limited operational roles; account activation and department assignment. Cannot read private employee contact/emergency-contact data or employment history, assign roles, or manage Super Admin/HR Administrator/Organization Admin accounts. |
| HR Administrator | Same HR/attendance/leave management including employee private contacts and employment history; can provision limited operational roles and reissue registration codes/manage account access but cannot assign roles. |
| HR Manager | Employee/department management, private contacts and employment history, organization attendance, leave-type management and leave review; no user admin. |
| Department Manager | Reads assigned department/employee/linked team attendance; reviews assigned-team leave; may submit own attendance/leave. Requires active department assignment. |
| Recruiter | Overview and settings UI only; no recruitment API/module. Other access is denied. |
| Payroll Administrator | Overview and settings UI only; no payroll API/module. Other access is denied. |
| Attendance Administrator | Organization attendance view and own clock actions; no HR employee directory. |
| Employee | Own attendance and leave; own linked employee profile, contact details, emergency contacts and recorded employment history. Publicly registered Employee profiles may not yet be linked; limited directory disabled by default. |

## Legacy migration policy

- Preserve current stored role strings in a staged migration. First inventory counts, active states, department assignments and user-to-employee links.
- Preserve the current one-organization mapping to NEXORA. Before enabling additional organizations, design membership/account assignment and an explicit Organization Admin setup process; no user gets cross-tenant access by default.
- Map `Payroll Administrator` to `Payroll Officer` only after payroll scope is configured and reviewed.
- Map `HR Administrator` to Organization Admin only after its tenant boundary and account ownership are known; otherwise assign a reviewed HR role. Never infer cross-organization authority.
- Keep `Attendance Administrator` as a time-limited compatibility role or reassign explicitly; do not grant it payroll, HR, or finance access.
- Record each mapping in migration audit output, test preserved user counts, and support rollback/restore from a verified backup before production cutover.
