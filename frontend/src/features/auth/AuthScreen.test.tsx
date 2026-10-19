// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import AuthScreen from "./AuthScreen";
import { api, jsonBody, saveAccessToken, saveCsrfToken } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  api: vi.fn(),
  jsonBody: vi.fn((value: unknown) => JSON.stringify(value)),
  saveAccessToken: vi.fn(),
  saveCsrfToken: vi.fn(),
}));

const mockedApi = vi.mocked(api);
const user = { id: 19, name: "Invited Manager", email: "manager@example.com", role: "Department Manager", active: true };
const authResponse = { message: "Registration complete. You are now signed in.", access_token: "access-token", csrf_token: "csrf-token", user };

describe("invited registration screen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.mockImplementation(async <T,>(path: string): Promise<T> => {
      if (path === "/api/auth/admin-registration-status") return { available: false } as T;
      return authResponse as T;
    });
  });

  afterEach(() => cleanup());

  it("submits the one-time code and password without asking for an email or role", async () => {
    const onAuthenticated = vi.fn();
    render(<AuthScreen onAuthenticated={onAuthenticated} />);

    fireEvent.click(screen.getByRole("button", { name: "Complete registration" }));
    expect(screen.getByRole("heading", { name: "Complete registration" })).toBeTruthy();
    expect(screen.queryByLabelText("Work email")).toBeNull();
    expect(screen.queryByLabelText("Full name")).toBeNull();

    fireEvent.change(screen.getByLabelText("One-time registration code"), {
      target: { value: "single-use-registration-code-that-is-long-enough" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "a-strong-registration-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Complete registration" }));

    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith(user, authResponse.message));
    expect(api).toHaveBeenCalledWith("/api/auth/register-invited", {
      method: "POST",
      body: JSON.stringify({
        password: "a-strong-registration-password",
        invitation_token: "single-use-registration-code-that-is-long-enough",
      }),
    });
    expect(jsonBody).toHaveBeenCalledWith({
      password: "a-strong-registration-password",
      invitation_token: "single-use-registration-code-that-is-long-enough",
    });
    expect(saveAccessToken).toHaveBeenCalledWith("access-token");
    expect(saveCsrfToken).toHaveBeenCalledWith("csrf-token");
  });

  it("shows the server's message when an invitation code is rejected", async () => {
    mockedApi.mockImplementation(async <T,>(path: string): Promise<T> => {
      if (path === "/api/auth/admin-registration-status") return { available: false } as T;
      throw new Error("Registration code is invalid, expired, or already used.");
    });
    render(<AuthScreen onAuthenticated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Complete registration" }));
    fireEvent.change(screen.getByLabelText("One-time registration code"), { target: { value: "x".repeat(48) } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "a-strong-registration-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Complete registration" }));
    expect((await screen.findByRole("status")).textContent).toContain("Registration code is invalid, expired, or already used.");
  });
});
