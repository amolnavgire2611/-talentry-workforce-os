// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import EmployeeProfilePanel from "./EmployeeProfilePanel";
import { api } from "../../lib/api";

vi.mock("../../lib/api", () => ({
  api: vi.fn(),
  jsonBody: vi.fn((value: unknown) => JSON.stringify(value)),
}));

const mockedApi = vi.mocked(api);
const employee = { id: 7, employee_code: "NX-7", name: "Taylor Employee", department: "People", role: "Analyst", status: "Active" };

describe("employee private profile panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.mockImplementation(async <T,>(path: string): Promise<T> => {
      if (path.endsWith("/contact")) return null as T;
      if (path.endsWith("/emergency-contacts")) return [] as T;
      if (path.endsWith("/employment-history")) return [] as T;
      if (path.endsWith("/contracts")) return [] as T;
      return {} as T;
    });
  });

  afterEach(() => cleanup());

  it("loads and saves contact information through the employee self-service endpoint", async () => {
    render(<EmployeeProfilePanel employee={employee} isSelf canManagePrivate canManageContracts={false} onClose={vi.fn()}/>);
    await screen.findByText("No history events are recorded for this profile yet.");
    const contactForm = screen.getByRole("button", { name: "Save contact details" }).closest("form");
    if (!contactForm) throw new Error("Contact form was not rendered");
    fireEvent.change(screen.getByLabelText("Personal email"), { target: { value: "taylor@example.com" } });
    fireEvent.change(within(contactForm).getByLabelText("Phone"), { target: { value: "+1 555 123 4567" } });
    fireEvent.click(screen.getByRole("button", { name: "Save contact details" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/api/employees/me/contact", expect.objectContaining({ method: "PUT" })));
    expect(await screen.findByText("Contact details saved.")).toBeTruthy();
  });

  it("does not request or render private details for roles without HR or owner access", async () => {
    render(<EmployeeProfilePanel employee={employee} isSelf={false} canManagePrivate={false} canManageContracts={false} onClose={vi.fn()}/>);
    expect(await screen.findByText("Contact information, emergency contacts, and employment history are available only to the employee and authorized HR roles.")).toBeTruthy();
    expect(api).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Personal email")).toBeNull();
  });
});
