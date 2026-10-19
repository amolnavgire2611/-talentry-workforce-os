# NEXORA Workforce & Enterprise Management Platform — Requirements

**Status:** target requirements; this document does not imply implementation. See [TRACEABILITY.md](TRACEABILITY.md) for the audited baseline and per-requirement status.

## 1. Product and release boundary

NEXORA is a modular-monolith workforce and enterprise operations platform. It must persist real business records, apply tenant and object-level authorization on the server, and expose only workflows that are implemented end to end. A feature is complete only when its model/migration, API, validation, UI, permissions, negative and positive tests, and operator documentation are complete. Do not fill gaps with invented metrics or nonfunctional controls.

Production data is never reset as part of development. Schema changes are additive or explicitly reviewed, backed up, migrated, and verified. PostgreSQL is the production target; SQLite remains an isolated local/test option.

## 2. Required personas and security invariants

Required roles: **Super Admin, Organization Admin, HR Manager, HR Executive, Department Manager, Payroll Officer, Recruiter, Finance Officer, Employee**. The role/permission details and legacy-role migration policy are in [ROLE_PERMISSION_MATRIX.md](ROLE_PERMISSION_MATRIX.md).

Security invariants:

1. Resolve identity from a verified session/token. Never accept role, user, organization, department, owner, or approver scope as authority from the browser.
2. Enforce tenant, team, and record ownership in every read and write query; hiding a React control is not authorization.
3. Employee access is self-only except explicitly approved, non-sensitive directory fields. Department managers are restricted to assigned teams and approval scope.
4. Payroll, finance, medical/employee-relations documents, candidate records, and commercial data have separate permissions.
5. Public registration creates only an Employee. First-administrator setup is a one-time, documented CLI or environment-controlled operation. Never ship default production credentials.
6. Use adaptive password hashing, short-lived access credentials, revocable server-side sessions, secure refresh-cookie handling and CSRF protection where cookie sessions are used. Validate issuer, audience, expiry and signing configuration. Keep secrets and credentials out of logs and source.
7. Log privileged and sensitive changes without recording passwords, tokens, receipts, document content, or unnecessary personal data.
8. Cross-organization requests and direct-object-reference attacks return a safe denial or not-found response and leave no data changed.

## 3. Functional modules, pages, APIs, entities, workflows and acceptance criteria

The paths below are the target `/api/v1` contract. The existing unversioned endpoints are compatibility routes to be migrated incrementally; see [ARCHITECTURE.md](ARCHITECTURE.md). `{id}` parameters are opaque identifiers. Every list supports server-side filtering, sorting where meaningful, and bounded pagination.

### AUTH — identity and access

- **Pages:** sign in, Employee registration, first-admin setup (operator-gated), invitation-code registration, forgot/reset password, account sessions, MFA enrollment, access denied/not found.
- **API:** `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh`, `GET /auth/me`, `POST /auth/register`, `POST /auth/register-invited`, `POST /auth/invitations`, `POST /users/{id}/invitation` (reissue pending code), `POST /auth/password/forgot`, `POST /auth/password/reset`, `PUT /auth/password`, `GET /auth/sessions`, `DELETE /auth/sessions/{id}`, `DELETE /auth/sessions`, `POST /auth/mfa/enrollment`, `POST /auth/mfa/verify`, `DELETE /auth/mfa/enrollment`.
- **Entities:** User, Role, Permission, UserRole, Session, PasswordReset, Invitation, MFAFactor, AuditEvent.
- **Workflow:** bootstrap first Super Admin once; authorized admin invites a role-scoped user; invitee sets a password; login creates a revocable session; refresh rotates session token; logout/password reset/deactivation revokes sessions. Forgot-password responses do not reveal account existence.
- **Acceptance:** correct and incorrect credentials; throttling; inactive/suspended account; expired/revoked/rotated session; refresh replay; CSRF; invite expiry and one-time use; registration cannot supply privileged roles; first-admin setup closes after use; reset token is single-use; one user's session revocation does not revoke another's.

### ORG — organizations, branches, departments and configuration

- **Pages:** organization profile/settings, branch list/detail, department list/detail, designation and grade catalog, business calendar, retention/configuration settings.
- **API:** `GET/POST /organizations`; `GET/PATCH /organizations/{id}`; `GET/POST /organizations/{id}/branches`; `GET/PATCH/DELETE /branches/{id}`; `GET/POST /organizations/{id}/departments`; `GET/PATCH/DELETE /departments/{id}`; `GET/POST /designations`; `GET/PATCH/DELETE /designations/{id}`; `GET/POST /job-grades`; `GET/PATCH/DELETE /job-grades/{id}`; `GET/PATCH /organizations/{id}/settings`.
- **Entities:** Organization, OrganizationMembership, Branch, Department, Designation, JobGrade, OrganizationSetting, Calendar, Holiday.
- **Workflow:** Organization Admin establishes tenant structure and memberships; assignments reference active organization records; archival preserves history.
- **Acceptance:** tenant A cannot list/read/change tenant B; duplicate normalized codes/names rejected within the correct scope; department/branch archival retains historical employee and transaction references.

### HR — employee lifecycle and onboarding

- **Pages:** employee directory, employee profile (overview/contact/employment/documents/history tabs), create/edit employee, onboarding checklist, probation/confirmation, transfer/promotion, exit/offboarding, HR dashboard.
- **API:** `GET/POST /employees`; `GET/PATCH /employees/{id}`; `POST /employees/{id}/archive`; `GET/POST /employees/{id}/contacts`; `GET/POST /employees/{id}/employment-history`; `GET/POST /employees/{id}/contracts`; `GET/POST /employees/{id}/documents`; `GET /employees/{id}/documents/{document_id}/download`; `GET/POST /employees/{id}/onboarding-tasks`; `PATCH /onboarding-tasks/{id}`; `POST /employees/{id}/transfers`; `POST /employees/{id}/promotions`; `POST /employees/{id}/offboarding`.
- **Entities:** Employee, EmployeeContact, EmergencyContact, EmploymentRecord, EmploymentContract, EmployeeDocument, EmployeeHistoryEvent, EmployeeFieldDefinition, OnboardingTemplate, OnboardingTask, ProbationReview, Transfer, Promotion, ExitInterview.
- **Workflow:** hire/create -> onboarding tasks -> probation/confirmation -> ongoing employment changes -> offboarding. Sensitive files use private object storage and short-lived authorized downloads.
- **Acceptance:** unique employee ID per organization; valid employment dates; only permitted self-profile fields editable; employee A cannot retrieve employee B's profile, contacts, contract, history or document by ID; upload size/type checks; archive leaves linked records intact; export contains only authorized fields.

### ATT — attendance, shifts and timesheets

- **Pages:** personal clock panel, attendance history, team attendance, correction inbox, shift catalog, roster calendar, timesheet submission/review, overtime request, attendance reports.
- **API:** `POST /attendance/clock-in`, `POST /attendance/clock-out`, `GET /attendance`; `POST /attendance/corrections`; `GET /attendance/corrections`; `POST /attendance/corrections/{id}/decision`; `GET/POST /shifts`; `GET/PATCH/DELETE /shifts/{id}`; `GET/POST /rosters`; `GET/PATCH /rosters/{id}`; `POST /timesheets`; `GET /timesheets`; `POST /timesheets/{id}/submit`; `POST /timesheets/{id}/decision`; `POST /overtime-requests`; `POST /overtime-requests/{id}/decision`; `GET /reports/attendance`.
- **Entities:** AttendanceEvent, AttendanceDay, AttendanceCorrection, Shift, ShiftAssignment, Roster, WorkSchedule, Timesheet, TimesheetEntry, OvertimeRequest, AttendanceRule, Holiday.
- **Workflow:** clock event -> daily record; correction/overtime/timesheet -> configured approval -> immutable history. Rules use organization timezone and effective dates.
- **Acceptance:** duplicate punches and invalid transitions denied; employees read only own records; manager sees assigned team; corrections require permission and retain before/after values; overlapping shifts and invalid duration rejected; timezone boundary cases tested.

### LEAVE — policies, balances, calendar and approvals

- **Pages:** leave dashboard, personal balances/requests, team calendar, request form/detail, approval inbox, policy/accrual editor, holiday calendar, reports.
- **API:** `GET/POST /leave-types`; `GET/PATCH /leave-types/{id}`; `GET/POST /leave-policies`; `GET/PATCH /leave-policies/{id}`; `GET /employees/{id}/leave-balances`; `POST /leave-requests`; `GET /leave-requests`; `GET /leave-requests/{id}`; `POST /leave-requests/{id}/submit`; `POST /leave-requests/{id}/cancel`; `GET/POST /holidays`; `POST /leave-requests/{id}/resubmit`; approvals use `/approvals/{id}/actions`.
- **Entities:** LeaveType, LeavePolicy, LeavePolicyRule, LeaveBalance, LeaveLedgerEntry, LeaveRequest, Holiday, ApprovalInstance, ApprovalStage, ApprovalAction.
- **Workflow:** draft -> submitted -> stage approvals -> approved/rejected/changes requested -> optional resubmission/cancellation. Balance reservation/deduction is transaction-safe and follows configured accrual, carry-forward, expiry, work calendar and timezone rules.
- **Acceptance:** overlap and entitlement validation; weekend/holiday/half-day/date-boundary cases; policy changes are effective-dated; only authorized manager approves within scope; requester cannot approve own request; duplicate/replayed decision cannot double-adjust ledger; balance history reconciles.

### PAY — compensation and payroll

- **Pages:** restricted payroll dashboard, salary profile, compensation history, payroll calendar/period, draft run, validation/reconciliation report, approval/finalization, payslip list/detail/download.
- **API:** `GET/POST /salary-structures`; `GET/PATCH /salary-structures/{id}`; `POST /employees/{id}/compensation-changes`; `GET /payroll-periods`; `POST /payroll-periods`; `POST /payroll-runs`; `GET /payroll-runs/{id}`; `POST /payroll-runs/{id}/validate`; `POST /payroll-runs/{id}/submit`; approval through `/approvals/{id}/actions`; `POST /payroll-runs/{id}/finalize`; `GET /employees/{id}/payslips`; `GET /payslips/{id}/download`; `GET /reports/payroll`.
- **Entities:** SalaryStructure, SalaryComponent, CompensationChange, PayrollPeriod, PayrollRun, PayrollLine, PayrollValidation, Payslip, TaxRuleSet, StatutoryRule, PayrollJournalLink.
- **Workflow:** draft -> calculate from approved/effective inputs -> validate/reconcile -> authorized review -> approval -> idempotent finalization -> payslip publication. Tax/statutory rules are selected-jurisdiction configuration, never inferred or fabricated.
- **Acceptance:** unauthorized roles cannot query salary/payslips; duplicate period/run and duplicate finalization rejected; recalculation is deterministic and transaction-safe; effective-date, rounding, leave/attendance inputs and jurisdiction rule versions are auditable; payslip download checks owner/admin scope.

### REC — recruitment and applicant tracking

- **Pages:** requisition list/detail/approval, job openings, candidate directory/profile, application pipeline/board, interview schedule, scorecards, offers, recruitment reports.
- **API:** `GET/POST /job-requisitions`; `GET/PATCH /job-requisitions/{id}`; approvals via `/approvals/{id}/actions`; `GET/POST /job-postings`; `GET/PATCH /job-postings/{id}`; `GET/POST /candidates`; `GET/PATCH /candidates/{id}`; `GET/POST /applications`; `GET/PATCH /applications/{id}`; `POST /applications/{id}/stage`; `GET/POST /applications/{id}/interviews`; `POST /interviews/{id}/feedback`; `POST /applications/{id}/offers`; `POST /offers/{id}/decision`; `POST /applications/{id}/hire`; `GET /reports/recruitment`.
- **Entities:** JobRequisition, JobPosting, Candidate, Application, RecruitmentStage, Interview, InterviewerFeedback, Offer, CandidateConsent, RecruitmentSource.
- **Workflow:** requisition approval -> posting -> application stages -> interviews/scorecards -> offer approval/acceptance -> employee conversion.
- **Acceptance:** recruiter cannot access payroll/employee confidential files; candidate consent/retention state enforced; stage transitions validated; duplicate candidate/application handling tested; hired candidate conversion is idempotent and creates linked employment history.

### PERF — performance and goals

- **Pages:** cycle setup, goal catalog, personal goals/progress, self-review, manager review, feedback, approval inbox, appraisal history.
- **API:** `GET/POST /performance-cycles`; `GET/PATCH /performance-cycles/{id}`; `GET/POST /employees/{id}/goals`; `PATCH /goals/{id}`; `POST /goals/{id}/progress`; `POST /performance-reviews`; `GET /performance-reviews`; `POST /performance-reviews/{id}/submit`; approvals via `/approvals/{id}/actions`.
- **Entities:** PerformanceCycle, Goal, GoalProgress, SelfAssessment, ManagerReview, Feedback, AppraisalDecision.
- **Workflow:** cycle -> goals -> progress -> self-assessment -> manager review -> approval/feedback -> immutable appraisal history.
- **Acceptance:** employees access own review only; manager scope required; reviewer cannot bypass cycle dates/states; confidential comments have explicit visibility tests.

### LND — learning and development

- **Pages:** course catalog, program detail, enrollment, training plan, certifications, expiry inbox and reports.
- **API:** `GET/POST /courses`; `GET/PATCH /courses/{id}`; `GET/POST /training-programs`; `POST /training-enrollments`; `PATCH /training-enrollments/{id}`; `GET/POST /employees/{id}/certifications`; `GET /reports/training`.
- **Entities:** Course, TrainingProgram, TrainingEnrollment, Certification, Skill, EmployeeSkill, TrainingBudget.
- **Workflow:** publish course -> enroll/assign -> record completion -> issue certification -> notify before expiry.
- **Acceptance:** employee sees own enrollments; manager/HR sees permitted team/organization scope; completion/certification dates validated; expiry query uses configured timezone.

### EXP — expenses and reimbursement

- **Pages:** expense dashboard, policy/category setup, personal claims, receipt detail, approval inbox, finance payment queue and reports.
- **API:** `GET/POST /expense-categories`; `GET/PATCH /expense-policies/{id}`; `POST /expense-claims`; `GET /expense-claims`; `GET /expense-claims/{id}`; `POST /expense-claims/{id}/receipts`; `GET /expense-claims/{id}/receipts/{receipt_id}/download`; `POST /expense-claims/{id}/submit`; decisions via `/approvals/{id}/actions`; `POST /expense-claims/{id}/payments`; `GET /reports/expenses`.
- **Entities:** ExpenseCategory, ExpensePolicy, ExpenseClaim, ExpenseLine, Receipt, ReimbursementPayment, ApprovalInstance.
- **Workflow:** draft with validated receipts -> submit -> configured approvals -> approved/rejected/changes requested -> finance reimbursement -> reconciliation.
- **Acceptance:** owner-only claim/receipt access; file size/type/content checks; duplicate claim detection; policy amount/currency/date validation; only Finance Officer records payment; approval history immutable.

### ESS — employee self-service

- **Pages:** personal dashboard, permitted profile, attendance, leave, payslips, documents, expenses, training, notifications, tasks and request history.
- **API:** own scoped views are resources above plus `GET/PATCH /employees/me`, `GET /employees/me/requests`, `GET /employees/me/notifications`, `PATCH /notifications/{id}/read`, `GET /employees/me/documents`, `GET /employees/me/payslips`.
- **Entities:** Employee plus scoped module entities, Notification, NotificationPreference, TaskAssignment.
- **Workflow:** employee submits self-service requests; server resolves owner from session and creates approval task.
- **Acceptance:** mutating URL/query/body user IDs never exposes another employee's data; profile editable-field allowlist enforced; notification read/write is owner-scoped.

### DOC — employee relations and secure documents

- **Pages:** employee document list/detail/upload, templates/letters, policy acknowledgements, secure employee-relations case list/detail, retention administration.
- **API:** `GET/POST /documents`; `GET /documents/{id}`; `GET /documents/{id}/download`; `POST /document-templates`; `POST /employees/{id}/policy-acknowledgements`; `GET/POST /employee-cases`; `GET/PATCH /employee-cases/{id}`; `POST /retention-runs/preview`; `POST /retention-runs/{id}/execute`.
- **Entities:** Document, DocumentAccessGrant, DocumentTemplate, PolicyAcknowledgement, EmployeeRelationsCase, RetentionPolicy, RetentionRun.
- **Workflow:** upload -> malware/type validation -> private storage -> explicit authorization on each download -> retention preview/approval -> controlled deletion or legal hold.
- **Acceptance:** no public object URLs; cross-owner and cross-tenant access denied; permitted roles audited; legal holds block deletion; retention actions are dry-run reviewable and recorded.

### FIN — finance and accounting

- **Pages:** finance overview, chart of accounts, journal entries, ledger, AP bills, AR invoices, payments/reconciliation, budgets/cost centers, reports.
- **API:** `GET/POST /accounts`; `GET/PATCH /accounts/{id}`; `GET/POST /journal-entries`; `GET /journal-entries/{id}`; `POST /journal-entries/{id}/post`; `GET /ledger`; `GET/POST /vendor-bills`; `POST /vendor-bills/{id}/decision`; `GET/POST /customer-invoices`; `POST /customer-invoices/{id}/issue`; `POST /payments`; `POST /reconciliations`; `GET/POST /budgets`; `GET /reports/finance`.
- **Entities:** Account, JournalEntry, JournalLine, LedgerPosting, VendorBill, CustomerInvoice, Payment, Reconciliation, Budget, CostCenter, AccountingPeriod.
- **Workflow:** draft transaction -> balanced validation -> approval where required -> post to ledger -> payment/reconciliation -> immutable audit trail.
- **Acceptance:** debit/credit balance; closed-period denial; tenant and finance-role scope; no direct mutation of posted entries; duplicate payment/reconciliation idempotency; report totals reconcile to ledger.

### PROC — procurement

- **Pages:** vendor list/detail, requisitions, approval inbox, purchase orders, receipts, invoice matching and history.
- **API:** `GET/POST /vendors`; `GET/PATCH /vendors/{id}`; `POST /purchase-requisitions`; `GET /purchase-requisitions`; decisions via `/approvals/{id}/actions`; `POST /purchase-orders`; `GET/PATCH /purchase-orders/{id}`; `POST /purchase-orders/{id}/receipts`; `POST /purchase-orders/{id}/match-invoice`; `GET /reports/procurement`.
- **Entities:** Vendor, PurchaseRequisition, PurchaseRequisitionLine, PurchaseOrder, PurchaseOrderLine, GoodsReceipt, InvoiceMatch.
- **Workflow:** requisition -> staged approval -> PO -> goods receipt -> bill matching -> finance handoff.
- **Acceptance:** requester/approver separation; threshold stages validated server side; receipt quantity and invoice match rules; vendor/organization scope; duplicate submission idempotency.

### INV — inventory

- **Pages:** product/SKU catalog, warehouse/location tree, stock balances, receipts/issues/transfers/adjustments, reorder alerts, valuation reports.
- **API:** `GET/POST /products`; `GET/PATCH /products/{id}`; `GET/POST /warehouses`; `GET/POST /stock-movements`; `POST /stock-transfers`; `POST /inventory-adjustments`; `GET /inventory-balances`; `GET /inventory-alerts`; `GET /reports/inventory`.
- **Entities:** Product, SKU, Warehouse, StockLocation, InventoryMovement, StockBalance, InventoryAdjustment, ReorderRule, ValuationLayer.
- **Workflow:** authorized movement records append immutable stock ledger; transfers debit and credit atomically; configured costing method derives valuation.
- **Acceptance:** no negative stock unless policy allows; transfer atomicity; duplicate movement idempotency; adjustment approval and audit; valuation reconciles to movement history.

### ASSET — asset management

- **Pages:** asset register/detail, employee/department assignment, maintenance schedule/history, warranty/expiry inbox, return and disposal.
- **API:** `GET/POST /assets`; `GET/PATCH /assets/{id}`; `POST /assets/{id}/assignments`; `POST /assets/{id}/returns`; `POST /assets/{id}/maintenance`; `POST /assets/{id}/dispose`; `GET /reports/assets`.
- **Entities:** Asset, AssetAssignment, AssetMaintenance, Warranty, AssetDisposal, AssetHistoryEvent.
- **Workflow:** register -> assign -> maintain/return -> transfer/dispose; every state transition recorded.
- **Acceptance:** unique identifier; no simultaneous active assignments; return/disposal authorization and required history; asset data scoped to organization.

### PROJ — projects and timesheets

- **Pages:** project list/detail, tasks/milestones, team allocation, timesheets, approval inbox, project budget/progress reports.
- **API:** `GET/POST /projects`; `GET/PATCH /projects/{id}`; `POST /projects/{id}/tasks`; `PATCH /tasks/{id}`; `POST /projects/{id}/assignments`; `POST /project-timesheets`; `GET /project-timesheets`; decisions via `/approvals/{id}/actions`; `GET /reports/projects`.
- **Entities:** Project, ProjectTask, Milestone, ProjectAssignment, ProjectTimesheet, ProjectCost, ProjectBudget.
- **Workflow:** project setup -> task/assignment -> time/cost recording -> approval -> progress and budget rollup.
- **Acceptance:** assignment scope, date/effort validation, approved timesheet immutability, budget totals from persisted entries.

### CRM — customers, vendors, sales and service

- **Pages:** customer/vendor profiles, contracts, quotation/order pipeline, service ticket queue/detail, assignment, resolution and reports.
- **API:** `GET/POST /customers`; `GET/PATCH /customers/{id}`; `GET/POST /commercial-contracts`; `GET/POST /quotations`; `POST /quotations/{id}/decision`; `POST /sales-orders`; `GET/PATCH /sales-orders/{id}`; `POST /service-tickets`; `GET /service-tickets`; `GET/PATCH /service-tickets/{id}`; `POST /service-tickets/{id}/resolve`; `GET /reports/service`.
- **Entities:** Customer, CustomerContact, Supplier, CommercialContract, Quotation, SalesOrder, ServiceTicket, TicketEvent.
- **Workflow:** quote -> authorized approval -> order -> service ticket assignment -> resolution with history.
- **Acceptance:** tenant and commercial-role scope; valid status transitions; customer contacts only visible to authorized team; reports reconcile to transactions.

### APPROVAL — reusable approvals

- **Pages:** pending-action inbox, approval detail/history, workflow definition/stages, delegation/escalation settings.
- **API:** `GET/POST /approval-workflows`; `GET/PATCH /approval-workflows/{id}`; `GET /approvals`; `GET /approvals/{id}`; `POST /approvals/{id}/actions`; `POST /approvals/{id}/delegate`; `GET /approvals/{id}/history`.
- **Entities:** ApprovalWorkflow, ApprovalStageDefinition, ApprovalInstance, ApprovalStage, ApprovalAction, ApproverAssignment, Delegation, EscalationRule.
- **Workflow:** requester submits a domain record -> instantiated stages resolve permitted role/manager approvers -> approve/reject/request changes -> resubmit or terminal state -> reminders/escalation when configured. Separation of duties and allowed transitions are server-enforced.
- **Acceptance:** cannot approve own request where policy forbids it; stage order and scope respected; comments and history immutable; replay/concurrent actions are idempotent; resubmission advances only valid state.

### DASH, NOTIF, SEARCH and REPORTS — shared work surface

- **Pages:** role-specific dashboard, global search results, pending-action inbox, notification center/preferences, saved filters, report catalog and report detail.
- **API:** `GET /dashboard`; `GET /search?q=...`; `GET /notifications`; `PATCH /notifications/{id}`; `GET/PATCH /notification-preferences`; `GET /approvals`; `GET /reports`; `POST /reports/{id}/export`; `GET/POST /saved-filters`.
- **Entities:** DashboardQueryDefinition, Notification, NotificationPreference, ReminderJob, SavedFilter, ReportDefinition, ExportJob.
- **Workflow:** domain event -> in-app notification/reminder; report/search scopes derive from authenticated permissions; export is generated from the same authorized query and audited.
- **Acceptance:** metrics are database-derived with date/department filters; no fabricated metrics; search and reports do not leak protected fields; unread state is owner-only; export escaping prevents spreadsheet formula injection; unavailable email is explicitly reported.

## 4. Cross-cutting API rules

- JSON REST under `/api/v1`, plural resources, explicit schemas, correct status codes, stable error envelope (`code`, safe `message`, field errors, request ID).
- Authentication: session cookie/CSRF contract as documented in architecture; never accept authorization scope in a client-controlled filter without intersecting it with server-derived scope.
- Lists default to a conservative page size, cap maximum, use stable ordering, and return `{items, total, limit, offset}` or documented cursor equivalent.
- State-changing requests validate transitions, use transactions, and support idempotency keys for retries on payments, finalization, stock movement, submissions and approvals.
- File APIs stream from private storage only after object authorization; never expose path or public bucket keys.
- Existing `/api/...` routes remain compatibility adapters until migration and clients are complete. They must not gain weaker permissions during transition.

## 5. Non-functional acceptance

- **Security/privacy:** permission matrix, IDOR, tenant isolation, session lifecycle, secret scanning, safe logs, upload checks and dependency review pass.
- **Data integrity:** migrations preserve existing users/employees and add constraints after preflight; rollback behavior is tested on disposable DBs; backup/restore drill is documented.
- **Reliability:** critical transitions are transactional; no duplicate payroll finalization or stock/payment posting; health/liveness/readiness are distinct.
- **Performance:** avoid N+1; indexes support tenant/time/status lookups; load tests measure dashboard, employee search and approval inbox on production-like PostgreSQL.
- **Accessibility:** keyboard operation, visible focus, labels, errors, contrast and responsive layouts verified; automated axe and manual screen-reader checks on core flows.
- **Operations:** reproducible environment config, Docker Compose, migrations, seed-only development data, structured logs, backups, restore and deployment procedure.
- **Quality:** pytest, frontend unit/component tests, lint, type check, production build, Playwright critical flows, migration tests, security-negative tests and supported-database tests pass before a stage is marked verified.
