export type RefreshSession = {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  revoked_at: string | null;
  current: boolean;
};

export default function SessionManager({
  sessions,
  busy,
  onEndSession,
  onEndAllSessions,
}: {
  sessions: RefreshSession[];
  busy: boolean;
  onEndSession: (session: RefreshSession) => void;
  onEndAllSessions: () => void;
}) {
  const hasActiveSessions = sessions.some((session) => !session.revoked_at);

  return <section className="surface-card module-card">
    <div className="card-heading session-heading">
      <div><h2>Active sessions</h2><p>End sessions you no longer use. Ending this session signs you out.</p></div>
      <button className="secondary-button" disabled={busy || !hasActiveSessions} onClick={onEndAllSessions}>End all sessions</button>
    </div>
    <div className="session-list">
      {sessions.length ? sessions.map((session) => <article className="session-row" key={session.id}>
        <div className="session-description">
          <b>{session.current ? "This session" : "Other session"}</b>
          <small>Started {new Date(session.created_at).toLocaleString()}</small>
          <small>Last refreshed {new Date(session.last_seen_at).toLocaleString()} · Expires {new Date(session.expires_at).toLocaleDateString()}</small>
        </div>
        <span className={`status-badge ${session.revoked_at ? "muted" : session.current ? "green" : "amber"}`}>
          <i/>{session.revoked_at ? "Ended" : session.current ? "Current" : "Active"}
        </span>
        {!session.revoked_at && <button className="row-action" disabled={busy} onClick={() => onEndSession(session)}>
          {session.current ? "Sign out" : "End session"}
        </button>}
      </article>) : <p className="session-empty">No sessions found.</p>}
    </div>
  </section>;
}
