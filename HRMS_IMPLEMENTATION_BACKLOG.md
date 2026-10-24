# NEXORA Workforce OS - Implementation Backlog

## Priority: High

### [P0] Employee Department Foreign Key Migration

**Description**: Migrate employee department from string to relational foreign key. 
- Currently `employees.department` is `String(100)` 
- Need to populate `employees.department_id` from existing department strings
- Then make `department_id` non-nullable and drop the string column

**Acceptance Criteria**:
- [ ] Department data from string field transferred to FK
- [ ] FK constraint enforced with `ondelete="SET NULL"` 
- [ ] String `department` column deprecated (kept for read compatibility or removed)
- [ ] All API endpoints updated to use FK instead of string

**Related Code**:
- `backend/migrations/versions/0001_additive_foundation.py` - initial department_id addition
- `backend/models.py` - Employee model department field
- `backend/application.py` - employee department lookup endpoints

---

### [P0] Authentication Authorization Enforcement Tests

**Description**: Add test coverage verifying that role-based access control actually enforces module permissions at the endpoint level.

**Acceptance Criteria**:
- [ ] Test that Employee role cannot access `/api/modules` administrative endpoints
- [ ] Test that HR Administrator can access attendance/leave modules
- [ ] Test that Super Admin has access to all modules including `module-access`
- [ ] Test organization-scoped role assignments from `organization_memberships`

**Related Code**:
- `backend/tests/test_api.py` - Add permission enforcement tests
- `backend/application.py` - Module permission check logic

---

### [P1] Leave Policy Enforcement

**Description**: Implement and test policy boundary conditions for leave management.

**Acceptance Criteria**:
- [ ] API rejects leave requests exceeding annual allowance
- [ ] API checks holidays table when computing work days
- [ ] Half-day requests rejected on weekends (already tested in `test_half_day_on_weekend_is_rejected`)
- [ ] Cross-year range requests rejected (already tested in `test_leave_requests_reject_non_workdays_and_cross_year_ranges`)

**Related Code**:
- `backend/application.py` - Leave request validation
- `backend/models.py` - Leave balance computation

---

### [P1] Audit Log Coverage Expansion

**Description**: Add audit logging for all API endpoints that modify state.

**Acceptance Criteria**:
- [ ] Employee profile updates logged
- [ ] Contact detail changes logged
- [ ] Leave request create/cancel/review logged
- [ ] Attendance records logged
- [ ] Password changes logged

**Related Code**:
- `backend/models.py` - AuditLog model and logging decorator
- `backend/application.py` - Endpoints needing audit logging

---

## Priority: Medium

### [P2] Employee Department String Deprecation

**Description**: After FK migration (P0), deprecate the `department` string field in `employees` table.

**Acceptance Criteria**:
- [ ] String field kept for backward compatibility with documentation
- [ ] API responses optionally include department string
- [ ] New development uses `department_id` FK

**Related Code**:
- `backend/models.py` - Employee model
- API endpoint responses

---

### [P2] Payroll Computation Logic

**Description**: Implement payroll run computation and payslip generation.

**Acceptance Criteria**:
- [ ] Payroll run creates summary statistics from compensation records
- [ ] Payslips generated with gross/deductions/net pay
- [ ] Employee count computed per payroll run

**Related Code**:
- `backend/migrations/versions/0010_payroll.py` - Tables already exist
- `backend/application.py` - Payroll computation endpoints

---

### [P2] Recruitment Pipeline Features

**Description**: Add candidate screening and application tracking features.

**Acceptance Criteria**:
- [ ] requisitions can be created and closed
- [ ] Candidates assigned to requisitions
- [ ] Applications progress through stages (Applied -> Shortlisted -> Offer -> Hired)

**Related Code**:
- `backend/migrations/versions/0011_recruitment.py` - Tables already exist
- `backend/application.py` - Recruitment API endpoints

---

### [P2] Performance Review Workflow

**Description**: Implement performance review cycle management with reviewer assignment.

**Acceptance Criteria**:
- [ ] Review cycles created with start/end dates
- [ ] Goals assigned to employees per cycle
- [ ] Reviews completed with ratings and comments
- [ ] Reviewer assignment respects organizational scope

**Related Code**:
- `backend/migrations/versions/0012_performance_goals.py` - Tables already exist
- `backend/application.py` - Performance review endpoints

---

### [P3] MFA Backup Code Consumption

**Description**: Implement backup code tracking and consumption on MFA verification.

**Acceptance Criteria**:
- [ ] Backup codes decremented on successful verification
- [ ] Zero backup codes prevents MFA-verification-only login
- [ ] Emergency access flow for lost authenticator

**Related Code**:
- `backend/migrations/versions/0009_password_reset_mfa.py` - MFA factors table
- `frontend/src/features/auth/AuthScreen.tsx` - MFA enrollment UI
- `frontend/src/features/auth/SessionManager.tsx` - Session management

---

## Priority: Low

### [P3] Module Catalog Dynamic Seeding

**Description**: Make module catalog seeding configurable instead of hardcoded constant.

**Acceptance Criteria**:
- [ ] `DEFAULT_MODULES` can be overridden via database or config
- [ ] Admin can add custom modules via API
- [ ] Module permissions can be granted/revoked per role

**Related Code**:
- `backend/application.py` - `DEFAULT_MODULES` constant and `bootstrap_modules()`
- `backend/migrations/versions/0014_module_permissions.py` - Module table structure

---

### [P3] Branch/Designation/Job Grade Assignment to Employees

**Description**: Complete the organization catalog features by adding branch/designation/grade assignment to employee profiles.

**Acceptance Criteria**:
- [ `employees` table has `branch_id`, `designation_id`, `job_grade_id` FK columns (already added in migration 0006)
- [ ] UI can assign/ view these assignments
- [ ] Reports can filter by branch/designation/grade

**Related Code**:
- `backend/migrations/versions/0006_organization_catalogs.py` - Employee assignment columns added
- `frontend/src/features/employees/EmployeeProfilePanel.tsx` - Assignment display
- `frontend/src/features/organization/OrganizationStructure.tsx` - Management UI

---

### [P3] Organization Membership Role Granularity

**Description**: Enhance `organization_memberships` to support more granular role assignment beyond just `users.role`.

**Acceptance Criteria**:
- [ ] `organization_memberships.role` distinct from `users.role`
- [ ] Department-level role assignment possible
- [ ] Module permissions at department level

**Related Code**:
- `backend/migrations/versions/0008_organization_memberships.py` - Organization memberships table
- `backend/models.py` - Membership model
