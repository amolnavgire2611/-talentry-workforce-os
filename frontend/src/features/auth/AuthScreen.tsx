import { useEffect, useState, type FormEvent } from "react";
import { api, jsonBody, saveAccessToken, saveCsrfToken } from "../../lib/api";

type User = { id: number; name: string; email: string; role: string; active: boolean };
type AuthResponse = { message: string; access_token: string; csrf_token: string; user: User };
type AuthMode = "login" | "register" | "admin" | "invited" | "forgot" | "reset" | "mfa";

// Roles an administrator can grant through a one-time registration code.
// Super Admin is intentionally excluded; it is created only through the
// one-time setup key or the trusted-terminal bootstrap command.
const ROLE_OPTIONS = [
  "Employee", "Department Manager", "HR Manager", "HR Administrator", "Organization Admin",
  "Recruiter", "Payroll Administrator", "Attendance Administrator",
];

export default function AuthScreen({ onAuthenticated, infoMessage }: {
  onAuthenticated: (user: User, message: string) => void;
  infoMessage?: string | null;
}) {
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [adminRegistrationAvailable, setAdminRegistrationAvailable] = useState(false);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [registerRole, setRegisterRole] = useState("Employee");

  useEffect(() => {
    let mounted = true;
    api<{ available: boolean }>("/api/auth/admin-registration-status")
      .then((status) => { if (mounted) setAdminRegistrationAvailable(status.available); })
      .catch(() => { if (mounted) setAdminRegistrationAvailable(false); });
    return () => { mounted = false; };
  }, []);

  async function submitAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    const form = new FormData(event.currentTarget);
    const roleInvitation = authMode === "register" && registerRole !== "Employee";
    const body: Record<string, unknown> = {
      ...(authMode !== "invited" && authMode !== "forgot" && authMode !== "reset" && authMode !== "mfa" && !roleInvitation
        ? { email: String(form.get("email") ?? "") } : {}),
      password: String(form.get("password") ?? ""),
      ...((authMode === "admin" || (authMode === "register" && !roleInvitation)) ? { name: String(form.get("name") ?? "") } : {}),
      ...(authMode === "admin" ? { setup_token: String(form.get("setup_token") ?? "") } : {}),
      ...((authMode === "invited" || roleInvitation) ? { invitation_token: String(form.get("invitation_token") ?? "") } : {}),
      ...(authMode === "reset" ? { token: String(form.get("token") ?? "") } : {}),
    };
    const path = authMode === "admin" ? "/api/auth/register-admin"
      : authMode === "register" && !roleInvitation ? "/api/auth/register"
        : authMode === "invited" || roleInvitation ? "/api/auth/register-invited"
          : authMode === "forgot" ? "/api/auth/password/forgot"
            : authMode === "reset" ? "/api/auth/password/reset"
              : authMode === "mfa" ? "/api/auth/mfa/verify" : "/api/auth/login";
    try {
      if (authMode === "forgot") {
        await api<void>(path, { method: "POST", body: jsonBody(body) });
        setNotice({ kind: "success", text: "If an account exists for that email, a password reset code has been sent through your organization's trusted channel." });
      } else if (authMode === "reset") {
        await api<void>(path, { method: "POST", body: jsonBody(body) });
        setNotice({ kind: "success", text: "Your password has been reset. You can now sign in." });
        setAuthMode("login");
      } else if (authMode === "mfa") {
        await api<void>(path, { method: "POST", body: jsonBody(body) });
        setNotice({ kind: "success", text: "MFA verification complete. Your account is now protected." });
        setAuthMode("login");
      } else {
        const result = await api<AuthResponse>(path, { method: "POST", body: jsonBody(body) });
        saveAccessToken(result.access_token);
        saveCsrfToken(result.csrf_token);
        onAuthenticated(result.user, result.message);
      }
    } catch (error) {
      setNotice({ kind: "error", text: error instanceof Error ? error.message : "Something went wrong. Please try again." });
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-screen">
    <section className="auth-aside">
      <div className="brand-lockup"><span className="brand-mark">T</span><span><b>Talentry</b><small>Workforce OS</small></span></div>
      <div className="auth-story"><p className="eyebrow">PEOPLE. OPERATIONS. PROGRESS.</p><h1>Make people<br />work <em>better.</em></h1><p>A thoughtful workspace for the teams shaping what comes next.</p><div className="auth-proof"><span>01</span><div><b>One place for your people</b><small>Manage workforce operations with clarity.</small></div></div></div>
      <small className="auth-copyright">© 2026 Talentry Workforce OS</small>
    </section>
    <section className="auth-main"><div className="auth-card">
      <span className="auth-mobile-brand">Talentry Workforce OS</span>
      <p className="eyebrow">{authMode === "forgot" ? "RESET YOUR PASSWORD" : authMode === "reset" ? "SET NEW PASSWORD" : authMode === "mfa" ? "MULTI-FACTOR AUTHENTICATION" : "SECURE WORKSPACE ACCESS"}</p>
      <h2>{authMode === "admin" ? "Set up the administrator" : authMode === "register" ? "Create your account" : authMode === "invited" ? "Complete registration" : authMode === "forgot" ? "Forgot password" : authMode === "reset" ? "Reset password" : authMode === "mfa" ? "Verify MFA" : "Sign in to your workspace"}</h2>
      <p className="auth-intro">{authMode === "admin" ? "Create the first Super Admin account using the setup key from your administrator." : authMode === "register" ? "Register with your work email to get started." : authMode === "invited" ? "Enter the one-time registration code from your administrator and choose a password." : authMode === "forgot" ? "Enter your work email. A password reset code will be sent through your organization's trusted channel." : authMode === "reset" ? "Enter the reset code and choose a new password." : authMode === "mfa" ? "Verify your authenticator app code to complete MFA setup." : "Use your account credentials to access your workspace."}</p>
      <form onSubmit={submitAuth} className="stack-form">
        {authMode !== "mfa" && (authMode === "admin" || (authMode === "register" && registerRole === "Employee")) && <label>Full name<input name="name" autoComplete="name" minLength={2} maxLength={100} placeholder="Your full name" required /></label>}
        {(authMode === "login" || authMode === "forgot" || authMode === "admin" || (authMode === "register" && registerRole === "Employee")) && <label>Work email<input name="email" type="email" autoComplete="email" placeholder="you@company.com" required /></label>}
        {authMode === "register" && <label>Account role<select value={registerRole} onChange={(event) => { setRegisterRole(event.target.value); setNotice(null); }}>{ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}</select></label>}
        {authMode === "register" && registerRole !== "Employee" && <label>Administrator registration code<input name="invitation_token" type="password" autoComplete="off" minLength={32} maxLength={256} placeholder="Paste the one-time code from your administrator" required /></label>}
        {authMode === "invited" && <label>One-time registration code<input name="invitation_token" type="password" autoComplete="off" minLength={32} maxLength={256} placeholder="Paste the code from your administrator" required /></label>}
        {authMode === "reset" && <label>Reset code<input name="token" type="text" autoComplete="off" minLength={32} maxLength={256} placeholder="Paste the reset code" required /></label>}
        {authMode === "mfa" && <label>Verification code<input name="code" type="text" autoComplete="off" minLength={6} maxLength={8} placeholder="123456" required /></label>}
        {(authMode !== "mfa" && authMode !== "forgot") && <label>Password<input name="password" type="password" autoComplete={authMode === "login" ? "current-password" : "new-password"} minLength={authMode === "admin" || authMode === "invited" || authMode === "reset" || (authMode === "register" && registerRole !== "Employee") ? 12 : authMode === "register" ? 8 : 1} maxLength={128} placeholder={authMode === "login" ? "Enter your password" : authMode === "register" && registerRole === "Employee" ? "At least 8 characters" : "At least 12 characters"} required /></label>}
        {authMode === "admin" && <label>Administrator setup key<input name="setup_token" type="password" autoComplete="off" minLength={32} maxLength={256} placeholder="Paste the setup key" required /></label>}
        <button className="primary-button wide" disabled={busy}>{busy ? "Please wait…" : authMode === "admin" ? "Create administrator" : authMode === "register" ? "Create account" : authMode === "invited" ? "Complete registration" : authMode === "forgot" ? "Send reset code" : authMode === "reset" ? "Reset password" : authMode === "mfa" ? "Verify MFA code" : "Sign in"}<span aria-hidden="true">→</span></button>
      </form>
      {authMode === "login" ? <p className="auth-switch">New to Nexora?<button type="button" onClick={() => { setAuthMode("register"); setNotice(null); }}>Register</button></p> : <p className="auth-switch">Already have an account?<button type="button" onClick={() => { setAuthMode("login"); setNotice(null); }}>Sign in</button></p>}
      {authMode === "login" && <p className="auth-switch">Forgot your password?<button type="button" onClick={() => { setAuthMode("forgot"); setNotice(null); }}>Reset password</button></p>}
      {authMode === "login" && <p className="auth-switch">Received an invitation code?<button type="button" onClick={() => { setAuthMode("invited"); setNotice(null); }}>Complete registration</button></p>}
      {adminRegistrationAvailable && authMode === "login" && <p className="auth-switch">Setting up Nexora?<button type="button" onClick={() => { setAuthMode("admin"); setNotice(null); }}>Create administrator</button></p>}
      {notice && <p className={`inline-notice ${notice.kind}`} role="status">{notice.text}</p>}
      {infoMessage && <p className="inline-notice success" role="status">{infoMessage}</p>}
      <p className="security-note">{authMode === "admin" ? "This setup is available only until the first Super Admin account is created." : authMode === "register" ? (registerRole === "Employee" ? "New registrations receive the Employee role. Other roles require a one-time code issued by an administrator." : `Selected role: ${registerRole}. The administrator's one-time code authorizes this role and is valid for 48 hours.`) : authMode === "invited" ? "The registration code is single-use and expires after 48 hours." : "Role permissions are verified by the service."}</p>
    </div></section>
  </main>;
}
