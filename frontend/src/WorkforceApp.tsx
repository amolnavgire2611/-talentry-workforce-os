import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, clearAccessToken, getAccessToken, getCsrfToken, jsonBody, refreshAccessToken } from "./lib/api";
import AuthScreen from "./features/auth/AuthScreen";
import SessionManager, { type RefreshSession } from "./features/auth/SessionManager";
import OrganizationStructure from "./features/organization/OrganizationStructure";
import EmployeeProfilePanel from "./features/employees/EmployeeProfilePanel";
import "./WorkforceApp.css";

type User = { id: number; name: string; email: string; role: string; active: boolean; registration_pending?: boolean };
type Organization = { id: number; name: string; slug: string; active: boolean; created_at: string };
type Employee = { id: number; employee_code: string; name: string; department: string; role: string; status: string; user_id?: number | null; branch_id?: number | null; designation_id?: number | null; job_grade_id?: number | null; reporting_manager_id?: number | null };
type Department = { id: number; name: string; description: string | null; active: boolean; created_at: string };
type Attendance = { id: number; user_id: number; work_date: string; check_in: string; check_out: string | null; status: string };
type LeaveRequest = { id: number; user_id: number; start_date: string; end_date: string; leave_type_id: number | null; leave_type: string | null; half_day: boolean; days_requested: number; reason: string; status: string; reviewed_by: number | null; reviewed_at: string | null; review_comment: string | null; created_at: string };
type LeaveType = { id: number; name: string; description: string | null; annual_allowance_days: number; paid: boolean; active: boolean };
type LeaveBalance = { id: number; leave_type_id: number; leave_type: string; year: number; allocated_days: number; used_days: number; pending_days: number; remaining_days: number };
type Page<T> = { items: T[]; total: number; limit: number; offset: number };
type Dashboard = { scope: "organization" | "department" | "personal" | "recruitment" | "payroll" | "attendance"; employee_count: number | null; active_employee_count: number | null; employees_on_leave_count: number | null; department_count: number | null; present_today: number; pending_leave_requests: number; my_pending_leave_requests: number };
type Branch = { id: number; code: string; name: string; address: string | null; active: boolean; created_at: string };
type Designation = { id: number; name: string; description: string | null; active: boolean; created_at: string };
type JobGrade = { id: number; code: string; name: string; description: string | null; rank: number; active: boolean; created_at: string };
type PayrollRun = { id: number; name: string; period_start: string; period_end: string; pay_date: string; status: string; total_gross: number; total_deductions: number; total_net: number; employee_count: number; created_by: number | null; created_at: string; finalized_at: string | null };
type Payslip = { id: number; payroll_run_id: number; employee_id: number; employee_name: string | null; gross_pay: number; deductions: number; net_pay: number; payslip_date: string; status: string; created_at: string };
type Requisition = { id: number; title: string; department: string | null; employment_type: string; status: string; created_by: number | null; created_at: string; closed_at: string | null };
type Candidate = { id: number; requisition_id: number; name: string; email: string; phone: string | null; status: string; resume_url: string | null; applied_at: string };
type Goal = { id: number; employee_id: number; title: string; description: string | null; category: string; status: string; target_date: string | null; progress: number; created_by: number | null; created_at: string; updated_at: string };
type ReviewCycle = { id: number; name: string; start_date: string; end_date: string; status: string; created_at: string };
type PerformanceReview = { id: number; review_cycle_id: number; employee_id: number; reviewer_id: number | null; overall_rating: string | number | null; comments: string | null; status: string; submitted_at: string | null; created_at: string; updated_at: string };
type TrainingCourse = { id: number; title: string; description: string | null; category: string; provider: string | null; duration_hours: string | number; active: boolean; created_at: string };
type TrainingEnrollment = { id: number; course_id: number; employee_id: number; status: string; score: string | number | null; enrolled_at: string; completed_at: string | null };
type AppNotification = { id: number; user_id: number; title: string; message: string; category: string; read: boolean; created_at: string };
type Announcement = { id: number; title: string; body: string; pinned: boolean; created_by: number | null; created_at: string; expires_at: string | null };
type ReportSummary = { employee_count: number; active_employee_count: number; department_count: number; pending_leave_requests: number; present_today: number; payroll_gross_total: string; payroll_deductions_total: string; payroll_net_total: string; open_requisitions: number; active_training_enrollments: number };
type ModulePermission = { id: number; module_id: number; role: string; granted: boolean; created_at: string };
type Module = { id: number; module_key: string; name: string; description: string | null; parent_id: number | null; active: boolean; created_at: string; permissions: ModulePermission[] };
type MyPermissions = { accessible_modules: string[]; modules: Module[] };
type Section = string;

const MODULE_LABELS: Record<string, { label: string; icon: string }> = {
  overview: { label: "Overview", icon: "◫" },
  employees: { label: "Employees", icon: "♙" },
  departments: { label: "Departments", icon: "▤" },
  organization: { label: "Organization structure", icon: "⌂" },
  attendance: { label: "Attendance", icon: "◷" },
  leave: { label: "Leave management", icon: "▧" },
  users: { label: "Access & users", icon: "♧" },
  payroll: { label: "Payroll", icon: "💰" },
  recruitment: { label: "Recruitment", icon: "📋" },
  performance: { label: "Performance", icon: "◎" },
  learning: { label: "Learning", icon: "🎓" },
  notifications: { label: "Notifications", icon: "🔔" },
  reports: { label: "Reports", icon: "📊" },
  settings: { label: "Account settings", icon: "⚙" },
  "module-access": { label: "Module Access", icon: "🔐" },
};

const MODULE_ROLES = ["Super Admin", "Organization Admin", "HR Administrator", "HR Manager", "Department Manager", "Recruiter", "Payroll Administrator", "Attendance Administrator", "Employee"];

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function dateLabel(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

function timeLabel(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function ModuleTree({
  module,
  modules,
  depth = 0,
  moduleAccessDraft,
  setModuleAccessDraft,
  busy,
  removeModule,
}: {
  module: Module;
  modules: Module[];
  depth?: number;
  moduleAccessDraft: Record<string, boolean>;
  setModuleAccessDraft: (
    val: Record<string, boolean> | ((prev: Record<string, boolean>) => Record<string, boolean>)
  ) => void;
  busy: boolean;
  removeModule: (module: Module) => void;
}) {
  const [loading, setLoading] = useState(true);
  const [local, setLocal] = useState(module);
  const [checking, setChecking] = useState(false);
  const childCount = modules.filter((m) => m.parent_id === module.id).length;
  const toggle = () => {
    setChecking(true);
    setTimeout(() => { setLocal((l) => ({ ...l, active: !l.active })); setChecking(false); }, 200);
  };
  return (
    <tr>
      <td style={{ paddingLeft: `${18 + depth * 18}px` }}>
        <div className="tree-row" onClick={() => toggle()}>
          <span className={"tree-toggle" + (local.active ? " open" : "")}></span>
          <input
            type="checkbox"
            checked={local.active}
            disabled={checking}
            onChange={toggle}
            aria-label={`Toggle ${local.name}`}
          />
          <span className="tree-name">{local.name}</span>
          {childCount > 0 && <span className="tree-count">{childCount}</span>}
        </div>
        {(local.active || !local.active) && modules.filter((m) => m.parent_id === module.id).map((child) => (
          <ModuleTree
            key={child.id}
            module={child}
            modules={modules}
            depth={depth + 1}
            moduleAccessDraft={moduleAccessDraft}
            setModuleAccessDraft={setModuleAccessDraft}
            busy={busy}
            removeModule={removeModule}
          />
        ))}
      </td>
      <td style={{ paddingLeft: `${18 + depth * 18 + 12}px` }}><small>{local.description ?? "—"}</small></td>
      {MODULE_ROLES.map((role) => (
        <td key={role}>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={local.permissions.find((p) => p.role === role)?.granted ?? false}
              onChange={(event) => setModuleAccessDraft({ ...moduleAccessDraft, [`${local.module_key}:${role}`]: event.target.checked })}
            />
            <span className="checkmark"></span>
          </label>
        </td>
      ))}
      <td style={{ paddingTop: "6px", paddingBottom: "6px" }}>
        <button className="icon-button" title="Delete module" onClick={() => removeModule(module)} disabled={busy}>
          <span aria-hidden="true">✕</span>
        </button>
      </td>
    </tr>
  );
}

export default function WorkforceApp() {
  const [user, setUser] = useState<User | null>(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [loginNotice, setLoginNotice] = useState<string | null>(null);
  const [active, setActive] = useState<Section>("overview");
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [organizationName, setOrganizationName] = useState("");
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeTotal, setEmployeeTotal] = useState(0);
  const [employeeOffset, setEmployeeOffset] = useState(0);
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [employeeQuery, setEmployeeQuery] = useState("");
  const [employeeForm, setEmployeeForm] = useState(false);
  const [profileName, setProfileName] = useState("");
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [profileEmployee, setProfileEmployee] = useState<Employee | null>(null);
  const [employeeDraft, setEmployeeDraft] = useState({ employee_code: "", name: "", department: "", role: "", status: "Active", branch_id: "", designation_id: "", job_grade_id: "", reporting_manager_id: "" });
  const [employeeOptions, setEmployeeOptions] = useState<Employee[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [jobGrades, setJobGrades] = useState<JobGrade[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [departmentTotal, setDepartmentTotal] = useState(0);
  const [departmentName, setDepartmentName] = useState("");
  const [departmentDescription, setDepartmentDescription] = useState("");
  const [attendance, setAttendance] = useState<Page<Attendance> | null>(null);
  const [leaveRequests, setLeaveRequests] = useState<Page<LeaveRequest> | null>(null);
  const [leaveDraft, setLeaveDraft] = useState({ start_date: "", end_date: "", leave_type_id: "", half_day: false, reason: "" });
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([]);
  const [leaveBalances, setLeaveBalances] = useState<LeaveBalance[]>([]);
  const [payrollRuns, setPayrollRuns] = useState<PayrollRun[]>([]);
  const [payslips, setPayslips] = useState<Payslip[]>([]);
  const [payrollRunDraft, setPayrollRunDraft] = useState({ name: "", period_start: "", period_end: "", pay_date: "" });
  const [showPayrollForm, setShowPayrollForm] = useState(false);
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [requisitionDraft, setRequisitionDraft] = useState({ title: "", department: "", employment_type: "Permanent" });
  const [candidateDraft, setCandidateDraft] = useState({ requisition_id: "", name: "", email: "", phone: "" });
  const [showRequisitionForm, setShowRequisitionForm] = useState(false);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [reviewCycles, setReviewCycles] = useState<ReviewCycle[]>([]);
  const [reviews, setReviews] = useState<PerformanceReview[]>([]);
  const [goalDraft, setGoalDraft] = useState({ employee_id: "", title: "", description: "", category: "Performance", target_date: "" });
  const [cycleDraft, setCycleDraft] = useState({ name: "", start_date: "", end_date: "" });
  const [reviewDraft, setReviewDraft] = useState({ review_cycle_id: "", employee_id: "", overall_rating: "", comments: "" });
  const [showGoalForm, setShowGoalForm] = useState(false);
  const [showCycleForm, setShowCycleForm] = useState(false);
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [courses, setCourses] = useState<TrainingCourse[]>([]);
  const [enrollments, setEnrollments] = useState<TrainingEnrollment[]>([]);
  const [courseDraft, setCourseDraft] = useState({ title: "", description: "", category: "General", provider: "", duration_hours: "2" });
  const [enrollmentDraft, setEnrollmentDraft] = useState({ course_id: "", employee_id: "" });
  const [showCourseForm, setShowCourseForm] = useState(false);
  const [showEnrollmentForm, setShowEnrollmentForm] = useState(false);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [announcementDraft, setAnnouncementDraft] = useState({ title: "", body: "", pinned: false });
  const [notificationDraft, setNotificationDraft] = useState({ title: "", message: "", category: "General" });
  const [showAnnouncementForm, setShowAnnouncementForm] = useState(false);
  const [showNotificationForm, setShowNotificationForm] = useState(false);
  const [reportSummary, setReportSummary] = useState<ReportSummary | null>(null);
  const [leavePolicyDraft, setLeavePolicyDraft] = useState({ name: "", description: "", annual_allowance_days: "20", paid: true });
  const [showLeavePolicyForm, setShowLeavePolicyForm] = useState(false);
  const [users, setUsers] = useState<Page<User> | null>(null);
  const [passwordDraft, setPasswordDraft] = useState({ current_password: "", new_password: "" });
  const [sessions, setSessions] = useState<RefreshSession[]>([]);
  const [invitationDraft, setInvitationDraft] = useState({ name: "", email: "", role: "Employee", department_id: "", employee_id: "" });
  const [moduleAccessDraft, setModuleAccessDraft] = useState<Record<string, boolean>>({});
  const [showModuleForm, setShowModuleForm] = useState(false);
  const [moduleDraft, setModuleDraft] = useState({ module_key: "", name: "", description: "", parent_id: "" });
  const [issuedInvitation, setIssuedInvitation] = useState<{ email: string; token: string; expires_at: string } | null>(null);
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [mfaEnrolling, setMfaEnrolling] = useState(false);
  const [mfaSecret, setMfaSecret] = useState<string | null>(null);
  const [mfaBackupCodes, setMfaBackupCodes] = useState<string[]>([]);
  const [mfaVerifying, setMfaVerifying] = useState(false);
  const [mfaVerifyingCode, setMfaVerifyingCode] = useState("");

  const [modules, setModules] = useState<Module[]>([]);
  const [accessibleModules, setAccessibleModules] = useState<string[]>([]);
  const [modulesLoaded, setModulesLoaded] = useState(false);

  const canManage = user ? modulesLoaded && accessibleModules.includes("employees") : false;
  const canCreateEmployee = canManage || user?.role === "Organization Admin";
  const canManageDepartments = modulesLoaded && accessibleModules.includes("departments");
  const canAdminUsers = modulesLoaded && accessibleModules.includes("users");
  const canAdminOrganization = modulesLoaded && accessibleModules.includes("organization");
  const canManageOrganizationStructure = modulesLoaded && accessibleModules.includes("organization");
  const canAdminPayroll = modulesLoaded && accessibleModules.includes("payroll");
  const canManageRecruitment = modulesLoaded && accessibleModules.includes("recruitment");
  const canReviewLeave = modulesLoaded && accessibleModules.includes("leave");
  const canManageLeavePolicy = modulesLoaded && accessibleModules.includes("leave");
  const canManagePerformance = modulesLoaded && accessibleModules.includes("performance");
  const canManageLearning = modulesLoaded && accessibleModules.includes("learning");
  const canSendNotifications = modulesLoaded && accessibleModules.includes("notifications");
  const canViewReports = modulesLoaded && accessibleModules.includes("reports");
  const canManageModuleAccess = modulesLoaded && accessibleModules.includes("module-access");
  const userRole = user?.role;
  const todayAttendance = attendance?.items.find((row) => row.user_id === user?.id && row.work_date === new Date().toISOString().slice(0, 10));

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setEmployeeOffset(0);
      setEmployeeQuery(employeeSearch.trim());
    }, 250);
    return () => window.clearTimeout(timer);
  }, [employeeSearch]);

  const loadModules = useCallback(async () => {
    try {
      const perms = await api<MyPermissions>("/api/my-permissions");
      setModules(perms.modules);
      setAccessibleModules(perms.accessible_modules);
      setModulesLoaded(true);
    } catch (error) {
      setNotice({ kind: "error", text: errorMessage(error) });
      setModules([]);
      setAccessibleModules([]);
      setModulesLoaded(true);
    }
  }, []);

  const loadSession = useCallback(async () => {
    if (!getAccessToken() && getCsrfToken()) {
      await refreshAccessToken();
    }
    if (!getAccessToken()) {
      setCheckingSession(false);
      return;
    }
    try {
      setUser(await api<User>("/api/auth/me"));
    } catch {
      clearAccessToken();
      setUser(null);
    } finally {
      setCheckingSession(false);
    }
  }, []);

  const loadDashboard = useCallback(async () => {
    try { setDashboard(await api<Dashboard>("/api/dashboard")); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadOrganization = useCallback(async () => {
    try {
      const current = await api<Organization>("/api/organization");
      setOrganization(current);
      setOrganizationName(current.name);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadEmployees = useCallback(async () => {
    try {
      if (userRole === "Employee") {
        const profile = await api<Employee>("/api/employees/me");
        setEmployees([profile]);
        setEmployeeTotal(1);
        setProfileName(profile.name);
        return;
      }
      if (active === "users") {
        const rows = await api<Employee[]>("/api/employees?limit=100&offset=0");
        setEmployees(rows);
        setEmployeeTotal(rows.length);
        return;
      }
      const params = new URLSearchParams({ limit: "10", offset: String(employeeOffset) });
      if (employeeQuery) params.set("search", employeeQuery);
      const page = await api<Page<Employee>>(`/api/employees/directory?${params}`);
      setEmployees(page.items);
      setEmployeeTotal(page.total);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, [active, employeeOffset, employeeQuery, userRole]);

  const loadEmployeeOptions = useCallback(async () => {
    try {
      const [rows, branchPage, designationPage, gradePage] = await Promise.all([
        api<Employee[]>("/api/employees?limit=100&offset=0"),
        api<Page<Branch>>("/api/branches?limit=100&offset=0"),
        api<Page<Designation>>("/api/designations?limit=100&offset=0"),
        api<Page<JobGrade>>("/api/job-grades?limit=100&offset=0"),
      ]);
      setEmployeeOptions(rows);
      setBranches(branchPage.items);
      setDesignations(designationPage.items);
      setJobGrades(gradePage.items);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadDepartments = useCallback(async () => {
    try {
      const page = await api<Page<Department>>("/api/departments?limit=100&offset=0");
      setDepartments(page.items);
      setDepartmentTotal(page.total);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadAttendance = useCallback(async () => {
    try { setAttendance(await api<Page<Attendance>>("/api/attendance?limit=100&offset=0")); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadLeave = useCallback(async () => {
    try {
      const [requests, types, balances] = await Promise.all([
        api<Page<LeaveRequest>>("/api/leave-requests?limit=100&offset=0"),
        api<LeaveType[]>("/api/leave-types"),
        api<LeaveBalance[]>("/api/leave-balances"),
      ]);
      setLeaveRequests(requests);
      setLeaveTypes(types);
      setLeaveBalances(balances);
      setLeaveDraft((current) => current.leave_type_id || !types.length ? current : { ...current, leave_type_id: String(types[0].id) });
    }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadPayroll = useCallback(async () => {
    try {
      const [runs, slips] = await Promise.all([
        api<PayrollRun[]>("/api/payroll/runs?limit=100&offset=0"),
        api<Payslip[]>("/api/payroll/payslips?limit=100&offset=0"),
      ]);
      setPayrollRuns(runs);
      setPayslips(slips);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadRecruitment = useCallback(async () => {
    try {
      const [reqs, cands] = await Promise.all([
        api<Requisition[]>("/api/recruitment/requisitions?limit=100&offset=0"),
        api<Candidate[]>("/api/recruitment/candidates?limit=100&offset=0"),
      ]);
      setRequisitions(reqs);
      setCandidates(cands);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadPerformance = useCallback(async () => {
    try {
      const [goalRows, cycleRows, reviewRows] = await Promise.all([
        api<Goal[]>("/api/performance/goals"),
        api<ReviewCycle[]>("/api/performance/review-cycles"),
        api<PerformanceReview[]>("/api/performance/reviews"),
      ]);
      setGoals(goalRows);
      setReviewCycles(cycleRows);
      setReviews(reviewRows);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadLearning = useCallback(async () => {
    try {
      const [courseRows, enrollmentRows] = await Promise.all([
        api<TrainingCourse[]>("/api/learning/courses"),
        api<TrainingEnrollment[]>("/api/learning/enrollments"),
      ]);
      setCourses(courseRows);
      setEnrollments(enrollmentRows);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadNotifications = useCallback(async () => {
    try {
      const [notificationRows, announcementRows] = await Promise.all([
        api<AppNotification[]>("/api/notifications"),
        api<Announcement[]>("/api/announcements"),
      ]);
      setNotifications(notificationRows);
      setAnnouncements(announcementRows);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadReports = useCallback(async () => {
    try { setReportSummary(await api<ReportSummary>("/api/reports/summary")); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadUsers = useCallback(async () => {
    try { setUsers(await api<Page<User>>("/api/users?limit=100&offset=0")); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  const loadSessions = useCallback(async () => {
    try { setSessions(await api<RefreshSession[]>("/api/auth/sessions")); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }, []);

  useEffect(() => { void Promise.resolve().then(loadSession); }, [loadSession]);
  // Load the module catalog/permissions whenever a user becomes available
  // (initial session restore AND fresh login). Modules are reset whenever
  // the session ends (sign-out / password change / ended current session) so
  // a subsequent account never inherits the previous user's menu, and again
  // if reloading permissions fails so a stale menu is never shown.
  useEffect(() => {
    if (user) {
      void Promise.resolve().then(loadModules);
    }
  }, [user, loadModules]);
  useEffect(() => {
    if (user && active === "settings") void Promise.resolve().then(loadSessions);
  }, [user, active, loadSessions]);
  useEffect(() => {
    if (user && active === "settings" && canAdminOrganization) void Promise.resolve().then(loadOrganization);
  }, [user, active, canAdminOrganization, loadOrganization]);
  useEffect(() => {
    if (!user) return;
    void Promise.resolve().then(loadDashboard);
  }, [user, loadDashboard]);
  useEffect(() => {
    if (user && active === "employees") {
      void Promise.resolve().then(loadEmployees);
      if (user.role !== "Employee") void Promise.resolve().then(loadEmployeeOptions);
    }
  }, [user, active, loadEmployees, loadEmployeeOptions]);
  useEffect(() => {
    if (user && active === "departments") void Promise.resolve().then(loadDepartments);
  }, [user, active, loadDepartments]);
  useEffect(() => {
    if (user && active === "attendance") void Promise.resolve().then(loadAttendance);
  }, [user, active, loadAttendance]);
  useEffect(() => {
    if (user && active === "leave") void Promise.resolve().then(loadLeave);
  }, [user, active, loadLeave]);
  useEffect(() => {
    if (user && active === "payroll") void Promise.resolve().then(loadPayroll);
  }, [user, active, loadPayroll]);
  useEffect(() => {
    if (user && active === "recruitment") void Promise.resolve().then(loadRecruitment);
  }, [user, active, loadRecruitment]);
  useEffect(() => {
    if (user && active === "performance") {
      void Promise.resolve().then(loadPerformance);
      if (user.role !== "Employee") void Promise.resolve().then(loadEmployeeOptions);
    }
  }, [user, active, loadPerformance, loadEmployeeOptions]);
  useEffect(() => {
    if (user && active === "learning") {
      void Promise.resolve().then(loadLearning);
      if (canManageLearning && user.role !== "Employee") void Promise.resolve().then(loadEmployeeOptions);
    }
  }, [user, active, canManageLearning, loadLearning, loadEmployeeOptions]);
  useEffect(() => {
    if (user && active === "notifications") void Promise.resolve().then(loadNotifications);
  }, [user, active, loadNotifications]);
  useEffect(() => {
    if (user && active === "reports" && canViewReports) void Promise.resolve().then(loadReports);
  }, [user, active, canViewReports, loadReports]);
  useEffect(() => {
    if (user && active === "users" && canAdminUsers) {
      void Promise.resolve().then(loadUsers);
      void Promise.resolve().then(loadDepartments);
      void Promise.resolve().then(loadEmployees);
    }
  }, [user, active, canAdminUsers, loadUsers, loadDepartments, loadEmployees]);

  async function signOut() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* The access token is still cleared locally. */ }
    clearAccessToken(); setUser(null); setActive("overview"); setNotice({ kind: "success", text: "You have been signed out." });
  }

  async function endSession(session: RefreshSession) {
    setBusy(true);
    try {
      await api<void>(`/api/auth/sessions/${session.id}`, { method: "DELETE" });
      if (session.current) {
        clearAccessToken();
        setLoginNotice("This session was ended. Sign in again to continue.");
        setUser(null);
      } else {
        setNotice({ kind: "success", text: "The selected session was ended." });
        await loadSessions();
      }
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function endOtherSessions() {
    setBusy(true);
    try {
      await api<void>("/api/auth/sessions", { method: "DELETE" });
      clearAccessToken();
      setLoginNotice("All sessions were ended. Sign in again to continue.");
      setUser(null);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function saveEmployee(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice(null);
    try {
      await api<Employee>(editingEmployee ? `/api/employees/${editingEmployee.id}` : "/api/employees", {
        method: editingEmployee ? "PUT" : "POST", body: jsonBody({
          ...employeeDraft,
          branch_id: employeeDraft.branch_id ? Number(employeeDraft.branch_id) : null,
          designation_id: employeeDraft.designation_id ? Number(employeeDraft.designation_id) : null,
          job_grade_id: employeeDraft.job_grade_id ? Number(employeeDraft.job_grade_id) : null,
          reporting_manager_id: employeeDraft.reporting_manager_id ? Number(employeeDraft.reporting_manager_id) : null,
        }),
      });
      setNotice({ kind: "success", text: editingEmployee ? "Employee profile updated." : "Employee added to the directory." });
      setEmployeeForm(false); setEditingEmployee(null); setEmployeeDraft({ employee_code: "", name: "", department: "", role: "", status: "Active", branch_id: "", designation_id: "", job_grade_id: "", reporting_manager_id: "" });
      await Promise.all([loadEmployees(), loadDashboard()]);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function saveMyProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      const profile = await api<Employee>("/api/employees/me", { method: "PUT", body: jsonBody({ name: profileName }) });
      setEmployees([profile]);
      setUser((current) => current ? { ...current, name: profile.name } : current);
      setNotice({ kind: "success", text: "Your display name was updated." });
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function editEmployee(employee: Employee) {
    try {
      const profile = await api<Employee>(`/api/employees/${employee.id}`);
      setEditingEmployee(profile);
      setEmployeeDraft({ employee_code: profile.employee_code, name: profile.name, department: profile.department, role: profile.role, status: profile.status, branch_id: profile.branch_id ? String(profile.branch_id) : "", designation_id: profile.designation_id ? String(profile.designation_id) : "", job_grade_id: profile.job_grade_id ? String(profile.job_grade_id) : "", reporting_manager_id: profile.reporting_manager_id ? String(profile.reporting_manager_id) : "" });
      setEmployeeForm(true);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function removeEmployee(employee: Employee) {
    if (!window.confirm(`Remove ${employee.name} from the directory?`)) return;
    try { await api<void>(`/api/employees/${employee.id}`, { method: "DELETE" }); setNotice({ kind: "success", text: "Employee removed." }); await Promise.all([loadEmployees(), loadDashboard()]); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function saveDepartment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<Department>("/api/departments", { method: "POST", body: jsonBody({ name: departmentName, description: departmentDescription || null }) });
      setDepartmentName(""); setDepartmentDescription(""); setNotice({ kind: "success", text: "Department created." }); await Promise.all([loadDepartments(), loadDashboard()]);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function saveOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      const updated = await api<Organization>("/api/organization", {
        method: "PATCH", body: jsonBody({ name: organizationName }),
      });
      setOrganization(updated);
      setOrganizationName(updated.name);
      setNotice({ kind: "success", text: "Organization profile updated." });
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function toggleDepartment(department: Department) {
    try {
      await api<Department>(`/api/departments/${department.id}`, { method: "PUT", body: jsonBody({ name: department.name, description: department.description, active: !department.active }) });
      setNotice({ kind: "success", text: `Department ${department.active ? "archived" : "activated"}.` }); await loadDepartments();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function clock(action: "clock-in" | "clock-out") {
    try { await api<Attendance>(`/api/attendance/${action}`, { method: "POST" }); setNotice({ kind: "success", text: action === "clock-in" ? "Your attendance has been recorded." : "Your check-out has been recorded." }); await Promise.all([loadAttendance(), loadDashboard()]); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function saveCandidate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try { await api<Candidate>("/api/recruitment/candidates", { method: "POST", body: jsonBody({ ...candidateDraft, requisition_id: Number(candidateDraft.requisition_id) }) }); setNotice({ kind: "success", text: "Candidate added." }); setCandidateDraft({ requisition_id: "", name: "", email: "", phone: "" }); setShowCandidateForm(false); await loadRecruitment(); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function submitLeave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try { await api<LeaveRequest>("/api/leave-requests", { method: "POST", body: jsonBody({ ...leaveDraft, leave_type_id: Number(leaveDraft.leave_type_id) }) }); setLeaveDraft({ start_date: "", end_date: "", leave_type_id: leaveTypes[0] ? String(leaveTypes[0].id) : "", half_day: false, reason: "" }); setNotice({ kind: "success", text: "Leave request submitted for review." }); await Promise.all([loadLeave(), loadDashboard()]); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function saveLeavePolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<LeaveType>("/api/leave-types", { method: "POST", body: jsonBody({ ...leavePolicyDraft, annual_allowance_days: Number(leavePolicyDraft.annual_allowance_days) }) });
      setLeavePolicyDraft({ name: "", description: "", annual_allowance_days: "20", paid: true });
      setShowLeavePolicyForm(false);
      setNotice({ kind: "success", text: "Leave type and annual allowance created." });
      await loadLeave();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function toggleLeavePolicy(policy: LeaveType) {
    try {
      await api<LeaveType>(`/api/leave-types/${policy.id}`, { method: "PUT", body: jsonBody({ ...policy, active: !policy.active }) });
      setNotice({ kind: "success", text: `${policy.name} leave type ${policy.active ? "archived" : "reactivated"}.` });
      await loadLeave();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function reviewLeave(request: LeaveRequest, decision: "Approved" | "Rejected") {
    const comment = decision === "Rejected" ? window.prompt("Add a reason for declining this request:") : window.prompt("Optional approval note:") ?? "";
    if (decision === "Rejected" && comment === null) return;
    try { await api<LeaveRequest>(`/api/leave-requests/${request.id}/review`, { method: "POST", body: jsonBody({ decision, comment: comment || null }) }); setNotice({ kind: "success", text: `Request ${decision.toLowerCase()}.` }); await Promise.all([loadLeave(), loadDashboard()]); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function cancelLeave(request: LeaveRequest) {
    if (!window.confirm("Cancel this leave request? Future approved leave will be returned to your balance.")) return;
    try { await api<LeaveRequest>(`/api/leave-requests/${request.id}/cancel`, { method: "POST" }); setNotice({ kind: "success", text: "Leave request cancelled." }); await Promise.all([loadLeave(), loadDashboard()]); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function saveModule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<Module>('/api/modules', { method: 'POST', body: jsonBody({
        module_key: moduleDraft.module_key,
        name: moduleDraft.name,
        description: moduleDraft.description || null,
        ...(moduleDraft.parent_id ? { parent_id: Number(moduleDraft.parent_id) } : {}),
      }) });
      setShowModuleForm(false);
      setModuleDraft({ module_key: '', name: '', description: '', parent_id: '' });
      setNotice({ kind: 'success', text: 'Module created.' });
      await loadModules();
    } catch (error) { setNotice({ kind: 'error', text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function removeModule(module: Module) {
    if (!window.confirm('Delete this module and its submodules?')) return;
    try { await api<void>(`/api/modules/${module.id}`, { method: 'DELETE' }); setNotice({ kind: 'success', text: 'Module deleted.' }); await loadModules(); }
    catch (error) { setNotice({ kind: 'error', text: errorMessage(error) }); }
  }

  async function changeUser(userId: number, patch: { role?: string; active?: boolean }) {
    try { await api<User>(`/api/users/${userId}`, { method: "PATCH", body: jsonBody(patch) }); setNotice({ kind: "success", text: "Account access updated." }); await loadUsers(); }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function provisionAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setIssuedInvitation(null);
    try {
      const payload = {
        name: invitationDraft.name,
        email: invitationDraft.email,
        role: invitationDraft.role,
        ...(invitationDraft.department_id ? { department_id: Number(invitationDraft.department_id) } : {}),
        ...(invitationDraft.role === "Employee" && invitationDraft.employee_id ? { employee_id: Number(invitationDraft.employee_id) } : {}),
      };
      const result = await api<{ user: User; invitation_token: string; expires_at: string }>("/api/users/invitations", {
        method: "POST", body: jsonBody(payload),
      });
      setIssuedInvitation({ email: result.user.email, token: result.invitation_token, expires_at: result.expires_at });
      setInvitationDraft({ name: "", email: "", role: "Employee", department_id: "", employee_id: "" });
      setNotice({ kind: "success", text: "Registration invitation created. Share its one-time code with the invitee through a trusted channel." });
      await loadUsers();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function reissueRegistrationCode(account: User) {
    setBusy(true);
    try {
      const result = await api<{ user: User; invitation_token: string; expires_at: string }>(
        `/api/users/${account.id}/invitation`, { method: "POST" },
      );
      setIssuedInvitation({ email: result.user.email, token: result.invitation_token, expires_at: result.expires_at });
      setNotice({ kind: "success", text: `A new registration code was issued for ${result.user.email}. The previous code no longer works.` });
      await loadUsers();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<void>("/api/auth/password", { method: "POST", body: jsonBody(passwordDraft) });
      clearAccessToken();
      setPasswordDraft({ current_password: "", new_password: "" });
      setLoginNotice("Password updated. Sign in with your new password.");
      setUser(null);
    }
    catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function enrollMFA() {
    setMfaEnrolling(true); setNotice(null);
    try {
      const result = await api<{ id: number; factor_type: string; verified: boolean; created_at: string; secret: string; backup_codes: string[] }>("/api/auth/mfa/enrollment", { method: "POST" });
      setMfaSecret(result.secret);
      setMfaBackupCodes(result.backup_codes);
      setMfaVerifying(true);
      setNotice({ kind: "success", text: "Save your backup codes and setup key, then verify with a code from your authenticator app." });
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setMfaEnrolling(false); }
  }

  async function verifyMFA(code: string) {
    setBusy(true);
    try {
      await api<void>("/api/auth/mfa/verify", { method: "POST", body: jsonBody({ code }) });
      setMfaEnabled(true);
      setMfaVerifying(false);
      setMfaSecret(null);
      setMfaBackupCodes([]);
      setNotice({ kind: "success", text: "MFA is now active on your account." });
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function removeMFA() {
    if (!window.confirm("Remove MFA from your account? You will lose access to backup codes.")) return;
    setBusy(true);
    try {
      await api<void>("/api/auth/mfa/enrollment", { method: "DELETE" });
      setMfaEnabled(false);
      setNotice({ kind: "success", text: "MFA removed from your account." });
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function saveGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<Goal>("/api/performance/goals", { method: "POST", body: jsonBody({ employee_id: Number(goalDraft.employee_id), title: goalDraft.title, description: goalDraft.description || null, category: goalDraft.category, target_date: goalDraft.target_date || null }) });
      setGoalDraft({ employee_id: "", title: "", description: "", category: "Performance", target_date: "" });
      setShowGoalForm(false);
      setNotice({ kind: "success", text: "Goal created." });
      await loadPerformance();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function updateGoal(goal: Goal, progress: number, status: string) {
    try {
      await api<Goal>(`/api/performance/goals/${goal.id}`, { method: "PATCH", body: jsonBody({ progress, status }) });
      setNotice({ kind: "success", text: "Goal updated." });
      await loadPerformance();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function saveReviewCycle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<ReviewCycle>("/api/performance/review-cycles", { method: "POST", body: jsonBody(cycleDraft) });
      setCycleDraft({ name: "", start_date: "", end_date: "" });
      setShowCycleForm(false);
      setNotice({ kind: "success", text: "Review cycle created." });
      await loadPerformance();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function saveReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<PerformanceReview>("/api/performance/reviews", { method: "POST", body: jsonBody({
        review_cycle_id: Number(reviewDraft.review_cycle_id),
        employee_id: Number(reviewDraft.employee_id),
        ...(reviewDraft.overall_rating !== "" ? { overall_rating: Number(reviewDraft.overall_rating) } : {}),
        ...(reviewDraft.comments ? { comments: reviewDraft.comments } : {}),
      }) });
      setReviewDraft({ review_cycle_id: "", employee_id: "", overall_rating: "", comments: "" });
      setShowReviewForm(false);
      setNotice({ kind: "success", text: "Performance review created." });
      await loadPerformance();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function submitReview(review: PerformanceReview) {
    const rating = window.prompt("Overall rating (0–5):", "4");
    if (rating === null) return;
    const parsed = Number(rating);
    if (Number.isNaN(parsed) || parsed < 0 || parsed > 5) { setNotice({ kind: "error", text: "Rating must be a number between 0 and 5." }); return; }
    const comments = window.prompt("Reviewer comments (optional):") ?? "";
    try {
      await api<void>(`/api/performance/reviews/${review.id}/submit`, { method: "POST", body: jsonBody({ overall_rating: parsed, comments: comments || null }) });
      setNotice({ kind: "success", text: "Review submitted." });
      await loadPerformance();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function saveCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<TrainingCourse>("/api/learning/courses", { method: "POST", body: jsonBody({ title: courseDraft.title, description: courseDraft.description || null, category: courseDraft.category, provider: courseDraft.provider || null, duration_hours: Number(courseDraft.duration_hours) }) });
      setCourseDraft({ title: "", description: "", category: "General", provider: "", duration_hours: "2" });
      setShowCourseForm(false);
      setNotice({ kind: "success", text: "Training course created." });
      await loadLearning();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function saveEnrollment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<TrainingEnrollment>("/api/learning/enrollments", { method: "POST", body: jsonBody({ course_id: Number(enrollmentDraft.course_id), employee_id: Number(enrollmentDraft.employee_id) }) });
      setEnrollmentDraft({ course_id: "", employee_id: "" });
      setShowEnrollmentForm(false);
      setNotice({ kind: "success", text: "Employee enrolled in the course." });
      await loadLearning();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function updateEnrollment(enrollment: TrainingEnrollment, status: string) {
    const score = status === "Completed" ? window.prompt("Score (0–100, optional):") : null;
    if (status === "Completed" && score === null) return;
    const parsedScore = score !== null && score !== "" ? Number(score) : null;
    if (parsedScore !== null && (Number.isNaN(parsedScore) || parsedScore < 0 || parsedScore > 100)) {
      setNotice({ kind: "error", text: "Score must be a number between 0 and 100." }); return;
    }
    try {
      await api<TrainingEnrollment>(`/api/learning/enrollments/${enrollment.id}`, { method: "PATCH", body: jsonBody({ status, score: parsedScore }) });
      setNotice({ kind: "success", text: `Enrollment marked ${status.toLowerCase()}.` });
      await loadLearning();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function sendNotification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      const result = await api<{ recipients: number }>("/api/notifications", { method: "POST", body: jsonBody({ ...notificationDraft, user_id: null }) });
      setNotificationDraft({ title: "", message: "", category: "General" });
      setShowNotificationForm(false);
      setNotice({ kind: "success", text: `Notification sent to ${result.recipients} account${result.recipients === 1 ? "" : "s"}.` });
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function markRead(notification: AppNotification) {
    try {
      await api<void>(`/api/notifications/${notification.id}/read`, { method: "PATCH" });
      await loadNotifications();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  async function saveAnnouncement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true);
    try {
      await api<Announcement>("/api/announcements", { method: "POST", body: jsonBody({ title: announcementDraft.title, body: announcementDraft.body, pinned: announcementDraft.pinned }) });
      setAnnouncementDraft({ title: "", body: "", pinned: false });
      setShowAnnouncementForm(false);
      setNotice({ kind: "success", text: "Announcement published." });
      await loadNotifications();
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
    finally { setBusy(false); }
  }

  async function exportCsv(path: string, filename: string) {
    try {
      const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";
      const response = await fetch(`${base}${path}`, { headers: { Authorization: `Bearer ${getAccessToken()}` } });
      if (!response.ok) throw new Error("The export could not be generated.");
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) { setNotice({ kind: "error", text: errorMessage(error) }); }
  }

  const title = useMemo(() => active === "employees" && userRole === "Employee"
    ? "My profile"
    : MODULE_LABELS[active]?.label ?? "Overview", [active, userRole]);

  if (checkingSession) return <main className="auth-loading"><div className="loading-mark">N</div><p>Verifying your secure session…</p></main>;

  if (!user) return <AuthScreen infoMessage={loginNotice} onAuthenticated={(authenticatedUser, message) => {
    setLoginNotice(null);
    setUser(authenticatedUser);
    setNotice({ kind: "success", text: message });
  }} />;

  return <main className={`nexora-app ${user.role === "Employee" ? "employee-mode" : ""}`}><aside className="app-sidebar"><a className="brand-lockup" href="#overview" onClick={(event) => { event.preventDefault(); setActive("overview"); }}><span className="brand-mark">T</span><span><b>Talentry</b><small>Workforce OS</small></span></a><p className="nav-caption">WORKSPACE</p><nav aria-label="Main navigation">{modulesLoaded ? modules.filter((m) => accessibleModules.includes(m.module_key)).map((m) => <button key={m.module_key} className={`nav-link ${active === m.module_key ? "selected" : ""}`} onClick={() => { setActive(m.module_key as Section); setNotice(null); }}><span className="nav-icon" aria-hidden="true">{MODULE_LABELS[m.module_key]?.icon ?? "●"}</span>{m.module_key === "employees" && userRole === "Employee" ? "My profile" : m.name}{m.module_key === "leave" && dashboard?.pending_leave_requests ? <span className="nav-count">{dashboard.pending_leave_requests}</span> : null}</button>) : []}</nav><div className="sidebar-bottom"><div className="sidebar-note"><span className="note-mark">✳</span><b>People first.</b><p>Build a better workplace, every day.</p></div><small>SECURE WORKSPACE · 1.0</small></div></aside><section className="app-body"><header className="app-topbar"><div className="breadcrumbs"><span>Workspace</span><i>/</i><b>{title}</b></div><div className="topbar-user"><span className="online-dot" /> <span className="role-pill">{user.role}</span><span className="top-avatar">{user.name.slice(0, 1).toUpperCase()}</span><span className="user-summary"><b>{user.name}</b><small>{user.email}</small></span><button className="quiet-button" onClick={() => void signOut()}>Sign out</button></div></header><div className="page-content"><div className="page-heading"><div><p className="eyebrow">PEOPLE & OPERATIONS</p><h1>{active === "overview" ? `Welcome back, ${user.name.split(" ")[0]}` : title}</h1><p>{active === "overview" ? "A clear view of today’s workforce operations." : sectionDescription(active)}</p></div><div className="date-stamp">{new Date().toLocaleDateString(undefined, { weekday: "short", day: "2-digit", month: "short", year: "numeric" })}</div></div>{notice && <div className={`toast-message ${notice.kind}`} role="status"><span>{notice.kind === "success" ? "✓" : "!"}</span>{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss notification">×</button></div>}

{active === "overview" && <><div className="metric-grid">{dashboard?.scope === "organization" || dashboard?.scope === "department" ? <><Metric title={dashboard.scope === "department" ? "Department headcount" : "Total employees"} value={dashboard.employee_count} symbol="♙" tone="blue" detail={dashboard.scope === "department" ? "Employees in your assigned department" : "Employee records in the organization"}/><Metric title="Active employees" value={dashboard.active_employee_count} symbol="✓" tone="green" detail={dashboard.scope === "department" ? "Active in your assigned department" : "Currently marked active"}/><Metric title="Employees on leave" value={dashboard.employees_on_leave_count} symbol="◷" tone="amber" detail={dashboard.scope === "department" ? "Current status in your assigned department" : "Current directory status"}/><Metric title="Departments" value={dashboard.department_count} symbol="▤" tone="violet" detail={dashboard.scope === "department" ? "Your assigned department" : "Configured organization units"}/></> : dashboard?.scope === "attendance" ? <Metric title="Present today" value={dashboard.present_today} symbol="◷" tone="green" detail="Explicit check-in records across the organization"/> : dashboard?.scope === "personal" ? <><Metric title="Your attendance today" value={todayAttendance ? (todayAttendance.check_out ? "Complete" : "Checked in") : "Not recorded"} symbol="◷" tone="blue" detail={todayAttendance ? `Checked in at ${timeLabel(todayAttendance.check_in)}` : "Use Attendance to record today's work"}/><Metric title="Your pending leave" value={dashboard?.my_pending_leave_requests} symbol="▧" tone="amber" detail="Requests awaiting manager review"/><Metric title="Today's date" value={new Date().toLocaleDateString(undefined, { day: "numeric", month: "short" })} symbol="◷" tone="green" detail="Your personal workspace"/></> : <section className="surface-card specialized-role-card"><p className="eyebrow">{user.role.toUpperCase()} WORKSPACE</p><h2>{user.role === "Recruiter" ? "Recruitment operations" : "Payroll operations"}</h2><p>{user.role === "Recruiter" ? "Your recruiter account is authenticated, but no requisition or candidate records have been implemented yet. No pipeline totals are fabricated." : "Your payroll role is authenticated, but payroll periods, salary records, and calculations are not implemented. No compensation data is exposed or fabricated."}</p><span className="status-badge muted"><i/>DOMAIN WORKSPACE NOT YET CONFIGURED</span></section>}</div><div className="dashboard-grid"><section className="surface-card overview-card"><div className="card-heading"><div><h2>Workforce snapshot</h2><p>Live totals from the employee and department records.</p></div><button className="text-action" onClick={() => setActive("employees")}>Open directory <span>→</span></button></div>{dashboard?.scope === "organization" && dashboard.employee_count ? <><div className="snapshot-total"><b>{dashboard.employee_count}</b><span>employees recorded</span></div><div className="snapshot-bar"><span style={{ width: `${dashboard.employee_count ? Math.round(((dashboard.active_employee_count ?? 0) / dashboard.employee_count) * 100) : 0}%` }} /></div><div className="snapshot-legend"><span><i className="legend-active"/>Active <b>{dashboard.active_employee_count}</b></span><span><i className="legend-leave"/>On leave <b>{dashboard.employees_on_leave_count}</b></span></div></> : <EmptyState title="No workforce records yet" detail="Add employee records to see real organization metrics here." action="Add an employee" onClick={() => { setActive("employees"); setEmployeeForm(true); }}/>}</section><section className="surface-card task-card"><div className="card-heading"><div><h2>Needs attention</h2><p>Pending requests from live records.</p></div><span className="task-indicator">●</span></div>{dashboard?.scope === "organization" ? <div className="task-row"><span className="task-icon">▧</span><div><b>Leave requests</b><small>Waiting for review</small></div><strong>{dashboard.pending_leave_requests}</strong><button className="text-action" onClick={() => setActive("leave")}>Review →</button></div> : <div className="task-row"><span className="task-icon">▧</span><div><b>Your leave requests</b><small>Waiting for review</small></div><strong>{dashboard?.my_pending_leave_requests ?? 0}</strong><button className="text-action" onClick={() => setActive("leave")}>View →</button></div>}<div className="quick-actions"><button onClick={() => { setActive("attendance"); }}>Open attendance <span>→</span></button>{canManage && <button onClick={() => { setActive("employees"); setEmployeeForm(true); }}>Add employee <span>→</span></button>}</div></section></div><section className="surface-card definition-note"><span>i</span><p>Attendance is counted from check-in records for today. Unrecorded attendance is not assumed to be present; dates use the API server’s UTC calendar.</p></section></>}

{active === "employees" && <section className="surface-card module-card"><div className="card-heading module-heading"><div><h2>{user.role === "Employee" ? "My profile" : "Employee directory"}</h2><p>{user.role === "Employee" ? "Review the limited employee details linked to your account." : "Search across employee names, IDs, departments and job titles."}</p></div>{canCreateEmployee && <button className="primary-button" onClick={() => { setEditingEmployee(null); setEmployeeDraft({ employee_code: "", name: "", department: "", role: "", status: "Active", branch_id: "", designation_id: "", job_grade_id: "", reporting_manager_id: "" }); setEmployeeForm(!employeeForm); }}>＋ Add employee</button>}</div>{user.role === "Employee" && employees[0] && <form className="record-form compact-form" onSubmit={saveMyProfile}><b>Update display name</b><label>Your name<input required minLength={2} maxLength={100} value={profileName} onChange={(event) => setProfileName(event.target.value)}/></label><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Save profile"}</button></form>}{employees[0] && <button className="secondary-button profile-open-button" onClick={() => setProfileEmployee(employees[0])}>View full profile</button>}{employeeForm && canCreateEmployee && <form className="record-form" onSubmit={saveEmployee}><div className="form-title"><b>{editingEmployee ? "Edit employee" : "New employee"}</b><button type="button" className="quiet-button" onClick={() => { setEmployeeForm(false); setEditingEmployee(null); }}>Cancel</button></div><div className="form-grid"><label>Employee ID<input required minLength={2} maxLength={20} value={employeeDraft.employee_code} onChange={(e) => setEmployeeDraft({ ...employeeDraft, employee_code: e.target.value })} placeholder="NX-1029"/></label><label>Full name<input required minLength={2} maxLength={100} value={employeeDraft.name} onChange={(e) => setEmployeeDraft({ ...employeeDraft, name: e.target.value })} placeholder="Employee name"/></label><label>Department<input required minLength={2} maxLength={100} value={employeeDraft.department} onChange={(e) => setEmployeeDraft({ ...employeeDraft, department: e.target.value })} placeholder="e.g. People" list="department-options"/><datalist id="department-options">{departments.map((item) => <option key={item.id} value={item.name}/>)}</datalist></label><label>Job title<input required minLength={2} maxLength={100} value={employeeDraft.role} onChange={(e) => setEmployeeDraft({ ...employeeDraft, role: e.target.value })} placeholder="Job title"/></label><label>Branch <span className="optional">Optional</span><select value={employeeDraft.branch_id} onChange={(event) => setEmployeeDraft({ ...employeeDraft, branch_id: event.target.value })}><option value="">No branch</option>{branches.filter((branch) => branch.active).map((branch) => <option key={branch.id} value={branch.id}>{branch.name} · {branch.code}</option>)}</select></label><label>Designation <span className="optional">Optional</span><select value={employeeDraft.designation_id} onChange={(event) => setEmployeeDraft({ ...employeeDraft, designation_id: event.target.value })}><option value="">No designation</option>{designations.filter((item) => item.active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Job grade <span className="optional">Optional</span><select value={employeeDraft.job_grade_id} onChange={(event) => setEmployeeDraft({ ...employeeDraft, job_grade_id: event.target.value })}><option value="">No grade</option>{jobGrades.filter((grade) => grade.active).map((grade) => <option key={grade.id} value={grade.id}>{grade.code} · {grade.name}</option>)}</select></label><label>Reporting manager <span className="optional">Optional</span><select value={employeeDraft.reporting_manager_id} onChange={(event) => setEmployeeDraft({ ...employeeDraft, reporting_manager_id: event.target.value })}><option value="">No reporting manager</option>{employeeOptions.filter((item) => item.id !== editingEmployee?.id && item.status === "Active").map((item) => <option key={item.id} value={item.id}>{item.employee_code} · {item.name}</option>)}</select></label><label>Status<select value={employeeDraft.status} onChange={(e) => setEmployeeDraft({ ...employeeDraft, status: e.target.value })}><option>Active</option><option>On leave</option></select></label></div><button className="primary-button" disabled={busy}>{busy ? "Saving…" : editingEmployee ? "Save changes" : "Create employee"}</button></form>}<div className="table-toolbar"><label className="search-field"><span>⌕</span><input type="search" value={employeeSearch} onChange={(e) => setEmployeeSearch(e.target.value)} placeholder="Search directory…" aria-label="Search employees"/></label><span className="record-count">{employeeTotal} records</span></div><div className="table-scroll"><table className="data-table"><thead><tr><th>EMPLOYEE</th><th>DEPARTMENT</th><th>EMPLOYEE ID</th><th>STATUS</th><th>ACTIONS</th></tr></thead><tbody>{employees.map((employee) => <tr key={employee.id}><td><div className="person-cell"><span className="person-avatar">{employee.name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase()}</span><span><b>{employee.name}</b><small>{employee.role}</small></span></div></td><td>{employee.department}</td><td><span className="code-text">{employee.employee_code}</span></td><td><span className={`status-badge ${employee.status === "Active" ? "green" : "amber"}`}><i/>{employee.status}</span></td><td><button className="row-action" onClick={() => setProfileEmployee(employee)}>Profile</button>{canManage && <><button className="row-action" onClick={() => void editEmployee(employee)}>Edit</button><button className="row-action danger" onClick={() => void removeEmployee(employee)}>Remove</button></>}</td></tr>)}{employees.length === 0 && <tr><td colSpan={5}><EmptyState title="No employees found" detail={employeeQuery ? "Try another search term." : "Add your first employee to start the directory."} action={canCreateEmployee ? "Add employee" : undefined} onClick={canCreateEmployee ? () => setEmployeeForm(true) : undefined}/></td></tr>}</tbody></table></div><div className="table-footer"><span>Showing {employeeTotal ? employeeOffset + 1 : 0}–{Math.min(employeeOffset + 10, employeeTotal)} of {employeeTotal}</span><div><button className="pagination-button" disabled={employeeOffset === 0} onClick={() => setEmployeeOffset(Math.max(0, employeeOffset - 10))}>Previous</button><button className="pagination-button" disabled={employeeOffset + 10 >= employeeTotal} onClick={() => setEmployeeOffset(employeeOffset + 10)}>Next</button></div></div>{profileEmployee && <EmployeeProfilePanel employee={profileEmployee} isSelf={user.role === "Employee"} canManagePrivate={user.role === "Employee" || ["Super Admin", "HR Administrator", "HR Manager"].includes(user.role)} canManageContracts={canManage} onClose={() => setProfileEmployee(null)}/>}</section>}

{active === "departments" && <section className="surface-card module-card"><div className="card-heading module-heading"><div><h2>Departments</h2><p>Manage active organization units. Records are retained when archived.</p></div><span className="record-count">{departmentTotal} departments</span></div>{canManageDepartments && <form className="record-form compact-form" onSubmit={saveDepartment}><b>Create a department</b><div className="form-grid two-col"><label>Department name<input required minLength={2} maxLength={100} value={departmentName} onChange={(e) => setDepartmentName(e.target.value)} placeholder="e.g. Product"/></label><label>Description <span className="optional">Optional</span><input maxLength={1000} value={departmentDescription} onChange={(e) => setDepartmentDescription(e.target.value)} placeholder="What this team does"/></label></div><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Create department"}</button></form>}<div className="department-list">{departments.map((department) => <article className="department-row" key={department.id}><span className="department-symbol">{department.name.slice(0, 1).toUpperCase()}</span><div><b>{department.name}</b><p>{department.description || "No description provided"}</p></div><span className={`status-badge ${department.active ? "green" : "muted"}`}><i/>{department.active ? "Active" : "Archived"}</span>{canManageDepartments && <button className="row-action" onClick={() => void toggleDepartment(department)}>{department.active ? "Archive" : "Reactivate"}</button>}</article>)}{departments.length === 0 && <EmptyState title="No departments yet" detail="Create a department to organize your workforce."/>}</div></section>}

{active === "organization" && canManageOrganizationStructure && <OrganizationStructure/>}
{active === "organization" && !canManageOrganizationStructure && <section className="surface-card"><EmptyState title="Access denied" detail="Organization structure is restricted to organization and HR administrators." action="Return to overview" onClick={() => setActive("overview")}/></section>}

{active === "attendance" && <><section className="attendance-banner"><div><p className="eyebrow">DAILY TIME RECORD</p><h2>{todayAttendance ? (todayAttendance.check_out ? "Your workday is complete" : "You're checked in") : "Start your workday"}</h2><p>{todayAttendance ? `Checked in at ${timeLabel(todayAttendance.check_in)}${todayAttendance.check_out ? ` · Checked out at ${timeLabel(todayAttendance.check_out)}` : ""}` : "Record attendance when you begin work. Times are stored by the API in UTC."}</p></div><div className="attendance-actions"><button className="primary-button" onClick={() => void clock("clock-in")} disabled={Boolean(todayAttendance)}>Check in</button><button className="secondary-button" onClick={() => void clock("clock-out")} disabled={!todayAttendance || Boolean(todayAttendance.check_out)}>Check out</button></div></section><section className="surface-card module-card"><div className="card-heading"><div><h2>{canManage ? "Attendance records" : "Your attendance history"}</h2><p>Records are based on explicit check-in and check-out events.</p></div></div><div className="table-scroll"><table className="data-table"><thead><tr>{canManage && <th>USER ID</th>}<th>WORK DATE</th><th>CHECK IN</th><th>CHECK OUT</th><th>STATUS</th></tr></thead><tbody>{(attendance?.items ?? []).map((row) => <tr key={row.id}>{canManage && <td>{row.user_id}</td>}<td>{dateLabel(row.work_date)}</td><td>{timeLabel(row.check_in)} UTC</td><td>{row.check_out ? `${timeLabel(row.check_out)} UTC` : "—"}</td><td><span className="status-badge green"><i/>{row.status}</span></td></tr>)}{attendance?.items.length === 0 && <tr><td colSpan={canManage ? 5 : 4}><EmptyState title="No attendance records" detail="Attendance appears here after a check-in is recorded."/></td></tr>}</tbody></table></div></section></>}

{active === "leave" && <><section className="module-summary-strip"><div><span>Requests awaiting review</span><b>{user.role === "Employee" ? dashboard?.my_pending_leave_requests ?? 0 : dashboard?.pending_leave_requests ?? 0}</b></div><div><span>Your pending requests</span><b>{dashboard?.my_pending_leave_requests ?? 0}</b></div><small>Annual balances deduct only after approval. Weekends and configured holidays are excluded; leave policies use a calendar-year allocation.</small></section>{leaveBalances.length > 0 && <section className="leave-balance-grid" aria-label="Your leave balances">{leaveBalances.map((balance) => <article className="leave-balance-card" key={balance.id}><span>{balance.leave_type}</span><b>{balance.remaining_days}<small> / {balance.allocated_days} days</small></b><p>{balance.used_days} used · {balance.pending_days} pending · {balance.year}</p></article>)}</section>}{canManageLeavePolicy && <section className="surface-card policy-panel"><div className="card-heading"><div><h2>Leave policies</h2><p>Configure leave categories and yearly allocations; no statutory allowance is assumed.</p></div><button className="secondary-button" onClick={() => setShowLeavePolicyForm(!showLeavePolicyForm)}>{showLeavePolicyForm ? "Cancel" : "＋ Add leave type"}</button></div>{showLeavePolicyForm && <form className="record-form" onSubmit={saveLeavePolicy}><div className="form-grid two-col"><label>Leave type<input value={leavePolicyDraft.name} onChange={(event) => setLeavePolicyDraft({ ...leavePolicyDraft, name: event.target.value })} required minLength={2} maxLength={80} placeholder="e.g. Annual leave"/></label><label>Annual allocation (days)<input type="number" min="0" max="365" value={leavePolicyDraft.annual_allowance_days} onChange={(event) => setLeavePolicyDraft({ ...leavePolicyDraft, annual_allowance_days: event.target.value })} required/></label><label>Description<input value={leavePolicyDraft.description} onChange={(event) => setLeavePolicyDraft({ ...leavePolicyDraft, description: event.target.value })} maxLength={500} placeholder="Policy description"/></label><label className="checkbox-label"><input type="checkbox" checked={leavePolicyDraft.paid} onChange={(event) => setLeavePolicyDraft({ ...leavePolicyDraft, paid: event.target.checked })}/> Paid leave</label></div><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Create leave type"}</button></form>}<div className="policy-list">{leaveTypes.map((policy) => <article className="policy-row" key={policy.id}><span><b>{policy.name}</b><small>{policy.annual_allowance_days} days per calendar year · {policy.paid ? "Paid" : "Unpaid"}</small></span><button className="row-action" onClick={() => void toggleLeavePolicy(policy)}>Archive</button></article>)}</div></section>}<div className="leave-layout"><section className="surface-card module-card"><div className="card-heading"><div><h2>Request time off</h2><p>Submit a request for manager review.</p></div></div>{leaveTypes.length === 0 ? <EmptyState title="No leave policy is configured" detail="Ask an HR administrator to create a leave type before submitting a request."/> : <form className="record-form leave-form" onSubmit={submitLeave}><div className="form-grid two-col"><label>First day<input type="date" value={leaveDraft.start_date} onChange={(e) => setLeaveDraft({ ...leaveDraft, start_date: e.target.value })} required/></label><label>Last day<input type="date" min={leaveDraft.start_date || undefined} value={leaveDraft.end_date} onChange={(e) => setLeaveDraft({ ...leaveDraft, end_date: e.target.value })} required/></label></div><label>Leave type<select value={leaveDraft.leave_type_id} onChange={(event) => setLeaveDraft({ ...leaveDraft, leave_type_id: event.target.value })} required>{leaveTypes.map((type) => <option key={type.id} value={type.id}>{type.name} · {type.annual_allowance_days} days</option>)}</select></label><label className="checkbox-label"><input type="checkbox" checked={leaveDraft.half_day} onChange={(event) => setLeaveDraft({ ...leaveDraft, half_day: event.target.checked, ...(event.target.checked && leaveDraft.start_date ? { end_date: leaveDraft.start_date } : {}) })}/> Half-day request</label><label>Reason<textarea minLength={5} maxLength={1000} rows={4} value={leaveDraft.reason} onChange={(e) => setLeaveDraft({ ...leaveDraft, reason: e.target.value })} placeholder="Share a brief reason for your request" required/></label><button className="primary-button" disabled={busy}>{busy ? "Submitting…" : "Submit leave request"}</button></form>}</section><section className="surface-card module-card"><div className="card-heading"><div><h2>{canReviewLeave ? "Leave inbox" : "Your requests"}</h2><p>Pending requests can be reviewed by authorized HR managers or your assigned department manager.</p></div></div><div className="leave-list">{(leaveRequests?.items ?? []).map((request) => <article className="leave-item" key={request.id}><div className="leave-item-top"><span className={`status-badge ${request.status === "Approved" ? "green" : request.status === "Rejected" ? "red" : "amber"}`}><i/>{request.status}</span><small>Request #{request.id}{canManageLeavePolicy ? ` · User ${request.user_id}` : ""}</small></div><b>{dateLabel(request.start_date)} – {dateLabel(request.end_date)}</b><p>{request.reason}</p>{canReviewLeave && request.status === "Pending" && request.user_id !== user.id && <div className="review-actions"><button className="secondary-button" onClick={() => void reviewLeave(request, "Rejected")}>Decline</button><button className="primary-button" onClick={() => void reviewLeave(request, "Approved")}>Approve</button></div>}{request.user_id === user.id && (request.status === "Pending" || (request.status === "Approved" && request.start_date > new Date().toISOString().slice(0, 10))) && <button className="row-action danger" onClick={() => void cancelLeave(request)}>Cancel request</button>}{request.review_comment && <p className="review-comment"><b>Reviewer note:</b> {request.review_comment}</p>}</article>)}{leaveRequests?.items.length === 0 && <EmptyState title="No leave requests" detail="New requests and their review outcomes will appear here."/>}</div></section></div></>}
{active === "users" && canAdminUsers && <div className="user-admin-layout"><section className="surface-card module-card"><div className="card-heading"><div><h2>Invite an account</h2><p>The invitee completes registration with a one-time code before the account is enabled.</p></div></div><form className="record-form" onSubmit={provisionAccount}><div className="form-grid two-col"><label>Full name<input required minLength={2} maxLength={100} value={invitationDraft.name} onChange={(event) => setInvitationDraft({ ...invitationDraft, name: event.target.value })}/></label><label>Work email<input type="email" required value={invitationDraft.email} onChange={(event) => setInvitationDraft({ ...invitationDraft, email: event.target.value })}/></label><label>Account role<select value={invitationDraft.role} onChange={(event) => setInvitationDraft({ ...invitationDraft, role: event.target.value })}><option>Employee</option><option>Department Manager</option><option>Recruiter</option><option>Attendance Administrator</option>{user.role === "Super Admin" && <><option>Organization Admin</option><option>HR Administrator</option><option>HR Manager</option><option>Payroll Administrator</option></>}</select></label>{invitationDraft.role === "Department Manager" && <label>Assigned department<select required value={invitationDraft.department_id} onChange={(event) => setInvitationDraft({ ...invitationDraft, department_id: event.target.value })}><option value="">Select department</option>{departments.filter((department) => department.active).map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select></label>}{invitationDraft.role === "Employee" && <label>Employee profile<select required value={invitationDraft.employee_id} onChange={(event) => setInvitationDraft({ ...invitationDraft, employee_id: event.target.value })}><option value="">Select an unlinked employee</option>{employees.filter((employee) => !employee.user_id).map((employee) => <option key={employee.id} value={employee.id}>{employee.employee_code} · {employee.name}</option>)}</select></label>}</div><button className="primary-button" disabled={busy}>{busy ? "Creating invitation…" : "Send registration invitation"}</button></form>{issuedInvitation && <div className="invitation-result" role="status"><b>One-time registration code for {issuedInvitation.email}</b><p>Expires {new Date(issuedInvitation.expires_at).toLocaleString()}. Copy the code now and deliver it only through a trusted private channel.</p><code>{issuedInvitation.token}</code><button className="secondary-button" onClick={() => void navigator.clipboard.writeText(issuedInvitation.token)}>Copy registration code</button></div>}</section><section className="surface-card module-card"><div className="card-heading"><div><h2>Account access</h2><p>Roles are server-assigned. Only Super Admin may change roles.</p></div></div><div className="table-scroll"><table className="data-table"><thead><tr><th>ACCOUNT</th><th>ROLE</th><th>STATUS</th><th>ACCESS</th></tr></thead><tbody>{(users?.items ?? []).map((account) => <tr key={account.id}><td><div className="person-cell"><span className="person-avatar">{account.name.slice(0, 1).toUpperCase()}</span><span><b>{account.name}</b><small>{account.email}</small></span></div></td><td>{user.role === "Super Admin" && account.id !== user.id ? <select className="inline-select" value={account.role} onChange={(event) => void changeUser(account.id, { role: event.target.value })}>{["Organization Admin", "HR Administrator", "HR Manager", "Department Manager", "Recruiter", "Payroll Administrator", "Attendance Administrator", "Employee"].map((role) => <option key={role}>{role}</option>)}</select> : account.role}</td><td><span className={`status-badge ${account.registration_pending ? "amber" : account.active ? "green" : "muted"}`}><i/>{account.registration_pending ? "Registration pending" : account.active ? "Active" : "Inactive"}</span></td><td><button className="row-action" disabled={busy || account.id === user.id} onClick={() => account.registration_pending ? void reissueRegistrationCode(account) : void changeUser(account.id, { active: !account.active })}>{account.registration_pending ? "Reissue code" : account.active ? "Deactivate" : "Reactivate"}</button></td></tr>)}</tbody></table></div></section></div>}
{active === "users" && !canAdminUsers && <section className="surface-card"><EmptyState title="Access denied" detail="User administration is restricted to authorized administrators." action="Return to overview" onClick={() => setActive("overview")}/></section>}

{active === "module-access" && canManageModuleAccess && (
  <div className="user-admin-layout">
    <section className="surface-card module-card">
      <div className="card-heading">
        <div>
          <h2>Module Access Control</h2>
          <p>Super Admin can grant or revoke module access for each role. Add new modules or submodules to build a tree. Changes apply immediately.</p>
        </div>
        <button className="secondary-button" onClick={() => setShowModuleForm(!showModuleForm)}>{showModuleForm ? "Cancel" : "+ Add module"}</button>
      </div>
      {showModuleForm && <form className="record-form compact-form" onSubmit={saveModule}>
        <div className="form-grid two-col">
          <label>Module key<input required minLength={2} maxLength={60} value={moduleDraft.module_key} onChange={(e) => setModuleDraft({ ...moduleDraft, module_key: e.target.value })} placeholder="e.g. custom-module"/></label>
          <label>Name<input required minLength={2} maxLength={120} value={moduleDraft.name} onChange={(e) => setModuleDraft({ ...moduleDraft, name: e.target.value })}/></label>
          <label>Description<input value={moduleDraft.description} onChange={(e) => setModuleDraft({ ...moduleDraft, description: e.target.value })}/></label>
          <label>Parent module<select value={moduleDraft.parent_id} onChange={(e) => setModuleDraft({ ...moduleDraft, parent_id: e.target.value })}><option value="">Top-level module</option>{modules.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
        </div>
        <div className="form-actions"><button className="primary-button" disabled={busy}>{busy ? "Creating..." : "Create module"}</button></div>
      </form>}
      <div className="record-list">
        <table>
          <thead>
            <tr>
              <th>Module</th>
              <th>Description</th>
              {MODULE_ROLES.map((role) => <th key={role}>{role}</th>)}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {modules.filter((m) => m.parent_id === null).map((parent) => (
              <ModuleTree
                key={parent.id}
                module={parent}
                modules={modules}
                moduleAccessDraft={moduleAccessDraft}
                setModuleAccessDraft={setModuleAccessDraft}
                busy={busy}
                removeModule={removeModule}
              />
            ))}
            {modules.length === 0 && (
              <tr>
                <td colSpan={11}><EmptyState title="No modules" detail="Modules are loaded from the server." /></td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  </div>
)}

{active === "module-access" && !canManageModuleAccess && <section className="surface-card"><EmptyState title="Access denied" detail="Module Access Control is restricted to Super Admin." action="Return to overview" onClick={() => setActive("overview")}/></section>}

{active === "payroll" && <div className="payroll-layout">
  <section className="surface-card">
    <div className="card-heading"><div><h2>Payroll runs</h2><p>Create, calculate, and finalize payroll runs for the organization.</p></div></div>
    {payrollRuns.length === 0 ? <p className="profile-empty">No payroll runs yet.</p> : <div className="record-list">
      {payrollRuns.map((run) => <article className="record-row" key={run.id}>
        <div><b>{run.name}</b><small>{new Date(run.period_start).toLocaleDateString()} – {new Date(run.period_end).toLocaleDateString()} · Pay date {new Date(run.pay_date).toLocaleDateString()}</small></div>
        <div><span className={`status-badge ${run.status === "Finalized" ? "green" : run.status === "Calculated" ? "amber" : "muted"}`}><i/>{run.status}</span></div>
        <div><b>${run.total_net.toLocaleString()}</b><small>net · {run.employee_count} employees</small></div>
        <div className="row-actions">
          {run.status === "Draft" && <button className="row-action" onClick={() => { setShowPayrollForm(false); void api<void>(`/api/payroll/runs/${run.id}/calculate`, { method: "POST" }).then(() => { setNotice({ kind: "success", text: "Payroll calculated." }); loadPayroll(); }); }}>Calculate</button>}
          {run.status === "Calculated" && <button className="row-action" onClick={() => { void api<void>(`/api/payroll/runs/${run.id}/finalize`, { method: "POST" }).then(() => { setNotice({ kind: "success", text: "Payroll finalized." }); loadPayroll(); }); }}>Finalize</button>}
        </div>
      </article>)}
    </div>}
    {canAdminPayroll && <button className="primary-button" onClick={() => { setShowPayrollForm(true); setPayrollRunDraft({ name: "", period_start: "", period_end: "", pay_date: "" }); }}>Create payroll run</button>}
  </section>
  {showPayrollForm && <section className="surface-card">
    <div className="card-heading"><div><h2>Create payroll run</h2><p>Define the pay period and pay date.</p></div></div>
    <form className="record-form compact-form" onSubmit={(event) => {
      event.preventDefault();
      setBusy(true);
      api<PayrollRun>("/api/payroll/runs", { method: "POST", body: jsonBody(payrollRunDraft) })
        .then(() => { setShowPayrollForm(false); setNotice({ kind: "success", text: "Payroll run created." }); loadPayroll(); setBusy(false); })
        .catch((error) => { setNotice({ kind: "error", text: errorMessage(error) }); setBusy(false); });
    }}>
      <label>Run name<input required minLength={2} maxLength={100} value={payrollRunDraft.name} onChange={(e) => setPayrollRunDraft({ ...payrollRunDraft, name: e.target.value })}/></label>
      <label>Period start<input type="date" required value={payrollRunDraft.period_start} onChange={(e) => setPayrollRunDraft({ ...payrollRunDraft, period_start: e.target.value })}/></label>
      <label>Period end<input type="date" required value={payrollRunDraft.period_end} onChange={(e) => setPayrollRunDraft({ ...payrollRunDraft, period_end: e.target.value })}/></label>
      <label>Pay date<input type="date" required value={payrollRunDraft.pay_date} onChange={(e) => setPayrollRunDraft({ ...payrollRunDraft, pay_date: e.target.value })}/></label>
      <div className="form-actions"><button className="primary-button" disabled={busy}>{busy ? "Creating…" : "Create run"}</button> <button type="button" className="secondary-button" onClick={() => setShowPayrollForm(false)}>Cancel</button></div>
    </form>
  </section>}</div>}

{active === "payroll" && <div className="payroll-layout">
  <section className="surface-card">
    <div className="card-heading"><div><h2>Payslips</h2><p>View payslips for payroll runs.</p></div></div>
    {payslips.length === 0 ? <p className="profile-empty">No payslips yet.</p> : <div className="record-list">
      {payslips.map((slip) => <article className="record-row" key={slip.id}>
        <div><b>{slip.employee_name ?? "Employee #" + slip.employee_id}</b><small>Payslip #{slip.id}</small></div>
        <div><b>${slip.gross_pay.toLocaleString()}</b><small>gross</small></div>
        <div>- ${slip.deductions.toLocaleString()}<small>deductions</small></div>
        <div><b>${slip.net_pay.toLocaleString()}</b><small>net · {new Date(slip.payslip_date).toLocaleDateString()}</small></div>
        <div><span className={`status-badge ${slip.status === "Finalized" ? "green" : "muted"}`}><i/>{slip.status}</span></div>
      </article>)}
    </div>}
  </section></div>}

{active === "recruitment" && <div className="recruitment-layout">
  <section className="surface-card">
    <div className="card-heading"><div><h2>Job requisitions</h2><p>Create and manage open positions.</p></div></div>
    {requisitions.length === 0 ? <p className="profile-empty">No requisitions yet.</p> : <div className="record-list">
      {requisitions.map((req) => <article className="record-row" key={req.id}>
        <div><b>{req.title}</b><small>{req.department ?? "—"} · {req.employment_type}</small></div>
        <div><span className={`status-badge ${req.status === "Open" ? "green" : "muted"}`}><i/>{req.status}</span></div>
        <div><small>Created {new Date(req.created_at).toLocaleDateString()}</small></div>
        <div className="row-actions">
          {req.status === "Open" && <button className="row-action" onClick={() => { void api<void>(`/api/recruitment/requisitions/${req.id}/close`, { method: "POST" }).then(() => { setNotice({ kind: "success", text: "Requisition closed." }); loadRecruitment(); }); }}>Close</button>}
        </div>
      </article>)}
    </div>}
    {canManageRecruitment && <button className="primary-button" onClick={() => { setShowRequisitionForm(true); setRequisitionDraft({ title: "", department: "", employment_type: "Permanent" }); }}>Create requisition</button>}
  </section>
  {showRequisitionForm && <section className="surface-card">
    <div className="card-heading"><div><h2>Create requisition</h2><p>Define a new open position.</p></div></div>
    <form className="record-form compact-form" onSubmit={(event) => {
      event.preventDefault();
      setBusy(true);
      api<Requisition>("/api/recruitment/requisitions", { method: "POST", body: jsonBody(requisitionDraft) })
        .then(() => { setShowRequisitionForm(false); setNotice({ kind: "success", text: "Requisition created." }); loadRecruitment(); setBusy(false); })
        .catch((error) => { setNotice({ kind: "error", text: errorMessage(error) }); setBusy(false); });
    }}>
      <label>Position title<input required minLength={2} maxLength={200} value={requisitionDraft.title} onChange={(e) => setRequisitionDraft({ ...requisitionDraft, title: e.target.value })}/></label>
      <label>Department<input value={requisitionDraft.department} onChange={(e) => setRequisitionDraft({ ...requisitionDraft, department: e.target.value })} placeholder="e.g. Engineering"/></label>
      <label>Employment type<select value={requisitionDraft.employment_type} onChange={(e) => setRequisitionDraft({ ...requisitionDraft, employment_type: e.target.value })}><option>Permanent</option><option>Fixed-term</option><option>Temporary</option><option>Contractor</option></select></label>
      <div className="form-actions"><button className="primary-button" disabled={busy}>{busy ? "Creating…" : "Create requisition"}</button> <button type="button" className="secondary-button" onClick={() => setShowRequisitionForm(false)}>Cancel</button></div>
    </form>
  </section>}</div>}

{active === "recruitment" && <div className="recruitment-layout">
  <section className="surface-card">
    <div className="card-heading"><div><h2>Candidates</h2><p>Review applicants and track progress.</p></div></div>
    {candidates.length === 0 ? <p className="profile-empty">No candidates yet.</p> : <div className="record-list">
      {candidates.map((cand) => <article className="record-row" key={cand.id}>
        <div><b>{cand.name}</b><small>{cand.email}</small></div>
        <div><span className={`status-badge ${cand.status}`}><i/>{cand.status}</span></div>
        <div>{cand.phone ?? "—"}</div>
        <div><small>Applied {new Date(cand.applied_at).toLocaleDateString()}</small></div>
      </article>)}
    </div>}
    <div className="record-form small-form">
      <b>Add candidate</b>
      <form className="record-form compact-form" onSubmit={saveCandidate}>
        <div className="form-grid two-col">
          <label>Requisition<select value={candidateDraft.requisition_id} onChange={(e) => setCandidateDraft({ ...candidateDraft, requisition_id: e.target.value })}><option value="">Select requisition</option>{requisitions.map((r) => <option key={r.id} value={r.id}>{r.title} · {r.department ?? "—"}</option>)}</select></label>
          <label>Full name<input required minLength={2} maxLength={100} value={candidateDraft.name} onChange={(e) => setCandidateDraft({ ...candidateDraft, name: e.target.value })}/></label>
          <label>Email<input required type="email" maxLength={254} value={candidateDraft.email} onChange={(e) => setCandidateDraft({ ...candidateDraft, email: e.target.value })}/></label>
          <label>Phone<input maxLength={50} value={candidateDraft.phone} onChange={(e) => setCandidateDraft({ ...candidateDraft, phone: e.target.value })}/></label>
        </div>
        <div className="form-actions"><button className="primary-button" disabled={busy}>{busy ? "Adding..." : "Add candidate"}</button> <button type="button" className="secondary-button" onClick={() => setShowCandidateForm(false)}>Cancel</button></div>
      </form>
    </div>
  </section></div>}

{active === "performance" && <div className="payroll-layout">
  <section className="surface-card">
    <div className="card-heading"><div><h2>Goals</h2><p>Set and track employee goals and progress.</p></div>{canManagePerformance && <button className="secondary-button" onClick={() => setShowGoalForm(!showGoalForm)}>{showGoalForm ? "Cancel" : "＋ Add goal"}</button>}</div>
    {showGoalForm && canManagePerformance && <form className="record-form" onSubmit={saveGoal}><div className="form-grid two-col"><label>Employee<select required value={goalDraft.employee_id} onChange={(e) => setGoalDraft({ ...goalDraft, employee_id: e.target.value })}><option value="">Select employee</option>{employeeOptions.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></label><label>Goal title<input required minLength={2} maxLength={200} value={goalDraft.title} onChange={(e) => setGoalDraft({ ...goalDraft, title: e.target.value })} placeholder="e.g. Improve onboarding checklist"/></label><label>Category<input maxLength={50} value={goalDraft.category} onChange={(e) => setGoalDraft({ ...goalDraft, category: e.target.value })}/></label><label>Target date <span className="optional">Optional</span><input type="date" value={goalDraft.target_date} onChange={(e) => setGoalDraft({ ...goalDraft, target_date: e.target.value })}/></label><label>Description <span className="optional">Optional</span><input maxLength={2000} value={goalDraft.description} onChange={(e) => setGoalDraft({ ...goalDraft, description: e.target.value })}/></label></div><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Create goal"}</button></form>}
    <div className="table-scroll"><table className="data-table"><thead><tr><th>GOAL</th><th>CATEGORY</th><th>TARGET DATE</th><th>PROGRESS</th><th>STATUS</th><th>ACTION</th></tr></thead><tbody>{goals.map((goal) => <tr key={goal.id}><td>{goal.title}</td><td>{goal.category}</td><td>{goal.target_date ? dateLabel(goal.target_date) : "—"}</td><td>{goal.progress}%</td><td><span className={`status-badge ${goal.status === "Completed" ? "green" : "blue"}`}><i/>{goal.status}</span></td><td>{canManagePerformance && goal.status !== "Completed" && <button className="row-action" onClick={() => { const next = window.prompt("Progress (0–100):", String(goal.progress)); if (next === null) return; const parsed = Number(next); if (Number.isNaN(parsed) || parsed < 0 || parsed > 100) { setNotice({ kind: "error", text: "Progress must be between 0 and 100." }); return; } void updateGoal(goal, parsed, parsed >= 100 ? "Completed" : goal.status); }}>Update progress</button>}</td></tr>)}{goals.length === 0 && <tr><td colSpan={6}><EmptyState title="No goals yet" detail="Goals appear here once created for you or your team."/></td></tr>}</tbody></table></div>
  </section>
  <section className="surface-card">
    <div className="card-heading"><div><h2>Review cycles</h2><p>Organize performance reviews into dated cycles.</p></div>{canManagePerformance && <button className="secondary-button" onClick={() => setShowCycleForm(!showCycleForm)}>{showCycleForm ? "Cancel" : "＋ New cycle"}</button>}</div>
    {showCycleForm && <form className="record-form" onSubmit={saveReviewCycle}><div className="form-grid two-col"><label>Cycle name<input required minLength={2} maxLength={100} value={cycleDraft.name} onChange={(e) => setCycleDraft({ ...cycleDraft, name: e.target.value })} placeholder="e.g. H1 2026 reviews"/></label><label>Start date<input type="date" required value={cycleDraft.start_date} onChange={(e) => setCycleDraft({ ...cycleDraft, start_date: e.target.value })}/></label><label>End date<input type="date" required value={cycleDraft.end_date} onChange={(e) => setCycleDraft({ ...cycleDraft, end_date: e.target.value })}/></label></div><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Create cycle"}</button></form>}
    <div className="table-scroll"><table className="data-table"><thead><tr><th>CYCLE</th><th>PERIOD</th><th>STATUS</th></tr></thead><tbody>{reviewCycles.map((cycle) => <tr key={cycle.id}><td>{cycle.name}</td><td>{dateLabel(cycle.start_date)} – {dateLabel(cycle.end_date)}</td><td><span className={`status-badge ${cycle.status === "Active" ? "green" : "muted"}`}><i/>{cycle.status}</span></td></tr>)}{reviewCycles.length === 0 && <tr><td colSpan={3}><EmptyState title="No review cycles" detail="Create a cycle to organize reviews by period."/></td></tr>}</tbody></table></div>
  </section>
  <section className="surface-card">
    <div className="card-heading"><div><h2>Reviews</h2><p>Create reviews and submit overall ratings.</p></div>{canManagePerformance && <button className="secondary-button" onClick={() => setShowReviewForm(!showReviewForm)}>{showReviewForm ? "Cancel" : "＋ New review"}</button>}</div>
    {showReviewForm && <form className="record-form" onSubmit={saveReview}><div className="form-grid two-col"><label>Review cycle<select required value={reviewDraft.review_cycle_id} onChange={(e) => setReviewDraft({ ...reviewDraft, review_cycle_id: e.target.value })}><option value="">Select cycle</option>{reviewCycles.map((cycle) => <option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}</select></label><label>Employee<select required value={reviewDraft.employee_id} onChange={(e) => setReviewDraft({ ...reviewDraft, employee_id: e.target.value })}><option value="">Select employee</option>{employeeOptions.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></label><label>Initial rating (0–5) <span className="optional">Optional</span><input type="number" min="0" max="5" step="0.5" value={reviewDraft.overall_rating} onChange={(e) => setReviewDraft({ ...reviewDraft, overall_rating: e.target.value })}/></label><label>Comments <span className="optional">Optional</span><input maxLength={4000} value={reviewDraft.comments} onChange={(e) => setReviewDraft({ ...reviewDraft, comments: e.target.value })}/></label></div><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Create review"}</button></form>}
    <div className="table-scroll"><table className="data-table"><thead><tr><th>CYCLE</th><th>EMPLOYEE</th><th>RATING</th><th>STATUS</th><th>SUBMITTED</th><th>ACTION</th></tr></thead><tbody>{reviews.map((review) => { const cycle = reviewCycles.find((row) => row.id === review.review_cycle_id); const employee = employeeOptions.find((row) => row.id === review.employee_id); return <tr key={review.id}><td>{cycle?.name ?? `Cycle #${review.review_cycle_id}`}</td><td>{employee?.name ?? `Employee #${review.employee_id}`}</td><td>{review.overall_rating ?? "—"}</td><td><span className={`status-badge ${review.status === "Submitted" ? "green" : "amber"}`}><i/>{review.status}</span></td><td>{review.submitted_at ? dateLabel(review.submitted_at.slice(0, 10)) : "—"}</td><td>{canManagePerformance && review.status !== "Submitted" && <button className="row-action" onClick={() => void submitReview(review)}>Submit review</button>}</td></tr>; })}{reviews.length === 0 && <tr><td colSpan={6}><EmptyState title="No reviews yet" detail="Create a review from a cycle to start the appraisal process."/></td></tr>}</tbody></table></div>
  </section>
</div>}

{active === "learning" && <div className="payroll-layout">
  <section className="surface-card">
    <div className="card-heading"><div><h2>Training courses</h2><p>Course catalog available to employees.</p></div>{canManageLearning && <button className="secondary-button" onClick={() => setShowCourseForm(!showCourseForm)}>{showCourseForm ? "Cancel" : "＋ Add course"}</button>}</div>
    {showCourseForm && canManageLearning && <form className="record-form" onSubmit={saveCourse}><div className="form-grid two-col"><label>Title<input required minLength={2} maxLength={200} value={courseDraft.title} onChange={(e) => setCourseDraft({ ...courseDraft, title: e.target.value })} placeholder="e.g. Workplace safety"/></label><label>Category<input maxLength={50} value={courseDraft.category} onChange={(e) => setCourseDraft({ ...courseDraft, category: e.target.value })}/></label><label>Provider <span className="optional">Optional</span><input maxLength={120} value={courseDraft.provider} onChange={(e) => setCourseDraft({ ...courseDraft, provider: e.target.value })}/></label><label>Duration (hours)<input type="number" min="0" max="1000" step="0.5" value={courseDraft.duration_hours} onChange={(e) => setCourseDraft({ ...courseDraft, duration_hours: e.target.value })} required/></label><label>Description <span className="optional">Optional</span><input maxLength={2000} value={courseDraft.description} onChange={(e) => setCourseDraft({ ...courseDraft, description: e.target.value })}/></label></div><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Create course"}</button></form>}
    <div className="table-scroll"><table className="data-table"><thead><tr><th>COURSE</th><th>CATEGORY</th><th>PROVIDER</th><th>HOURS</th><th>STATUS</th></tr></thead><tbody>{courses.map((course) => <tr key={course.id}><td>{course.title}</td><td>{course.category}</td><td>{course.provider ?? "—"}</td><td>{String(course.duration_hours)}</td><td><span className={`status-badge ${course.active ? "green" : "muted"}`}><i/>{course.active ? "Active" : "Archived"}</span></td></tr>)}{courses.length === 0 && <tr><td colSpan={5}><EmptyState title="No courses yet" detail="Create a course to build your training catalog."/></td></tr>}</tbody></table></div>
  </section>
  <section className="surface-card">
    <div className="card-heading"><div><h2>Enrollments</h2><p>Track employee training progress and completion.</p></div>{canManageLearning && <button className="secondary-button" onClick={() => setShowEnrollmentForm(!showEnrollmentForm)}>{showEnrollmentForm ? "Cancel" : "＋ Enroll employee"}</button>}</div>
    {showEnrollmentForm && canManageLearning && <form className="record-form" onSubmit={saveEnrollment}><div className="form-grid two-col"><label>Course<select required value={enrollmentDraft.course_id} onChange={(e) => setEnrollmentDraft({ ...enrollmentDraft, course_id: e.target.value })}><option value="">Select course</option>{courses.filter((course) => course.active).map((course) => <option key={course.id} value={course.id}>{course.title}</option>)}</select></label><label>Employee<select required value={enrollmentDraft.employee_id} onChange={(e) => setEnrollmentDraft({ ...enrollmentDraft, employee_id: e.target.value })}><option value="">Select employee</option>{employeeOptions.map((employee) => <option key={employee.id} value={employee.id}>{employee.name}</option>)}</select></label></div><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Enroll"}</button></form>}
    <div className="table-scroll"><table className="data-table"><thead><tr><th>COURSE</th><th>EMPLOYEE</th><th>STATUS</th><th>SCORE</th><th>ACTION</th></tr></thead><tbody>{enrollments.map((enrollment) => { const course = courses.find((row) => row.id === enrollment.course_id); const employee = employeeOptions.find((row) => row.id === enrollment.employee_id); return <tr key={enrollment.id}><td>{course?.title ?? `Course #${enrollment.course_id}`}</td><td>{employee?.name ?? `Employee #${enrollment.employee_id}`}</td><td><span className={`status-badge ${enrollment.status === "Completed" ? "green" : "blue"}`}><i/>{enrollment.status}</span></td><td>{enrollment.score ?? "—"}</td><td>{canManageLearning && enrollment.status !== "Completed" && enrollment.status !== "Cancelled" && <><button className="row-action" onClick={() => void updateEnrollment(enrollment, "In Progress")}>Start</button> <button className="row-action" onClick={() => void updateEnrollment(enrollment, "Completed")}>Complete</button></>}</td></tr>; })}{enrollments.length === 0 && <tr><td colSpan={5}><EmptyState title="No enrollments yet" detail="Enroll employees in courses to track their progress."/></td></tr>}</tbody></table></div>
  </section>
</div>}

{active === "notifications" && <div className="payroll-layout">
  <section className="surface-card">
    <div className="card-heading"><div><h2>My notifications</h2><p>Account alerts sent by administrators.</p></div>{canSendNotifications && <button className="secondary-button" onClick={() => setShowNotificationForm(!showNotificationForm)}>{showNotificationForm ? "Cancel" : "＋ Send notification"}</button>}</div>
    {showNotificationForm && canSendNotifications && <form className="record-form" onSubmit={sendNotification}><div className="form-grid two-col"><label>Title<input required minLength={2} maxLength={200} value={notificationDraft.title} onChange={(e) => setNotificationDraft({ ...notificationDraft, title: e.target.value })}/></label><label>Category<select value={notificationDraft.category} onChange={(e) => setNotificationDraft({ ...notificationDraft, category: e.target.value })}><option>General</option><option>Leave</option><option>Payroll</option><option>Performance</option><option>Learning</option><option>Announcement</option></select></label></div><label>Message<textarea required minLength={2} maxLength={4000} rows={3} value={notificationDraft.message} onChange={(e) => setNotificationDraft({ ...notificationDraft, message: e.target.value })}/></label><button className="primary-button" disabled={busy}>{busy ? "Sending…" : "Broadcast to all active accounts"}</button></form>}
    <div className="notification-list">{notifications.map((notification) => <article className={`notification-row ${notification.read ? "" : "unread"}`} key={notification.id}><div><b>{notification.title}</b><p>{notification.message}</p><small>{notification.category} · {new Date(notification.created_at).toLocaleString()}</small></div>{!notification.read && <button className="row-action" onClick={() => void markRead(notification)}>Mark read</button>}</article>)}{notifications.length === 0 && <EmptyState title="No notifications" detail="Notifications appear here when administrators send them."/>}</div>
  </section>
  <section className="surface-card">
    <div className="card-heading"><div><h2>Announcements</h2><p>Organization-wide updates for every user.</p></div>{canSendNotifications && <button className="secondary-button" onClick={() => setShowAnnouncementForm(!showAnnouncementForm)}>{showAnnouncementForm ? "Cancel" : "＋ New announcement"}</button>}</div>
    {showAnnouncementForm && <form className="record-form" onSubmit={saveAnnouncement}><label>Title<input required minLength={2} maxLength={200} value={announcementDraft.title} onChange={(e) => setAnnouncementDraft({ ...announcementDraft, title: e.target.value })}/></label><label>Body<textarea required minLength={2} maxLength={8000} rows={3} value={announcementDraft.body} onChange={(e) => setAnnouncementDraft({ ...announcementDraft, body: e.target.value })}/></label><label className="checkbox-label"><input type="checkbox" checked={announcementDraft.pinned} onChange={(e) => setAnnouncementDraft({ ...announcementDraft, pinned: e.target.checked })}/> Pin to top</label><button className="primary-button" disabled={busy}>{busy ? "Publishing…" : "Publish announcement"}</button></form>}
    <div className="notification-list">{announcements.map((announcement) => <article className="notification-row" key={announcement.id}><div><b>{announcement.pinned ? "📌 " : ""}{announcement.title}</b><p>{announcement.body}</p><small>{new Date(announcement.created_at).toLocaleString()}{announcement.expires_at ? ` · expires ${new Date(announcement.expires_at).toLocaleDateString()}` : ""}</small></div></article>)}{announcements.length === 0 && <EmptyState title="No announcements" detail="Published announcements appear here for everyone."/>}</div>
  </section>
</div>}

{active === "reports" && !canViewReports && <section className="surface-card"><EmptyState title="Access denied" detail="Reports are restricted to HR and payroll administrators." action="Return to overview" onClick={() => setActive("overview")}/></section>}
{active === "reports" && canViewReports && <div className="payroll-layout">
  <section className="surface-card">
    <div className="card-heading"><div><h2>Reports & exports</h2><p>Organization metrics and downloadable CSV exports.</p></div></div>
    {reportSummary && <div className="metric-grid"><Metric title="Total employees" value={reportSummary.employee_count} symbol="♙" tone="blue" detail={`${reportSummary.active_employee_count} active`}/><Metric title="Departments" value={reportSummary.department_count} symbol="▤" tone="violet" detail="Active organization units"/><Metric title="Present today" value={reportSummary.present_today} symbol="◷" tone="green" detail="Explicit check-in records"/><Metric title="Pending leave" value={reportSummary.pending_leave_requests} symbol="▧" tone="amber" detail="Awaiting manager review"/><Metric title="Open requisitions" value={reportSummary.open_requisitions} symbol="📋" tone="blue" detail="Recruitment pipeline"/><Metric title="Active training" value={reportSummary.active_training_enrollments} symbol="🎓" tone="violet" detail="Enrolled or in progress"/></div>}
    {reportSummary && <div className="module-summary-strip"><div><span>Total gross payroll</span><b>{reportSummary.payroll_gross_total}</b></div><div><span>Total deductions</span><b>{reportSummary.payroll_deductions_total}</b></div><div><span>Total net pay</span><b>{reportSummary.payroll_net_total}</b></div><small>Payroll totals are calculated from stored payslips across all finalized runs.</small></div>}
    <div className="card-heading"><div><h3>CSV exports</h3><p>Exports reapply the same access rules as the interface.</p></div></div>
    <div className="attendance-actions"><button className="secondary-button" onClick={() => void exportCsv("/api/reports/employees.csv", "employees.csv")}>Employees CSV</button><button className="secondary-button" onClick={() => void exportCsv("/api/reports/attendance.csv", "attendance.csv")}>Attendance CSV</button><button className="secondary-button" onClick={() => void exportCsv("/api/reports/leave.csv", "leave-requests.csv")}>Leave CSV</button><button className="secondary-button" onClick={() => void exportCsv("/api/reports/payroll.csv", "payslips.csv")}>Payslips CSV</button></div>
  </section>
</div>}

{active === "settings" && <div className="settings-layout"><section className="surface-card settings-profile"><span className="large-avatar">{user.name.slice(0, 1).toUpperCase()}</span><div><p className="eyebrow">SIGNED IN ACCOUNT</p><h2>{user.name}</h2><p>{user.email}</p><span className="role-pill">{user.role}</span></div></section><div className="settings-security">{canAdminOrganization && <section className="surface-card module-card"><div className="card-heading"><div><h2>Organization profile</h2><p>Manage the active organization. Access remains scoped to this organization.</p></div></div><form className="record-form compact-form" onSubmit={saveOrganization}><label>Organization name<input required minLength={2} maxLength={120} value={organizationName} onChange={(event) => setOrganizationName(event.target.value)}/></label><p>Organization key: <code>{organization?.slug}</code></p><button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Save organization"}</button></form></section>}<section className="surface-card module-card"><div className="card-heading"><div><h2>Change password</h2><p>Use a unique password with at least eight characters. Changing it ends every active session.</p></div></div><form className="record-form password-form" onSubmit={changePassword}><label>Current password<input type="password" autoComplete="current-password" value={passwordDraft.current_password} onChange={(e) => setPasswordDraft({ ...passwordDraft, current_password: e.target.value })} required/></label><label>New password<input type="password" autoComplete="new-password" minLength={8} maxLength={128} value={passwordDraft.new_password} onChange={(e) => setPasswordDraft({ ...passwordDraft, new_password: e.target.value })} required/></label><button className="primary-button" disabled={busy}>{busy ? "Updating…" : "Update password"}</button></form>{mfaEnabled || mfaSecret || mfaEnrolling || mfaVerifying ? <section className="surface-card module-card"><div className="card-heading"><div><h2>{mfaEnabled ? "Multi-factor authentication (active)" : "Set up multi-factor authentication"}</h2><p>{mfaEnabled ? "Your account is protected with MFA. You can remove it if needed." : "Add an authenticator app for stronger account security."}</p></div></div>{mfaSecret && <div className="mfa-enrollment-card"><h3>Save your setup key and backup codes</h3><div className="mfa-secret"><b>Setup key:</b> <code>{mfaSecret}</code></div><div className="mfa-backup-codes"><b>Backup codes (save these somewhere safe):</b><ul>{mfaBackupCodes.map((code, i) => <li key={i}>{code}</li>)}</ul></div><p className="mfa-hint">Enter a 6-digit code from your authenticator app below to verify and activate MFA.</p></div>}{!mfaSecret && mfaVerifying && <label>Verification code<input type="text" autoComplete="off" minLength={6} maxLength={8} placeholder="123456" onChange={(e) => setMfaVerifyingCode(e.target.value)} required/></label>}{!mfaSecret && !mfaVerifying && <button className="primary-button" disabled={busy || mfaEnrolling} onClick={enrollMFA}>{mfaEnrolling ? "Generating…" : "Enable MFA"}</button>}{mfaVerifying && !mfaSecret && <div className="form-actions"><button className="primary-button" disabled={busy} onClick={() => verifyMFA(mfaVerifyingCode || "")}>Verify &amp; activate</button>{mfaBackupCodes.length > 0 && <button type="button" className="secondary-button" onClick={() => { setMfaSecret(null); setMfaBackupCodes([]); setMfaVerifying(false); }}>Cancel</button>}</div>}{mfaEnabled && <button className="primary-button" disabled={busy} onClick={removeMFA} style={{ background: "transparent", border: "1px solid var(--danger)", color: "var(--danger)" }}>Remove MFA</button>}</section> : <section className="surface-card module-card"><div className="card-heading"><div><h2>Multi-factor authentication</h2><p>Add an authenticator app for stronger account security.</p></div></div><button className="primary-button" disabled={busy} onClick={enrollMFA}>{mfaEnrolling ? "Generating…" : "Enable MFA"}</button></section>}<div className="security-explainer"><b>Session security</b><p>Access tokens stay in this browser tab. Refresh credentials use an HttpOnly cookie, and each browser session can be revoked here. Use HTTPS in production.</p></div></section><SessionManager sessions={sessions} busy={busy} onEndSession={(session) => void endSession(session)} onEndAllSessions={() => void endOtherSessions()}/></div></div>}

<footer className="app-footer">
  <span>© 2026 Talentry Workforce OS</span>
  <span className="footer-attribution">Talentry Workforce OS — view-only attribution, not editable.</span>
</footer></div></section></main>;
}

function sectionDescription(section: Section): string {
  const descriptions: Record<Section, string> = { overview: "A live view of workforce operations.", employees: "Manage employee records in the organization directory.", departments: "Maintain the organization’s department list.", organization: "Manage branches, designations, and job grades for this organization.", attendance: "Record and review daily work attendance.", leave: "Submit requests and review pending time off.", users: "Manage account access and server-assigned roles.", payroll: "Run payroll and view payslips.", recruitment: "Manage job requisitions and candidates.", performance: "Manage goals, review cycles, and performance reviews.", learning: "Manage training courses and employee enrollments.", notifications: "Read your notifications and publish announcements.", reports: "Review organization metrics and download CSV exports.", settings: "Review account details and update your password.", "module-access": "Control which roles can access each module." };
  return descriptions[section];
}

function Metric({ title, value, symbol, tone, detail }: { title: string; value: string | number | null | undefined; symbol: string; tone: string; detail: string }) {
  return <article className="metric-card"><div className="metric-top"><span>{title}</span><i className={`metric-icon ${tone}`}>{symbol}</i></div><b className="metric-value">{value ?? "—"}</b><p>{detail}</p></article>;
}

function EmptyState({ title, detail, action, onClick }: { title: string; detail: string; action?: string; onClick?: () => void }) {
  return <div className="empty-state"><span className="empty-symbol">⌁</span><b>{title}</b><p>{detail}</p>{action && onClick && <button className="text-action" onClick={onClick}>{action} →</button>}</div>;
}
