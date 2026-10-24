talentry-workforce-os

talentry-workforce-os is a workforce management application built with React, TypeScript, Vite, FastAPI, SQLAlchemy, and Alembic.

The project provides a functional foundation for workforce operations, including authentication, role-based access control, employee and department management, attendance tracking, leave management, account administration, and database-backed dashboard summaries.

The current objective is to evolve the existing application into a secure, reliable, maintainable, and production-ready workforce management platform by auditing existing modules, identifying real business limitations, improving incomplete workflows, and validating changes through automated testing.

Important: This repository is an existing application, not a greenfield project. Improvements must preserve working functionality, existing data, established security controls, and backward compatibility wherever practical.

Table of Contents
Project Overview
Technology Stack
Current Implementation
Prerequisites
Quick Start
Backend Setup
Frontend Setup
Authentication and Initial Administration
Environment Configuration
Database and Migrations
Testing and Quality Checks
Architecture and Security
Implemented Scope and Known Limitations
Production Readiness Roadmap
Production Engineering Requirements
AI-Assisted Development Guidelines
Documentation and Audit Artifacts
Deployment Considerations
Contributing and Development Workflow
License
Project Overview

The goal of talentry-workforce-os is to provide a centralized platform for managing employee information and core workforce processes.

The application currently supports the following operational areas:

Authentication and account lifecycle management.
Employee and department administration.
Role-based authorization.
Employee attendance and attendance history.
Leave requests, approvals, and balance management.
Administrative account management.
Database-backed dashboard summaries.
Audit records for implemented sensitive operations.

The long-term goal is to improve these capabilities into complete, integrated business workflows with configurable organizational policies, reliable data integrity, secure access, comprehensive testing, and operational monitoring.

The application must not advertise an incomplete capability as operational or production-ready.

Technology Stack
Component	Technology
Frontend	React, TypeScript, Vite
Backend	Python, FastAPI
ORM	SQLAlchemy
Database migrations	Alembic
Development database	SQLite
Potential production database	PostgreSQL
Authentication	JWT access tokens and rotating refresh sessions
Session storage	Browser sessionStorage for access tokens; HttpOnly cookies for refresh credentials
Backend testing	Pytest
Frontend testing	Existing project test runner and unit tests
Code quality	ESLint, TypeScript checks, production build

Refer to the installed dependency files and project configuration for exact package versions and supported runtime requirements.

Current Implementation

The current implementation includes:

Token-backed sign-in and authentication.
Employee registration.
Guarded first-Super-Admin registration.
Invitation-based registration for role-specific accounts.
Protected employee and department management.
Role- and department-scoped authorization.
Persistent attendance check-in and check-out.
Leave categories, annual allocations, and leave requests.
Leave approval and balance-ledger operations.
Administrative account and session management.
Database-backed dashboard summaries.
Explicit Alembic migrations.
Automated backend and frontend tests.

These features must be inspected and verified against the actual source code before any changes are made.

Prerequisites

Install the following software before starting development:

Python 3.12 or later.
Node.js 20.19+ or 22.12+, compatible with the installed Vite version.
npm.
Git.
A supported operating system and terminal.
SQLite for local development, or PostgreSQL for a configured deployment.

Confirm the installed versions:

python --version
node --version
npm --version
git --version

Quick Start
1. Clone or open the repository

If cloning from a remote repository:

git clone <repository-url>
cd talentry-workforce-os


If the repository is already available locally, open its root directory directly.

2. Set up the backend
cd backend

python -m venv .venv


Activate the virtual environment.

Linux or macOS:

source .venv/bin/activate


Windows PowerShell:

.venv\Scripts\Activate.ps1


Install dependencies:

pip install -r requirements.txt


Create the local environment file:

cp .env.example .env


On Windows, copy .env.example to .env using your preferred terminal or file manager.

Configure the required secrets and settings in backend/.env before running the application.

Back up any existing database before applying migrations.

Apply database migrations:

alembic upgrade head


Start the development API server:

uvicorn main:app --reload


The backend should be available at:

API base URL: http://127.0.0.1:8000
Interactive API documentation: http://127.0.0.1:8000/docs
Health endpoint: http://127.0.0.1:8000/health

Interactive API documentation should be restricted or disabled appropriately in production.

3. Set up the frontend

Open a second terminal:

cd frontend
npm ci
npm run dev


Use the local URL printed by Vite to access the application.

The default API origin is:

http://127.0.0.1:8000


To configure another API origin, create or update the frontend .env file:

VITE_API_BASE_URL=http://127.0.0.1:8000


Configure the matching frontend origin in the backend's CORS_ORIGINS setting.

Only trusted origins should be allowed. Never use a permissive CORS configuration as a shortcut for deployment.

Authentication and Initial Administration
Employee registration

The sign-in screen supports registration of a standard Employee account.

Registration must not grant administrative privileges.

First Super Admin

The first Super Admin can be created through the guarded administrator registration workflow.

Configure a private random bootstrap token of at least 32 characters in backend/.env:

ADMIN_BOOTSTRAP_TOKEN=<private-random-token>


Restart the backend after changing environment settings.

The Create administrator option is available only while the database has no Super Admin record.

After successfully creating the initial administrator:

Remove the bootstrap token from the active environment.
Restart or redeploy the application as appropriate.
Store deployment secrets securely.
Verify that the initial administrator has the expected permissions.

The trusted-terminal bootstrap command remains available:

python -m bootstrap_admin


Use it according to the implementation and instructions in the backend documentation.

Invitations and account management

Administrators can issue one-time invitations for role-specific accounts through the Access & users screen.

The system supports account/session administration, including session revocation and account-related security controls.

Invitation expiry, rate limiting, password recovery, MFA, and other advanced identity capabilities must be verified against the actual implementation before being treated as supported.

Environment Configuration

The backend configuration is documented in:

backend/README.md
backend/.env.example

The frontend configuration uses its own .env file.

Common settings include:

Setting	Purpose
NEXORA_SECRET_KEY	Existing backend signing-secret variable. Keep the variable name until a deliberate, compatible configuration migration is implemented.
APP_ENV	Environment mode, including production safeguards.
CORS_ORIGINS	Explicitly permitted browser origins.
DATABASE_URL	SQLAlchemy database connection URL.
ADMIN_BOOTSTRAP_TOKEN	Temporary token for guarded first-Super-Admin registration.
EMPLOYEE_DIRECTORY_ENABLED	Controls the optional employee directory.
VITE_API_BASE_URL	Frontend API origin.

Use the exact variable names, formats, and defaults supported by the checked-in application configuration.

Never commit secrets, credentials, private keys, production database files, or real employee data to version control.

Although the application name is changing to talentry-workforce-os, existing environment variable names must not be renamed blindly. Any future renaming must account for deployment configuration, existing installations, and backward compatibility.

Database and Migrations
Development database

SQLite is the default development database.

The existing database may contain user and employee records. Review the database configuration before running migration commands.

Apply schema changes explicitly:

cd backend
alembic upgrade head


Application startup must not automatically create, reset, or destructively modify the database schema.

PostgreSQL

PostgreSQL may be configured using a compatible SQLAlchemy database URL and an installed PostgreSQL driver.

Before adopting PostgreSQL for production:

Verify the installed driver and connection settings.
Validate all Alembic migrations against PostgreSQL.
Review SQL types, constraints, indexes, and transaction behavior.
Test concurrent updates and locking behavior.
Validate backup and restore procedures.
Test the application using a staging database.
Confirm that migrations preserve existing records.
Migration safety

All database changes must follow these rules:

Back up the database before risky changes.
Review migrations before execution.
Preserve existing employee and user records.
Reconcile legacy data before introducing new constraints.
Use explicit migrations rather than automatic schema resets.
Test upgrades against representative legacy data.
Document recovery procedures for failed migrations.
Avoid destructive downgrade operations where they could remove valuable data.

The initial migration strategy is designed to preserve legacy records. Review the actual migration history before making further schema changes.

Employee and department relationships

Employee records currently use a department-name string rather than a relational department foreign key.

A future improvement may introduce a relational department association, but this requires:

Identifying inconsistent and duplicate department names.
Mapping existing employee records to the correct department IDs.
Handling missing or archived departments.
Preserving historical employment information.
Migrating existing records safely.
Updating APIs and frontend forms.
Testing the migration and dependent workflows.

Do not remove the existing department-name field or modify historical data until a compatible migration strategy has been reviewed and tested.

Testing and Quality Checks

Run the existing automated checks before and after significant changes.

Backend tests
cd backend
pytest -q


The existing test suite uses temporary SQLite databases.

Migration coverage includes upgrading a synthetic legacy database and checking that legacy users and employees remain intact.

Frontend tests
cd frontend
npm test

Linting
cd frontend
npm run lint

Production build
cd frontend
npm run build

Additional verification

Where the relevant tooling and tests are available, also run:

Python static analysis and formatting checks.
TypeScript type checking.
API integration tests.
Browser-based end-to-end tests.
Authorization and cross-user access tests.
Database migration tests.
Concurrency tests for critical business operations.
Accessibility checks.
Performance and load tests.
Dependency and security scans.
Deployment smoke tests.

Record the commands executed and their actual results.

Do not report a successful test run if the command was not executed. Distinguish pre-existing failures from regressions introduced by new changes.

Architecture and Security
Authentication

The current authentication design includes:

Short-lived JWT access tokens.
Issuer and audience validation.
Rotating refresh sessions.
Server-side hashed refresh credentials.
HttpOnly, SameSite refresh cookies.
CSRF token and allowed-origin checks for refresh/logout.
Session inventory and revocation.
Active-account checks.
Refresh-session revocation after password changes and account deactivation.

Access tokens are held in browser sessionStorage.

Any successful same-origin script execution may access browser-readable state. Apply a strict Content Security Policy, avoid unsafe HTML, validate user-generated content, and keep dependencies updated.

Authorization

Authorization is enforced on the backend.

The current policy includes:

Employee users accessing their own permitted profile, attendance, and leave records.
HR-authorized employee and department management.
Department Managers being restricted to their assigned department.
Super Admin being responsible for role assignment.
Server-side checks for administrative operations.

Verify these boundaries at the API level, not only in the frontend.

Tests should cover direct requests using another employee's identifier, department reassignment, privilege escalation, unauthorized approvals, and access to sensitive records.

Data protection

The application must:

Avoid logging passwords, tokens, and sensitive employee information.
Restrict access to employee and compensation data.
Protect secrets and database files.
Use HTTPS in deployed environments.
Apply strict CORS and appropriate request limits.
Maintain audit records for sensitive actions.
Preserve historical records where required.
Apply applicable privacy and employment requirements.
Files and email

File uploads, document storage, and outbound email are not currently implemented.

Do not display these capabilities as operational until storage, access controls, validation, delivery, retry behavior, and appropriate tests have been implemented.

Implemented Scope and Known Limitations

The following table summarizes the documented implementation. Actual behavior must be verified against the repository.

Module	Current status	Known limitations
Authentication	Implemented	Password reset and MFA are not implemented.
Account administration	Implemented	Advanced identity and account lifecycle capabilities require further assessment.
Authorization	Implemented	Existing role and department boundaries require ongoing regression and security testing.
Employees	Implemented	Employee history and department relationships need further refinement.
Departments	Implemented	Department lifecycle and relational integrity require continued review.
Attendance	Implemented	Configurable shifts, breaks, holidays, correction approvals, and timezone policies are missing.
Leave management	Implemented	Carry-forward, automatic accrual, proration, multi-stage approval, and notifications are missing.
Dashboard	Implemented	Historical trends and advanced analytics are not available.
Audit logging	Partially implemented	Coverage must be reviewed for all sensitive operations and change histories.
Recruitment	Not implemented	Candidate management and hiring workflows are not available.
Onboarding/offboarding	Not implemented	Employee lifecycle checklists and separation workflows are not available.
Payroll	Not implemented	Payroll calculations, payslips, statutory calculations, and payment integrations are not available.
Performance management	Not implemented	Goals, review cycles, and appraisal workflows are not available.
Notifications	Not implemented	Email and other notification delivery workflows are not available.
File/document management	Not implemented	Secure uploads, storage, and document expiry tracking are not available.
Reports and exports	Not implemented	Advanced reporting and data export capabilities are not available.
Organization settings	Not implemented	Centralized configurable policy management is not available.
Integrations	Not implemented	External HR, payroll, and related integrations are not available.
Important operational limitations
EMPLOYEE_DIRECTORY_ENABLED=false by default. When enabled, employee users see only active employees' name, employee code, department, designation, and status.
Full employee records remain restricted to authorized HR roles.
Permanent employee removal may be inappropriate when historical attendance, leave, or employment records must be preserved.
No tax, bank transfer, statutory payroll, or external HR integrations are currently claimed.
Full browser end-to-end testing, accessibility auditing, production deployment testing, and load/security testing remain outstanding according to the existing project documentation.

Do not use the application to make payroll, employment, compliance, or performance decisions until the corresponding business rules and capabilities have been implemented and reviewed for the deployment jurisdiction.

Production Readiness Roadmap

Improvements must be prioritized using evidence from the existing repository.

Phase 1: Repository audit

Inspect:

Frontend pages, routes, and components.
Backend endpoints, business logic, and data models.
Authentication and authorization.
Database relationships and migration history.
Existing tests and build configuration.
Error handling, audit logging, and deployment settings.

Produce a module inventory and document confirmed defects, verified limitations, potential risks, and unresolved business requirements.

Phase 2: Security and data integrity

Prioritize:

Authentication and session lifecycle verification.
Role and department access enforcement.
Cross-user data isolation.
Employee and department relationship integrity.
Safe migrations and preservation of existing records.
Transaction safety for critical operations.
Audit coverage for sensitive changes.
Phase 3: Core HR workflow improvements

Improve the existing employee, attendance, leave, and department modules.

Examples include:

Employment lifecycle tracking.
Configurable attendance policies.
Attendance regularization and approval.
Advanced leave accrual and carry-forward.
Effective-dated organizational changes.
Historical records and correction workflows.
Manager delegation and approval handling where required.

Business rules must be defined before implementation. Do not assume that every organization follows the same HR policies.

Phase 4: Cross-module integration

Verify that employee, department, attendance, leave, account, and dashboard functionality remains consistent when data changes.

Test complete workflows rather than isolated pages or endpoints.

Phase 5: Additional HR capabilities

Evaluate future modules according to business needs:

Onboarding and offboarding.
Document management.
Notifications and reminders.
Recruitment and applicant tracking.
Payroll preparation and approvals.
Performance management.
Reports, exports, and analytics.
Configurable organization policies.
External integrations.

These are future candidates, not currently implemented features.

Phase 6: Production validation

Complete appropriate:

Automated integration and regression tests.
Browser-based end-to-end testing.
Security and authorization testing.
Migration and recovery validation.
Performance testing.
Accessibility checks.
Deployment and rollback exercises.
Backup and restore testing.
Operational monitoring and incident-response planning.

A production release must be based on explicit acceptance criteria and verification evidence.

Production Engineering Requirements
Code quality
Follow existing project conventions.
Keep business logic out of presentation components.
Avoid unnecessary rewrites and duplicate implementations.
Maintain type-safe API contracts.
Use clear error handling and validation.
Document important architectural decisions.
API design
Validate input on the backend.
Apply authorization to every protected operation.
Return consistent error responses.
Use appropriate HTTP status codes.
Implement pagination for potentially large collections.
Prevent duplicate and conflicting state transitions.
Document API changes and compatibility requirements.
Database reliability
Use transactions for related business updates.
Enforce unique and relational constraints where appropriate.
Prevent inconsistent concurrent balance or approval updates.
Preserve history and auditability.
Validate migrations against existing data.
Maintain verified backups and recovery procedures.
User experience
Display real persisted data.
Provide clear loading, empty, success, and error states.
Avoid fake success messages.
Prevent accidental duplicate submissions.
Support accessible forms and responsive layouts.
Ensure that visible actions are backed by functioning, authorized operations.
Operational readiness
Use environment-based configuration.
Store secrets securely.
Use HTTPS and restrictive CORS settings.
Configure structured logs and health checks.
Monitor errors and critical background tasks.
Document deployment, backup, recovery, and rollback procedures.
Verify production dependencies and database compatibility.
AI-Assisted Development Guidelines

AI coding tools working on this repository must follow a controlled, evidence-based workflow.

Mandatory workflow
Inspect the existing code before changing it.
Establish a baseline by running available tests and quality checks.
Audit all implemented modules.
Identify limitations with supporting code references or reproducible evidence.
Prioritize findings by security, data integrity, business impact, and dependencies.
Define expected behavior and acceptance criteria.
Implement small, coherent changes.
Add automated tests for the changes.
Run relevant regression checks.
Update documentation and report remaining limitations.
Prohibited practices
Rebuilding the application without justification.
Replacing real business logic with mock data.
Adding placeholder modules and fake integrations.
Bypassing authentication or authorization.
Removing existing records or migrations without an approved plan.
Introducing unsupported HR or statutory policies.
Claiming unexecuted tests have passed.
Claiming production readiness without evidence.
Silently skipping difficult workflows or edge cases.
Definition of done

A change is complete when:

Its business requirements are defined.
Server-side validation and authorization are implemented.
Data integrity is preserved.
The frontend reflects the actual persisted state.
Relevant error cases are handled.
Automated tests cover the behavior.
Regression checks have been executed.
Documentation has been updated.
Remaining risks are recorded.
Documentation and Audit Artifacts

Maintain these documents in the repository root or an appropriate documentation directory:

Document	Purpose
TALENTRY_SYSTEM_INVENTORY.md	Architecture, technology stack, modules, and dependencies.
TALENTRY_PRODUCTION_AUDIT.md	Evidence-backed defects, limitations, risks, and unresolved requirements.
TALENTRY_IMPLEMENTATION_BACKLOG.md	Prioritized tasks, dependencies, and acceptance criteria.
TALENTRY_CHANGELOG.md	Implemented changes, migrations, and behavior changes.
TALENTRY_TEST_REPORT.md	Commands executed, test results, and outstanding failures.
TALENTRY_PRODUCTION_READINESS.md	Deployment requirements, outstanding risks, and release assessment.

Update these documents as work progresses.

Do not mark a finding as fixed until the relevant implementation and verification have been completed.

Deployment Considerations

Before deploying to production:

Configure a private random NEXORA_SECRET_KEY of at least 32 characters.
Set APP_ENV=production and verify the production safeguards.
Configure exact trusted frontend origins in CORS_ORIGINS.
Use HTTPS and secure cookie settings.
Review API documentation exposure.
Configure and verify the production database.
Apply migrations deliberately after backup and staging validation.
Configure restricted file and database access.
Establish routine backups and test restoration.
Review dependency security and update procedures.
Validate authorization and session revocation.
Configure monitoring and error reporting.
Test critical employee, attendance, and leave workflows.
Document rollback and incident-response procedures.

The existing NEXORA_SECRET_KEY variable is intentionally retained in this README because environment variable names are part of the current application's configuration contract. A project branding change does not automatically require renaming internal configuration keys.

Do not deploy until the required controls have been verified for the actual environment.

Contributing and Development Workflow

When working on this project:

Review the README and relevant module documentation.
Understand the existing architecture before changing it.
Keep changes focused and testable.
Add tests for new business behavior and regression risks.
Review database migrations before applying them.
Run relevant backend and frontend checks.
Update documentation to reflect actual behavior.
Document known limitations and follow-up tasks.

Use synthetic data in tests. Never expose real employee information, credentials, or secrets in code, test fixtures, issue reports, or logs.

License

No license is specified in this README. Add the appropriate license information once the project's licensing terms have been established.

Project: talentry-workforce-os

Current status: Functional workforce management foundation with documented implementation gaps.

Long-term objective: Build a secure, integrated, reliable, and maintainable workforce management platform by systematically improving existing functionality, implementing verified business requirements, and validating production readiness through evidence and testing.