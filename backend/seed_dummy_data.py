"""Seed dummy data for development/demo usage.

Creates/updates two users:
  - amoln52@gmail.com        -> Employee, password: anishka123
  - amolnavgire2611@gmail.com -> Super Admin, password: anishka123

And populates all related tables with dummy data.
"""

from datetime import date, datetime, timedelta, timezone
from sqlalchemy import func

import models
from database import SessionLocal
from security import hash_password

PASSWORD = "anishka123"
ORG_NAME = "Nexora Demo Corp"
ORG_SLUG = "nexora-demo"


def _get_or_create(db, model, defaults=None, **kwargs):
    """Fetch existing row by kwargs, or create with defaults merged in."""
    # Auto-inject organization_id for TenantScoped models
    if hasattr(model, "organization_id") and "organization_id" not in kwargs:
        org_id = db.info.get("organization_id")
        if org_id is not None:
            kwargs["organization_id"] = org_id
    instance = db.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    params = dict(kwargs)
    if defaults:
        params.update(defaults)
    instance = model(**params)
    db.add(instance)
    db.flush()
    return instance, True


def main() -> None:
    db = SessionLocal()
    try:
        # 1. Organization
        org, _ = _get_or_create(
            db, models.Organization,
            defaults={"active": True},
            slug=ORG_SLUG,
            name=ORG_NAME,
        )
        org.active = True
        db.flush()

        org_id = org.id
        db.info["organization_id"] = org_id

        # 2. Users
        emp_user = db.query(models.User).filter(
            func.lower(models.User.email) == "amoln52@gmail.com"
        ).first()
        if emp_user is None:
            emp_user = models.User(
                name="Amol Navgire",
                email="amoln52@gmail.com",
                role="Employee",
                active=True,
                organization_id=org_id,
                hashed_password=hash_password(PASSWORD),
            )
            db.add(emp_user)
            db.flush()
        else:
            emp_user.name = "Amol Navgire"
            emp_user.role = "Employee"
            emp_user.active = True
            emp_user.organization_id = org_id
            emp_user.hashed_password = hash_password(PASSWORD)
        db.flush()

        admin_user = db.query(models.User).filter(
            func.lower(models.User.email) == "amolnavgire2611@gmail.com"
        ).first()
        if admin_user is None:
            admin_user = models.User(
                name="Admin Navgire",
                email="amolnavgire2611@gmail.com",
                role="Super Admin",
                active=True,
                organization_id=org_id,
                hashed_password=hash_password(PASSWORD),
            )
            db.add(admin_user)
            db.flush()
        else:
            admin_user.name = "Admin Navgire"
            admin_user.role = "Super Admin"
            admin_user.active = True
            admin_user.organization_id = org_id
            admin_user.hashed_password = hash_password(PASSWORD)
        db.flush()

        # 3. Departments
        dept_hr, _ = _get_or_create(
            db, models.Department,
            defaults={"description": "Human Resources", "active": True},
            name="Human Resources",
            organization_id=org_id,
        )
        dept_eng, _ = _get_or_create(
            db, models.Department,
            defaults={"description": "Engineering", "active": True},
            name="Engineering",
            organization_id=org_id,
        )
        dept_sales, _ = _get_or_create(
            db, models.Department,
            defaults={"description": "Sales", "active": True},
            name="Sales",
            organization_id=org_id,
        )
        db.flush()

        # 3b. Organization Memberships (required for login)
        emp_membership = db.query(models.OrganizationMembership).filter_by(
            organization_id=org_id, user_id=emp_user.id
        ).first()
        if emp_membership is None:
            emp_membership = models.OrganizationMembership(
                organization_id=org_id,
                user_id=emp_user.id,
                role="Employee",
                department_id=dept_eng.id,
                active=True,
            )
            db.add(emp_membership)
        else:
            emp_membership.role = "Employee"
            emp_membership.department_id = dept_eng.id
            emp_membership.active = True
        db.flush()

        admin_membership = db.query(models.OrganizationMembership).filter_by(
            organization_id=org_id, user_id=admin_user.id
        ).first()
        if admin_membership is None:
            admin_membership = models.OrganizationMembership(
                organization_id=org_id,
                user_id=admin_user.id,
                role="Super Admin",
                active=True,
            )
            db.add(admin_membership)
        else:
            admin_membership.role = "Super Admin"
            admin_membership.active = True
        db.flush()


        # 4. Branches
        branch_hq, _ = _get_or_create(
            db, models.Branch,
            defaults={"address": "100 Main Street, Downtown", "active": True},
            code="HQ",
            name="Headquarters",
            organization_id=org_id,
        )
        branch_north, _ = _get_or_create(
            db, models.Branch,
            defaults={"address": "200 North Ave, North City", "active": True},
            code="NORTH",
            name="North Branch",
            organization_id=org_id,
        )
        db.flush()

        # 5. Designations
        des_mgr, _ = _get_or_create(
            db, models.Designation,
            defaults={"description": "Department Manager", "active": True},
            name="Manager",
            organization_id=org_id,
        )
        des_eng, _ = _get_or_create(
            db, models.Designation,
            defaults={"description": "Software Engineer", "active": True},
            name="Engineer",
            organization_id=org_id,
        )
        des_admin, _ = _get_or_create(
            db, models.Designation,
            defaults={"description": "System Administrator", "active": True},
            name="Administrator",
            organization_id=org_id,
        )
        db.flush()

        # 6. Job Grades
        grade_1, _ = _get_or_create(
            db, models.JobGrade,
            defaults={"description": "Entry level", "rank": 1, "active": True},
            code="JG1",
            name="Associate",
            organization_id=org_id,
        )
        grade_2, _ = _get_or_create(
            db, models.JobGrade,
            defaults={"description": "Mid level", "rank": 2, "active": True},
            code="JG2",
            name="Senior",
            organization_id=org_id,
        )
        grade_3, _ = _get_or_create(
            db, models.JobGrade,
            defaults={"description": "Lead level", "rank": 3, "active": True},
            code="JG3",
            name="Lead",
            organization_id=org_id,
        )
        db.flush()
        # 7. Employees
        emp_amol, _ = _get_or_create(
            db, models.Employee,
            defaults={
                "department": "Engineering",
                "role": "Employee",
                "status": "Active",
                "user_id": emp_user.id,
                "branch_id": branch_hq.id,
                "designation_id": des_eng.id,
                "job_grade_id": grade_2.id,
                "reporting_manager_id": None,
            },
            employee_code="EMP-001",
            name="Amol Navgire",
            organization_id=org_id,
        )
        emp_amol.department = "Engineering"
        emp_amol.role = "Employee"
        emp_amol.status = "Active"
        emp_amol.user_id = emp_user.id
        emp_amol.branch_id = branch_hq.id
        emp_amol.designation_id = des_eng.id
        emp_amol.job_grade_id = grade_2.id
        db.flush()

        emp_admin, _ = _get_or_create(
            db, models.Employee,
            defaults={
                "department": "Human Resources",
                "role": "Super Admin",
                "status": "Active",
                "user_id": admin_user.id,
                "branch_id": branch_hq.id,
                "designation_id": des_admin.id,
                "job_grade_id": grade_3.id,
                "reporting_manager_id": None,
            },
            employee_code="EMP-002",
            name="Admin Navgire",
            organization_id=org_id,
        )
        emp_admin.department = "Human Resources"
        emp_admin.role = "Super Admin"
        emp_admin.status = "Active"
        emp_admin.user_id = admin_user.id
        emp_admin.branch_id = branch_hq.id
        emp_admin.designation_id = des_admin.id
        emp_admin.job_grade_id = grade_3.id
        db.flush()

        # 8. Leave Types
        lt_sick, _ = _get_or_create(
            db, models.LeaveType,
            defaults={"description": "Sick leave", "annual_allowance_days": 12, "paid": True, "active": True},
            name="Sick Leave",
            organization_id=org_id,
        )
        lt_casual, _ = _get_or_create(
            db, models.LeaveType,
            defaults={"description": "Casual leave", "annual_allowance_days": 15, "paid": True, "active": True},
            name="Casual Leave",
            organization_id=org_id,
        )
        lt_earned, _ = _get_or_create(
            db, models.LeaveType,
            defaults={"description": "Earned / privileged leave", "annual_allowance_days": 18, "paid": True, "active": True},
            name="Earned Leave",
            organization_id=org_id,
        )
        db.flush()

        # 9. Leave Balances
        current_year = date.today().year
        for user_obj, lt in [(emp_user, lt_sick), (emp_user, lt_casual), (emp_user, lt_earned),
                             (admin_user, lt_sick), (admin_user, lt_casual), (admin_user, lt_earned)]:
            _get_or_create(
                db, models.LeaveBalance,
                defaults={"allocated_days": lt.annual_allowance_days, "used_days": 0},
                user_id=user_obj.id,
                leave_type_id=lt.id,
                year=current_year,
            )
        db.flush()

        # 10. Leave Requests
        start = date.today() + timedelta(days=7)
        end = start + timedelta(days=2)
        lr, _ = _get_or_create(
            db, models.LeaveRequest,
            defaults={
                "leave_type_id": lt_casual.id,
                "half_day": False,
                "days_requested": 3,
                "reason": "Personal vacation",
                "status": "Pending",
                "reviewed_by": None,
                "reviewed_at": None,
                "review_comment": None,
            },
            user_id=emp_user.id,
            start_date=start,
            end_date=end,
        )
        db.flush()

        # 11. Attendance
        for i in range(5):
            work_date = date.today() - timedelta(days=i)
            _get_or_create(
                db, models.Attendance,
                defaults={
                    "check_in": datetime.combine(work_date, datetime.min.time().replace(hour=9, minute=0), tzinfo=timezone.utc),
                    "check_out": datetime.combine(work_date, datetime.min.time().replace(hour=17, minute=30), tzinfo=timezone.utc),
                    "status": "Present",
                    "note": None,
                },
                user_id=emp_user.id,
                work_date=work_date,
            )
        db.flush()

        # 12. Holidays
        current_year = date.today().year
        for h_date, h_name in [
            (date(current_year, 1, 1), "New Year's Day"),
            (date(current_year, 7, 4), "Independence Day"),
            (date(current_year, 12, 25), "Christmas Day"),
        ]:
            _get_or_create(
                db, models.Holiday,
                defaults={"active": True},
                holiday_date=h_date,
                name=h_name,
                organization_id=org_id,
            )
        db.flush()

        # 13. Compensation
        for emp in [emp_amol, emp_admin]:
            _get_or_create(
                db, models.Compensation,
                defaults={
                    "employment_type": "Permanent",
                    "base_salary": 75000.00,
                    "currency": "USD",
                    "pay_frequency": "monthly",
                    "effective_from": date(current_year, 1, 1),
                    "effective_to": None,
                    "active": True,
                },
                employee_id=emp.id,
            )
        db.flush()

        # 14. Payroll Run
        pr, _ = _get_or_create(
            db, models.PayrollRun,
            defaults={
                "period_start": date(current_year, 1, 1),
                "period_end": date(current_year, 1, 31),
                "pay_date": date(current_year, 2, 5),
                "status": "Paid",
                "total_gross": 150000.00,
                "total_deductions": 25000.00,
                "total_net": 125000.00,
                "employee_count": 2,
                "created_by": admin_user.id,
            },
            name=f"Payroll {current_year}-01",
            organization_id=org_id,
        )
        db.flush()

        # 15. Payslips
        for emp in [emp_amol, emp_admin]:
            _get_or_create(
                db, models.Payslip,
                defaults={
                    "gross_pay": 75000.00,
                    "deductions": 12500.00,
                    "net_pay": 62500.00,
                    "payslip_date": date(current_year, 2, 5),
                    "status": "Paid",
                },
                payroll_run_id=pr.id,
                employee_id=emp.id,
            )
        db.flush()

        # 16. Training Courses
        course_1, _ = _get_or_create(
            db, models.TrainingCourse,
            defaults={"description": "Onboarding basics", "category": "Compliance", "provider": "Internal", "duration_hours": 4, "active": True},
            title="Employee Onboarding",
            organization_id=org_id,
        )
        course_2, _ = _get_or_create(
            db, models.TrainingCourse,
            defaults={"description": "Advanced Python", "category": "Technical", "provider": "Udemy", "duration_hours": 20, "active": True},
            title="Python Programming",
            organization_id=org_id,
        )
        db.flush()

        # 17. Training Enrollments
        _get_or_create(
            db, models.TrainingEnrollment,
            defaults={"status": "Completed", "score": 92.0},
            course_id=course_1.id,
            employee_id=emp_amol.id,
        )
        _get_or_create(
            db, models.TrainingEnrollment,
            defaults={"status": "Enrolled", "score": None},
            course_id=course_2.id,
            employee_id=emp_amol.id,
        )
        db.flush()

        # 18. Goals
        goal_1, _ = _get_or_create(
            db, models.Goal,
            defaults={
                "description": "Deliver Q1 project milestones",
                "category": "Performance",
                "status": "Active",
                "target_date": date(current_year, 3, 31),
                "progress": 60,
                "created_by": admin_user.id,
            },
            employee_id=emp_amol.id,
            title="Q1 Delivery Goals",
            organization_id=org_id,
        )
        db.flush()

        # 19. Review Cycle
        rc, _ = _get_or_create(
            db, models.ReviewCycle,
            defaults={
                "start_date": date(current_year, 1, 1),
                "end_date": date(current_year, 3, 31),
                "status": "Completed",
            },
            name=f"Q1 {current_year} Review Cycle",
            organization_id=org_id,
        )
        db.flush()

        # 20. Performance Review
        _get_or_create(
            db, models.PerformanceReview,
            defaults={
                "reviewer_id": admin_user.id,
                "overall_rating": 4.5,
                "comments": "Strong performance this quarter.",
                "status": "Finalized",
                "submitted_at": datetime.now(timezone.utc),
            },
            review_cycle_id=rc.id,
            employee_id=emp_amol.id,
        )
        db.flush()

        # 21. Requisitions
        req, _ = _get_or_create(
            db, models.Requisition,
            defaults={
                "department": "Engineering",
                "employment_type": "Permanent",
                "status": "Open",
                "created_by": admin_user.id,
                "closed_at": None,
            },
            title="Senior Backend Engineer",
            organization_id=org_id,
        )
        db.flush()

        # 22. Candidates & Applications
        cand, _ = _get_or_create(
            db, models.Candidate,
            defaults={
                "phone": "+1-555-0100",
                "status": "Applied",
                "resume_url": "https://example.com/resumes/alice.pdf",
            },
            requisition_id=req.id,
            name="Alice Johnson",
            email="alice.johnson@example.com",
            organization_id=org_id,
        )
        db.flush()

        _get_or_create(
            db, models.Application,
            defaults={"stage": "Screening", "score": None, "notes": "Good initial profile"},
            candidate_id=cand.id,
        )
        db.flush()

        # 23. Module catalog is managed by the backend (seed_default_modules).
        # Remove any legacy "dashboard" module created by older seed versions so
        # the full default module catalog can be seeded cleanly.
        legacy_dashboard = db.query(models.Module).filter_by(
            organization_id=org_id, module_key="dashboard"
        ).first()
        if legacy_dashboard is not None:
            db.query(models.RoleModulePermission).filter_by(module_id=legacy_dashboard.id).delete()
            db.delete(legacy_dashboard)
            db.flush()
        db.flush()

        # 24. Notifications
        _get_or_create(
            db, models.Notification,
            defaults={"category": "General", "read": False, "created_by": admin_user.id},
            user_id=emp_user.id,
            title="Welcome to Nexora",
            message="Your account has been set up successfully.",
            organization_id=org_id,
        )
        db.flush()

        # 25. Announcements
        _get_or_create(
            db, models.Announcement,
            defaults={"body": "Welcome to the new HRMS portal. Please complete your profile.", "pinned": True, "created_by": admin_user.id},
            title="Portal Launch",
            organization_id=org_id,
        )
        db.flush()

        db.commit()
        print("Seed data created successfully.")
        print(f"  Organization: {ORG_NAME} (id={org_id})")
        print(f"  User 1: amoln52@gmail.com (Employee, password: {PASSWORD})")
        print(f"  User 2: amolnavgire2611@gmail.com (Super Admin, password: {PASSWORD})")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()