
from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import relationship
from database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    slug = Column(String(80), nullable=False, unique=True, index=True)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class TenantScoped:
    """Mixin for records that must remain inside one organization."""

    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)


class User(TenantScoped, Base):
    __tablename__ = "users"
    __table_args__ = (Index("uq_users_email_normalized", text("lower(email)"), unique=True),)

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False, default="Employee", server_default="Employee")
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    invitation = relationship("Invitation", back_populates="user", uselist=False, cascade="all, delete-orphan")

    @property
    def registration_pending(self):
        return bool(not self.active and self.invitation is not None and self.invitation.accepted_at is None)


class OrganizationMembership(TenantScoped, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_memberships_org_user"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(30), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Employee(TenantScoped, Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("organization_id", "employee_code", name="uq_employees_org_employee_code"),)

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(20), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    role = Column(String(100), nullable=False)
    status = Column(String(20), default="Active", nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    designation_id = Column(Integer, ForeignKey("designations.id", ondelete="SET NULL"), nullable=True, index=True)
    job_grade_id = Column(Integer, ForeignKey("job_grades.id", ondelete="SET NULL"), nullable=True, index=True)
    reporting_manager_id = Column(Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True, index=True)


class EmployeeContact(TenantScoped, Base):
    __tablename__ = "employee_contacts"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    personal_email = Column(String(255), nullable=True)
    phone = Column(String(30), nullable=True)
    alternate_phone = Column(String(30), nullable=True)
    address_line = Column(String(250), nullable=True)
    city = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    postal_code = Column(String(30), nullable=True)
    country = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class EmergencyContact(TenantScoped, Base):
    __tablename__ = "emergency_contacts"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    relationship = Column(String(60), nullable=False)
    phone = Column(String(30), nullable=False)
    email = Column(String(255), nullable=True)
    priority = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class EmployeeEmploymentHistory(TenantScoped, Base):
    """Append-only snapshots created by employee hire, assignment and status changes."""

    __tablename__ = "employee_employment_history"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(30), nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    department = Column(String(100), nullable=False)
    job_title = Column(String(100), nullable=False)
    branch_name = Column(String(100), nullable=True)
    designation_name = Column(String(100), nullable=True)
    grade_name = Column(String(100), nullable=True)
    reporting_manager_name = Column(String(100), nullable=True)
    employment_status = Column(String(20), nullable=False)
    notes = Column(String(500), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class EmploymentContract(TenantScoped, Base):
    __tablename__ = "employment_contracts"
    __table_args__ = (
        UniqueConstraint("organization_id", "employee_id", "reference", name="uq_contracts_org_employee_reference"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_contracts_end_after_start"),
    )

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    reference = Column(String(80), nullable=False)
    employment_type = Column(String(30), nullable=False)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=True)
    signed_date = Column(Date, nullable=True)
    status = Column(String(16), nullable=False, default="Draft", server_default="Draft", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class Department(TenantScoped, Base):
    __tablename__ = "departments"
    __table_args__ = (Index(
        "uq_departments_org_name_normalized", "organization_id", text("lower(name)"), unique=True,
    ),)

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Branch(TenantScoped, Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_branches_org_code"),
        Index("uq_branches_org_name_normalized", "organization_id", text("lower(name)"), unique=True),
    )

    id = Column(Integer, primary_key=True)
    code = Column(String(30), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    address = Column(String(300), nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Designation(TenantScoped, Base):
    __tablename__ = "designations"
    __table_args__ = (Index(
        "uq_designations_org_name_normalized", "organization_id", text("lower(name)"), unique=True,
    ),)

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class JobGrade(TenantScoped, Base):
    __tablename__ = "job_grades"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_job_grades_org_code"),
        Index("uq_job_grades_org_name_normalized", "organization_id", text("lower(name)"), unique=True),
    )

    id = Column(Integer, primary_key=True)
    code = Column(String(30), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    rank = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Invitation(TenantScoped, Base):
    __tablename__ = "invitations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    user = relationship("User", back_populates="invitation")


class RevokedToken(TenantScoped, Base):
    __tablename__ = "revoked_tokens"

    jti = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class RefreshSession(TenantScoped, Base):
    __tablename__ = "refresh_sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_refresh_sessions_token_hash"),)

    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    csrf_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)


class Attendance(TenantScoped, Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("user_id", "work_date", name="uq_attendance_user_date"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    check_in = Column(DateTime(timezone=True), nullable=False)
    check_out = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="Present", server_default="Present")
    note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class LeaveRequest(TenantScoped, Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="RESTRICT"), nullable=True)
    half_day = Column(Boolean, nullable=False, default=False, server_default="0")
    days_requested = Column(Numeric(7, 2), nullable=False, default=1, server_default="1")
    reason = Column(String(1000), nullable=False)
    status = Column(String(20), nullable=False, default="Pending", server_default="Pending", index=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_comment = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class LeaveType(TenantScoped, Base):
    __tablename__ = "leave_types"
    __table_args__ = (Index(
        "uq_leave_types_org_name_normalized", "organization_id", text("lower(name)"), unique=True,
    ),)

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    annual_allowance_days = Column(Integer, nullable=False)
    paid = Column(Boolean, nullable=False, default=True, server_default="1")
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class LeaveBalance(TenantScoped, Base):
    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint("user_id", "leave_type_id", "year", name="uq_leave_balance_user_type_year"),
        CheckConstraint("allocated_days >= 0 AND used_days >= 0 AND used_days <= allocated_days", name="ck_leave_balance_range"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id", ondelete="RESTRICT"), nullable=False)
    year = Column(Integer, nullable=False, index=True)
    allocated_days = Column(Integer, nullable=False)
    used_days = Column(Numeric(7, 2), nullable=False, default=0, server_default="0")
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class Holiday(TenantScoped, Base):
    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("organization_id", "holiday_date", name="uq_holidays_org_date"),)

    id = Column(Integer, primary_key=True)
    holiday_date = Column(Date, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    active = Column(Boolean, nullable=False, default=True, server_default="1")


class Compensation(TenantScoped, Base):
    __tablename__ = "compensation"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    employment_type = Column(String(40), nullable=False, default="Permanent")
    base_salary = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    pay_frequency = Column(String(20), nullable=False, default="monthly")
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class PayrollRun(TenantScoped, Base):
    __tablename__ = "payroll_runs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="Draft", index=True)  # Draft, Calculated, Finalized, Paid
    total_gross = Column(Numeric(14, 2), nullable=False, default=0)
    total_deductions = Column(Numeric(14, 2), nullable=False, default=0)
    total_net = Column(Numeric(14, 2), nullable=False, default=0)
    employee_count = Column(Integer, nullable=False, default=0)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    finalized_at = Column(DateTime(timezone=True), nullable=True)


class Payslip(TenantScoped, Base):
    __tablename__ = "payslips"

    id = Column(Integer, primary_key=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    gross_pay = Column(Numeric(12, 2), nullable=False, default=0)
    deductions = Column(Numeric(12, 2), nullable=False, default=0)
    net_pay = Column(Numeric(12, 2), nullable=False, default=0)
    payslip_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="Draft", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class PasswordReset(TenantScoped, Base):
    __tablename__ = "password_resets"
    __table_args__ = (
        Index("uq_password_resets_email_active", "organization_id", text("lower(email)"),
              unique=True, postgresql_where=text("used_at IS NULL AND consumed_at IS NULL")),
    )

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class MFAFactor(TenantScoped, Base):
    __tablename__ = "mfa_factors"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    factor_type = Column(String(20), nullable=False, default="totp")  # totp
    secret = Column(String(255), nullable=False)
    verified = Column(Boolean, nullable=False, default=False, server_default="0")
    backup_codes = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class Requisition(TenantScoped, Base):
    __tablename__ = "requisitions"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    department = Column(String(100), nullable=True)
    employment_type = Column(String(40), nullable=False, default="Permanent")
    status = Column(String(20), nullable=False, default="Open", index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    closed_at = Column(DateTime(timezone=True), nullable=True)


class Candidate(TenantScoped, Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True)
    requisition_id = Column(Integer, ForeignKey("requisitions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    status = Column(String(30), nullable=False, default="Applied", index=True)
    resume_url = Column(String(500), nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Application(TenantScoped, Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    stage = Column(String(30), nullable=False, default="Applied")
    score = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class AuditLog(TenantScoped, Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(64), nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True)


class Goal(TenantScoped, Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="Performance")  # Performance, Development, Sales, etc.
    status = Column(String(30), nullable=False, default="Active", index=True)  # Active, Completed, Cancelled
    target_date = Column(Date, nullable=True)
    progress = Column(Integer, nullable=False, default=0)  # 0-100
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class ReviewCycle(TenantScoped, Base):
    __tablename__ = "review_cycles"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(String(30), nullable=False, default="Planned", index=True)  # Planned, Active, Completed
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class PerformanceReview(TenantScoped, Base):
    __tablename__ = "performance_reviews"

    id = Column(Integer, primary_key=True)
    review_cycle_id = Column(Integer, ForeignKey("review_cycles.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    overall_rating = Column(Numeric(3, 2), nullable=True)  # 0.00-5.00
    comments = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="Pending", index=True)  # Pending, Submitted, Finalized
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=func.now())


class TrainingCourse(TenantScoped, Base):
    __tablename__ = "training_courses"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False, default="General")
    provider = Column(String(120), nullable=True)
    duration_hours = Column(Numeric(6, 1), nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class TrainingEnrollment(TenantScoped, Base):
    __tablename__ = "training_enrollments"
    __table_args__ = (UniqueConstraint("organization_id", "course_id", "employee_id", name="uq_training_enrollments_org_course_employee"),)

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="Enrolled", index=True)  # Enrolled, In Progress, Completed, Cancelled
    score = Column(Numeric(5, 2), nullable=True)
    enrolled_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    completed_at = Column(DateTime(timezone=True), nullable=True)


class Notification(TenantScoped, Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String(50), nullable=False, default="General")  # General, Leave, Payroll, Performance, Learning, Announcement
    read = Column(Boolean, nullable=False, default=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class Announcement(TenantScoped, Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    pinned = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    expires_at = Column(DateTime(timezone=True), nullable=True)


# --- Module-based role permissions ---

class Module(TenantScoped, Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True, index=True)
    module_key = Column(String(60), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("organization_id", "module_key", name="uq_modules_org_module_key"),
    )


class RoleModulePermission(TenantScoped, Base):
    __tablename__ = "role_module_permissions"

    id = Column(Integer, primary_key=True, index=True)
    module_id = Column(Integer, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(30), nullable=False, index=True)
    granted = Column(Boolean, nullable=False, default=True, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        UniqueConstraint("organization_id", "module_id", "role", name="uq_role_module_permissions_org_module_role"),
    )
