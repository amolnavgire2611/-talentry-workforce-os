const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "nexoraAccessToken";
const CSRF_KEY = "nexoraCsrfToken";

export type ApiError = Error & { status?: number; fields?: string[] };
type AuthPayload = { access_token: string; csrf_token: string };

let refreshInFlight: Promise<boolean> | null = null;

export function getAccessToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function saveAccessToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function getCsrfToken(): string | null {
  return localStorage.getItem(CSRF_KEY);
}

export function saveCsrfToken(token: string): void {
  localStorage.setItem(CSRF_KEY, token);
}

export function clearAccessToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(CSRF_KEY);
}

export function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  const rotate = async (): Promise<boolean> => {
    const csrfToken = getCsrfToken();
    if (!csrfToken) {
      clearAccessToken();
      return false;
    }
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfToken },
      });
      if (!response.ok) {
        clearAccessToken();
        return false;
      }
      const payload = await response.json() as AuthPayload;
      if (!payload.access_token || !payload.csrf_token) {
        clearAccessToken();
        return false;
      }
      saveAccessToken(payload.access_token);
      saveCsrfToken(payload.csrf_token);
      return true;
    } catch {
      return false;
    }
  };
  // Web Locks coordinate rotating the single browser cookie across tabs. The
  // local promise covers concurrent requests in browsers without that API.
  const lockRequest = typeof navigator !== "undefined" && navigator.locks
    ? navigator.locks.request("nexora-refresh-session", rotate)
    : rotate();
  refreshInFlight = lockRequest.finally(() => { refreshInFlight = null; });
  return refreshInFlight;
}

function isPublicAuthPath(path: string): boolean {
  return [
    "/api/auth/login", "/api/login", "/api/auth/register", "/api/register",
    "/api/auth/register-admin", "/api/auth/register-invited", "/api/auth/activate",
    "/api/auth/refresh",
  ].includes(path);
}

function requestInit(options: RequestInit, token: string | null): RequestInit {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const method = (options.method ?? "GET").toUpperCase();
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  }
  return { ...options, credentials: "include", headers };
}

async function fetchApi(path: string, options: RequestInit, token: string | null): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, requestInit(options, token));
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let token = getAccessToken();
  let response: Response;
  try {
    response = await fetchApi(path, options, token);
    if (response.status === 401 && token && !isPublicAuthPath(path)) {
      if (await refreshAccessToken()) {
        token = getAccessToken();
        response = await fetchApi(path, options, token);
      } else {
        clearAccessToken();
      }
    }
  } catch {
    throw Object.assign(new Error("Unable to reach NEXORA services. Check that the API is running."), { status: 0 }) as ApiError;
  }

  if (response.status === 204) return undefined as T;
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const body = payload as { detail?: unknown } | null;
    const detail = body?.detail;
    const fields = Array.isArray(detail)
      ? detail.map((issue) => {
          const item = issue as { loc?: (string | number)[]; msg?: string };
          return `${item.loc?.slice(1).join(" → ") || "Form"}: ${item.msg || "Invalid value"}`;
        })
      : [];
    const message = typeof detail === "string" ? detail : fields.join(". ") || `Request failed (${response.status}).`;
    if (response.status === 401) clearAccessToken();
    throw Object.assign(new Error(message), { status: response.status, fields }) as ApiError;
  }
  return payload as T;
}

export function jsonBody(value: unknown): string {
  return JSON.stringify(value);
}
