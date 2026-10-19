# Nexora Workforce OS User Manual

This guide describes the features currently available in the application. Your role controls which sections and records you can access.

## Sign in and register

- Open the application and choose **Sign in** or **Register**.
- Registration asks for your name, work email, and a password of at least 8 characters. New registrations receive the **Employee** role automatically.
- During initial setup, a **Create administrator** option appears if no active Super Admin exists and the backend has an administrator setup key configured. Enter that key to create the first Super Admin; this account needs a password of at least 12 characters.
- If you need a different role, ask a Super Admin to change it in **Access & users**. HR Administrators can manage account access but cannot change roles.
- If your Employee profile page says no profile is linked, ask an administrator to associate your account with your employee record.
- To sign out, choose **Sign out** in the upper right. Access tokens expire automatically. If your session expires, sign in again.

## Navigation

| Section | What it is for |
| --- | --- |
| Overview | Role-specific workforce summary and pending leave counts. |
| Employees / My profile | Search and maintain employee records, or view your own linked profile. |
| Departments | View departments and, for authorized HR roles, add, archive, or reactivate them. |
| Attendance | Record your check-in/check-out and review attendance records available to your role. Times are shown in UTC. |
| Leave management | View balances, request time off, and review requests when your role allows it. |
| Access & users | Manage accounts and roles, available to Super Admins and HR Administrators. |
| Account settings | View your account details and change your password. |

## Role access

| Role | Overview | Employees | Departments | Attendance | Leave | Access & users |
| --- | --- | --- | --- | --- | --- | --- |
| **Super Admin** | Organization summary | View, add, edit, and archive employee records | View, add, edit, archive, and reactivate departments | View organization records; record own time | Manage leave types; review organization requests; submit own requests | Invite/manage accounts, change roles, reissue pending registration codes, deactivate/reactivate completed accounts |
| **HR Administrator** | Organization summary | Same employee management as Super Admin | Same department management as Super Admin | View organization records; record own time | Manage leave types; review organization requests; submit own requests | Invite/manage permitted accounts, reissue pending registration codes, manage account access; cannot change roles |
| **HR Manager** | Organization summary | View, add, edit, and archive employee records | View, add, edit, archive, and reactivate departments | View organization records; record own time | Manage leave types; review organization requests; submit own requests | No access |
| **Department Manager** | Assigned department summary | Read employee records in the assigned department | View the assigned department | View linked team records and own time | Review requests from assigned department; submit own requests | No access |
| **Employee** | Personal summary | View/update own linked profile | No access | Record and view own attendance | View own balances, submit/cancel own requests | No access |
| **Attendance Administrator** | Attendance summary | No access | No access | View organization records; record own time | No access | No access |
| **Recruiter** | Recruitment-scoped summary | No access | No access | No access | No access | No access |
| **Payroll Administrator** | Payroll-scoped summary | No access | No access | No access | No access | No access |

Recruitment and payroll workflows are not implemented yet; those roles currently have Overview and Account settings only. Account settings are available to every role.

## Common tasks

### Check in and out

1. Open **Attendance**.
2. Choose **Check in** when you start work.
3. Choose **Check out** when you finish. You can check in and out once per UTC workday.
4. Review your history below the time-record panel. Authorized attendance viewers see records within their role scope.

### Request time off

1. Open **Leave management** and check your available balances.
2. Choose the first and last day, select a leave type, and enter a reason.
3. For a half-day request, select **Half-day request**; the end date should be the same as the first day.
4. Submit the request and check its status in the request list. Pending requests do not deduct from your balance. Approval deducts the requested working days.
5. You can cancel a pending request. Future approved leave can also be cancelled, which restores its balance.

Weekends and configured holidays are excluded from full-day leave calculations. The application currently does not provide a holiday management screen.

### Review leave requests

Super Admins, HR Administrators, HR Managers, and Department Managers can review pending requests within their scope. Open **Leave management**, find a pending request, then choose **Approve** or **Decline**. You cannot review your own request. Approval is rejected if the employee does not have enough balance.

### Manage employees and departments

- HR Managers and above can search the employee directory, add employee records, edit them, and archive them. Archiving marks a record **Inactive**; it does not permanently delete the record.
- HR Managers and above can add departments and archive/reactivate them. Archived departments are retained.
- Department Managers can view only their assigned department and its employee records. They cannot edit those records.
- Employee accounts can be linked to an employee record by the account provisioning workflow. Contact an administrator if your profile is not linked.

### Manage accounts and roles

- In **Access & users**, HR Administrators and Super Admins can review accounts, issue invitations, rotate pending registration codes, and deactivate/reactivate completed accounts. Pending invitations cannot be reactivated before registration.
- Only a Super Admin can change roles. The role selector appears beside eligible accounts.
- Public registration creates an Employee account; invite codes apply only the role selected by an authorized administrator. Users cannot assign themselves a privileged role.
- The first Super Admin can be created from the login page if `ADMIN_BOOTSTRAP_TOKEN` is configured in the backend, or from the backend terminal with the bootstrap command. The login-page option disappears after any Super Admin record exists, including an inactive account. Remove the environment key after setup.

**Complete an invited registration:** The administrator shares the one-time registration code through a trusted private channel. On the sign-in page choose **Complete registration**, paste the code, and choose a password of at least 12 characters. The code expires after 48 hours and can be used only once. If it expires or is lost, ask the administrator to reissue it. After registration, the account signs in automatically with its administrator-assigned role.

### Change your password

1. Open **Account settings**.
2. Enter your current password and a new password of at least 8 characters.
3. Submit the form. The current access token is revoked, so sign in again with the new password.

## Help and access problems

- **A section is missing:** your role may not include it. Ask your administrator to confirm your assigned role and department.
- **You cannot see a department team's records:** Department Manager access requires an active department assignment and linked employee/user records.
- **Your profile is unavailable:** ask HR or an administrator to link your login account to an employee record.
- **Your session has expired:** sign in again. If sign-in returns a service error, contact the administrator with the error message and time; do not send your password.

## Current product limits

Recruitment, payroll processing, audit-log screens, notifications, and holiday administration are not available in the current user interface. Dashboard summaries reflect the data and modules currently implemented.
