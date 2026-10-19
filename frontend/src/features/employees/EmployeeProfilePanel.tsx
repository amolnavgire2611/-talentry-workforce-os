import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, jsonBody } from "../../lib/api";

type Employee = {
  id: number; employee_code: string; name: string; department: string; role: string; status: string;
  branch_id?: number | null; designation_id?: number | null; job_grade_id?: number | null; reporting_manager_id?: number | null;
};
type Contact = {
  personal_email: string | null; phone: string | null; alternate_phone: string | null; address_line: string | null;
  city: string | null; region: string | null; postal_code: string | null; country: string | null; updated_at: string;
};
type EmergencyContact = {
  id: number; employee_id: number; name: string; relationship: string; phone: string; email: string | null;
  priority: number; created_at: string;
};
type EmploymentEvent = {
  id: number; event_type: string; effective_date: string; department: string; job_title: string;
  branch_name: string | null; designation_name: string | null; grade_name: string | null;
  reporting_manager_name: string | null; employment_status: string; notes: string | null; created_at: string;
};
type EmploymentContract = {
  id: number; employee_id: number; reference: string; employment_type: string; start_date: string;
  end_date: string | null; signed_date: string | null; status: "Draft" | "Active" | "Ended";
  created_at: string; updated_at: string;
};

const emptyContact = {
  personal_email: "", phone: "", alternate_phone: "", address_line: "", city: "", region: "", postal_code: "", country: "",
};
const emptyEmergency = { name: "", relationship: "", phone: "", email: "", priority: "1" };
const emptyContract = { reference: "", employment_type: "Permanent", start_date: "", end_date: "", signed_date: "", status: "Draft" as EmploymentContract["status"] };

function message(error: unknown) {
  return error instanceof Error ? error.message : "Could not load this employee profile.";
}

export default function EmployeeProfilePanel({ employee, isSelf, canManagePrivate, canManageContracts, onClose }: {
  employee: Employee; isSelf: boolean; canManagePrivate: boolean; canManageContracts: boolean; onClose: () => void;
}) {
  const [contact, setContact] = useState<Contact | null>(null);
  const [contactDraft, setContactDraft] = useState(emptyContact);
  const [emergencyContacts, setEmergencyContacts] = useState<EmergencyContact[]>([]);
  const [emergencyDraft, setEmergencyDraft] = useState(emptyEmergency);
  const [editingEmergency, setEditingEmergency] = useState<number | null>(null);
  const [history, setHistory] = useState<EmploymentEvent[]>([]);
  const [contracts, setContracts] = useState<EmploymentContract[]>([]);
  const [contractDraft, setContractDraft] = useState(emptyContract);
  const [editingContract, setEditingContract] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const basePath = isSelf ? "/api/employees/me" : `/api/employees/${employee.id}`;

  const load = useCallback(async () => {
    if (!canManagePrivate) return;
    try {
      const [loadedContact, contacts, events, loadedContracts] = await Promise.all([
        api<Contact | null>(`${basePath}/contact`),
        api<EmergencyContact[]>(`${basePath}/emergency-contacts`),
        api<EmploymentEvent[]>(`${basePath}/employment-history`),
        api<EmploymentContract[]>(`${basePath}/contracts`),
      ]);
      setContact(loadedContact);
      setContactDraft(loadedContact ? {
        personal_email: loadedContact.personal_email ?? "", phone: loadedContact.phone ?? "",
        alternate_phone: loadedContact.alternate_phone ?? "", address_line: loadedContact.address_line ?? "",
        city: loadedContact.city ?? "", region: loadedContact.region ?? "", postal_code: loadedContact.postal_code ?? "",
        country: loadedContact.country ?? "",
      } : emptyContact);
      setEmergencyContacts(contacts);
      setHistory(events);
      setContracts(loadedContracts);
    } catch (error) {
      setNotice({ kind: "error", text: message(error) });
    }
  }, [basePath, canManagePrivate]);

  useEffect(() => { void Promise.resolve().then(load); }, [load]);

  async function saveContact(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setNotice(null);
    try {
      const payload = Object.fromEntries(Object.entries(contactDraft).map(([key, value]) => [key, value.trim() || null]));
      const updated = await api<Contact>(`${basePath}/contact`, { method: "PUT", body: jsonBody(payload) });
      setContact(updated);
      setNotice({ kind: "success", text: "Contact details saved." });
    } catch (error) { setNotice({ kind: "error", text: message(error) }); }
    finally { setBusy(false); }
  }

  async function saveEmergency(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setNotice(null);
    const { priority, ...fields } = emergencyDraft;
    const payload = { ...fields, email: fields.email || null, priority: Number(priority) };
    try {
      await api<EmergencyContact>(editingEmergency ? `/api/emergency-contacts/${editingEmergency}` : `${basePath}/emergency-contacts`, {
        method: editingEmergency ? "PUT" : "POST", body: jsonBody(payload),
      });
      setEmergencyDraft(emptyEmergency); setEditingEmergency(null);
      setNotice({ kind: "success", text: `Emergency contact ${editingEmergency ? "updated" : "added"}.` });
      await load();
    } catch (error) { setNotice({ kind: "error", text: message(error) }); }
    finally { setBusy(false); }
  }

  async function removeEmergency(contactId: number) {
    if (!window.confirm("Remove this emergency contact?")) return;
    setBusy(true); setNotice(null);
    try {
      await api<void>(`/api/emergency-contacts/${contactId}`, { method: "DELETE" });
      setNotice({ kind: "success", text: "Emergency contact removed." });
      await load();
    } catch (error) { setNotice({ kind: "error", text: message(error) }); }
    finally { setBusy(false); }
  }

  async function saveContract(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setNotice(null);
    const payload = { ...contractDraft, end_date: contractDraft.end_date || null, signed_date: contractDraft.signed_date || null };
    try {
      await api<EmploymentContract>(editingContract ? `/api/employment-contracts/${editingContract}` : `${basePath}/contracts`, {
        method: editingContract ? "PUT" : "POST", body: jsonBody(payload),
      });
      setEditingContract(null); setContractDraft(emptyContract);
      setNotice({ kind: "success", text: `Contract ${editingContract ? "updated" : "created"}.` });
      await load();
    } catch (error) { setNotice({ kind: "error", text: message(error) }); }
    finally { setBusy(false); }
  }

  function editContract(contract: EmploymentContract) {
    setEditingContract(contract.id);
    setContractDraft({ reference: contract.reference, employment_type: contract.employment_type,
      start_date: contract.start_date, end_date: contract.end_date ?? "", signed_date: contract.signed_date ?? "",
      status: contract.status });
  }

  function editEmergency(contact: EmergencyContact) {
    setEditingEmergency(contact.id);
    setEmergencyDraft({ name: contact.name, relationship: contact.relationship, phone: contact.phone,
      email: contact.email ?? "", priority: String(contact.priority) });
  }

  return <section className="surface-card employee-profile-panel" aria-labelledby="employee-profile-title">
    <div className="card-heading"><div><p className="eyebrow">EMPLOYEE PROFILE</p><h2 id="employee-profile-title">{employee.name}</h2><p>{employee.employee_code} · {employee.role}</p></div>
      <button type="button" className="quiet-button" onClick={onClose}>Close</button></div>
    {notice && <div className={`toast-message ${notice.kind}`} role="status">{notice.text}<button onClick={() => setNotice(null)} aria-label="Dismiss notification">×</button></div>}
    <div className="profile-summary-grid"><span><small>Department</small><b>{employee.department}</b></span><span><small>Status</small><b>{employee.status}</b></span>
      <span><small>Branch</small><b>{employee.branch_id ?? "Not assigned"}</b></span><span><small>Designation</small><b>{employee.designation_id ?? "Not assigned"}</b></span></div>
    {canManagePrivate ? <>
      <form className="record-form profile-section" onSubmit={saveContact}>
        <div><h3>Private contact details</h3><p>Visible to this employee and authorized HR roles.</p></div>
        <div className="form-grid two-col">
          <label>Personal email<input type="email" maxLength={255} value={contactDraft.personal_email} onChange={(event) => setContactDraft({ ...contactDraft, personal_email: event.target.value })}/></label>
          <label>Phone<input type="tel" minLength={7} maxLength={30} value={contactDraft.phone} onChange={(event) => setContactDraft({ ...contactDraft, phone: event.target.value })}/></label>
          <label>Alternate phone<input type="tel" minLength={7} maxLength={30} value={contactDraft.alternate_phone} onChange={(event) => setContactDraft({ ...contactDraft, alternate_phone: event.target.value })}/></label>
          <label>Address<input maxLength={250} value={contactDraft.address_line} onChange={(event) => setContactDraft({ ...contactDraft, address_line: event.target.value })}/></label>
          <label>City<input maxLength={100} value={contactDraft.city} onChange={(event) => setContactDraft({ ...contactDraft, city: event.target.value })}/></label>
          <label>State / region<input maxLength={100} value={contactDraft.region} onChange={(event) => setContactDraft({ ...contactDraft, region: event.target.value })}/></label>
          <label>Postal code<input maxLength={30} value={contactDraft.postal_code} onChange={(event) => setContactDraft({ ...contactDraft, postal_code: event.target.value })}/></label>
          <label>Country<input maxLength={100} value={contactDraft.country} onChange={(event) => setContactDraft({ ...contactDraft, country: event.target.value })}/></label>
        </div>
        <button className="primary-button" disabled={busy}>{busy ? "Saving…" : "Save contact details"}</button>
      </form>
      <div className="profile-section">
        <div className="card-heading"><div><h3>Emergency contacts</h3><p>Up to ten contacts, ordered by priority.</p></div></div>
        {emergencyContacts.length === 0 && <p className="profile-empty">No emergency contacts have been added.</p>}
        <div className="emergency-contact-list">{emergencyContacts.map((contactItem) => <article className="emergency-contact-row" key={contactItem.id}>
          <span><b>{contactItem.name}</b><small>{contactItem.relationship} · {contactItem.phone}{contactItem.email ? ` · ${contactItem.email}` : ""}</small></span>
          <span className="contact-actions"><small>Priority {contactItem.priority}</small><button type="button" className="row-action" onClick={() => editEmergency(contactItem)}>Edit</button>
            <button type="button" className="row-action danger" disabled={busy} onClick={() => void removeEmergency(contactItem.id)}>Remove</button></span>
        </article>)}</div>
        <form className="record-form" onSubmit={saveEmergency}>
          <b>{editingEmergency ? "Edit emergency contact" : "Add emergency contact"}</b>
          <div className="form-grid two-col">
            <label>Name<input required minLength={2} maxLength={100} value={emergencyDraft.name} onChange={(event) => setEmergencyDraft({ ...emergencyDraft, name: event.target.value })}/></label>
            <label>Relationship<input required minLength={2} maxLength={60} value={emergencyDraft.relationship} onChange={(event) => setEmergencyDraft({ ...emergencyDraft, relationship: event.target.value })}/></label>
            <label>Phone<input required type="tel" minLength={7} maxLength={30} value={emergencyDraft.phone} onChange={(event) => setEmergencyDraft({ ...emergencyDraft, phone: event.target.value })}/></label>
            <label>Email <span className="optional">Optional</span><input type="email" maxLength={255} value={emergencyDraft.email} onChange={(event) => setEmergencyDraft({ ...emergencyDraft, email: event.target.value })}/></label>
            <label>Priority<input type="number" min="1" max="10" value={emergencyDraft.priority} onChange={(event) => setEmergencyDraft({ ...emergencyDraft, priority: event.target.value })}/></label>
          </div>
          <div className="form-actions"><button className="primary-button" disabled={busy}>{editingEmergency ? "Save emergency contact" : "Add emergency contact"}</button>
            {editingEmergency && <button type="button" className="secondary-button" onClick={() => { setEditingEmergency(null); setEmergencyDraft(emptyEmergency); }}>Cancel edit</button>}</div>
        </form>
      </div>
      <div className="profile-section"><div className="card-heading"><div><h3>Employment history</h3><p>Position and status changes are recorded automatically.</p></div></div>
        {history.length === 0 ? <p className="profile-empty">No history events are recorded for this profile yet.</p> : <ol className="employment-history-list">{history.map((event) => <li key={event.id}>
          <time>{new Date(`${event.effective_date}T12:00:00`).toLocaleDateString()}</time><div><b>{event.event_type.replaceAll("_", " ")}</b><p>{event.job_title} · {event.department} · {event.employment_status}</p>
            <small>{[event.branch_name, event.designation_name, event.grade_name, event.reporting_manager_name ? `Manager: ${event.reporting_manager_name}` : null].filter(Boolean).join(" · ")}</small>{event.notes && <small>{event.notes}</small>}</div>
        </li>)}</ol>}
      </div>
      <div className="profile-section"><div className="card-heading"><div><h3>Employment contracts</h3><p>Contract metadata and lifecycle; signed files are not stored here.</p></div></div>
        {contracts.length === 0 ? <p className="profile-empty">No employment contracts are recorded for this employee.</p> : <div className="contract-list">{contracts.map((contract) => <article className="contract-row" key={contract.id}>
          <span><b>{contract.reference}</b><small>{contract.employment_type} · {new Date(`${contract.start_date}T12:00:00`).toLocaleDateString()}{contract.end_date ? ` – ${new Date(`${contract.end_date}T12:00:00`).toLocaleDateString()}` : " · No end date"}{contract.signed_date ? ` · Signed ${new Date(`${contract.signed_date}T12:00:00`).toLocaleDateString()}` : ""}</small></span>
          <span className="contract-actions"><span className={`status-badge ${contract.status === "Active" ? "green" : contract.status === "Ended" ? "muted" : "amber"}`}><i/>{contract.status}</span>
            {canManageContracts && contract.status !== "Ended" && <button type="button" className="row-action" onClick={() => editContract(contract)}>Edit</button>}</span>
        </article>)}</div>}
        {canManageContracts && <form className="record-form" onSubmit={saveContract}>
          <b>{editingContract ? "Edit employment contract" : "Add employment contract"}</b>
          <div className="form-grid two-col">
            <label>Contract reference<input required minLength={2} maxLength={80} value={contractDraft.reference} onChange={(event) => setContractDraft({ ...contractDraft, reference: event.target.value })}/></label>
            <label>Employment type<select value={contractDraft.employment_type} onChange={(event) => setContractDraft({ ...contractDraft, employment_type: event.target.value })}>{["Permanent", "Fixed-term", "Temporary", "Internship", "Consultant", "Other"].map((value) => <option key={value}>{value}</option>)}</select></label>
            <label>Start date<input type="date" required value={contractDraft.start_date} onChange={(event) => setContractDraft({ ...contractDraft, start_date: event.target.value })}/></label>
            <label>End date <span className="optional">Optional</span><input type="date" min={contractDraft.start_date || undefined} value={contractDraft.end_date} onChange={(event) => setContractDraft({ ...contractDraft, end_date: event.target.value })}/></label>
            <label>Signed date <span className="optional">Optional</span><input type="date" value={contractDraft.signed_date} onChange={(event) => setContractDraft({ ...contractDraft, signed_date: event.target.value })}/></label>
            <label>Status<select value={contractDraft.status} onChange={(event) => setContractDraft({ ...contractDraft, status: event.target.value as EmploymentContract["status"] })}><option>Draft</option><option>Active</option><option>Ended</option></select></label>
          </div>
          <div className="form-actions"><button className="primary-button" disabled={busy}>{editingContract ? "Save contract" : "Create contract"}</button>
            {editingContract && <button type="button" className="secondary-button" onClick={() => { setEditingContract(null); setContractDraft(emptyContract); }}>Cancel edit</button>}</div>
        </form>}
      </div>
      {contact && <small className="profile-updated">Contact details updated {new Date(contact.updated_at).toLocaleString()}.</small>}
    </> : <div className="profile-private-note"><b>Private contact details</b><p>Contact information, emergency contacts, and employment history are available only to the employee and authorized HR roles.</p></div>}
  </section>;
}
