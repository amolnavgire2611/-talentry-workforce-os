# NEXORA Workforce OS - System Inventory

## Architecture Overview

The NEXORA Workforce OS is a FastAPI-based backend application with a React/TypeScript frontend. The system follows a modular architecture with separation of concerns between API layer, database models, schemas, and authentication/authorization.

## Core Modules

| Module | Description | Key Endpoints |
|--------|-------------|---------------|
| **Authentication** | User registration, login, password reset, MFA, session management | `/api/auth/*`, `/api/auth/admin-*` |
| **Employee Management** | Employee records, department assignment, profile management | `/api/employees/*` |
| **Department Management** | Department hierarchy, organization structure | `/api/departments/*` |
| **Attendance** | Time tracking, check-in/out, work date records | `/api/attendance/*` |
| **Leave Management** | Leave type definitions, balance tracking, request lifecycle | `/api/leave-types/*`, `/api/leave-requests/*`, `/api/leave-balances/*` |
| **Organization** | Multi-tenant support, organization scoping, organization memberships | `/api/organizations/*` |
| **Payroll** | Compensation, payroll runs, payslips | `/api/compensation/*`, `/api/payroll-runs/*`, `/api/payslips/*` |
| **Recruitment** | Job requisitions, candidates, applications | `/api/requisitions/*`, `/api/candidates/*`, `/api/applications/*` |
| **Learning & Notifications** | Training courses, enrollments, notifications, announcements | `/api/training-courses/*`, `/api/training-enrollments/*`, `/api/notifications/*`, `/api/announcements/*` |
| **Performance** | Goals, review cycles, performance reviews | `/api/goals/*`, `/api/review-cycles/*`, `/api/performance-reviews/*` |
| **Module Permissions** | Role-based module access control | `/api/my-permissions`, `/api/modules` |

## API Endpoints Summary

### Authentication (`/api/auth/`)
- `POST /login` - User login with username/password
- `POST /register` - Employee registration (requires role-based invitation for non-Employee roles)
- `POST /register-admin` - First-time Super Admin setup (one-time key required)
- `POST /refresh` - JWT refresh token rotation
- `POST /password/forgot` - Password reset initiation
- `POST /password/reset` - Password reset with token
- `POST /mfa/enrollment` - MFA enrollment
- `POST /mfa/verify` - MFA code verification
- `GET /admin-registration-status` - Check if admin registration is still available
- `POST /logout` - Logout and revoke sessions

### Employees (`/api/employees/`)
- `GET /` - List employees (with pagination, filtering)
- `POST /` - Create employee (admin only)
- `GET /me` - Current user profile
- `GET /{id}` - Get employee by ID
- `PUT /{id}` - Update employee
- `GET /{id}/contact` - Get contact details (private, HR/owner access only)
- `PUT /{id}/contact` - Update contact details (private)
- `GET /{id}/emergency-contacts` - Get emergency contacts (private)
- `GET /{id}/employment-history` - Get employment history
- `GET /{id}/contracts` - Get employment contracts

### Departments (`/api/departments/`)
- `GET /` - List departments
- `POST /` - Create department
- `GET /{id}` - Get department by ID

### Leave Types (`/api/leave-types/`)
- `GET /` - List leave types
- `POST /` - Create leave type (admin only)
- `GET /{id}` - Get leave type by ID
- `PUT /{id}` - Update leave type

### Leave Requests (`/api/leave-requests/`)
- `GET /` - List leave requests
- `POST /` - Create leave request (employee)
- `PUT /{id}/review` - Review/approve leave request (admin/manager)
- `PUT /{id}/cancel` - Cancel leave request

### Leave Balances (`/api/leave-balances/`)
- `GET /` - List leave balances for year
- Filters: `?year={year}`

### Organizations (`/api/organizations/`)
- `GET /` - List organizations
- `POST /` - Create organization
- `GET /{id}` - Get organization by ID

### Modules & Permissions (`/api/modules/`, `/api/my-permissions/`)
- `GET /api/modules` - Full module catalog (any authenticated user)
- `GET /api/my-permissions` - User's accessible modules and permissions
- Module catalog is seeded from `DEFAULT_MODULES` in `application.py`
- Role-based filtering: `EMPLOYEE_MODULE_KEYS` vs `ALL_MODULE_KEYS`

### Dashboard (`/api/dashboard/`)
- `GET /` - Dashboard statistics by scope (organization/department/personal)

### Invitations (`/api/users/invitations/`)
- `POST /` - Send registration invitation
- `POST /{id}/invitation` - Reissue registration code

### Security (`/api/auth/password/`)
- `POST /forgot` - Password reset request
- `POST /reset` - Password reset with token

## Database Models (SQLAlchemy)

### Core Tables

| Table | Key Columns | Relationships |
|-------|------------|---------------|
| `users` | id, name, email, hashed_password, role, active, department_id, organization_id | FK: departments(id), organizations(id) |
| `employees` | id, employee_code, name, department (string), role, status, user_id, branch_id, designation_id, job_grade_id, reporting_manager_id | FK: users(id), branches(id), designations(id), job_grades(id), employees(id) |
| `departments` | id, name, description, active, created_at, organization_id | FK: organizations(id) |
| `organizations` | id, name, slug, active, created_at | — |
| `leave_types` | id, name, description, annual_allowance_days, paid, active, created_at | — |
| `leave_balances` | id, user_id, leave_type_id, year, allocated_days, used_days, updated_at | FK: users(id), leave_types(id) |
| `holidays` | id, holiday_date, name, active | Unique: holiday_date |
| `attendance` | id, user_id, work_date, check_in, check_out, status | FK: users(id) |
| `leave_requests` | id, user_id, start_date, end_date, leave_type_id, half_day, days_requested, reason, status, reviewed_by, reviewed_at, review_comment | FK: users(id), leave_types(id) |
| `refresh_sessions` | id, user_id, token_hash, csrf_hash, created_at, last_seen_at, expires_at, revoked_at | FK: users(id) |
| `role_module_permissions` | id, organization_id, module_id, role, granted, created_at | FK: modules(id), organizations(id) |
| `modules` | id, organization_id, module_key, name, description, active, created_at | FK: organizations(id) |
| `password_resets` | id, email, token_hash, expires_at, used_at, organization_id | FK: organizations(id) |
| `mfa_factors` | id, user_id, factor_type, secret, verified, backup_codes, created_at, updated_at, organization_id | FK: users(id), organizations(id) |
| `password_history` | id, user_id, hashed_password, created_at | FK: users(id) |
| `compensation` | id, employee_id, employment_type, base_salary, currency, pay_frequency, effective_from, effective_to, active, created_at, organization_id | FK: employees(id), organizations(id) |
| `payroll_runs` | id, name, period_start, period_end, pay_date, status, total_gross, total_deductions, total_net, employee_count, created_by, finalized_at, created_at, organization_id | FK: users(created_by), organizations(id) |
| `payslips` | id, payroll_run_id, employee_id, gross_pay, deductions, net_pay, payslip_date, status, created_at, organization_id | FK: payroll_runs(id), employees(id), organizations(id) |
| `requisitions` | id, title, department, employment_type, status, created_by, created_at, closed_at, organization_id | FK: users(created_by), organizations(id) |
| `candidates` | id, requisition_id, name, email, phone, status, resume_url, applied_at, organization_id | FK: requisitions(requisition_id), organizations(id) |
| `applications` | id, candidate_id, stage, score, notes, created_at, updated_at, organization_id | FK: candidates(candidate_id), organizations(id) |
| `training_courses` | id, title, description, category, provider, duration_hours, active, created_at, organization_id | FK: organizations(id) |
| `training_enrollments` | id, course_id, employee_id, status, score, enrolled_at, completed_at, organization_id | FK: training_courses(course_id), employees(id), organizations(id) |
| `notifications` | id, user_id, title, message, category, read, created_by, created_at, organization_id | FK: users(user_id), organizations(id) |
| `announcements` | id, title, body, pinned, created_by, created_at, expires_at, organization_id | FK: organizations(id) |
| `goals` | id, employee_id, title, description, category, status, target_date, progress, created_by, created_at, updated_at, organization_id | FK: employees(id), organizations(id) |
| `review_cycles` | id, name, start_date, end_date, status, created_at, organization_id | FK: organizations(id) |
| `performance_reviews` | id, review_cycle_id, employee_id, reviewer_id, overall_rating, comments, status, submitted_at, created_at, updated_at, organization_id | FK: review_cycles(id), employees(id), users(reviewer_id), organizations(id) |
| `employment_contracts` | id, organization_id, employee_id, reference, employment_type, start_date, end_date, signed_date, status, created_by, created_at, updated_at | FK: employees(employee_id), users(created_by), organizations(id) |
| `organization_memberships` | id, organization_id, user_id, role, department_id, active, created_at | FK: organizations(id), users(id), departments(id) |
| `branches` | id, organization_id, code, name, address, active, created_at | FK: organizations(id) |
| `designations` | id, organization_id, name, description, active, created_at | FK: organizations(id) |
| `job_grades` | id, organization_id, code, name, description, rank, active, created_at | FK: organizations(id) |
| `invitations` | id, user_id, token_hash, expires_at, accepted_at, created_at | FK: users(id) |
| `revoked_tokens` | id, jti, user_id, expires_at, revoked_at | FK: users(id) |

## Authentication & Authorization Flow

### Token-Based Authentication
- JWT access tokens with configurable issuer and audience validation
- Refresh token rotation via `/api/auth/refresh`
- CSRF token protection for state-changing operations
- Token revocation via `revoked_tokens` table and `refresh_sessions` table

### Role-Based Access Control
- Roles defined: `Super Admin`, `HR Administrator`, `HR Manager`, `Organization Admin`, `Department Manager`, `HR Administrator`, `Recruiter`, `Payroll Administrator`, `Attendance Administrator`, `Employee`
- Module permissions stored in `role_module_permissions` table
- `GET /api/my-permissions` returns user's accessible modules based on role
- Super Admin sees all modules (`ALL_MODULE_KEYS`); Employees see subset (`EMPLOYEE_MODULE_KEYS`)
- Module `module-access` is never shown to Employee role

### Session Management
- Active sessions tracked in `refresh_sessions` table
- Session revocation via `/api/auth/logout` and `END ALL SESSIONS` UI
- Rate limiting on registration (20 attempts) and password reset (5 attempts)

## Frontend Application

### Technology Stack
- **Framework**: React 18 with TypeScript
- **Bundler**: Vite
- **State Management**: React hooks (useState, useEffect, useMemo, useCallback)
- **HTTP Client**: Custom `api.ts` wrapper around fetch API
- **Testing**: Vitest with Testing Library

### Key Frontend Components

| Component | Path | Description |
|-----------|------|-------------|
| `WorkforceApp` | `src/WorkforceApp.tsx` | Main app shell, sidebar navigation, layout |
| `AuthScreen` | `src/features/auth/AuthScreen.tsx` | Login, register, admin setup, forgot/reset, MFA |
| `SessionManager` | `src/features/auth/SessionManager.tsx` | View and end active sessions |
| `EmployeeProfilePanel` | `src/features/employees/EmployeeProfilePanel.tsx` | Private employee profile (contact, emergency, history, contracts) |
| `OrganizationStructure` | `src/features/organization/OrganizationStructure.tsx` | Branches, designations, job grades management |

### API Client (`src/lib/api.ts`)
- Bearer token authentication with automatic 401 retry/refresh
- CSRF token inclusion on POST/PUT/PATCH/DELETE
- Public auth paths exempt from authentication
- Error formatting for Pydantic validation errors

### Test Coverage
- Frontend: 7 test files covering auth, sessions, employees, API client
- Backend: 26 API tests covering registration, auth, leave, permissions, modules

## Configuration

### Environment Variables
- `VITE_API_BASE_URL` - Backend API base URL (default: `http://127.0.0.1:8000`)

### Security Settings (in `config.py`)
- `SECRET_KEY` - JWT signing key
- `ALGORITHM` - JWT algorithm (HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Access token lifetime
- `REFRESH_TOKEN_EXPIRE_DAYS` - Refresh token lifetime
- `PASSWORD_RESET_EXPIRE_HOURS` - Password reset link expiry
- `TOKEN_ISSUER` / `TOKEN_AUDIENCE` - JWT claim validation
- `RATE_LIMIT_REGISTRATION` - Max registration attempts per IP
- `RATE_LIMIT_PASSWORD_RESET` - Max password reset attempts per IP

### Default Modules (seeded from `application.py`)
`ALL_MODULE_KEYS`: overview, employees, departments, organization, attendance, leave, users, payroll, recruitment, performance, learning, notifications, reports, settings, module-access

`EMPLOYEE_MODULE_KEYS`: overview, employees, attendance, leave, payroll, performance, learning, notifications, settings
