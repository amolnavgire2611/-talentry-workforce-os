from datetime import date, datetime
from decimal import Decimal
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

ROLE_NAMES = (
    "Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Department Manager",
    "Recruiter", "Payroll Administrator", "Attendance Administrator", "Employee",
)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: EmailStr
    role: str
    active: bool
    registration_pending: bool = False


class RegisterRequest(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AdminRegistrationRequest(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    setup_token: str = Field(min_length=32, max_length=256)


class UserProvisionRequest(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    role: Literal[
        "Organization Admin", "HR Administrator", "HR Manager", "Department Manager", "Recruiter",
        "Payroll Administrator", "Attendance Administrator", "Employee",
    ]
    department_id: int | None = Field(default=None, gt=0)
    employee_id: int | None = Field(default=None, gt=0)


class UserProvisionResponse(BaseModel):
    user: UserResponse
    invitation_token: str
    expires_at: datetime


class InvitationRegistrationRequest(StrictRequest):
    invitation_token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(StrictRequest):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordChangeRequest(StrictRequest):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    message: str
    access_token: str = ""
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = 0
    csrf_token: str = ""
    user: UserResponse | None = None
    mfa_required: bool = False
    mfa_session_id: str | None = None


class RefreshSessionResponse(BaseModel):
    id: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    current: bool


class EmployeeCreate(StrictRequest):
    employee_code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=100)
    department: str = Field(min_length=2, max_length=100)
    role: str = Field(min_length=2, max_length=100)
    status: Literal["Active", "On leave", "Inactive"] = "Active"
    branch_id: int | None = Field(default=None, gt=0)
    designation_id: int | None = Field(default=None, gt=0)
    job_grade_id: int | None = Field(default=None, gt=0)
    reporting_manager_id: int | None = Field(default=None, gt=0)


class EmployeeUpdate(EmployeeCreate):
    pass


class EmployeeStatusUpdate(StrictRequest):
    status: Literal["Active", "On leave", "Inactive"]


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_code: str
    name: str
    department: str
    role: str
    status: str
    user_id: int | None = None
    branch_id: int | None = None
    designation_id: int | None = None
    job_grade_id: int | None = None
    reporting_manager_id: int | None = None


class EmployeeDirectoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_code: str
    name: str
    department: str
    role: str
    status: str


class EmployeeSelfUpdate(StrictRequest):
    name: str = Field(min_length=2, max_length=100)


class EmployeeContactUpdate(StrictRequest):
    personal_email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    alternate_phone: str | None = Field(default=None, min_length=7, max_length=30)
    address_line: str | None = Field(default=None, max_length=250)
    city: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=30)
    country: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_contact_method(self):
        if not (self.personal_email or self.phone or self.alternate_phone):
            raise ValueError("At least one email address or phone number is required")
        return self


class EmployeeContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    personal_email: EmailStr | None
    phone: str | None
    alternate_phone: str | None
    address_line: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    country: str | None
    updated_at: datetime


class EmergencyContactCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    relationship: str = Field(min_length=2, max_length=60)
    phone: str = Field(min_length=7, max_length=30)
    email: EmailStr | None = None
    priority: int = Field(default=1, ge=1, le=10)


class EmergencyContactUpdate(EmergencyContactCreate):
    pass


class EmergencyContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    name: str
    relationship: str
    phone: str
    email: EmailStr | None
    priority: int
    created_at: datetime


class EmployeeEmploymentHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    effective_date: date
    department: str
    job_title: str
    branch_name: str | None
    designation_name: str | None
    grade_name: str | None
    reporting_manager_name: str | None
    employment_status: str
    notes: str | None
    created_at: datetime


class EmploymentContractCreate(StrictRequest):
    reference: str = Field(min_length=2, max_length=80)
    employment_type: Literal["Permanent", "Fixed-term", "Temporary", "Internship", "Consultant", "Other"]
    start_date: date
    end_date: date | None = None
    signed_date: date | None = None
    status: Literal["Draft", "Active", "Ended"] = "Draft"

    @model_validator(mode="after")
    def validate_contract_dates(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.status == "Ended" and self.end_date is None:
            raise ValueError("An ended contract requires an end date")
        return self


class EmploymentContractUpdate(EmploymentContractCreate):
    status: Literal["Draft", "Active", "Ended"]


class EmploymentContractResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    reference: str
    employment_type: str
    start_date: date
    end_date: date | None
    signed_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime


class DepartmentCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    active: bool = True


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    active: bool
    created_at: datetime


class BranchCreate(StrictRequest):
    code: str = Field(min_length=2, max_length=30)
    name: str = Field(min_length=2, max_length=100)
    address: str | None = Field(default=None, max_length=300)
    active: bool = True


class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    address: str | None
    active: bool
    created_at: datetime


class DesignationCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    active: bool = True


class DesignationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    active: bool
    created_at: datetime


class JobGradeCreate(StrictRequest):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    rank: int = Field(ge=1, le=1000)
    active: bool = True


class JobGradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    description: str | None
    rank: int
    active: bool
    created_at: datetime


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    active: bool
    created_at: datetime


class OrganizationMembershipResponse(BaseModel):
    id: int
    user_id: int
    name: str
    email: EmailStr
    role: str
    active: bool
    department_id: int | None
    created_at: datetime


class OrganizationUpdate(StrictRequest):
    name: str = Field(min_length=2, max_length=120)


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    work_date: date
    check_in: datetime
    check_out: datetime | None
    status: str
    note: str | None


class LeaveCreate(StrictRequest):
    start_date: date
    end_date: date
    leave_type_id: int = Field(gt=0)
    half_day: bool = False
    reason: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="after")
    def validate_date_order(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.start_date.year != self.end_date.year:
            raise ValueError("A leave request must stay within one calendar year")
        if self.half_day and self.start_date != self.end_date:
            raise ValueError("half_day requests must cover a single date")
        return self


class LeaveTypeCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    annual_allowance_days: int = Field(ge=0, le=365)
    paid: bool = True
    active: bool = True


class LeaveTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    annual_allowance_days: int
    paid: bool
    active: bool


class LeaveBalanceResponse(BaseModel):
    id: int
    leave_type_id: int
    leave_type: str
    year: int
    allocated_days: int
    used_days: Decimal
    pending_days: Decimal
    remaining_days: Decimal


class HolidayCreate(StrictRequest):
    holiday_date: date
    name: str = Field(min_length=2, max_length=100)


class HolidayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    holiday_date: date
    name: str
    active: bool


class LeaveReview(StrictRequest):
    decision: Literal["Approved", "Rejected"]
    comment: str | None = Field(default=None, max_length=1000)


class LeaveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    start_date: date
    end_date: date
    leave_type_id: int | None
    leave_type: str | None = None
    half_day: bool
    days_requested: Decimal
    reason: str
    status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_comment: str | None
    created_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class DashboardResponse(BaseModel):
    scope: Literal["organization", "department", "personal", "recruitment", "payroll", "attendance"]
    employee_count: int | None
    active_employee_count: int | None
    employees_on_leave_count: int | None
    department_count: int | None
    present_today: int
    pending_leave_requests: int
    my_pending_leave_requests: int


class UserAdminUpdate(StrictRequest):
    role: Literal[
        "Organization Admin", "HR Administrator", "HR Manager", "Department Manager", "Recruiter",
        "Payroll Administrator", "Attendance Administrator", "Employee",
    ] | None = None
    active: bool | None = None
    department_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.model_fields_set:
            raise ValueError("Provide role and/or active")
        return self


class AuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    details: dict
    created_at: datetime


# --- Module-based role permissions ---

class ModuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    module_key: str
    name: str
    description: str | None
    parent_id: int | None = None
    active: bool
    created_at: datetime


class ModuleCreate(StrictRequest):
    module_key: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    parent_id: int | None = None


class ModuleUpdate(StrictRequest):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None
    parent_id: int | None = None


class RoleModulePermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    module_id: int
    role: str
    granted: bool
    created_at: datetime


class ModuleWithPermissions(ModuleResponse):
    permissions: list[RoleModulePermissionResponse] = []


class ModulePermissionUpdate(StrictRequest):
    roles: dict[str, bool]


class MyPermissionsResponse(BaseModel):
    accessible_modules: list[str]
    modules: list[ModuleWithPermissions]


# --- Password reset ---

class ForgotPasswordRequest(StrictRequest):
    email: EmailStr


class ResetPasswordRequest(StrictRequest):
    token: str = Field(min_length=32, max_length=256)
    new_password: str = Field(min_length=8, max_length=128)


# --- MFA ---

class MFAEnrollmentRequest(StrictRequest):
    pass


class MFAVerifyRequest(StrictRequest):
    code: str = Field(min_length=6, max_length=8)
    mfa_session_id: str | None = Field(default=None, max_length=128)


class MFAFactorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    factor_type: str
    verified: bool
    created_at: datetime


class MFAEnrollmentResponse(BaseModel):
    id: int
    factor_type: str
    verified: bool
    created_at: datetime
    secret: str
    backup_codes: list[str]


# --- Payroll ---

class CompensationCreate(StrictRequest):
    employee_id: int = Field(gt=0)
    employment_type: str = Field(default="Permanent", min_length=2, max_length=40)
    base_salary: Decimal = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    pay_frequency: str = Field(default="monthly", min_length=2, max_length=20)
    effective_from: date
    effective_to: date | None = None


class CompensationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    employment_type: str
    base_salary: Decimal
    currency: str
    pay_frequency: str
    effective_from: date
    effective_to: date | None
    active: bool
    created_at: datetime


class PayrollRunCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    period_start: date
    period_end: date
    pay_date: date


class PayrollRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    period_start: date
    period_end: date
    pay_date: date
    status: str
    total_gross: Decimal
    total_deductions: Decimal
    total_net: Decimal
    employee_count: int
    created_by: int | None
    created_at: datetime
    finalized_at: datetime | None


class PayslipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    payroll_run_id: int
    employee_id: int
    employee_name: str | None
    gross_pay: Decimal
    deductions: Decimal
    net_pay: Decimal
    payslip_date: date
    status: str
    created_at: datetime


class PayrollCalculateRequest(StrictRequest):
    employee_id: int = Field(gt=0)


# --- Recruitment ---

class RequisitionCreate(StrictRequest):
    title: str = Field(min_length=2, max_length=200)
    department: str | None = Field(default=None, max_length=100)
    employment_type: str = Field(default="Permanent", min_length=2, max_length=40)


class RequisitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    department: str | None
    employment_type: str
    status: str
    created_by: int | None
    created_at: datetime
    closed_at: datetime | None


class CandidateCreate(StrictRequest):
    requisition_id: int = Field(gt=0)
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    requisition_id: int
    name: str
    email: str
    phone: str | None
    status: str
    resume_url: str | None
    applied_at: datetime


class ApplicationCreate(StrictRequest):
    candidate_id: int = Field(gt=0)
    stage: str = Field(default="Applied", min_length=2, max_length=30)
    score: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=2000)


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    candidate_id: int
    stage: str
    score: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --- Performance & Goals ---

class GoalCreate(StrictRequest):
    employee_id: int = Field(gt=0)
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="Performance", min_length=2, max_length=50)
    target_date: date | None = None


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    employee_id: int
    title: str
    description: str | None
    category: str
    status: str
    target_date: date | None
    progress: int
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class GoalUpdate(StrictRequest):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, min_length=2, max_length=50)
    status: str | None = Field(default=None, min_length=2, max_length=30)
    target_date: date | None = None
    progress: int | None = Field(default=None, ge=0, le=100)


class ReviewCycleCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    start_date: date
    end_date: date


class ReviewCycleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    start_date: date
    end_date: date
    status: str
    created_at: datetime


class PerformanceReviewCreate(StrictRequest):
    review_cycle_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)
    reviewer_id: int | None = Field(default=None, gt=0)
    overall_rating: Decimal | None = Field(default=None, ge=0, le=5)
    comments: str | None = Field(default=None, max_length=4000)


class PerformanceReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    review_cycle_id: int
    employee_id: int
    reviewer_id: int | None
    overall_rating: Decimal | None
    comments: str | None
    status: str
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PerformanceReviewSubmit(StrictRequest):
    overall_rating: Decimal = Field(ge=0, le=5)
    comments: str | None = Field(default=None, max_length=4000)


# --- Learning & Development ---

class TrainingCourseCreate(StrictRequest):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="General", min_length=2, max_length=50)
    provider: str | None = Field(default=None, max_length=120)
    duration_hours: Decimal = Field(default=Decimal("1"), ge=0, le=1000)


class TrainingCourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    category: str
    provider: str | None
    duration_hours: Decimal
    active: bool
    created_at: datetime


class TrainingEnrollmentCreate(StrictRequest):
    course_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)


class TrainingEnrollmentUpdate(StrictRequest):
    status: Literal["Enrolled", "In Progress", "Completed", "Cancelled"]
    score: Decimal | None = Field(default=None, ge=0, le=100)


class TrainingEnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int
    employee_id: int
    status: str
    score: Decimal | None
    enrolled_at: datetime
    completed_at: datetime | None


# --- Notifications & Announcements ---

class NotificationCreate(StrictRequest):
    title: str = Field(min_length=2, max_length=200)
    message: str = Field(min_length=2, max_length=4000)
    category: str = Field(default="General", min_length=2, max_length=50)
    user_id: int | None = Field(default=None, gt=0)  # None broadcasts to every active user


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    title: str
    message: str
    category: str
    read: bool
    created_at: datetime


class AnnouncementCreate(StrictRequest):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=2, max_length=8000)
    pinned: bool = False
    expires_at: datetime | None = None


class AnnouncementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    body: str
    pinned: bool
    created_by: int | None
    created_at: datetime
    expires_at: datetime | None
