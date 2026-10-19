import base64
import csv
import hashlib
import hmac
import io
import logging
import secrets
import struct
import time
from collections import defaultdict, deque
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import event, func, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload, sessionmaker, with_loader_criteria
from sqlalchemy.orm.attributes import set_committed_value

import models
from config import settings
from database import make_engine
from schemas import (
    AdminRegistrationRequest, AttendanceResponse, AuthResponse, AuditResponse, DashboardResponse,
    DepartmentCreate, DepartmentResponse, EmployeeCreate, EmployeeResponse,
    EmployeeStatusUpdate, EmployeeUpdate, LeaveCreate, LeaveResponse,
    LeaveReview, LoginRequest, Page, RegisterRequest, UserAdminUpdate,
    UserResponse, PasswordChangeRequest, UserProvisionRequest,
    UserProvisionResponse, EmployeeDirectoryResponse, RefreshSessionResponse,
    EmployeeSelfUpdate, LeaveTypeCreate, LeaveTypeResponse, LeaveBalanceResponse,
    HolidayCreate, HolidayResponse, InvitationRegistrationRequest,
    OrganizationResponse, OrganizationUpdate,
    OrganizationMembershipResponse,
    BranchCreate, BranchResponse, DesignationCreate, DesignationResponse,
    JobGradeCreate, JobGradeResponse,
    EmployeeContactUpdate, EmployeeContactResponse, EmergencyContactCreate, EmergencyContactUpdate,
    EmergencyContactResponse, EmployeeEmploymentHistoryResponse, EmploymentContractCreate,
    EmploymentContractUpdate, EmploymentContractResponse,
    ForgotPasswordRequest, ResetPasswordRequest,
    MFAEnrollmentRequest, MFAVerifyRequest, MFAFactorResponse, MFAEnrollmentResponse,
    CompensationCreate, CompensationResponse,
    PayrollRunCreate, PayrollRunResponse,
    PayslipResponse, PayrollCalculateRequest,
    RequisitionCreate, RequisitionResponse,
    CandidateCreate, CandidateResponse,
    ApplicationCreate, ApplicationResponse,
    GoalCreate, GoalResponse, GoalUpdate,
    ReviewCycleCreate, ReviewCycleResponse,
    PerformanceReviewCreate, PerformanceReviewResponse, PerformanceReviewSubmit,
    TrainingCourseCreate, TrainingCourseResponse,
    TrainingEnrollmentCreate, TrainingEnrollmentUpdate, TrainingEnrollmentResponse,
    NotificationCreate, NotificationResponse,
    AnnouncementCreate, AnnouncementResponse,
    ModuleResponse, RoleModulePermissionResponse,
    ModuleWithPermissions, ModulePermissionUpdate,
    MyPermissionsResponse,
)
from security import create_access_token, hash_password, verify_access_token, verify_password

# Department-level access is intentionally not granted until employee-to-user
# department scope is modeled; this prevents an unscoped manager role bypass.
PLATFORM_ADMINS = {"Super Admin"}
HR_MANAGERS = {"Super Admin", "HR Administrator", "HR Manager"}
EMPLOYEE_READERS = HR_MANAGERS | {"Department Manager", "Organization Admin"}
ATTENDANCE_READERS = HR_MANAGERS | {"Department Manager", "Attendance Administrator"}
USER_ADMINISTRATORS = {"Super Admin", "HR Administrator", "Organization Admin"}
ORGANIZATION_STRUCTURE_ADMINISTRATORS = {"Super Admin", "Organization Admin", "HR Administrator", "HR Manager"}
ORGANIZATION_ADMIN_MANAGED_ROLES = {"Employee", "Department Manager", "Recruiter", "Attendance Administrator"}
ALL_ROLES = {
    "Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Department Manager",
    "Recruiter", "Payroll Administrator", "Attendance Administrator", "Employee",
}
logger = logging.getLogger("nexora.api")
bearer_scheme = HTTPBearer(auto_error=False)
login_attempts: dict[str, deque[float]] = defaultdict(deque)


@event.listens_for(Session, "do_orm_execute")
def enforce_organization_scope(execute_state):
    """Automatically constrain ORM reads and bulk writes after authentication."""
    organization_id = execute_state.session.info.get("organization_id")
    if organization_id is None or not (execute_state.is_select or execute_state.is_update or execute_state.is_delete):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            models.TenantScoped,
            lambda scoped: scoped.organization_id == organization_id,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def assign_and_validate_organization(session, _flush_context, _instances):
    organization_id = session.info.get("organization_id")
    for record in session.new.union(session.dirty):
        if not isinstance(record, models.TenantScoped):
            continue
        if organization_id is None:
            raise ValueError("Organization context is required for tenant records")
        if record.organization_id is None:
            record.organization_id = organization_id
        elif record.organization_id != organization_id:
            raise ValueError("Tenant records cannot be written across organizations")


def create_app(database_url: str | None = None, secret_key: str | None = None,
               employee_directory_enabled: bool | None = None,
               admin_bootstrap_token: str | None = None) -> FastAPI:
    engine = make_engine(database_url)

    @asynccontextmanager
    async def lifespan(_app):
        yield
        engine.dispose()

    app = FastAPI(title="Nexora Workforce API", version="1.0.0", lifespan=lifespan)
    app.state.engine = engine
    app.state.session_factory = sessionmaker(autocommit=False, autoflush=False, bind=app.state.engine)
    app.state.secret_key = secret_key or settings.secret_key
    app.state.admin_bootstrap_token = admin_bootstrap_token if admin_bootstrap_token is not None else settings.admin_bootstrap_token
    app.state.token_minutes = settings.access_token_minutes
    app.state.refresh_session_days = settings.refresh_session_days
    app.state.secure_cookies = settings.secure_cookies
    app.state.allowed_origins = {origin.rstrip("/") for origin in settings.cors_origins}
    app.state.employee_directory_enabled = (
        settings.employee_directory_enabled if employee_directory_enabled is None else employee_directory_enabled
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

    def get_db():
        db = app.state.session_factory()
        try:
            yield db
        finally:
            db.close()

    def utc_datetime(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    def activate_organization(db: Session, organization_id: int):
        current_id = db.info.get("organization_id")
        if current_id is not None and current_id != organization_id:
            raise HTTPException(401, "Session organization does not match this account")
        organization = db.get(models.Organization, organization_id)
        if organization is None or not organization.active:
            raise HTTPException(401, "Account organization is unavailable")
        db.info["organization_id"] = organization_id
        return organization

    def activate_membership(db: Session, user: models.User):
        organization = activate_organization(db, user.organization_id)
        membership = db.query(models.OrganizationMembership).filter_by(
            organization_id=organization.id, user_id=user.id, active=True,
        ).first()
        if membership is None:
            raise HTTPException(401, "Account has no active membership in this organization")
        # Membership is the authorization source; update the ORM identity without
        # changing the legacy user row as a side effect of another transaction.
        set_committed_value(user, "role", membership.role)
        set_committed_value(user, "department_id", membership.department_id)
        return membership

    def default_organization(db: Session):
        organizations = db.query(models.Organization).filter_by(active=True).order_by(models.Organization.id).limit(2).all()
        if len(organizations) != 1:
            raise HTTPException(503, "Registration is unavailable until one active organization is configured")
        return activate_organization(db, organizations[0].id)

    def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
                     db: Session = Depends(get_db)) -> models.User:
        if credentials is None:
            raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
        payload = verify_access_token(credentials.credentials, app.state.secret_key)
        if payload is None:
            raise HTTPException(401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})
        if not payload.get("jti") or db.get(models.RevokedToken, payload["jti"]) is not None:
            raise HTTPException(401, "Session has been revoked", headers={"WWW-Authenticate": "Bearer"})
        try:
            user_id = int(payload["sub"])
            refresh_session_id = payload["sid"]
        except (KeyError, TypeError, ValueError):
            raise HTTPException(401, "Invalid access session", headers={"WWW-Authenticate": "Bearer"})
        refresh_session = db.get(models.RefreshSession, refresh_session_id)
        if (
            refresh_session is None
            or refresh_session.user_id != user_id
            or refresh_session.revoked_at is not None
            or utc_datetime(refresh_session.expires_at) <= datetime.now(timezone.utc)
        ):
            raise HTTPException(401, "Session has been revoked", headers={"WWW-Authenticate": "Bearer"})
        user = db.get(models.User, user_id)
        if user is None or not user.active:
            raise HTTPException(401, "Invalid or inactive account")
        if refresh_session.organization_id != user.organization_id:
            raise HTTPException(401, "Session organization does not match this account")
        activate_membership(db, user)
        return user

    def require_roles(*roles: str):
        def check(user: models.User = Depends(current_user)):
            if user.role not in roles:
                raise HTTPException(403, "Insufficient permissions")
            return user
        return check

    def require_module(module_key: str):
        def check(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
            if user.role == "Super Admin":
                return user
            module = db.query(models.Module).filter(
                models.Module.module_key == module_key,
                models.Module.active.is_(True),
            ).first()
            if module is None:
                raise HTTPException(403, f"Module '{module_key}' is not available")
            permission = db.query(models.RoleModulePermission).filter(
                models.RoleModulePermission.module_id == module.id,
                models.RoleModulePermission.role == user.role,
            ).first()
            if permission is None or not permission.granted:
                raise HTTPException(403, f"Your role does not have access to '{module_key}'")
            return user
        return check

    def audit(db: Session, actor: models.User | None, action: str, kind: str,
              entity_id=None, details=None):
        db.add(models.AuditLog(actor_id=actor.id if actor else None, action=action,
                               organization_id=actor.organization_id if actor else db.info.get("organization_id"),
                               entity_type=kind, entity_id=str(entity_id) if entity_id is not None else None,
                               details=details or {}))

    def flush(db: Session, conflict="A record with these values already exists"):
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, conflict)
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Unexpected database flush failure")
            raise HTTPException(500, "Database operation failed")

    def commit(db: Session, conflict="A record with these values already exists"):
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, conflict)
        except SQLAlchemyError:
            db.rollback()
            logger.exception("Unexpected database commit failure")
            raise HTTPException(500, "Database operation failed")

    def revoke_user_sessions(db: Session, user_id: int, at: datetime | None = None) -> int:
        return db.query(models.RefreshSession).filter_by(user_id=user_id).filter(
            models.RefreshSession.revoked_at.is_(None),
        ).update(
            {models.RefreshSession.revoked_at: at or datetime.now(timezone.utc)},
            synchronize_session=False,
        )

    def department_for(user, db):
        if user.role != "Department Manager":
            return None
        department = db.get(models.Department, user.department_id) if user.department_id else None
        if department is None or not department.active:
            raise HTTPException(403, "A department assignment is required for this action")
        return department

    def validate_employee_references(data, db, employee_id=None):
        for field_name, model, label in (
            ("branch_id", models.Branch, "Branch"),
            ("designation_id", models.Designation, "Designation"),
            ("job_grade_id", models.JobGrade, "Job grade"),
        ):
            record_id = getattr(data, field_name, None)
            if record_id is not None:
                record = db.get(model, record_id)
                if record is None:
                    raise HTTPException(422, f"{label} does not exist in this organization")
                if not record.active:
                    raise HTTPException(422, f"Select an active {label.lower()}")

        manager_id = getattr(data, "reporting_manager_id", None)
        if manager_id is None:
            return
        manager = db.get(models.Employee, manager_id)
        if manager is None:
            raise HTTPException(422, "Reporting manager does not exist in this organization")
        visited = set()
        cursor = manager
        while cursor is not None:
            if cursor.id == employee_id:
                raise HTTPException(422, "Reporting manager assignment would create a reporting cycle")
            if cursor.id in visited:
                raise HTTPException(409, "An existing reporting cycle must be resolved before this assignment")
            visited.add(cursor.id)
            cursor = db.get(models.Employee, cursor.reporting_manager_id) if cursor.reporting_manager_id else None

    def constrain_employee_query(query, user, db):
        if user.role == "Department Manager":
            department = department_for(user, db)
            return query.filter(models.Employee.department == department.name)
        if user.role not in EMPLOYEE_READERS:
            raise HTTPException(403, "Employee records are not available to this role")
        return query

    def private_employee_record(employee_id, user, db):
        row = db.get(models.Employee, employee_id)
        if row is None:
            raise HTTPException(404, "Employee not found")
        if user.role in HR_MANAGERS or (user.role == "Employee" and row.user_id == user.id):
            return row
        raise HTTPException(403, "Private employee details are not available to this role")

    def own_employee_record(user, db):
        if user.role != "Employee":
            raise HTTPException(403, "This endpoint is reserved for employee self-service")
        row = db.query(models.Employee).filter_by(user_id=user.id).first()
        if row is None:
            raise HTTPException(404, "No employee profile is linked to this account")
        return row

    def add_employment_snapshot(db, employee, actor, event_type, notes=None):
        branch = db.get(models.Branch, employee.branch_id) if employee.branch_id else None
        designation = db.get(models.Designation, employee.designation_id) if employee.designation_id else None
        grade = db.get(models.JobGrade, employee.job_grade_id) if employee.job_grade_id else None
        manager = db.get(models.Employee, employee.reporting_manager_id) if employee.reporting_manager_id else None
        db.add(models.EmployeeEmploymentHistory(
            employee_id=employee.id,
            event_type=event_type,
            effective_date=datetime.now(timezone.utc).date(),
            department=employee.department,
            job_title=employee.role,
            branch_name=branch.name if branch else None,
            designation_name=designation.name if designation else None,
            grade_name=grade.name if grade else None,
            reporting_manager_name=manager.name if manager else None,
            employment_status=employee.status,
            notes=notes,
            created_by=actor.id,
        ))

    def token_digest(token):
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def leave_days(start_date, end_date, half_day, db):
        if half_day:
            holiday = db.query(models.Holiday.id).filter_by(holiday_date=start_date, active=True).first()
            return Decimal("0.5") if start_date.weekday() < 5 and holiday is None else Decimal("0")
        holidays = {
            row[0] for row in db.query(models.Holiday.holiday_date).filter(
                models.Holiday.active.is_(True),
                models.Holiday.holiday_date >= start_date,
                models.Holiday.holiday_date <= end_date,
            ).all()
        }
        days = Decimal("0")
        current = start_date
        while current <= end_date:
            if current.weekday() < 5 and current not in holidays:
                days += Decimal("1")
            current += timedelta(days=1)
        return days

    def provision_user(data, actor, db):
        email = str(data.email).strip().lower()
        if db.query(models.User.id).filter(func.lower(models.User.email) == email).first():
            raise HTTPException(409, "An account with this email already exists.")
        if data.role not in ALL_ROLES - PLATFORM_ADMINS:
            raise HTTPException(422, "The requested role cannot be provisioned here")
        if actor.role == "Organization Admin" and data.role not in ORGANIZATION_ADMIN_MANAGED_ROLES:
            raise HTTPException(403, "Organization Admin cannot provision this role")
        if actor.role not in {"Super Admin", "Organization Admin"} and data.role not in ORGANIZATION_ADMIN_MANAGED_ROLES:
            raise HTTPException(403, "Only a Super Admin may provision this role")
        if data.role == "Department Manager" and not data.department_id:
            raise HTTPException(422, "Department Managers must be assigned a department")
        if data.department_id and db.get(models.Department, data.department_id) is None:
            raise HTTPException(422, "Department does not exist")
        if data.role == "Employee":
            if data.employee_id is None:
                raise HTTPException(422, "Link the employee profile before inviting an Employee account")
            employee = db.get(models.Employee, data.employee_id)
            if employee is None or employee.user_id is not None:
                raise HTTPException(409, "Employee profile is missing or already linked")
            matching_department = db.query(models.Department).filter(
                func.lower(models.Department.name) == employee.department.strip().lower(),
                models.Department.active.is_(True),
            ).first()
            if matching_department is None:
                raise HTTPException(422, "Create an active matching department before inviting this employee")
            if data.department_id is not None and data.department_id != matching_department.id:
                raise HTTPException(422, "Employee department must match their employee profile")
            department_id = matching_department.id
        else:
            employee = None
            department_id = data.department_id

        raw_token = secrets.token_urlsafe(36)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
        user = models.User(name=data.name.strip(), email=email,
                           hashed_password=hash_password(secrets.token_urlsafe(48)),
                           role=data.role, active=False, department_id=department_id)
        db.add(user)
        flush(db, "An account with this email already exists.")
        db.add(models.OrganizationMembership(
            user_id=user.id, role=data.role, department_id=department_id, active=True,
        ))
        if employee is not None:
            employee.user_id = user.id
        db.add(models.Invitation(user_id=user.id, token_hash=token_digest(raw_token), expires_at=expires_at))
        audit(db, actor, "user.invited", "user", user.id, {"role": user.role})
        commit(db)
        db.refresh(user)
        return UserProvisionResponse(user=UserResponse.model_validate(user), invitation_token=raw_token,
                                    expires_at=expires_at)

    def set_refresh_cookie(response: Response, session: models.RefreshSession, secret: str):
        remaining = max(0, int((utc_datetime(session.expires_at) - datetime.now(timezone.utc)).total_seconds()))
        response.set_cookie(
            "nexora_refresh", f"{session.id}.{secret}", max_age=remaining,
            httponly=True, secure=app.state.secure_cookies, samesite="strict", path="/api/auth",
        )
        response.headers["Cache-Control"] = "no-store"

    def clear_refresh_cookie(response: Response):
        response.delete_cookie(
            "nexora_refresh", path="/api/auth", httponly=True,
            secure=app.state.secure_cookies, samesite="strict",
        )
        response.headers["Cache-Control"] = "no-store"

    def auth_response(user, session: models.RefreshSession, response: Response,
                      raw_refresh_secret: str, csrf_token: str, message: str):
        token = create_access_token(
            {"sub": str(user.id), "role": user.role, "sid": session.id},
            secret_key=app.state.secret_key,
            expires_minutes=app.state.token_minutes,
        )
        set_refresh_cookie(response, session, raw_refresh_secret)
        return AuthResponse(
            message=message, access_token=token, expires_in=app.state.token_minutes * 60,
            csrf_token=csrf_token, user=UserResponse.model_validate(user),
        )

    def token_response(user, response: Response, db: Session, message="Login successful!"):
        activate_membership(db, user)
        now = datetime.now(timezone.utc)
        refresh_secret = secrets.token_urlsafe(48)
        csrf_token = secrets.token_urlsafe(32)
        session = models.RefreshSession(
            id=secrets.token_hex(16), user_id=user.id,
            token_hash=token_digest(refresh_secret), csrf_hash=token_digest(csrf_token),
            created_at=now, last_seen_at=now,
            expires_at=now + timedelta(days=app.state.refresh_session_days),
        )
        db.add(session)
        audit(db, user, "auth.session_created", "refresh_session", session.id)
        commit(db)
        db.refresh(session)
        return auth_response(user, session, response, refresh_secret, csrf_token, message)

    def authenticate(data, db):
        email = str(data.email).strip().lower()
        user = db.query(models.User).filter(func.lower(models.User.email) == email).first()
        if user is None or not verify_password(data.password, user.hashed_password):
            raise HTTPException(401, "Invalid email or password.")
        if not user.active:
            raise HTTPException(403, "This account is inactive.")
        activate_membership(db, user)
        audit(db, user, "auth.login", "user", user.id)
        commit(db)
        return user

    def validate_browser_origin(request: Request):
        origin = request.headers.get("origin")
        if origin is None or origin.rstrip("/") not in app.state.allowed_origins:
            raise HTTPException(403, "Request origin is not allowed")

    def refresh_session_from_request(request: Request, response: Response, csrf_token: str | None,
                                     db: Session):
        validate_browser_origin(request)
        raw_cookie = request.cookies.get("nexora_refresh")
        if not raw_cookie:
            clear_refresh_cookie(response)
            raise HTTPException(401, "Refresh session is missing")
        session_id, separator, secret = raw_cookie.partition(".")
        if not separator or not session_id or not secret:
            clear_refresh_cookie(response)
            raise HTTPException(401, "Refresh session is invalid")
        session = db.get(models.RefreshSession, session_id)
        if session is None or session.revoked_at is not None or utc_datetime(session.expires_at) <= datetime.now(timezone.utc):
            clear_refresh_cookie(response)
            raise HTTPException(401, "Refresh session has expired or been revoked")
        owner = db.get(models.User, session.user_id)
        if owner is None or not owner.active:
            clear_refresh_cookie(response)
            raise HTTPException(401, "Account is inactive")
        if session.organization_id != owner.organization_id:
            raise HTTPException(401, "Refresh session organization does not match this account")
        activate_membership(db, owner)
        if not csrf_token or not secrets.compare_digest(token_digest(csrf_token), session.csrf_hash):
            raise HTTPException(403, "CSRF token is missing or invalid")
        return session, secret

    @app.get("/")
    def home():
        return {"message": "My Login App Backend is Running!"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/test")
    def test_connection():
        return {"message": "React and FastAPI are connected successfully!"}

    @app.get("/api/organization", response_model=OrganizationResponse)
    def current_organization(user=Depends(current_user), db: Session = Depends(get_db)):
        organization = db.get(models.Organization, user.organization_id)
        if organization is None or not organization.active:
            raise HTTPException(404, "Organization not found")
        return organization

    @app.patch("/api/organization", response_model=OrganizationResponse)
    def update_organization(data: OrganizationUpdate,
                            user=Depends(require_roles("Super Admin", "Organization Admin")),
                            db: Session = Depends(get_db)):
        organization = db.get(models.Organization, user.organization_id)
        if organization is None or not organization.active:
            raise HTTPException(404, "Organization not found")
        organization.name = data.name.strip()
        audit(db, user, "organization.updated", "organization", organization.id, {"name": organization.name})
        commit(db)
        db.refresh(organization)
        return organization

    @app.get("/api/organization-memberships", response_model=Page[OrganizationMembershipResponse])
    def organization_memberships(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                                 _admin=Depends(require_roles(*USER_ADMINISTRATORS)), db: Session = Depends(get_db)):
        query = db.query(models.OrganizationMembership, models.User).join(
            models.User, models.User.id == models.OrganizationMembership.user_id,
        )
        total = query.count()
        rows = query.order_by(models.OrganizationMembership.id).offset(offset).limit(limit).all()
        items = [OrganizationMembershipResponse(
            id=membership.id, user_id=member.id, name=member.name, email=member.email,
            role=membership.role, active=membership.active, department_id=membership.department_id,
            created_at=membership.created_at,
        ) for membership, member in rows]
        return Page(items=items, total=total, limit=limit, offset=offset)

    @app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
    @app.post("/api/register", response_model=AuthResponse, status_code=201)
    def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)):
        default_organization(db)
        email = str(data.email).strip().lower()
        if db.query(models.User.id).filter(func.lower(models.User.email) == email).first():
            raise HTTPException(409, "An account with this email already exists.")
        user = models.User(
            name=data.name.strip(), email=email,
            hashed_password=hash_password(data.password), role="Employee", active=True,
        )
        db.add(user)
        flush(db, "An account with this email already exists.")
        db.add(models.OrganizationMembership(user_id=user.id, role="Employee", active=True))
        audit(db, user, "auth.register", "user", user.id)
        commit(db)
        db.refresh(user)
        return token_response(user, response, db, "Registration successful!")

    @app.get("/api/auth/admin-registration-status")
    def admin_registration_status(db: Session = Depends(get_db)):
        configured = len(app.state.admin_bootstrap_token) >= 32
        organization_count = db.query(models.Organization.id).filter_by(active=True).limit(2).count()
        admin_exists = db.query(models.User.id).filter_by(
            role="Super Admin",
        ).first() is not None
        return {"available": configured and organization_count == 1 and not admin_exists}

    @app.post("/api/auth/register-admin", response_model=AuthResponse, status_code=201)
    def register_first_admin(data: AdminRegistrationRequest, response: Response,
                             db: Session = Depends(get_db)):
        setup_token = app.state.admin_bootstrap_token
        if len(setup_token) < 32:
            raise HTTPException(503, "First-admin registration is not configured. Contact the application administrator.")
        if not secrets.compare_digest(data.setup_token, setup_token):
            raise HTTPException(403, "The administrator setup key is invalid.")

        # Serialize first-admin setup across concurrent requests on supported databases.
        dialect = db.get_bind().dialect.name
        if dialect == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
        elif dialect == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(482901733)"))

        default_organization(db)

        admin_exists = db.query(models.User.id).filter_by(
            role="Super Admin",
        ).first() is not None
        if admin_exists:
            raise HTTPException(409, "A Super Admin account has already been registered.")

        email = str(data.email).strip().lower()
        user = models.User(
            name=data.name.strip(), email=email,
            hashed_password=hash_password(data.password), role="Super Admin", active=True,
        )
        db.add(user)
        flush(db, "An account with this email already exists.")
        db.add(models.OrganizationMembership(user_id=user.id, role="Super Admin", active=True))
        audit(db, None, "auth.first_super_admin_registered", "user", user.id)
        commit(db, "An account with this email already exists.")
        db.refresh(user)
        return token_response(user, response, db, "Administrator account created successfully!")

    @app.post("/api/auth/login", response_model=AuthResponse)
    def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
        now = __import__("time").monotonic()
        key = request.client.host if request.client else "unknown"
        attempts = login_attempts[key]
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Too many sign-in attempts. Try again in one minute.")
        try:
            user = authenticate(data, db)
        except HTTPException as error:
            if error.status_code == 401:
                attempts.append(now)
                logger.warning("Rejected sign-in attempt from client %s", key)
            raise
        attempts.clear()
        login_attempts.pop(key, None)
        return token_response(user, response, db)

    @app.post("/api/auth/refresh", response_model=AuthResponse)
    def refresh_session(request: Request, response: Response,
                        csrf_token: str | None = Header(None, alias="X-CSRF-Token"),
                        db: Session = Depends(get_db)):
        session, presented_secret = refresh_session_from_request(request, response, csrf_token, db)
        now = datetime.now(timezone.utc)
        if not secrets.compare_digest(token_digest(presented_secret), session.token_hash):
            session.revoked_at = now
            audit(db, None, "auth.refresh_reuse_rejected", "refresh_session", session.id)
            commit(db)
            clear_refresh_cookie(response)
            raise HTTPException(401, "Refresh session is invalid or has already been rotated")

        user = db.get(models.User, session.user_id)
        if user is None or not user.active:
            session.revoked_at = now
            commit(db)
            clear_refresh_cookie(response)
            raise HTTPException(401, "Account is inactive")

        new_secret = secrets.token_urlsafe(48)
        new_csrf_token = secrets.token_urlsafe(32)
        rotated = db.execute(update(models.RefreshSession).where(
            models.RefreshSession.id == session.id,
            models.RefreshSession.token_hash == token_digest(presented_secret),
            models.RefreshSession.csrf_hash == token_digest(csrf_token),
            models.RefreshSession.revoked_at.is_(None),
            models.RefreshSession.expires_at > now,
        ).values(
            token_hash=token_digest(new_secret),
            csrf_hash=token_digest(new_csrf_token),
            last_seen_at=now,
        ).execution_options(synchronize_session=False))
        if rotated.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Refresh session was already used; sign in again")
        commit(db)
        db.refresh(session)
        return auth_response(user, session, response, new_secret, new_csrf_token, "Session refreshed.")

    @app.post("/api/login")
    def legacy_login(data: LoginRequest, request: Request, response: Response,
                     db: Session = Depends(get_db)):
        now = __import__("time").monotonic()
        key = request.client.host if request.client else "unknown"
        attempts = login_attempts[key]
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Too many sign-in attempts. Try again in one minute.")
        try:
            user = authenticate(data, db)
        except HTTPException as error:
            if error.status_code == 401:
                attempts.append(now)
                logger.warning("Rejected sign-in attempt from client %s", key)
            raise
        attempts.clear()
        login_attempts.pop(key, None)
        return token_response(user, response, db).model_dump()

    @app.post("/api/auth/activate", response_model=AuthResponse, include_in_schema=False)
    @app.post("/api/auth/register-invited", response_model=AuthResponse, status_code=201)
    def register_invited_account(data: InvitationRegistrationRequest, response: Response,
                                 db: Session = Depends(get_db)):
        invite = db.query(models.Invitation).filter_by(token_hash=token_digest(data.invitation_token)).first()
        now = datetime.now(timezone.utc)
        if invite is None or invite.accepted_at is not None or invite.expires_at.replace(tzinfo=timezone.utc) <= now:
            raise HTTPException(400, "Registration code is invalid, expired, or already used. Ask an administrator for a new code.")
        user = db.get(models.User, invite.user_id)
        if user is None or user.active:
            raise HTTPException(400, "Registration code is invalid, expired, or already used. Ask an administrator for a new code.")
        activate_membership(db, user)

        password_hash = hash_password(data.password)
        claimed = db.execute(update(models.Invitation).where(
            models.Invitation.id == invite.id,
            models.Invitation.accepted_at.is_(None),
            models.Invitation.expires_at > now,
        ).values(accepted_at=now).execution_options(synchronize_session=False))
        if claimed.rowcount != 1:
            db.rollback()
            raise HTTPException(400, "Registration code is invalid, expired, or already used. Ask an administrator for a new code.")
        registered = db.execute(update(models.User).where(
            models.User.id == user.id,
            models.User.active.is_(False),
        ).values(hashed_password=password_hash, active=True).execution_options(synchronize_session=False))
        if registered.rowcount != 1:
            db.rollback()
            raise HTTPException(400, "Registration code is invalid, expired, or already used. Ask an administrator for a new code.")
        audit(db, user, "user.registration_completed", "user", user.id, {"source": "invitation"})
        commit(db)
        db.refresh(user)
        return token_response(user, response, db, "Registration complete. You are now signed in.")

    @app.post("/api/auth/invitations", response_model=UserProvisionResponse, status_code=201)
    @app.post("/api/users/invitations", response_model=UserProvisionResponse, status_code=201)
    def create_invitation(data: UserProvisionRequest, actor=Depends(require_roles(*USER_ADMINISTRATORS)),
                          db: Session = Depends(get_db)):
        return provision_user(data, actor, db)

    @app.get("/api/auth/me", response_model=UserResponse)
    @app.get("/api/me", response_model=UserResponse)
    def me(user: models.User = Depends(current_user)):
        return user

    @app.get("/api/auth/sessions", response_model=list[RefreshSessionResponse])
    def list_sessions(limit: int = Query(50, ge=1, le=100),
                      credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
                      user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        payload = verify_access_token(credentials.credentials, app.state.secret_key)
        current_id = payload.get("sid") if payload else None
        sessions = db.query(models.RefreshSession).filter_by(user_id=user.id).order_by(
            models.RefreshSession.created_at.desc(),
        ).limit(limit).all()
        return [
            RefreshSessionResponse(
                id=session.id, created_at=session.created_at, last_seen_at=session.last_seen_at,
                expires_at=session.expires_at, revoked_at=session.revoked_at,
                current=session.id == current_id,
            )
            for session in sessions
        ]

    @app.delete("/api/auth/sessions/{session_id}", status_code=204)
    def revoke_session(session_id: str, request: Request, response: Response,
                       credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
                       user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        target = db.query(models.RefreshSession).filter_by(id=session_id, user_id=user.id).first()
        if target is None:
            raise HTTPException(404, "Session not found")
        payload = verify_access_token(credentials.credentials, app.state.secret_key)
        current_id = payload.get("sid") if payload else None
        if target.revoked_at is None:
            target.revoked_at = datetime.now(timezone.utc)
            audit(db, user, "auth.session_revoked", "refresh_session", target.id)
        if session_id == current_id and payload and payload.get("jti"):
            db.add(models.RevokedToken(
                jti=payload["jti"], user_id=user.id,
                expires_at=datetime.fromtimestamp(float(payload["exp"]), timezone.utc),
            ))
            browser_cookie = request.cookies.get("nexora_refresh", "")
            if browser_cookie.startswith(f"{session_id}."):
                clear_refresh_cookie(response)
        commit(db)
        response.status_code = 204
        return response

    @app.delete("/api/auth/sessions", status_code=204)
    def revoke_all_sessions(response: Response,
                            credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
                            user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        now = datetime.now(timezone.utc)
        sessions = db.query(models.RefreshSession).filter_by(user_id=user.id).filter(
            models.RefreshSession.revoked_at.is_(None),
        ).all()
        for session in sessions:
            session.revoked_at = now
        payload = verify_access_token(credentials.credentials, app.state.secret_key)
        if payload and payload.get("jti"):
            db.add(models.RevokedToken(
                jti=payload["jti"], user_id=user.id,
                expires_at=datetime.fromtimestamp(float(payload["exp"]), timezone.utc),
            ))
        audit(db, user, "auth.sessions_revoked", "user", user.id, {"count": len(sessions)})
        commit(db)
        clear_refresh_cookie(response)
        response.status_code = 204
        return response

    @app.post("/api/auth/password", status_code=204)
    def change_password(data: PasswordChangeRequest,
                        response: Response,
                        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
                        user=Depends(current_user), db: Session = Depends(get_db)):
        if not verify_password(data.current_password, user.hashed_password):
            raise HTTPException(400, "Current password is incorrect")
        user.hashed_password = hash_password(data.new_password)
        payload = verify_access_token(credentials.credentials, app.state.secret_key)
        if payload and payload.get("jti"):
            db.add(models.RevokedToken(
                jti=payload["jti"], user_id=user.id,
                expires_at=datetime.fromtimestamp(float(payload["exp"]), timezone.utc),
            ))
        now = datetime.now(timezone.utc)
        revoke_user_sessions(db, user.id, now)
        audit(db, user, "auth.password_changed", "user", user.id)
        commit(db)
        clear_refresh_cookie(response)
        response.status_code = 204
        return response

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response,
               csrf_token: str | None = Header(None, alias="X-CSRF-Token"),
               credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
               user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        payload = verify_access_token(credentials.credentials, app.state.secret_key)
        session, _ = refresh_session_from_request(request, response, csrf_token, db)
        if not payload or payload.get("sid") != session.id:
            raise HTTPException(409, "The browser refresh session does not match this access session")
        if session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
        if payload and payload.get("jti"):
            expiry = datetime.fromtimestamp(float(payload["exp"]), timezone.utc)
            db.add(models.RevokedToken(jti=payload["jti"], user_id=user.id, expires_at=expiry))
        audit(db, user, "auth.logout", "user", user.id)
        commit(db)
        clear_refresh_cookie(response)
        return {"message": "Session closed."}

    @app.get("/api/employees", response_model=list[EmployeeResponse])
    def employees(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0),
                  search: str | None = Query(None, max_length=100),
                  department: str | None = Query(None, max_length=100),
                  status: str | None = Query(None, pattern="^(Active|On leave|Inactive)$"),
                  user=Depends(current_user), db: Session = Depends(get_db)):
        query = constrain_employee_query(db.query(models.Employee), user, db)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter((models.Employee.name.ilike(pattern)) |
                                 (models.Employee.employee_code.ilike(pattern)) |
                                 (models.Employee.department.ilike(pattern)) |
                                 (models.Employee.role.ilike(pattern)))
        if department:
            query = query.filter(models.Employee.department == department)
        if status:
            query = query.filter(models.Employee.status == status)
        return query.order_by(models.Employee.id).offset(offset).limit(limit).all()

    @app.get("/api/employees/directory", response_model=Page[EmployeeDirectoryResponse])
    def employee_directory(limit: int = Query(10, ge=1, le=100), offset: int = Query(0, ge=0),
                           search: str | None = Query(None, max_length=100),
                           department: str | None = Query(None, max_length=100),
                           status: str | None = Query(None, pattern="^(Active|On leave|Inactive)$"),
                           user=Depends(current_user), db: Session = Depends(get_db)):
        if user.role == "Employee":
            if not app.state.employee_directory_enabled:
                raise HTTPException(403, "The employee directory is disabled by organization policy")
            query = db.query(models.Employee)
            if search:
                pattern = f"%{search.strip()}%"
                query = query.filter((models.Employee.name.ilike(pattern)) |
                                     (models.Employee.department.ilike(pattern)) |
                                     (models.Employee.role.ilike(pattern)))
            if department:
                query = query.filter(models.Employee.department == department)
            query = query.filter(models.Employee.status == "Active")
            return Page(items=query.with_entities(
                models.Employee.id, models.Employee.employee_code, models.Employee.name,
                models.Employee.department, models.Employee.role, models.Employee.status,
            ).order_by(models.Employee.name).offset(offset).limit(limit).all(),
                total=query.count(), limit=limit, offset=offset)
        query = constrain_employee_query(db.query(models.Employee), user, db)
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter((models.Employee.name.ilike(pattern)) |
                                 (models.Employee.employee_code.ilike(pattern)) |
                                 (models.Employee.department.ilike(pattern)) |
                                 (models.Employee.role.ilike(pattern)))
        if department:
            query = query.filter(models.Employee.department == department)
        if status:
            query = query.filter(models.Employee.status == status)
        return Page(items=query.order_by(models.Employee.id).offset(offset).limit(limit).all(),
                    total=query.count(), limit=limit, offset=offset)

    @app.get("/api/employees/me", response_model=EmployeeResponse)
    def my_employee_profile(user=Depends(current_user), db: Session = Depends(get_db)):
        return own_employee_record(user, db)

    @app.get("/api/employees/me/contact", response_model=EmployeeContactResponse | None)
    def my_employee_contact(user=Depends(current_user), db: Session = Depends(get_db)):
        employee = own_employee_record(user, db)
        return db.query(models.EmployeeContact).filter_by(employee_id=employee.id).first()

    @app.put("/api/employees/me/contact", response_model=EmployeeContactResponse)
    def update_my_employee_contact(data: EmployeeContactUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
        employee = own_employee_record(user, db)
        row = db.query(models.EmployeeContact).filter_by(employee_id=employee.id).first()
        if row is None:
            row = models.EmployeeContact(employee_id=employee.id, **data.model_dump())
            db.add(row)
        else:
            for key, value in data.model_dump().items():
                setattr(row, key, value)
        audit(db, user, "employee.contact_updated", "employee", employee.id,
              {"fields": sorted(data.model_fields_set)})
        commit(db)
        db.refresh(row)
        return row

    @app.get("/api/employees/me/emergency-contacts", response_model=list[EmergencyContactResponse])
    def my_emergency_contacts(user=Depends(current_user), db: Session = Depends(get_db)):
        employee = own_employee_record(user, db)
        return db.query(models.EmergencyContact).filter_by(employee_id=employee.id).order_by(
            models.EmergencyContact.priority, models.EmergencyContact.id,
        ).all()

    @app.post("/api/employees/me/emergency-contacts", response_model=EmergencyContactResponse, status_code=201)
    def create_my_emergency_contact(data: EmergencyContactCreate, user=Depends(current_user), db: Session = Depends(get_db)):
        employee = own_employee_record(user, db)
        if db.query(models.EmergencyContact).filter_by(employee_id=employee.id).count() >= 10:
            raise HTTPException(409, "An employee may have at most ten emergency contacts")
        row = models.EmergencyContact(employee_id=employee.id, **data.model_dump())
        db.add(row)
        audit(db, user, "employee.emergency_contact_created", "employee", employee.id, {})
        commit(db)
        db.refresh(row)
        return row

    @app.get("/api/employees/me/employment-history", response_model=list[EmployeeEmploymentHistoryResponse])
    def my_employment_history(user=Depends(current_user), db: Session = Depends(get_db)):
        employee = own_employee_record(user, db)
        return db.query(models.EmployeeEmploymentHistory).filter_by(employee_id=employee.id).order_by(
            models.EmployeeEmploymentHistory.effective_date.desc(), models.EmployeeEmploymentHistory.id.desc(),
        ).all()

    @app.get("/api/employees/me/contracts", response_model=list[EmploymentContractResponse])
    def my_employment_contracts(user=Depends(current_user), db: Session = Depends(get_db)):
        employee = own_employee_record(user, db)
        return db.query(models.EmploymentContract).filter_by(employee_id=employee.id).order_by(
            models.EmploymentContract.start_date.desc(), models.EmploymentContract.id.desc(),
        ).all()

    @app.post("/api/employees", response_model=EmployeeResponse, status_code=201)
    def create_employee(data: EmployeeCreate,
                        user=Depends(require_roles(*HR_MANAGERS, "Organization Admin")), db: Session = Depends(get_db)):
        validate_employee_references(data, db)
        row = models.Employee(**data.model_dump())
        db.add(row)
        flush(db, "Employee ID already exists")
        add_employment_snapshot(db, row, user, "hire", "Initial employment profile")
        audit(db, user, "employee.created", "employee", row.id, {"employee_code": row.employee_code})
        commit(db, "Employee ID already exists")
        db.refresh(row)
        return row

    @app.put("/api/employees/{employee_id}", response_model=EmployeeResponse)
    def update_employee(employee_id: int, data: EmployeeUpdate,
                        user=Depends(require_roles(*HR_MANAGERS)), db: Session = Depends(get_db)):
        row = db.get(models.Employee, employee_id)
        if row is None:
            raise HTTPException(404, "Employee not found")
        validate_employee_references(data, db, row.id)
        assignment_fields = ("department", "role", "branch_id", "designation_id", "job_grade_id", "reporting_manager_id")
        assignment_changed = any(getattr(row, key) != getattr(data, key) for key in assignment_fields)
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        if assignment_changed:
            add_employment_snapshot(db, row, user, "assignment_change", "Position or organization assignment updated")
        audit(db, user, "employee.updated", "employee", row.id)
        commit(db, "Employee code already exists")
        db.refresh(row)
        return row

    @app.patch("/api/employees/{employee_id}/status", response_model=EmployeeResponse)
    def update_employee_status(employee_id: int, data: EmployeeStatusUpdate,
                               user=Depends(require_roles(*HR_MANAGERS)), db: Session = Depends(get_db)):
        row = db.get(models.Employee, employee_id)
        if row is None:
            raise HTTPException(404, "Employee not found")
        status_changed = row.status != data.status
        row.status = data.status
        if status_changed:
            add_employment_snapshot(db, row, user, "status_change", "Employment status updated")
        audit(db, user, "employee.status_updated", "employee", row.id, {"status": data.status})
        commit(db)
        db.refresh(row)
        return row

    @app.delete("/api/employees/{employee_id}", status_code=204)
    def delete_employee(employee_id: int, user=Depends(require_roles(*HR_MANAGERS)), db: Session = Depends(get_db)):
        row = db.get(models.Employee, employee_id)
        if row is None:
            raise HTTPException(404, "Employee not found")
        was_active = row.status != "Inactive"
        row.status = "Inactive"
        if was_active:
            add_employment_snapshot(db, row, user, "status_change", "Employee record archived")
        audit(db, user, "employee.archived", "employee", row.id, {"employee_code": row.employee_code})
        commit(db)
        return Response(status_code=204)

    @app.get("/api/employees/{employee_id}", response_model=EmployeeResponse)
    def employee_detail(employee_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(models.Employee, employee_id)
        if row is None:
            raise HTTPException(404, "Employee not found")
        if user.role == "Employee":
            if row.user_id != user.id:
                raise HTTPException(403, "You may only view your own employee profile")
            return row
        if user.role == "Department Manager":
            department = department_for(user, db)
            if row.department != department.name:
                raise HTTPException(403, "This profile is outside your department")
            return row
        if user.role not in EMPLOYEE_READERS:
            raise HTTPException(403, "Employee records are not available to this role")
        return row

    @app.get("/api/employees/{employee_id}/contact", response_model=EmployeeContactResponse | None)
    def employee_contact(employee_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
        employee = private_employee_record(employee_id, user, db)
        return db.query(models.EmployeeContact).filter_by(employee_id=employee.id).first()

    @app.put("/api/employees/{employee_id}/contact", response_model=EmployeeContactResponse)
    def update_employee_contact(employee_id: int, data: EmployeeContactUpdate,
                                user=Depends(current_user), db: Session = Depends(get_db)):
        employee = private_employee_record(employee_id, user, db)
        row = db.query(models.EmployeeContact).filter_by(employee_id=employee.id).first()
        if row is None:
            row = models.EmployeeContact(employee_id=employee.id, **data.model_dump())
            db.add(row)
        else:
            for key, value in data.model_dump().items():
                setattr(row, key, value)
        audit(db, user, "employee.contact_updated", "employee", employee.id,
              {"fields": sorted(data.model_fields_set)})
        commit(db)
        db.refresh(row)
        return row

    @app.get("/api/employees/{employee_id}/emergency-contacts", response_model=list[EmergencyContactResponse])
    def employee_emergency_contacts(employee_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
        employee = private_employee_record(employee_id, user, db)
        return db.query(models.EmergencyContact).filter_by(employee_id=employee.id).order_by(
            models.EmergencyContact.priority, models.EmergencyContact.id,
        ).all()

    @app.post("/api/employees/{employee_id}/emergency-contacts", response_model=EmergencyContactResponse, status_code=201)
    def create_employee_emergency_contact(employee_id: int, data: EmergencyContactCreate,
                                          user=Depends(current_user), db: Session = Depends(get_db)):
        employee = private_employee_record(employee_id, user, db)
        if db.query(models.EmergencyContact).filter_by(employee_id=employee.id).count() >= 10:
            raise HTTPException(409, "An employee may have at most ten emergency contacts")
        row = models.EmergencyContact(employee_id=employee.id, **data.model_dump())
        db.add(row)
        audit(db, user, "employee.emergency_contact_created", "employee", employee.id, {})
        commit(db)
        db.refresh(row)
        return row

    @app.put("/api/emergency-contacts/{contact_id}", response_model=EmergencyContactResponse)
    def update_emergency_contact(contact_id: int, data: EmergencyContactUpdate,
                                 user=Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(models.EmergencyContact, contact_id)
        if row is None:
            raise HTTPException(404, "Emergency contact not found")
        employee = private_employee_record(row.employee_id, user, db)
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        audit(db, user, "employee.emergency_contact_updated", "employee", employee.id, {})
        commit(db)
        db.refresh(row)
        return row

    @app.delete("/api/emergency-contacts/{contact_id}", status_code=204)
    def delete_emergency_contact(contact_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(models.EmergencyContact, contact_id)
        if row is None:
            raise HTTPException(404, "Emergency contact not found")
        employee = private_employee_record(row.employee_id, user, db)
        db.delete(row)
        audit(db, user, "employee.emergency_contact_deleted", "employee", employee.id, {})
        commit(db)
        return Response(status_code=204)

    @app.get("/api/employees/{employee_id}/employment-history", response_model=list[EmployeeEmploymentHistoryResponse])
    def employee_employment_history(employee_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
        employee = private_employee_record(employee_id, user, db)
        return db.query(models.EmployeeEmploymentHistory).filter_by(employee_id=employee.id).order_by(
            models.EmployeeEmploymentHistory.effective_date.desc(), models.EmployeeEmploymentHistory.id.desc(),
        ).all()

    @app.get("/api/employees/{employee_id}/contracts", response_model=list[EmploymentContractResponse])
    def employee_contracts(employee_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
        employee = private_employee_record(employee_id, user, db)
        return db.query(models.EmploymentContract).filter_by(employee_id=employee.id).order_by(
            models.EmploymentContract.start_date.desc(), models.EmploymentContract.id.desc(),
        ).all()

    @app.post("/api/employees/{employee_id}/contracts", response_model=EmploymentContractResponse, status_code=201)
    def create_employment_contract(employee_id: int, data: EmploymentContractCreate,
                                   user=Depends(require_roles(*HR_MANAGERS)), db: Session = Depends(get_db)):
        employee = db.get(models.Employee, employee_id)
        if employee is None:
            raise HTTPException(404, "Employee not found")
        row = models.EmploymentContract(employee_id=employee.id, created_by=user.id, **data.model_dump())
        db.add(row)
        flush(db, "A contract with this reference already exists for this employee")
        audit(db, user, "employee.contract_created", "employment_contract", row.id,
              {"employee_id": employee.id, "status": row.status})
        commit(db, "A contract with this reference already exists for this employee")
        db.refresh(row)
        return row

    @app.put("/api/employment-contracts/{contract_id}", response_model=EmploymentContractResponse)
    def update_employment_contract(contract_id: int, data: EmploymentContractUpdate,
                                   user=Depends(require_roles(*HR_MANAGERS)), db: Session = Depends(get_db)):
        row = db.get(models.EmploymentContract, contract_id)
        if row is None:
            raise HTTPException(404, "Employment contract not found")
        if row.status == "Ended":
            raise HTTPException(409, "Ended contracts are immutable; create a new contract record")
        allowed_statuses = {"Draft": {"Draft", "Active", "Ended"}, "Active": {"Active", "Ended"}}
        if data.status not in allowed_statuses.get(row.status, set()):
            raise HTTPException(409, "This contract status transition is not allowed")
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        audit(db, user, "employee.contract_updated", "employment_contract", row.id,
              {"employee_id": row.employee_id, "status": row.status})
        commit(db, "A contract with this reference already exists for this employee")
        db.refresh(row)
        return row

    @app.put("/api/employees/me", response_model=EmployeeResponse)
    def update_my_employee_profile(data: EmployeeSelfUpdate, user=Depends(current_user), db: Session = Depends(get_db)):
        row = own_employee_record(user, db)
        user.name = data.name
        row.name = data.name
        audit(db, user, "employee.self_profile_updated", "employee", row.id, {"name_changed": True})
        commit(db)
        db.refresh(row)
        return row

    @app.get("/api/departments", response_model=Page[DepartmentResponse])
    def departments(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                    user=Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.Department)
        if user.role == "Department Manager":
            department = department_for(user, db)
            query = query.filter(models.Department.id == department.id)
        return Page(items=query.order_by(models.Department.name).offset(offset).limit(limit).all(),
                    total=query.count(), limit=limit, offset=offset)

    @app.post("/api/departments", response_model=DepartmentResponse, status_code=201)
    def create_department(data: DepartmentCreate,
                          user=Depends(require_roles(*HR_MANAGERS, "Organization Admin")), db: Session = Depends(get_db)):
        row = models.Department(**data.model_dump())
        db.add(row)
        flush(db, "Department already exists")
        audit(db, user, "department.created", "department", row.id)
        commit(db, "Department already exists")
        db.refresh(row)
        return row

    @app.put("/api/departments/{department_id}", response_model=DepartmentResponse)
    def update_department(department_id: int, data: DepartmentCreate,
                          user=Depends(require_roles(*HR_MANAGERS, "Organization Admin")), db: Session = Depends(get_db)):
        row = db.get(models.Department, department_id)
        if row is None:
            raise HTTPException(404, "Department not found")
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        audit(db, user, "department.updated", "department", row.id)
        commit(db, "Department already exists")
        db.refresh(row)
        return row

    @app.delete("/api/departments/{department_id}", status_code=204)
    def delete_department(department_id: int,
                          user=Depends(require_roles(*HR_MANAGERS, "Organization Admin")), db: Session = Depends(get_db)):
        row = db.get(models.Department, department_id)
        if row is None:
            raise HTTPException(404, "Department not found")
        row.active = False
        audit(db, user, "department.archived", "department", row.id)
        commit(db)
        return Response(status_code=204)

    @app.get("/api/branches", response_model=Page[BranchResponse])
    def branches(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                 _user=Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.Branch)
        return Page(items=query.order_by(models.Branch.name).offset(offset).limit(limit).all(),
                    total=query.count(), limit=limit, offset=offset)

    @app.post("/api/branches", response_model=BranchResponse, status_code=201)
    def create_branch(data: BranchCreate,
                      user=Depends(require_roles(*ORGANIZATION_STRUCTURE_ADMINISTRATORS)), db: Session = Depends(get_db)):
        row = models.Branch(**data.model_dump())
        db.add(row)
        flush(db, "Branch code or name already exists in this organization")
        audit(db, user, "branch.created", "branch", row.id, {"code": row.code})
        commit(db)
        db.refresh(row)
        return row

    @app.put("/api/branches/{branch_id}", response_model=BranchResponse)
    def update_branch(branch_id: int, data: BranchCreate,
                      user=Depends(require_roles(*ORGANIZATION_STRUCTURE_ADMINISTRATORS)), db: Session = Depends(get_db)):
        row = db.get(models.Branch, branch_id)
        if row is None:
            raise HTTPException(404, "Branch not found")
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        audit(db, user, "branch.updated", "branch", row.id)
        commit(db, "Branch code or name already exists in this organization")
        db.refresh(row)
        return row

    @app.delete("/api/branches/{branch_id}", status_code=204)
    def archive_branch(branch_id: int,
                       user=Depends(require_roles(*ORGANIZATION_STRUCTURE_ADMINISTRATORS)), db: Session = Depends(get_db)):
        row = db.get(models.Branch, branch_id)
        if row is None:
            raise HTTPException(404, "Branch not found")
        row.active = False
        audit(db, user, "branch.archived", "branch", row.id)
        commit(db)
        return Response(status_code=204)

    @app.get("/api/designations", response_model=Page[DesignationResponse])
    def designations(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                     _user=Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.Designation)
        return Page(items=query.order_by(models.Designation.name).offset(offset).limit(limit).all(),
                    total=query.count(), limit=limit, offset=offset)

    @app.post("/api/designations", response_model=DesignationResponse, status_code=201)
    def create_designation(data: DesignationCreate,
                           user=Depends(require_roles(*ORGANIZATION_STRUCTURE_ADMINISTRATORS)), db: Session = Depends(get_db)):
        row = models.Designation(**data.model_dump())
        db.add(row)
        flush(db, "Designation already exists in this organization")
        audit(db, user, "designation.created", "designation", row.id)
        commit(db)
        db.refresh(row)
        return row

    @app.put("/api/designations/{designation_id}", response_model=DesignationResponse)
    def update_designation(designation_id: int, data: DesignationCreate,
                           user=Depends(require_roles(*ORGANIZATION_STRUCTURE_ADMINISTRATORS)), db: Session = Depends(get_db)):
        row = db.get(models.Designation, designation_id)
        if row is None:
            raise HTTPException(404, "Designation not found")
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        audit(db, user, "designation.updated", "designation", row.id)
        commit(db, "Designation already exists in this organization")
        db.refresh(row)
        return row

    @app.delete("/api/designations/{designation_id}", status_code=204)
    def archive_designation(designation_id: int,
                            user=Depends(require_roles(*ORGANIZATION_STRUCTURE_ADMINISTRATORS)), db: Session = Depends(get_db)):
        row = db.get(models.Designation, designation_id)
        if row is None:
            raise HTTPException(404, "Designation not found")
        row.active = False
        audit(db, user, "designation.archived", "designation", row.id)
        commit(db)
        return Response(status_code=204)

    @app.get("/api/job-grades", response_model=Page[JobGradeResponse])
    def job_grades(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   _user=Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.JobGrade)
        return Page(items=query.order_by(models.JobGrade.rank, models.JobGrade.name).offset(offset).limit(limit).all(),
                    total=query.count(), limit=limit, offset=offset)

    @app.post("/api/job-grades", response_model=JobGradeResponse, status_code=201)
    def create_job_grade(data: JobGradeCreate,
                         user=Depends(require_roles(*ORGANIZATION_STRUCTURE_ADMINISTRATORS)), db: Session = Depends(get_db)):
        row = models.JobGrade(**data.model_dump())
        db.add(row)
        flush(db, "Job grade code or name already exists in this organization")
        audit(db, user, "job_grade.created", "job_grade", row.id, {"code": row.code})
        commit(db)
        db.refresh(row)
        return row

    @app.put("/api/job-grades/{grade_id}", response_model=JobGradeResponse)
    def update_job_grade(grade_id: int, data: JobGradeCreate,
                         user=Depends(require_roles(*ORGANIZATION_STRUCTURE_ADMINISTRATORS)), db: Session = Depends(get_db)):
        row = db.get(models.JobGrade, grade_id)
        if row is None:
            raise HTTPException(404, "Job grade not found")
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        audit(db, user, "job_grade.updated", "job_grade", row.id)
        commit(db, "Job grade code or name already exists in this organization")
        db.refresh(row)
        return row

    @app.delete("/api/job-grades/{grade_id}", status_code=204)
    def archive_job_grade(grade_id: int,
                          user=Depends(require_roles(*ORGANIZATION_STRUCTURE_ADMINISTRATORS)), db: Session = Depends(get_db)):
        row = db.get(models.JobGrade, grade_id)
        if row is None:
            raise HTTPException(404, "Job grade not found")
        row.active = False
        audit(db, user, "job_grade.archived", "job_grade", row.id)
        commit(db)
        return Response(status_code=204)

    @app.post("/api/attendance/clock-in", response_model=AttendanceResponse, status_code=201)
    def clock_in(user=Depends(current_user), db: Session = Depends(get_db)):
        now = datetime.now(timezone.utc)
        row = models.Attendance(user_id=user.id, work_date=now.date(), check_in=now, status="Present")
        db.add(row)
        flush(db, "You have already clocked in today")
        audit(db, user, "attendance.clocked_in", "attendance", row.id)
        commit(db)
        db.refresh(row)
        return row

    @app.post("/api/attendance/clock-out", response_model=AttendanceResponse)
    def clock_out(user=Depends(current_user), db: Session = Depends(get_db)):
        today = datetime.now(timezone.utc).date()
        row = db.query(models.Attendance).filter_by(user_id=user.id, work_date=today).first()
        if row is None:
            raise HTTPException(404, "No clock-in found for today")
        if row.check_out is not None:
            raise HTTPException(409, "You have already clocked out today")
        row.check_out = datetime.now(timezone.utc)
        audit(db, user, "attendance.clocked_out", "attendance", row.id)
        commit(db)
        db.refresh(row)
        return row

    @app.get("/api/attendance", response_model=Page[AttendanceResponse])
    def attendance(user_id: int | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   user=Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.Attendance)
        if user.role in HR_MANAGERS | {"Attendance Administrator"}:
            if user_id is not None:
                query = query.filter(models.Attendance.user_id == user_id)
        elif user.role == "Department Manager":
            department = department_for(user, db)
            query = query.join(models.Employee, models.Employee.user_id == models.Attendance.user_id).filter(
                models.Employee.department == department.name,
            )
            if user_id is not None:
                query = query.filter(models.Attendance.user_id == user_id)
        else:
            if user_id not in (None, user.id):
                raise HTTPException(403, "You may only view your own attendance")
            query = query.filter(models.Attendance.user_id == user.id)
        return Page(items=query.order_by(models.Attendance.work_date.desc()).offset(offset).limit(limit).all(),
                    total=query.count(), limit=limit, offset=offset)

    @app.get("/api/leave-types", response_model=list[LeaveTypeResponse])
    def list_leave_types(_user=Depends(current_user), db: Session = Depends(get_db)):
        return db.query(models.LeaveType).filter_by(active=True).order_by(models.LeaveType.name).all()

    @app.post("/api/leave-types", response_model=LeaveTypeResponse, status_code=201)
    def create_leave_type(data: LeaveTypeCreate, user=Depends(require_roles(*HR_MANAGERS)), db: Session = Depends(get_db)):
        row = models.LeaveType(**data.model_dump())
        db.add(row)
        flush(db, "A leave type with this name already exists")
        audit(db, user, "leave_type.created", "leave_type", row.id)
        commit(db)
        db.refresh(row)
        return row

    @app.get("/api/leave-types/all", response_model=list[LeaveTypeResponse])
    def list_all_leave_types(_admin=Depends(require_roles(*HR_MANAGERS)), db: Session = Depends(get_db)):
        return db.query(models.LeaveType).order_by(models.LeaveType.name).all()

    @app.put("/api/leave-types/{leave_type_id}", response_model=LeaveTypeResponse)
    def update_leave_type(leave_type_id: int, data: LeaveTypeCreate,
                          user=Depends(require_roles(*HR_MANAGERS)), db: Session = Depends(get_db)):
        row = db.get(models.LeaveType, leave_type_id)
        if row is None:
            raise HTTPException(404, "Leave type not found")
        for key, value in data.model_dump().items():
            setattr(row, key, value)
        audit(db, user, "leave_type.updated", "leave_type", row.id)
        commit(db, "A leave type with this name already exists")
        db.refresh(row)
        return row

    @app.get("/api/leave-balances/all", response_model=Page[LeaveBalanceResponse])
    def leave_balances_all(user_id: int | None = None, year: int | None = Query(None, ge=2000, le=2200),
                           limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                           user=Depends(require_roles(*HR_MANAGERS, "Department Manager")),
                           db: Session = Depends(get_db)):
        target_ids: list[int] | None = None
        if user.role == "Department Manager":
            department = department_for(user, db)
            scoped = db.query(models.User.id).filter(models.User.department_id == department.id)
            if user_id is not None:
                if not db.query(models.User.id).filter(models.User.id == user_id, models.User.department_id == department.id).first():
                    raise HTTPException(403, "This account is outside your department")
                scoped = scoped.filter(models.User.id == user_id)
            target_ids = [row[0] for row in scoped.all()]

        balance_year = year or date.today().year
        query = db.query(models.LeaveBalance).filter(models.LeaveBalance.year == balance_year)
        if user_id is not None:
            query = query.filter(models.LeaveBalance.user_id == user_id)
        elif target_ids is not None:
            query = query.filter(models.LeaveBalance.user_id.in_(target_ids)) if target_ids else query.filter(False)
        rows = query.order_by(models.LeaveBalance.user_id, models.LeaveBalance.leave_type_id).offset(offset).limit(limit).all()
        count = query.count()
        policies = {item.id: item.name for item in db.query(models.LeaveType).all()}
        pending_rows = db.query(models.LeaveRequest.user_id, models.LeaveRequest.leave_type_id, 
                                func.sum(models.LeaveRequest.days_requested)).filter(
            models.LeaveRequest.status == "Pending",
            models.LeaveRequest.start_date >= date(balance_year, 1, 1),
            models.LeaveRequest.start_date < date(balance_year + 1, 1, 1),
        ).group_by(models.LeaveRequest.user_id, models.LeaveRequest.leave_type_id).all()
        pending = {(owner, policy): Decimal(str(days or 0)) for owner, policy, days in pending_rows}
        items = [LeaveBalanceResponse(
            id=row.id, leave_type_id=row.leave_type_id, leave_type=policies.get(row.leave_type_id, "Archived policy"),
            year=row.year, allocated_days=row.allocated_days, used_days=row.used_days,
            pending_days=pending.get((row.user_id, row.leave_type_id), Decimal("0")),
            remaining_days=Decimal(row.allocated_days) - Decimal(row.used_days),
        ) for row in rows]
        return Page(items=items, total=count, limit=limit, offset=offset)

    @app.get("/api/holidays", response_model=list[HolidayResponse])
    def list_holidays(start_date: date | None = None, end_date: date | None = None,
                      _user=Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.Holiday).filter_by(active=True)
        if start_date:
            query = query.filter(models.Holiday.holiday_date >= start_date)
        if end_date:
            query = query.filter(models.Holiday.holiday_date <= end_date)
        return [{"id": row.id, "holiday_date": row.holiday_date, "name": row.name} for row in query.order_by(models.Holiday.holiday_date).all()]

    @app.post("/api/holidays", status_code=201)
    def create_holiday(data: HolidayCreate, user=Depends(require_roles(*HR_MANAGERS)), db: Session = Depends(get_db)):
        row = models.Holiday(**data.model_dump())
        db.add(row)
        flush(db, "A holiday already exists for this date")
        audit(db, user, "holiday.created", "holiday", row.id)
        commit(db)
        db.refresh(row)
        return row

    def get_leave_balances(user_id: int | None, balance_year: int, user, db: Session):
        target_id = user.id
        if user.role in HR_MANAGERS | {"Department Manager"}:
            if user_id is not None:
                target_id = user_id
                if user.role == "Department Manager":
                    department = department_for(user, db)
                    target = db.get(models.User, target_id)
                    if target is None or target.department_id != department.id:
                        raise HTTPException(403, "This account is outside your department")
        elif user_id is not None and user_id != user.id:
            raise HTTPException(403, "You may only view your own leave balances")

        policies = db.query(models.LeaveType).filter_by(active=True).all()
        existing = {row.leave_type_id: row for row in db.query(models.LeaveBalance).filter_by(
            user_id=target_id, year=balance_year,
        ).all()}
        for policy in policies:
            if policy.id not in existing:
                row = models.LeaveBalance(user_id=target_id, leave_type_id=policy.id,
                                          year=balance_year, allocated_days=policy.annual_allowance_days,
                                          used_days=Decimal("0"))
                db.add(row)
                existing[policy.id] = row
        if policies:
            flush(db, "Could not initialize leave balances")
            commit(db)
        pending_rows = db.query(models.LeaveRequest.leave_type_id, func.sum(models.LeaveRequest.days_requested)).filter(
            models.LeaveRequest.user_id == target_id,
            models.LeaveRequest.status == "Pending",
            models.LeaveRequest.start_date >= date(balance_year, 1, 1),
            models.LeaveRequest.start_date < date(balance_year + 1, 1, 1),
        ).group_by(models.LeaveRequest.leave_type_id).all()
        pending = {type_id: Decimal(str(days or 0)) for type_id, days in pending_rows}
        return [LeaveBalanceResponse(
            id=existing[policy.id].id, leave_type_id=policy.id, leave_type=policy.name,
            year=balance_year, allocated_days=existing[policy.id].allocated_days,
            used_days=existing[policy.id].used_days, pending_days=pending.get(policy.id, Decimal("0")),
            remaining_days=Decimal(existing[policy.id].allocated_days) - Decimal(existing[policy.id].used_days),
        ) for policy in policies if policy.id in existing]

    @app.get("/api/leave-balances", response_model=list[LeaveBalanceResponse])
    def leave_balances(user_id: int | None = None, year: int | None = Query(None, ge=2000, le=2200),
                       user=Depends(current_user), db: Session = Depends(get_db)):
        return get_leave_balances(user_id, year or date.today().year, user, db)

    @app.post("/api/leave-requests", response_model=LeaveResponse, status_code=201)
    def create_leave(data: LeaveCreate, user=Depends(current_user), db: Session = Depends(get_db)):
        leave_type = db.get(models.LeaveType, data.leave_type_id)
        if leave_type is None or not leave_type.active:
            raise HTTPException(422, "Select an active leave type")
        days_requested = leave_days(data.start_date, data.end_date, data.half_day, db)
        if days_requested <= 0:
            raise HTTPException(422, "The requested dates contain no working days")
        overlap = db.query(models.LeaveRequest.id).filter(
            models.LeaveRequest.user_id == user.id,
            models.LeaveRequest.status.in_(("Pending", "Approved")),
            models.LeaveRequest.start_date <= data.end_date,
            models.LeaveRequest.end_date >= data.start_date,
        ).first()
        if overlap:
            raise HTTPException(409, "This request overlaps an existing pending or approved leave")
        year = data.start_date.year
        balance = db.query(models.LeaveBalance).filter_by(
            user_id=user.id, leave_type_id=leave_type.id, year=year,
        ).first()
        if balance is None:
            balance = models.LeaveBalance(user_id=user.id, leave_type_id=leave_type.id, year=year,
                                          allocated_days=leave_type.annual_allowance_days, used_days=Decimal("0"))
            db.add(balance)
            flush(db, "Could not initialize leave balance")
        row = models.LeaveRequest(
            user_id=user.id, start_date=data.start_date, end_date=data.end_date,
            leave_type_id=leave_type.id, half_day=data.half_day, days_requested=days_requested,
            reason=data.reason,
        )
        db.add(row)
        flush(db)
        audit(db, user, "leave.submitted", "leave_request", row.id)
        commit(db)
        db.refresh(row)
        return LeaveResponse.model_validate(row).model_copy(update={"leave_type": leave_type.name})

    @app.get("/api/leave-requests", response_model=Page[LeaveResponse])
    def leave_requests(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                       user=Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.LeaveRequest)
        if user.role in HR_MANAGERS:
            pass
        elif user.role == "Department Manager":
            department = department_for(user, db)
            query = query.join(models.User, models.User.id == models.LeaveRequest.user_id).filter(
                models.User.department_id == department.id,
            )
        else:
            query = query.filter(models.LeaveRequest.user_id == user.id)
        rows = query.order_by(models.LeaveRequest.created_at.desc()).offset(offset).limit(limit).all()
        type_ids = {row.leave_type_id for row in rows if row.leave_type_id is not None}
        labels = {item.id: item.name for item in db.query(models.LeaveType).filter(models.LeaveType.id.in_(type_ids)).all()} if type_ids else {}
        items = [LeaveResponse.model_validate(row).model_copy(update={"leave_type": labels.get(row.leave_type_id)}) for row in rows]
        return Page(items=items, total=query.count(), limit=limit, offset=offset)

    @app.post("/api/leave-requests/{request_id}/review", response_model=LeaveResponse)
    def review_leave(request_id: int, data: LeaveReview,
                     user=Depends(require_roles(*HR_MANAGERS, "Department Manager")), db: Session = Depends(get_db)):
        row = db.get(models.LeaveRequest, request_id)
        if row is None:
            raise HTTPException(404, "Leave request not found")
        if row.user_id == user.id:
            raise HTTPException(403, "You cannot review your own leave request")
        if user.role == "Department Manager":
            department = department_for(user, db)
            employee_user = db.get(models.User, row.user_id)
            if employee_user is None or employee_user.department_id != department.id:
                raise HTTPException(403, "This request is outside your department")
        if row.status != "Pending":
            raise HTTPException(409, "Only pending leave requests can be reviewed")

        if data.decision == "Approved":
            if row.leave_type_id is None:
                raise HTTPException(409, "This legacy request has no leave policy; resolve it using an approved HR process")
            policy = db.get(models.LeaveType, row.leave_type_id)
            if policy is None:
                raise HTTPException(409, "The request's leave type is no longer available")
            balance = db.query(models.LeaveBalance).filter_by(
                user_id=row.user_id, leave_type_id=policy.id, year=row.start_date.year,
            ).first()
            if balance is None:
                balance = models.LeaveBalance(
                    user_id=row.user_id, leave_type_id=policy.id, year=row.start_date.year,
                    allocated_days=policy.annual_allowance_days, used_days=Decimal("0"),
                )
                db.add(balance)
                flush(db, "Could not initialize leave balance")
            updated = db.execute(update(models.LeaveBalance).where(
                models.LeaveBalance.id == balance.id,
                models.LeaveBalance.used_days + row.days_requested <= models.LeaveBalance.allocated_days,
            ).values(used_days=models.LeaveBalance.used_days + row.days_requested))
            if updated.rowcount != 1:
                db.rollback()
                raise HTTPException(409, "Insufficient leave balance for this approval")

        reviewed_at = datetime.now(timezone.utc)
        transitioned = db.execute(update(models.LeaveRequest).where(
            models.LeaveRequest.id == row.id,
            models.LeaveRequest.status == "Pending",
        ).values(
            status=data.decision,
            reviewed_by=user.id,
            reviewed_at=reviewed_at,
            review_comment=data.comment,
        ))
        if transitioned.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "This request has already been reviewed")
        details = {"decision": data.decision}
        if data.comment:
            details["comment"] = data.comment
        audit(db, user, "leave.reviewed", "leave_request", row.id, details)
        commit(db)
        db.refresh(row)
        label = db.get(models.LeaveType, row.leave_type_id).name if row.leave_type_id else None
        return LeaveResponse.model_validate(row).model_copy(update={"leave_type": label})

    @app.post("/api/leave-requests/{request_id}/cancel", response_model=LeaveResponse)
    def cancel_leave(request_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(models.LeaveRequest, request_id)
        if row is None:
            raise HTTPException(404, "Leave request not found")
        if row.user_id != user.id:
            raise HTTPException(403, "You may only cancel your own leave request")
        if row.status not in {"Pending", "Approved"}:
            raise HTTPException(409, "Only pending or approved requests can be cancelled")
        previous_status = row.status
        if previous_status == "Approved":
            if row.start_date <= date.today():
                raise HTTPException(409, "Approved leave can only be cancelled before it starts")
            balance = db.query(models.LeaveBalance).filter_by(
                user_id=user.id, leave_type_id=row.leave_type_id, year=row.start_date.year,
            ).first()
            if balance is None or Decimal(balance.used_days) < Decimal(row.days_requested):
                raise HTTPException(409, "Leave balance could not be restored safely; contact HR")
            restored = db.execute(update(models.LeaveBalance).where(
                models.LeaveBalance.id == balance.id,
                models.LeaveBalance.used_days >= row.days_requested,
            ).values(used_days=models.LeaveBalance.used_days - row.days_requested))
            if restored.rowcount != 1:
                db.rollback()
                raise HTTPException(409, "Leave balance changed concurrently; retry the cancellation")
        transitioned = db.execute(update(models.LeaveRequest).where(
            models.LeaveRequest.id == row.id,
            models.LeaveRequest.status == previous_status,
        ).values(status="Cancelled"))
        if transitioned.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "This request changed concurrently; reload and retry")
        audit(db, user, "leave.cancelled", "leave_request", row.id)
        commit(db)
        db.refresh(row)
        label = db.get(models.LeaveType, row.leave_type_id).name if row.leave_type_id else None
        return LeaveResponse.model_validate(row).model_copy(update={"leave_type": label})

    @app.get("/api/dashboard", response_model=DashboardResponse)
    def dashboard(user=Depends(current_user), db: Session = Depends(get_db)):
        today = datetime.now(timezone.utc).date()
        scope = {
            "Super Admin": "organization", "HR Administrator": "organization", "HR Manager": "organization",
            "Organization Admin": "organization",
            "Department Manager": "department", "Recruiter": "recruitment",
            "Payroll Administrator": "payroll", "Attendance Administrator": "attendance",
            "Employee": "personal",
        }.get(user.role, "personal")
        personal = scope == "personal"
        attendance_query = db.query(models.Attendance).filter(models.Attendance.work_date == today)
        pending = db.query(models.LeaveRequest).filter(models.LeaveRequest.status == "Pending")
        mine = pending.filter(models.LeaveRequest.user_id == user.id)
        if personal:
            attendance_query = attendance_query.filter(models.Attendance.user_id == user.id)
        elif scope == "department":
            department = department_for(user, db)
            attendance_query = attendance_query.join(models.Employee, models.Employee.user_id == models.Attendance.user_id).filter(models.Employee.department == department.name)
            pending = pending.join(models.User, models.User.id == models.LeaveRequest.user_id).filter(models.User.department_id == department.id)
        elif scope != "organization" and scope != "attendance":
            attendance_query = attendance_query.filter(models.Attendance.user_id == user.id)
        employee_query = db.query(models.Employee)
        department_query = db.query(models.Department)
        if scope == "department":
            employee_query = employee_query.filter(models.Employee.department == department.name)
            department_query = department_query.filter(models.Department.id == department.id)
        organization_metrics = scope in {"organization", "department"}
        return DashboardResponse(
            scope=scope,
            employee_count=employee_query.count() if organization_metrics else None,
            active_employee_count=employee_query.filter_by(status="Active").count() if organization_metrics else None,
            employees_on_leave_count=employee_query.filter_by(status="On leave").count() if organization_metrics else None,
            department_count=department_query.count() if organization_metrics else None,
            present_today=attendance_query.count() if scope in {"organization", "department", "attendance", "personal"} else 0,
            pending_leave_requests=pending.count() if organization_metrics else 0,
            my_pending_leave_requests=mine.count(),
        )

    @app.get("/api/users", response_model=Page[UserResponse])
    def users(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
              _admin=Depends(require_roles(*USER_ADMINISTRATORS)), db: Session = Depends(get_db)):
        query = db.query(models.User).options(selectinload(models.User.invitation))
        return Page(items=query.order_by(models.User.id).offset(offset).limit(limit).all(),
                    total=query.count(), limit=limit, offset=offset)

    @app.post("/api/users/{user_id}/invitation", response_model=UserProvisionResponse)
    def reissue_invitation(user_id: int, admin=Depends(require_roles(*USER_ADMINISTRATORS)),
                           db: Session = Depends(get_db)):
        target = db.query(models.User).options(selectinload(models.User.invitation)).filter_by(id=user_id).first()
        if target is None:
            raise HTTPException(404, "User not found")
        if target.role == "Organization Admin" and admin.role != "Super Admin":
            raise HTTPException(403, "Only a Super Admin may reissue an Organization Admin invitation")
        if admin.role != "Super Admin" and target.role not in ORGANIZATION_ADMIN_MANAGED_ROLES:
            raise HTTPException(403, "Only a Super Admin may reissue this registration code")
        invitation = target.invitation
        if target.active or invitation is None or invitation.accepted_at is not None:
            raise HTTPException(409, "This account does not have a pending registration")

        raw_token = secrets.token_urlsafe(36)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
        invitation.token_hash = token_digest(raw_token)
        invitation.expires_at = expires_at
        audit(db, admin, "user.registration_code_reissued", "user", target.id, {"role": target.role})
        commit(db)
        db.refresh(target)
        return UserProvisionResponse(user=UserResponse.model_validate(target), invitation_token=raw_token,
                                     expires_at=expires_at)

    @app.patch("/api/users/{user_id}", response_model=UserResponse)
    def update_user(user_id: int, data: UserAdminUpdate,
                    admin=Depends(require_roles(*USER_ADMINISTRATORS)), db: Session = Depends(get_db)):
        target = db.get(models.User, user_id)
        if target is None:
            raise HTTPException(404, "User not found")
        if admin.role == "Organization Admin" and target.role in {"Super Admin", "HR Administrator", "Organization Admin"}:
            raise HTTPException(403, "Organization Admin cannot change this account")
        if target.id == admin.id and data.active is False:
            raise HTTPException(409, "You cannot deactivate your own account")
        if target.registration_pending and data.active is True:
            raise HTTPException(409, "This account must complete registration with its one-time code")
        if admin.role != "Super Admin" and data.role is not None:
            raise HTTPException(403, "Only a Super Admin may change account roles")
        if admin.role not in {"Super Admin", "Organization Admin"} and "department_id" in data.model_fields_set:
            raise HTTPException(403, "Only a Super Admin may assign department scope")
        if "department_id" in data.model_fields_set and data.department_id is not None:
            if db.get(models.Department, data.department_id) is None:
                raise HTTPException(422, "Department does not exist")
        if target.role == "Super Admin" and (data.role not in (None, "Super Admin") or data.active is False):
            other_admins = db.query(models.User).filter(models.User.role == "Super Admin", models.User.active.is_(True), models.User.id != target.id).count()
            if not other_admins:
                raise HTTPException(409, "At least one active Super Admin must remain")
        was_active = target.active
        changes = {key: value for key, value in data.model_dump(exclude_unset=True).items()
               if key not in {"role", "active"} or value is not None}
        for key, value in changes.items():
            setattr(target, key, value)
        membership = db.query(models.OrganizationMembership).filter_by(user_id=target.id).first()
        if membership is None:
            raise HTTPException(409, "User organization membership is missing")
        membership.role = target.role
        membership.department_id = target.department_id
        membership.active = target.active
        if was_active and target.active is False:
            revoked_count = revoke_user_sessions(db, target.id)
            audit(db, admin, "auth.sessions_revoked_on_deactivation", "user", target.id,
                  {"count": revoked_count})
        audit(db, admin, "user.updated", "user", target.id, changes)
        commit(db)
        db.refresh(target)
        return target

    @app.get("/api/audit-logs", response_model=Page[AuditResponse])
    def audit_logs(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   _admin=Depends(require_roles("Super Admin")), db: Session = Depends(get_db)):
        query = db.query(models.AuditLog)
        return Page(items=query.order_by(models.AuditLog.id.desc()).offset(offset).limit(limit).all(),
                    total=query.count(), limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Password reset (forgot / reset)
    # ------------------------------------------------------------------
    @app.post("/api/auth/password/forgot", status_code=204)
    def forgot_password(data: ForgotPasswordRequest, response: Response, db: Session = Depends(get_db)):
        organization = default_organization(db)
        email = str(data.email).strip().lower()
        user = db.query(models.User).filter(
            func.lower(models.User.email) == email,
            models.User.organization_id == organization.id,
        ).first()
        if user is None or not user.active:
            return response
        now = datetime.now(timezone.utc)
        db.query(models.PasswordReset).filter(
            func.lower(models.PasswordReset.email) == email,
            models.PasswordReset.organization_id == organization.id,
            models.PasswordReset.used_at.is_(None),
            models.PasswordReset.expires_at > now,
        ).delete(synchronize_session=False)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        db.add(models.PasswordReset(
            organization_id=organization.id,
            email=email,
            token_hash=token_hash,
            expires_at=now + timedelta(minutes=settings.access_token_minutes * 4),
        ))
        audit(db, user, "auth.password_reset_requested", "user", user.id,
              {"email": email})
        commit(db)
        response.status_code = 204
        return response

    @app.post("/api/auth/password/reset", status_code=204)
    def reset_password(data: ResetPasswordRequest, response: Response, db: Session = Depends(get_db)):
        organization = default_organization(db)
        now = datetime.now(timezone.utc)
        token_hash = hashlib.sha256(data.token.encode("utf-8")).hexdigest()
        reset = db.query(models.PasswordReset).filter(
            models.PasswordReset.token_hash == token_hash,
            models.PasswordReset.organization_id == organization.id,
            models.PasswordReset.used_at.is_(None),
            models.PasswordReset.expires_at > now,
        ).first()
        if reset is None:
            raise HTTPException(400, "Invalid or expired password reset token.")
        user = db.query(models.User).filter(
            func.lower(models.User.email) == func.lower(reset.email),
            models.User.organization_id == organization.id,
        ).first()
        if user is None or not user.active:
            raise HTTPException(400, "Invalid or expired password reset token.")
        user.hashed_password = hash_password(data.new_password)
        reset.used_at = now
        revoke_user_sessions(db, user.id, now)
        audit(db, user, "auth.password_reset_completed", "user", user.id)
        commit(db)
        clear_refresh_cookie(response)
        response.status_code = 204
        return response

    # ------------------------------------------------------------------
    # MFA (TOTP) enrollment / verify / removal
    # ------------------------------------------------------------------
    def _verify_totp(secret_b32: str, code: str, window: int = 1) -> bool:
        if not code.isdigit() or len(code) != 6:
            return False
        key = base64.b32decode(secret_b32, casefold=True)
        now_counter = int(time.time()) // 30
        for offset in range(-window, window + 1):
            msg = struct.pack(">Q", now_counter + offset)
            digest = hmac.new(key, msg, hashlib.sha1).digest()
            off = digest[-1] & 0x0F
            binary = ((digest[off] & 0x7F) << 24
                      | (digest[off + 1] & 0xFF) << 16
                      | (digest[off + 2] & 0xFF) << 8
                      | (digest[off + 3] & 0xFF))
            candidate = f"{binary % 1000000:06d}"
            if secrets.compare_digest(candidate, code):
                return True
        return False

    @app.post("/api/auth/mfa/enrollment", response_model=MFAEnrollmentResponse, status_code=201)
    def mfa_enrollment(data: MFAEnrollmentRequest,
                       credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
                       user=Depends(current_user), db: Session = Depends(get_db)):
        existing = db.query(models.MFAFactor).filter_by(user_id=user.id).first()
        secret = base64.b32encode(secrets.token_bytes(20)).decode("ascii")
        backup_codes = [secrets.token_hex(4) for _ in range(8)]
        if existing is not None:
            existing.secret = secret
            existing.verified = False
            existing.backup_codes = backup_codes
            db.flush()
            audit(db, user, "mfa.factor_reset", "mfa_factor", existing.id)
            commit(db)
            db.refresh(existing)
            return MFAEnrollmentResponse(
                id=existing.id, factor_type=existing.factor_type, verified=existing.verified,
                created_at=existing.created_at, secret=secret, backup_codes=backup_codes,
            )
        factor = models.MFAFactor(
            organization_id=user.organization_id,
            user_id=user.id,
            factor_type="totp",
            secret=secret,
            verified=False,
            backup_codes=backup_codes,
        )
        db.add(factor)
        audit(db, user, "mfa.factor_enrolled", "mfa_factor", factor.id)
        commit(db)
        db.refresh(factor)
        return MFAEnrollmentResponse(
            id=factor.id, factor_type=factor.factor_type, verified=factor.verified,
            created_at=factor.created_at, secret=secret, backup_codes=backup_codes,
        )

    @app.post("/api/auth/mfa/verify", status_code=204)
    def mfa_verify(data: MFAVerifyRequest,
                   credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
                   user=Depends(current_user), db: Session = Depends(get_db)):
        factor = db.query(models.MFAFactor).filter_by(user_id=user.id).first()
        if factor is None or not factor.secret:
            raise HTTPException(404, "No MFA factor is enrolled for this account.")
        code = data.code.strip()
        if code in factor.backup_codes:
            backup_codes = [c for c in factor.backup_codes if c != code]
            factor.backup_codes = backup_codes
            factor.verified = True
            audit(db, user, "mfa.backup_code_used", "mfa_factor", factor.id)
            commit(db)
            response = Response(status_code=204)
            return response
        if not _verify_totp(factor.secret, code):
            raise HTTPException(400, "Invalid verification code.")
        factor.verified = True
        audit(db, user, "mfa.factor_verified", "mfa_factor", factor.id)
        commit(db)
        response = Response(status_code=204)
        return response

    @app.delete("/api/auth/mfa/enrollment", status_code=204)
    def mfa_remove(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
                   user=Depends(current_user), db: Session = Depends(get_db)):
        factor = db.query(models.MFAFactor).filter_by(user_id=user.id).first()
        if factor is None:
            raise HTTPException(404, "No MFA factor is enrolled for this account.")
        audit(db, user, "mfa.factor_removed", "mfa_factor", factor.id)
        db.delete(factor)
        commit(db)
        response = Response(status_code=204)
        return response

    # ------------------------------------------------------------------
    # Payroll / compensation
    # ------------------------------------------------------------------
    PAYROLL_ROLES = {"Super Admin", "Payroll Administrator", "HR Administrator", "HR Manager"}

    @app.get("/api/payroll/compensation", response_model=list[CompensationResponse])
    def list_compensation(_payroll=Depends(require_roles(*PAYROLL_ROLES)), db: Session = Depends(get_db)):
        return db.query(models.Compensation).order_by(models.Compensation.id.desc()).all()

    @app.post("/api/payroll/compensation", response_model=CompensationResponse, status_code=201)
    def create_compensation(data: CompensationCreate,
                            _payroll=Depends(require_roles(*PAYROLL_ROLES)),
                            user=Depends(current_user), db: Session = Depends(get_db)):
        employee = db.query(models.Employee).filter_by(id=data.employee_id).first()
        if employee is None:
            raise HTTPException(404, "Employee not found.")
        comp = models.Compensation(
            organization_id=employee.organization_id,
            employee_id=data.employee_id,
            employment_type=data.employment_type,
            base_salary=data.base_salary,
            currency=data.currency,
            pay_frequency=data.pay_frequency,
            effective_from=data.effective_from,
            effective_to=data.effective_to,
        )
        db.add(comp)
        audit(db, user, "payroll.compensation_created", "compensation", comp.id,
              {"employee_id": data.employee_id, "base_salary": str(data.base_salary)})
        commit(db)
        db.refresh(comp)
        return comp

    @app.get("/api/payroll/runs", response_model=list[PayrollRunResponse])
    def list_payroll_runs(_payroll=Depends(require_roles(*PAYROLL_ROLES)), db: Session = Depends(get_db)):
        return db.query(models.PayrollRun).order_by(models.PayrollRun.id.desc()).all()

    @app.post("/api/payroll/runs", response_model=PayrollRunResponse, status_code=201)
    def create_payroll_run(data: PayrollRunCreate,
                           _payroll=Depends(require_roles(*PAYROLL_ROLES)),
                           user=Depends(current_user), db: Session = Depends(get_db)):
        if data.period_end < data.period_start:
            raise HTTPException(400, "period_end must be on or after period_start.")
        run = models.PayrollRun(
            organization_id=user.organization_id,
            name=data.name,
            period_start=data.period_start,
            period_end=data.period_end,
            pay_date=data.pay_date,
            status="Draft",
            created_by=user.id,
        )
        db.add(run)
        audit(db, user, "payroll.run_created", "payroll_run", run.id,
              {"name": data.name, "period_start": str(data.period_start), "period_end": str(data.period_end)})
        commit(db)
        db.refresh(run)
        return run

    @app.post("/api/payroll/runs/{run_id}/calculate", status_code=204)
    def calculate_payroll(run_id: int,
                          _payroll=Depends(require_roles(*PAYROLL_ROLES)),
                          user=Depends(current_user), db: Session = Depends(get_db)):
        run = db.query(models.PayrollRun).filter_by(id=run_id).first()
        if run is None:
            raise HTTPException(404, "Payroll run not found.")
        if run.status != "Draft":
            raise HTTPException(400, "Only draft payroll runs can be calculated.")
        employees = db.query(models.Employee).filter(
            models.Employee.organization_id == run.organization_id,
            models.Employee.status == "Active",
        ).all()
        total_gross = Decimal("0")
        total_deductions = Decimal("0")
        for emp in employees:
            comp = db.query(models.Compensation).filter_by(
                employee_id=emp.id, active=True,
            ).order_by(models.Compensation.effective_from.desc()).first()
            gross = comp.base_salary if comp else Decimal("0")
            deductions = gross * Decimal("0.05")
            net = gross - deductions
            total_gross += gross
            total_deductions += deductions
            db.add(models.Payslip(
                organization_id=run.organization_id,
                payroll_run_id=run.id,
                employee_id=emp.id,
                gross_pay=gross,
                deductions=deductions,
                net_pay=net,
                payslip_date=run.pay_date,
                status="Draft",
            ))
        run.status = "Calculated"
        run.total_gross = total_gross
        run.total_deductions = total_deductions
        run.total_net = total_gross - total_deductions
        run.employee_count = len(employees)
        audit(db, user, "payroll.run_calculated", "payroll_run", run.id,
              {"employee_count": len(employees), "total_net": str(run.total_net)})
        commit(db)
        response = Response(status_code=204)
        return response

    @app.post("/api/payroll/runs/{run_id}/finalize", status_code=204)
    def finalize_payroll(run_id: int,
                         _payroll=Depends(require_roles("Super Admin", "Payroll Administrator")),
                         user=Depends(current_user), db: Session = Depends(get_db)):
        run = db.query(models.PayrollRun).filter_by(id=run_id).first()
        if run is None:
            raise HTTPException(404, "Payroll run not found.")
        if run.status != "Calculated":
            raise HTTPException(400, "Only calculated payroll runs can be finalized.")
        run.status = "Finalized"
        run.finalized_at = datetime.now(timezone.utc)
        audit(db, user, "payroll.run_finalized", "payroll_run", run.id)
        commit(db)
        response = Response(status_code=204)
        return response

    @app.get("/api/payroll/payslips", response_model=list[PayslipResponse])
    def list_payslips(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.Payslip)
        if user.role not in PAYROLL_ROLES:
            query = query.filter_by(employee_id=user.id)
        return query.order_by(models.Payslip.created_at.desc()).all()

    # ------------------------------------------------------------------
    # Recruitment
    # ------------------------------------------------------------------
    RECRUITMENT_ROLES = {"Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Recruiter"}

    @app.get("/api/recruitment/requisitions", response_model=list[RequisitionResponse])
    def list_requisitions(_recruit=Depends(require_roles(*RECRUITMENT_ROLES)), db: Session = Depends(get_db)):
        return db.query(models.Requisition).order_by(models.Requisition.id.desc()).all()

    @app.post("/api/recruitment/requisitions", response_model=RequisitionResponse, status_code=201)
    def create_requisition(data: RequisitionCreate,
                           _recruit=Depends(require_roles(*RECRUITMENT_ROLES)),
                           user=Depends(current_user), db: Session = Depends(get_db)):
        req = models.Requisition(
            organization_id=user.organization_id,
            title=data.title,
            department=data.department,
            employment_type=data.employment_type,
            status="Open",
            created_by=user.id,
        )
        db.add(req)
        audit(db, user, "recruitment.requisition_created", "requisition", req.id,
              {"title": data.title, "department": data.department})
        commit(db)
        db.refresh(req)
        return req

    @app.post("/api/recruitment/requisitions/{req_id}/close", status_code=204)
    def close_requisition(req_id: int,
                          _recruit=Depends(require_roles(*RECRUITMENT_ROLES)),
                          user=Depends(current_user), db: Session = Depends(get_db)):
        req = db.query(models.Requisition).filter_by(id=req_id).first()
        if req is None:
            raise HTTPException(404, "Requisition not found.")
        req.status = "Closed"
        req.closed_at = datetime.now(timezone.utc)
        audit(db, user, "recruitment.requisition_closed", "requisition", req_id)
        commit(db)
        response = Response(status_code=204)
        return response

    @app.get("/api/recruitment/candidates", response_model=list[CandidateResponse])
    def list_candidates(_recruit=Depends(require_roles(*RECRUITMENT_ROLES)), db: Session = Depends(get_db)):
        return db.query(models.Candidate).order_by(models.Candidate.applied_at.desc()).all()

    @app.post("/api/recruitment/candidates", response_model=CandidateResponse, status_code=201)
    def create_candidate(data: CandidateCreate,
                         _recruit=Depends(require_roles(*RECRUITMENT_ROLES)),
                         user=Depends(current_user), db: Session = Depends(get_db)):
        req = db.query(models.Requisition).filter_by(id=data.requisition_id).first()
        if req is None:
            raise HTTPException(404, "Requisition not found.")
        cand = models.Candidate(
            organization_id=req.organization_id,
            requisition_id=data.requisition_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
            status="Applied",
        )
        db.add(cand)
        audit(db, user, "recruitment.candidate_created", "candidate", cand.id,
              {"name": data.name, "email": data.email, "requisition_id": data.requisition_id})
        commit(db)
        db.refresh(cand)
        return cand

    @app.get("/api/recruitment/candidates/{candidate_id}/applications", response_model=list[ApplicationResponse])
    def list_applications(candidate_id: int,
                          _recruit=Depends(require_roles(*RECRUITMENT_ROLES)), db: Session = Depends(get_db)):
        return db.query(models.Application).filter_by(candidate_id=candidate_id).order_by(
            models.Application.created_at.desc()).all()

    @app.post("/api/recruitment/applications", response_model=ApplicationResponse, status_code=201)
    def create_application(data: ApplicationCreate,
                           _recruit=Depends(require_roles(*RECRUITMENT_ROLES)),
                           user=Depends(current_user), db: Session = Depends(get_db)):
        cand = db.query(models.Candidate).filter_by(id=data.candidate_id).first()
        if cand is None:
            raise HTTPException(404, "Candidate not found.")
        app_row = models.Application(
            organization_id=cand.organization_id,
            candidate_id=data.candidate_id,
            stage=data.stage,
            score=data.score,
            notes=data.notes,
        )
        db.add(app_row)
        cand.status = data.stage
        audit(db, user, "recruitment.application_created", "application", app_row.id,
              {"candidate_id": data.candidate_id, "stage": data.stage})
        commit(db)
        db.refresh(app_row)
        return app_row

    # ------------------------------------------------------------------
    # Performance & Goals
    # ------------------------------------------------------------------
    PERF_ROLES = {"Super Admin", "HR Administrator", "HR Manager", "Department Manager", "Employee"}

    @app.get("/api/performance/goals", response_model=list[GoalResponse])
    def list_goals(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.Goal)
        if user.role == "Employee":
            emp = db.query(models.Employee).filter_by(user_id=user.id).first()
            if emp:
                query = query.filter_by(employee_id=emp.id)
        return query.order_by(models.Goal.created_at.desc()).all()

    @app.post("/api/performance/goals", response_model=GoalResponse, status_code=201)
    def create_goal(data: GoalCreate,
                    _perf=Depends(require_roles(*PERF_ROLES)),
                    user=Depends(current_user), db: Session = Depends(get_db)):
        emp = db.query(models.Employee).filter_by(id=data.employee_id).first()
        if emp is None:
            raise HTTPException(404, "Employee not found.")
        goal = models.Goal(
            organization_id=emp.organization_id,
            employee_id=data.employee_id,
            title=data.title,
            description=data.description,
            category=data.category,
            target_date=data.target_date,
            progress=0,
            created_by=user.id,
        )
        db.add(goal)
        audit(db, user, "performance.goal_created", "goal", goal.id,
              {"employee_id": data.employee_id, "title": data.title})
        commit(db)
        db.refresh(goal)
        return goal

    @app.patch("/api/performance/goals/{goal_id}", response_model=GoalResponse)
    def update_goal(goal_id: int,
                    data: GoalUpdate,
                    _perf=Depends(require_roles(*PERF_ROLES)),
                    user=Depends(current_user), db: Session = Depends(get_db)):
        goal = db.query(models.Goal).filter_by(id=goal_id).first()
        if goal is None:
            raise HTTPException(404, "Goal not found.")
        if user.role == "Employee":
            emp = db.query(models.Employee).filter_by(user_id=user.id).first()
            if not emp or goal.employee_id != emp.id:
                raise HTTPException(403, "Employees can only update their own goals.")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(goal, field, value)
        audit(db, user, "performance.goal_updated", "goal", goal_id)
        commit(db)
        db.refresh(goal)
        return goal

    @app.get("/api/performance/review-cycles", response_model=list[ReviewCycleResponse])
    def list_review_cycles(_perf=Depends(require_roles(*PERF_ROLES)), db: Session = Depends(get_db)):
        return db.query(models.ReviewCycle).order_by(models.ReviewCycle.created_at.desc()).all()

    @app.post("/api/performance/review-cycles", response_model=ReviewCycleResponse, status_code=201)
    def create_review_cycle(data: ReviewCycleCreate,
                            _perf=Depends(require_roles("Super Admin", "HR Administrator", "HR Manager")),
                            user=Depends(current_user), db: Session = Depends(get_db)):
        cycle = models.ReviewCycle(
            organization_id=user.organization_id,
            name=data.name,
            start_date=data.start_date,
            end_date=data.end_date,
            status="Planned",
        )
        db.add(cycle)
        audit(db, user, "performance.review_cycle_created", "review_cycle", cycle.id,
              {"name": data.name})
        commit(db)
        db.refresh(cycle)
        return cycle

    @app.get("/api/performance/reviews", response_model=list[PerformanceReviewResponse])
    def list_performance_reviews(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.PerformanceReview)
        if user.role == "Employee":
            emp = db.query(models.Employee).filter_by(user_id=user.id).first()
            if emp:
                query = query.filter_by(employee_id=emp.id)
        return query.order_by(models.PerformanceReview.created_at.desc()).all()

    @app.post("/api/performance/reviews", response_model=PerformanceReviewResponse, status_code=201)
    def create_performance_review(data: PerformanceReviewCreate,
                                  _perf=Depends(require_roles(*PERF_ROLES)),
                                  user=Depends(current_user), db: Session = Depends(get_db)):
        emp = db.query(models.Employee).filter_by(id=data.employee_id).first()
        if emp is None:
            raise HTTPException(404, "Employee not found.")
        review = models.PerformanceReview(
            organization_id=emp.organization_id,
            review_cycle_id=data.review_cycle_id,
            employee_id=data.employee_id,
            reviewer_id=data.reviewer_id or user.id,
            overall_rating=data.overall_rating,
            comments=data.comments,
            status="Pending",
        )
        db.add(review)
        audit(db, user, "performance.review_created", "performance_review", review.id,
              {"employee_id": data.employee_id})
        commit(db)
        db.refresh(review)
        return review

    @app.post("/api/performance/reviews/{review_id}/submit", status_code=204)
    def submit_performance_review(review_id: int,
                                  data: PerformanceReviewSubmit,
                                  _perf=Depends(require_roles("Super Admin", "HR Administrator", "HR Manager", "Department Manager")),
                                  user=Depends(current_user), db: Session = Depends(get_db)):
        review = db.query(models.PerformanceReview).filter_by(id=review_id).first()
        if review is None:
            raise HTTPException(404, "Performance review not found.")
        review.overall_rating = data.overall_rating
        review.comments = data.comments
        review.status = "Submitted"
        review.submitted_at = datetime.now(timezone.utc)
        audit(db, user, "performance.review_submitted", "performance_review", review_id)
        commit(db)
        response = Response(status_code=204)
        return response

    # ------------------------------------------------------------------
    # Learning & Development
    # ------------------------------------------------------------------
    LEARNING_MANAGERS = {"Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Department Manager"}

    @app.get("/api/learning/courses", response_model=list[TrainingCourseResponse])
    def list_training_courses(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.TrainingCourse)
        if user.role == "Employee":
            query = query.filter(models.TrainingCourse.active.is_(True))
        return query.order_by(models.TrainingCourse.id.desc()).all()

    @app.post("/api/learning/courses", response_model=TrainingCourseResponse, status_code=201)
    def create_training_course(data: TrainingCourseCreate,
                               _learn=Depends(require_roles(*LEARNING_MANAGERS)),
                               user=Depends(current_user), db: Session = Depends(get_db)):
        course = models.TrainingCourse(organization_id=user.organization_id, **data.model_dump())
        db.add(course)
        audit(db, user, "learning.course_created", "training_course", course.id, {"title": data.title})
        commit(db)
        db.refresh(course)
        return course

    @app.get("/api/learning/enrollments", response_model=list[TrainingEnrollmentResponse])
    def list_training_enrollments(user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        query = db.query(models.TrainingEnrollment)
        if user.role == "Employee":
            employee = db.query(models.Employee).filter_by(user_id=user.id).first()
            if employee is None:
                return []
            query = query.filter(models.TrainingEnrollment.employee_id == employee.id)
        return query.order_by(models.TrainingEnrollment.id.desc()).all()

    @app.post("/api/learning/enrollments", response_model=TrainingEnrollmentResponse, status_code=201)
    def create_training_enrollment(data: TrainingEnrollmentCreate,
                                   _learn=Depends(require_roles(*LEARNING_MANAGERS)),
                                   user=Depends(current_user), db: Session = Depends(get_db)):
        course = db.get(models.TrainingCourse, data.course_id)
        if course is None or not course.active:
            raise HTTPException(404, "Training course not found.")
        employee = db.get(models.Employee, data.employee_id)
        if employee is None:
            raise HTTPException(404, "Employee not found.")
        duplicate = db.query(models.TrainingEnrollment.id).filter_by(course_id=course.id, employee_id=employee.id).first()
        if duplicate is not None:
            raise HTTPException(409, "This employee is already enrolled in this course.")
        enrollment = models.TrainingEnrollment(organization_id=user.organization_id, course_id=course.id,
                                               employee_id=employee.id)
        db.add(enrollment)
        audit(db, user, "learning.enrollment_created", "training_enrollment", enrollment.id,
              {"course_id": course.id, "employee_id": employee.id})
        commit(db)
        db.refresh(enrollment)
        return enrollment

    @app.patch("/api/learning/enrollments/{enrollment_id}", response_model=TrainingEnrollmentResponse)
    def update_training_enrollment(enrollment_id: int, data: TrainingEnrollmentUpdate,
                                   _learn=Depends(require_roles(*LEARNING_MANAGERS)),
                                   user=Depends(current_user), db: Session = Depends(get_db)):
        enrollment = db.get(models.TrainingEnrollment, enrollment_id)
        if enrollment is None:
            raise HTTPException(404, "Enrollment not found.")
        enrollment.status = data.status
        enrollment.score = data.score
        enrollment.completed_at = datetime.now(timezone.utc) if data.status == "Completed" else None
        audit(db, user, "learning.enrollment_updated", "training_enrollment", enrollment_id, {"status": data.status})
        commit(db)
        db.refresh(enrollment)
        return enrollment

    # ------------------------------------------------------------------
    # Notifications & Announcements
    # ------------------------------------------------------------------
    NOTIFICATION_SENDERS = {"Super Admin", "Organization Admin", "HR Administrator", "HR Manager",
                            "Payroll Administrator", "Department Manager"}

    @app.get("/api/notifications", response_model=list[NotificationResponse])
    def my_notifications(limit: int = Query(50, ge=1, le=200),
                         user: models.User = Depends(current_user), db: Session = Depends(get_db)):
        return db.query(models.Notification).filter_by(user_id=user.id).order_by(
            models.Notification.id.desc()).limit(limit).all()

    @app.post("/api/notifications", status_code=201)
    def send_notification(data: NotificationCreate,
                          _sender=Depends(require_roles(*NOTIFICATION_SENDERS)),
                          user=Depends(current_user), db: Session = Depends(get_db)):
        if data.user_id is not None:
            target = db.get(models.User, data.user_id)
            if target is None:
                raise HTTPException(404, "Recipient not found.")
            recipients = [target]
        else:
            recipients = db.query(models.User).filter_by(active=True).all()
        for target in recipients:
            db.add(models.Notification(
                organization_id=user.organization_id, user_id=target.id,
                title=data.title, message=data.message, category=data.category,
                created_by=user.id,
            ))
        audit(db, user, "notifications.sent", "notification", None,
              {"recipients": len(recipients), "category": data.category})
        commit(db)
        return {"recipients": len(recipients)}

    @app.patch("/api/notifications/{notification_id}/read", status_code=204)
    def mark_notification_read(notification_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
        row = db.get(models.Notification, notification_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(404, "Notification not found.")
        row.read = True
        commit(db)
        return Response(status_code=204)

    @app.get("/api/announcements", response_model=list[AnnouncementResponse])
    def list_announcements(_user=Depends(current_user), db: Session = Depends(get_db)):
        now = datetime.now(timezone.utc)
        return db.query(models.Announcement).filter(
            (models.Announcement.expires_at.is_(None)) | (models.Announcement.expires_at > now)
        ).order_by(models.Announcement.pinned.desc(), models.Announcement.id.desc()).limit(100).all()

    @app.post("/api/announcements", response_model=AnnouncementResponse, status_code=201)
    def create_announcement(data: AnnouncementCreate,
                            _sender=Depends(require_roles(*NOTIFICATION_SENDERS)),
                            user=Depends(current_user), db: Session = Depends(get_db)):
        row = models.Announcement(organization_id=user.organization_id, title=data.title, body=data.body,
                                  pinned=data.pinned, created_by=user.id, expires_at=data.expires_at)
        db.add(row)
        audit(db, user, "announcements.created", "announcement", row.id, {"title": data.title})
        commit(db)
        db.refresh(row)
        return row

    # ------------------------------------------------------------------
    # Reports & CSV exports
    # ------------------------------------------------------------------
    REPORT_READERS = {"Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Payroll Administrator"}

    def csv_safe(value):
        if value is None:
            return ""
        text = str(value)
        if text[:1] in ("=", "+", "-", "@"):
            return "'" + text
        return text

    def csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> Response:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([csv_safe(cell) for cell in row])
        return Response(content=buffer.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    @app.get("/api/reports/summary")
    def reports_summary(_report=Depends(require_roles(*REPORT_READERS)), db: Session = Depends(get_db)):
        employee_count = db.query(models.Employee.id).count()
        active_count = db.query(models.Employee.id).filter_by(status="Active").count()
        department_count = db.query(models.Department.id).filter_by(active=True).count()
        pending_leave = db.query(models.LeaveRequest.id).filter_by(status="Pending").count()
        today = date.today()
        present_today = db.query(models.Attendance.id).filter(func.date(models.Attendance.check_in) == today).count()
        payroll_totals = db.query(
            func.coalesce(func.sum(models.Payslip.gross_pay), 0),
            func.coalesce(func.sum(models.Payslip.deductions), 0),
            func.coalesce(func.sum(models.Payslip.net_pay), 0),
        ).one()
        open_requisitions = db.query(models.Requisition.id).filter_by(status="Open").count()
        active_enrollments = db.query(models.TrainingEnrollment.id).filter(
            models.TrainingEnrollment.status.in_(("Enrolled", "In Progress"))).count()
        return {
            "employee_count": employee_count,
            "active_employee_count": active_count,
            "department_count": department_count,
            "pending_leave_requests": pending_leave,
            "present_today": present_today,
            "payroll_gross_total": str(payroll_totals[0]),
            "payroll_deductions_total": str(payroll_totals[1]),
            "payroll_net_total": str(payroll_totals[2]),
            "open_requisitions": open_requisitions,
            "active_training_enrollments": active_enrollments,
        }

    @app.get("/api/reports/employees.csv")
    def export_employees_csv(_report=Depends(require_roles(*REPORT_READERS)), db: Session = Depends(get_db)):
        rows = db.query(models.Employee).order_by(models.Employee.id).all()
        return csv_response("employees.csv",
                            ["Employee ID", "Name", "Department", "Role", "Status"],
                            [[row.employee_code, row.name, row.department, row.role, row.status] for row in rows])

    @app.get("/api/reports/attendance.csv")
    def export_attendance_csv(_report=Depends(require_roles(*REPORT_READERS)), db: Session = Depends(get_db)):
        rows = db.query(models.Attendance).order_by(models.Attendance.id).all()
        return csv_response("attendance.csv",
                            ["User ID", "Work date", "Check in (UTC)", "Check out (UTC)", "Status"],
                            [[row.user_id, row.work_date, row.check_in, row.check_out, row.status] for row in rows])

    @app.get("/api/reports/leave.csv")
    def export_leave_csv(_report=Depends(require_roles(*REPORT_READERS)), db: Session = Depends(get_db)):
        rows = db.query(models.LeaveRequest).order_by(models.LeaveRequest.id).all()
        return csv_response("leave-requests.csv",
                            ["User ID", "Start", "End", "Days", "Status", "Reason"],
                            [[row.user_id, row.start_date, row.end_date, row.days_requested, row.status, row.reason]
                             for row in rows])

    @app.get("/api/reports/payroll.csv")
    def export_payroll_csv(_report=Depends(require_roles(*REPORT_READERS)), db: Session = Depends(get_db)):
        rows = db.query(models.Payslip).order_by(models.Payslip.id).all()
        return csv_response("payslips.csv",
                            ["Payslip ID", "Payroll run ID", "Employee ID", "Gross", "Deductions", "Net", "Status"],
                            [[row.id, row.payroll_run_id, row.employee_id, row.gross_pay, row.deductions, row.net_pay,
                              row.status] for row in rows])

    # ------------------------------------------------------------------
    # Module-based role permissions
    # ------------------------------------------------------------------
    DEFAULT_MODULES = [
        {"module_key": "overview", "name": "Overview", "description": "Dashboard and workspace overview",
         "default_granted": list(ALL_ROLES)},
        {"module_key": "employees", "name": "Employees", "description": "Employee directory and profiles",
         "default_granted": ["Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Department Manager", "Employee"]},
        {"module_key": "departments", "name": "Departments", "description": "Department management",
         "default_granted": ["Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Department Manager"]},
        {"module_key": "organization", "name": "Organization Structure", "description": "Branches, designations, job grades",
         "default_granted": ["Super Admin", "Organization Admin", "HR Administrator", "HR Manager"]},
        {"module_key": "attendance", "name": "Attendance", "description": "Time tracking and attendance records",
         "default_granted": ["Super Admin", "HR Administrator", "HR Manager", "Department Manager", "Attendance Administrator", "Employee"]},
        {"module_key": "leave", "name": "Leave Management", "description": "Leave requests and balances",
         "default_granted": ["Super Admin", "HR Administrator", "HR Manager", "Department Manager", "Employee"]},
        {"module_key": "users", "name": "Access & Users", "description": "User invitations and account administration",
         "default_granted": ["Super Admin", "Organization Admin", "HR Administrator"]},
        {"module_key": "payroll", "name": "Payroll", "description": "Payroll runs and payslips",
         "default_granted": ["Super Admin", "Payroll Administrator", "HR Administrator", "HR Manager", "Employee"]},
        {"module_key": "recruitment", "name": "Recruitment", "description": "Job requisitions and candidates",
         "default_granted": ["Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Recruiter"]},
        {"module_key": "performance", "name": "Performance", "description": "Goals and review cycles",
         "default_granted": ["Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Department Manager", "Employee"]},
        {"module_key": "learning", "name": "Learning", "description": "Training courses and enrollments",
         "default_granted": ["Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Department Manager", "Employee"]},
        {"module_key": "notifications", "name": "Notifications", "description": "Notifications and announcements",
         "default_granted": list(ALL_ROLES)},
        {"module_key": "reports", "name": "Reports", "description": "Reports and CSV exports",
         "default_granted": ["Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Payroll Administrator"]},
        {"module_key": "settings", "name": "Account Settings", "description": "Personal account settings",
         "default_granted": list(ALL_ROLES)},
        {"module_key": "module-access", "name": "Module Access", "description": "Manage role-based module permissions",
         "default_granted": ["Super Admin"]},
    ]

    def seed_default_modules(db: Session) -> None:
        existing = db.query(models.Module.id).first()
        if existing is not None:
            return
        organization = default_organization(db)
        for mod in DEFAULT_MODULES:
            row = models.Module(
                organization_id=organization.id,
                module_key=mod["module_key"],
                name=mod["name"],
                description=mod["description"],
                active=True,
            )
            db.add(row)
            db.flush()
            for role in ALL_ROLES:
                granted = role in mod["default_granted"]
                db.add(models.RoleModulePermission(
                    organization_id=organization.id,
                    module_id=row.id,
                    role=role,
                    granted=granted,
                ))
        # Persist the seed immediately: request sessions only close() without
        # committing, which would otherwise roll the catalog back on every call.
        db.commit()

    @app.get("/api/modules", response_model=list[ModuleWithPermissions])
    def list_modules(_user=Depends(current_user), db: Session = Depends(get_db)):
        seed_default_modules(db)
        modules = db.query(models.Module).filter_by(active=True).order_by(models.Module.module_key).all()
        result = []
        for module in modules:
            perms = db.query(models.RoleModulePermission).filter_by(module_id=module.id).order_by(
                models.RoleModulePermission.role).all()
            result.append(ModuleWithPermissions.model_validate(module).model_copy(
                update={"permissions": [RoleModulePermissionResponse.model_validate(p) for p in perms]}))
        return result

    @app.put("/api/modules/{module_key}/roles", response_model=ModuleWithPermissions)
    def update_module_roles(module_key: str, data: ModulePermissionUpdate,
                            _admin=Depends(require_roles("Super Admin")), db: Session = Depends(get_db)):
        seed_default_modules(db)
        module = db.query(models.Module).filter_by(module_key=module_key, active=True).first()
        if module is None:
            raise HTTPException(404, f"Module '{module_key}' not found")
        for role, granted in data.roles.items():
            if role not in ALL_ROLES:
                raise HTTPException(422, f"Unknown role '{role}'")
            perm = db.query(models.RoleModulePermission).filter_by(
                module_id=module.id, role=role).first()
            if perm is None:
                perm = models.RoleModulePermission(
                    organization_id=module.organization_id,
                    module_id=module.id,
                    role=role,
                    granted=bool(granted),
                )
                db.add(perm)
            else:
                perm.granted = bool(granted)
        commit(db)
        perms = db.query(models.RoleModulePermission).filter_by(module_id=module.id).order_by(
            models.RoleModulePermission.role).all()
        audit(db, _admin, "module.roles_updated", "module", module.id, {"module_key": module_key,
                                                                         "roles": data.roles})
        return ModuleWithPermissions.model_validate(module).model_copy(
            update={"permissions": [RoleModulePermissionResponse.model_validate(p) for p in perms]})

    @app.get("/api/my-permissions", response_model=MyPermissionsResponse)
    def my_permissions(user=Depends(current_user), db: Session = Depends(get_db)):
        seed_default_modules(db)
        if user.role == "Super Admin":
            accessible = [m["module_key"] for m in DEFAULT_MODULES]
        else:
            modules = db.query(models.Module).filter_by(active=True).all()
            accessible = []
            for module in modules:
                perm = db.query(models.RoleModulePermission).filter_by(
                    module_id=module.id, role=user.role, granted=True).first()
                if perm is not None:
                    accessible.append(module.module_key)
        module_rows = db.query(models.Module).filter_by(active=True).order_by(models.Module.module_key).all()
        module_list = []
        for module in module_rows:
            perms = db.query(models.RoleModulePermission).filter_by(module_id=module.id).order_by(
                models.RoleModulePermission.role).all()
            module_list.append(ModuleWithPermissions.model_validate(module).model_copy(
                update={"permissions": [RoleModulePermissionResponse.model_validate(p) for p in perms]}))
        return MyPermissionsResponse(accessible_modules=accessible, modules=module_list)

    return app


app = create_app()
