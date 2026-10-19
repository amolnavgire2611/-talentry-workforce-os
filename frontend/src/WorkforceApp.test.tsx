// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import WorkforceApp from "./WorkforceApp";
import { api } from "./lib/api";

vi.mock("./lib/api", () => ({
  api: vi.fn(),
  clearAccessToken: vi.fn(),
  getAccessToken: vi.fn(() => null),
  getCsrfToken: vi.fn(() => null),
  jsonBody: vi.fn((value: unknown) => JSON.stringify(value)),
  refreshAccessToken: vi.fn(async () => false),
  saveAccessToken: vi.fn(),
  saveCsrfToken: vi.fn(),
}));

const mockedApi = vi.mocked(api);

const user = { id: 7, name: "Asha Admin", email: "asha@example.com", role: "HR Administrator", active: true };
const authResponse = { message: "Signed in.", access_token: "access-token", csrf_token: "csrf-token", user };

const moduleCatalog = [
  { id: 1, module_key: "overview", name: "Overview", description: null, active: true, created_at: "2026-01-01T00:00:00", permissions: [] },
  { id: 2, module_key: "employees", name: "Employees", description: null, active: true, created_at: "2026-01-01T00:00:00", permissions: [] },
  { id: 3, module_key: "module-access", name: "Module Access", description: null, active: true, created_at: "2026-01-01T00:00:00", permissions: [] },
];

const permissionsResponse = {
  accessible_modules: ["overview", "employees"],
  modules: moduleCatalog,
};

function mockBackend(loadPermissions: () => Promise<unknown> = () => Promise.resolve(permissionsResponse)) {
  mockedApi.mockImplementation(async <T,>(path: string): Promise<T> => {
    if (path === "/api/auth/admin-registration-status") return { available: false } as T;
    if (path === "/api/auth/login") return authResponse as T;
    if (path === "/api/my-permissions") return (await loadPermissions()) as T;
    if (path === "/api/dashboard") return null as T;
    if (path === "/api/auth/logout") return undefined as T;
    throw new Error(`Unhandled route in test: ${path}`);
  });
}

async function fillLoginForm() {
  fireEvent.change(await screen.findByLabelText("Work email"), { target: { value: user.email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a-strong-password" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

describe("workforce app sidebar", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => cleanup());

  it("renders the sidebar menu right after a fresh login without a page reload", async () => {
    mockBackend();
    render(<WorkforceApp />);
    await screen.findByRole("heading", { name: "Sign in to your workspace" });

    await fillLoginForm();
    await screen.findByRole("button", { name: "Overview" });

    // Permissions are fetched because a user became available, not only on reload.
    expect(mockedApi).toHaveBeenCalledWith("/api/my-permissions");
    expect(screen.getByRole("button", { name: "Employees" })).toBeTruthy();
    // The full catalog is returned, but role filtering hides ungranted modules.
    expect(screen.queryByRole("button", { name: "Module Access" })).toBeNull();
  });

  it("does not leak the previous account's menu into the next session", async () => {
    let failPermissions = false;
    mockBackend(() => (failPermissions
      ? Promise.reject(new Error("permissions unavailable"))
      : Promise.resolve(permissionsResponse)));
    render(<WorkforceApp />);
    await screen.findByRole("heading", { name: "Sign in to your workspace" });
    await fillLoginForm();
    await screen.findByRole("button", { name: "Overview" });

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await screen.findByRole("heading", { name: "Sign in to your workspace" });

    failPermissions = true;
    await fillLoginForm();
    // Second login: permissions fail, so the menu must stay empty instead of
    // showing the signed-out account's modules.
    await screen.findByText("permissions unavailable");
    expect(screen.queryByRole("button", { name: "Overview" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Employees" })).toBeNull();
  });
});
