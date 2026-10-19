// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SessionManager, { type RefreshSession } from "./SessionManager";

const sessions: RefreshSession[] = [
  { id: "current-session", created_at: "2026-10-15T10:00:00Z", last_seen_at: "2026-10-16T10:00:00Z", expires_at: "2026-10-23T10:00:00Z", revoked_at: null, current: true },
  { id: "other-session", created_at: "2026-10-14T10:00:00Z", last_seen_at: "2026-10-15T10:00:00Z", expires_at: "2026-10-22T10:00:00Z", revoked_at: null, current: false },
  { id: "ended-session", created_at: "2026-10-10T10:00:00Z", last_seen_at: "2026-10-10T10:00:00Z", expires_at: "2026-10-17T10:00:00Z", revoked_at: "2026-10-11T10:00:00Z", current: false },
];

describe("session manager", () => {
  afterEach(() => cleanup());

  it("shows current and other sessions and delegates ending the selected session", () => {
    const onEndSession = vi.fn();
    const onEndAllSessions = vi.fn();
    render(<SessionManager sessions={sessions} busy={false} onEndSession={onEndSession} onEndAllSessions={onEndAllSessions}/>);

    expect(screen.getByText("This session")).toBeTruthy();
    expect(screen.getAllByText("Other session")).toHaveLength(2);
    expect(screen.getByText("Ended")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "End session" }));
    expect(onEndSession).toHaveBeenCalledWith(sessions[1]);
    fireEvent.click(screen.getByRole("button", { name: "End all sessions" }));
    expect(onEndAllSessions).toHaveBeenCalledOnce();
  });

  it("does not offer revocation for ended sessions or when no active sessions remain", () => {
    const ended = { ...sessions[0], revoked_at: "2026-10-16T12:00:00Z" };
    render(<SessionManager sessions={[ended]} busy={false} onEndSession={vi.fn()} onEndAllSessions={vi.fn()}/>);
    expect(screen.queryByRole("button", { name: "Sign out" })).toBeNull();
    expect(screen.getByRole("button", { name: "End all sessions" }).hasAttribute("disabled")).toBe(true);
  });
});
