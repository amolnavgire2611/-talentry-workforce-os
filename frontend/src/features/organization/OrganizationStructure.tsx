import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, jsonBody } from "../../lib/api";

type Page<T> = { items: T[]; total: number; limit: number; offset: number };
type Branch = { id: number; code: string; name: string; address: string | null; active: boolean; created_at: string };
type Designation = { id: number; name: string; description: string | null; active: boolean; created_at: string };
type JobGrade = { id: number; code: string; name: string; description: string | null; rank: number; active: boolean; created_at: string };

function message(error: unknown) {
  return error instanceof Error ? error.message : "Could not save the organization catalog item.";
}

export default function OrganizationStructure() {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [grades, setGrades] = useState<JobGrade[]>([]);
  const [branchDraft, setBranchDraft] = useState({ code: "", name: "", address: "" });
  const [designationDraft, setDesignationDraft] = useState({ name: "", description: "" });
  const [gradeDraft, setGradeDraft] = useState({ code: "", name: "", description: "", rank: "1" });
  const [editingBranch, setEditingBranch] = useState<number | null>(null);
  const [editingDesignation, setEditingDesignation] = useState<number | null>(null);
  const [editingGrade, setEditingGrade] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    try {
      const [branchPage, designationPage, gradePage] = await Promise.all([
        api<Page<Branch>>("/api/branches?limit=100&offset=0"),
        api<Page<Designation>>("/api/designations?limit=100&offset=0"),
        api<Page<JobGrade>>("/api/job-grades?limit=100&offset=0"),
      ]);
      setBranches(branchPage.items);
      setDesignations(designationPage.items);
      setGrades(gradePage.items);
    } catch (error) {
      setNotice({ kind: "error", text: message(error) });
    }
  }, []);

  useEffect(() => { void Promise.resolve().then(load); }, [load]);

  async function submit(event: FormEvent<HTMLFormElement>, path: string, payload: unknown, editingId: number | null,
                       reset: () => void, kind: string) {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      await api(path, { method: editingId === null ? "POST" : "PUT", body: jsonBody(payload) });
      reset();
      setNotice({ kind: "success", text: `${kind} ${editingId === null ? "created" : "updated"}.` });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: message(error) });
    } finally {
      setBusy(false);
    }
  }

  async function archive(path: string, name: string, reset?: () => void) {
    if (!window.confirm(`Archive ${name}? Existing employee history will be retained.`)) return;
    setBusy(true);
    setNotice(null);
    try {
      await api<void>(path, { method: "DELETE" });
      reset?.();
      setNotice({ kind: "success", text: `${name} archived.` });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: message(error) });
    } finally {
      setBusy(false);
    }
  }

  async function reactivate(path: string, payload: unknown, name: string) {
    setBusy(true);
    setNotice(null);
    try {
      await api(path, { method: "PUT", body: jsonBody(payload) });
      setNotice({ kind: "success", text: `${name} reactivated.` });
      await load();
    } catch (error) {
      setNotice({ kind: "error", text: message(error) });
    } finally {
      setBusy(false);
    }
  }

  function resetBranch() { setBranchDraft({ code: "", name: "", address: "" }); setEditingBranch(null); }
  function resetDesignation() { setDesignationDraft({ name: "", description: "" }); setEditingDesignation(null); }
  function resetGrade() { setGradeDraft({ code: "", name: "", description: "", rank: "1" }); setEditingGrade(null); }

  return <div className="organization-structure">
    {notice && <div className={`toast-message ${notice.kind}`} role="status"><span>{notice.kind === "success" ? "✓" : "!"}</span>{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss notification">×</button></div>}
    <div className="catalog-grid">
      <section className="surface-card module-card">
        <div className="card-heading"><div><h2>Branches</h2><p>Maintain office locations for this organization.</p></div><span className="record-count">{branches.length} records</span></div>
        <form className="record-form compact-form" onSubmit={(event) => void submit(event, editingBranch === null ? "/api/branches" : `/api/branches/${editingBranch}`, branchDraft, editingBranch, resetBranch, "Branch")}>
          <div className="form-grid two-col"><label>Branch code<input required minLength={2} maxLength={30} value={branchDraft.code} onChange={(event) => setBranchDraft({ ...branchDraft, code: event.target.value })}/></label><label>Branch name<input required minLength={2} maxLength={100} value={branchDraft.name} onChange={(event) => setBranchDraft({ ...branchDraft, name: event.target.value })}/></label></div>
          <label>Address <span className="optional">Optional</span><input maxLength={300} value={branchDraft.address} onChange={(event) => setBranchDraft({ ...branchDraft, address: event.target.value })}/></label>
          <div className="form-actions">{editingBranch !== null && <button type="button" className="secondary-button" onClick={resetBranch}>Cancel</button>}<button className="primary-button" disabled={busy}>{busy ? "Saving…" : editingBranch === null ? "Add branch" : "Save branch"}</button></div>
        </form>
        <div className="department-list">{branches.map((branch) => <article className="department-row" key={branch.id}><span className="department-symbol">{branch.code.slice(0, 1).toUpperCase()}</span><div><b>{branch.name} <span className="code-text">{branch.code}</span></b><p>{branch.address || "No address provided"}</p></div><span className={`status-badge ${branch.active ? "green" : "muted"}`}><i/>{branch.active ? "Active" : "Archived"}</span><button className="row-action" disabled={busy} onClick={() => { setEditingBranch(branch.id); setBranchDraft({ code: branch.code, name: branch.name, address: branch.address ?? "" }); }}>Edit</button>{branch.active ? <button className="row-action" disabled={busy} onClick={() => void archive(`/api/branches/${branch.id}`, branch.name, editingBranch === branch.id ? resetBranch : undefined)}>Archive</button> : <button className="row-action" disabled={busy} onClick={() => void reactivate(`/api/branches/${branch.id}`, { code: branch.code, name: branch.name, address: branch.address, active: true }, branch.name)}>Reactivate</button>}</article>)}{branches.length === 0 && <p className="empty-inline">No branches have been added.</p>}</div>
      </section>

      <section className="surface-card module-card">
        <div className="card-heading"><div><h2>Designations</h2><p>Define job titles used in employee records.</p></div><span className="record-count">{designations.length} records</span></div>
        <form className="record-form compact-form" onSubmit={(event) => void submit(event, editingDesignation === null ? "/api/designations" : `/api/designations/${editingDesignation}`, designationDraft, editingDesignation, resetDesignation, "Designation")}>
          <label>Designation name<input required minLength={2} maxLength={100} value={designationDraft.name} onChange={(event) => setDesignationDraft({ ...designationDraft, name: event.target.value })}/></label>
          <label>Description <span className="optional">Optional</span><input maxLength={500} value={designationDraft.description} onChange={(event) => setDesignationDraft({ ...designationDraft, description: event.target.value })}/></label>
          <div className="form-actions">{editingDesignation !== null && <button type="button" className="secondary-button" onClick={resetDesignation}>Cancel</button>}<button className="primary-button" disabled={busy}>{busy ? "Saving…" : editingDesignation === null ? "Add designation" : "Save designation"}</button></div>
        </form>
        <div className="department-list">{designations.map((designation) => <article className="department-row" key={designation.id}><span className="department-symbol">{designation.name.slice(0, 1).toUpperCase()}</span><div><b>{designation.name}</b><p>{designation.description || "No description provided"}</p></div><span className={`status-badge ${designation.active ? "green" : "muted"}`}><i/>{designation.active ? "Active" : "Archived"}</span><button className="row-action" disabled={busy} onClick={() => { setEditingDesignation(designation.id); setDesignationDraft({ name: designation.name, description: designation.description ?? "" }); }}>Edit</button>{designation.active ? <button className="row-action" disabled={busy} onClick={() => void archive(`/api/designations/${designation.id}`, designation.name, editingDesignation === designation.id ? resetDesignation : undefined)}>Archive</button> : <button className="row-action" disabled={busy} onClick={() => void reactivate(`/api/designations/${designation.id}`, { name: designation.name, description: designation.description, active: true }, designation.name)}>Reactivate</button>}</article>)}{designations.length === 0 && <p className="empty-inline">No designations have been added.</p>}</div>
      </section>

      <section className="surface-card module-card">
        <div className="card-heading"><div><h2>Job grades</h2><p>Set organization-specific grade codes and ordering.</p></div><span className="record-count">{grades.length} records</span></div>
        <form className="record-form compact-form" onSubmit={(event) => void submit(event, editingGrade === null ? "/api/job-grades" : `/api/job-grades/${editingGrade}`, { ...gradeDraft, rank: Number(gradeDraft.rank) }, editingGrade, resetGrade, "Job grade")}>
          <div className="form-grid two-col"><label>Grade code<input required minLength={1} maxLength={30} value={gradeDraft.code} onChange={(event) => setGradeDraft({ ...gradeDraft, code: event.target.value })}/></label><label>Grade name<input required minLength={2} maxLength={100} value={gradeDraft.name} onChange={(event) => setGradeDraft({ ...gradeDraft, name: event.target.value })}/></label><label>Rank<input type="number" min={1} max={1000} required value={gradeDraft.rank} onChange={(event) => setGradeDraft({ ...gradeDraft, rank: event.target.value })}/></label></div>
          <label>Description <span className="optional">Optional</span><input maxLength={500} value={gradeDraft.description} onChange={(event) => setGradeDraft({ ...gradeDraft, description: event.target.value })}/></label>
          <div className="form-actions">{editingGrade !== null && <button type="button" className="secondary-button" onClick={resetGrade}>Cancel</button>}<button className="primary-button" disabled={busy}>{busy ? "Saving…" : editingGrade === null ? "Add job grade" : "Save job grade"}</button></div>
        </form>
        <div className="department-list">{grades.map((grade) => <article className="department-row" key={grade.id}><span className="department-symbol">{grade.rank}</span><div><b>{grade.name} <span className="code-text">{grade.code}</span></b><p>{grade.description || "No description provided"}</p></div><span className={`status-badge ${grade.active ? "green" : "muted"}`}><i/>{grade.active ? "Active" : "Archived"}</span><button className="row-action" disabled={busy} onClick={() => { setEditingGrade(grade.id); setGradeDraft({ code: grade.code, name: grade.name, description: grade.description ?? "", rank: String(grade.rank) }); }}>Edit</button>{grade.active ? <button className="row-action" disabled={busy} onClick={() => void archive(`/api/job-grades/${grade.id}`, grade.name, editingGrade === grade.id ? resetGrade : undefined)}>Archive</button> : <button className="row-action" disabled={busy} onClick={() => void reactivate(`/api/job-grades/${grade.id}`, { code: grade.code, name: grade.name, description: grade.description, rank: grade.rank, active: true }, grade.name)}>Reactivate</button>}</article>)}{grades.length === 0 && <p className="empty-inline">No job grades have been added.</p>}</div>
      </section>
    </div>
  </div>;
}
