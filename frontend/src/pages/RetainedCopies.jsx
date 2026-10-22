import { useState } from "react";
import { api } from "../services/api";
import { ErrorNotice, Field, Submit, formatDate } from "../components";
import { label } from "../product-components";

const categories = ["backup", "recovery_snapshot", "plaintext_original", "evidence_export", "audit_checkpoint", "downstream_copy"];

function CopyAction({ copy, action, title, busy, perform, report = false }) {
  return <form className="form-grid" onSubmit={event => { event.preventDefault(); perform(`/retention/copies/${copy.id}/${action}`, Object.fromEntries(new FormData(event.currentTarget))); }}>
    <Field label={`${title} reason`}><textarea name="reason" minLength={10} maxLength={2000} required disabled={busy} /></Field>
    {report && <><Field label="Removal evidence reference"><input name="evidence_reference" minLength={3} maxLength={500} required disabled={busy} /></Field><Field label="Removal evidence SHA-256"><input name="evidence_sha256" pattern="[a-f0-9]{64}" required disabled={busy} /></Field></>}
    <div><Submit busy={busy}>{title}</Submit></div>
  </form>;
}

export default function RetainedCopies({ copies, user, policy, reload }) {
  const [scope, setScope] = useState("workspace");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const canManage = ["admin", "reviewer"].includes(user.role);
  async function perform(path, body) {
    setBusy(true); setError(""); setNotice("");
    try { await api(path, { method: "POST", body }); reload(); setNotice("Custody review recorded. PolicyLens did not delete an external file or verify its absence."); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <section className="panel section-padding"><h2>Retained copies and custodians</h2>
    <p>Register backups, exports and downstream copies. A reported hash identifies supplied evidence; it does not prove that storage was erased. References are recorded without opening or deleting the named location.</p>
    <ErrorNotice message={error} />{notice && <p role="status">{notice}</p>}
    {canManage && policy && <details><summary>Register a retained copy</summary><form className="form-grid" onSubmit={event => {
      event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget));
      try { body.copy_created_at = new Date(body.copy_created_at).toISOString(); body.preserve_until = new Date(body.preserve_until).toISOString(); }
      catch { setError("Choose valid copy and preservation dates."); return; }
      if (scope === "workspace") body.target_id = "";
      perform("/retention/copies", body);
    }}>
      <Field label="Copy category"><select name="category" required disabled={busy}>{categories.map(category => <option key={category} value={category}>{label(category)}</option>)}</select></Field>
      <Field label="Copy scope"><select name="scope" value={scope} onChange={event => setScope(event.target.value)} disabled={busy}><option value="workspace">Entire workspace</option><option value="customer">Customer</option><option value="case">Case</option></select></Field>
      {scope !== "workspace" && <Field label="Copy target record ID"><input name="target_id" maxLength={100} required disabled={busy} /></Field>}
      <Field label="Copy custodian"><input name="custodian" minLength={3} maxLength={160} required disabled={busy} /></Field>
      <Field label="Copy location reference" hint="An inventory reference, without credentials or private key material."><input name="location_reference" minLength={3} maxLength={500} required disabled={busy} /></Field>
      <Field label="Copy content SHA-256"><input name="content_sha256" pattern="[a-f0-9]{64}" required disabled={busy} /></Field>
      <Field label="Copy created at" hint="Local time; saved as UTC."><input name="copy_created_at" type="datetime-local" required disabled={busy} /></Field>
      <Field label="Preserve copy until" hint="Local time; cannot shorten the approved policy's minimum."><input name="preserve_until" type="datetime-local" required disabled={busy} /></Field>
      <Field label="Copy registration reason" wide><textarea name="reason" minLength={10} maxLength={2000} required disabled={busy} /></Field>
      <div><Submit busy={busy}>Register copy custody</Submit></div>
    </form></details>}
    {!policy && <p>Approve a retention policy before registering or reconciling copies.</p>}
    {copies.length === 0 && <p>No copies have been registered. This does not prove that no external copies exist.</p>}
    {copies.map(copy => <article className="detail-section" key={copy.id}><h3>{label(copy.category)} · {label(copy.status)}</h3>
      <p>{copy.custodian} · {copy.location_reference}</p><p>{label(copy.scope)}: {copy.target_id || "Entire workspace"}</p>
      <p>Declared preservation: {copy.preserve_until ? formatDate(copy.preserve_until) : "Awaiting an approved retention policy"}. The server also applies the current approved policy and all applicable holds.</p>
      {copy.origin === "application" && <p>Application-generated · {label(copy.generation_status)} · Hash encoding: {copy.hash_encoding}</p>}
      <p>Copy hash: <code>{copy.content_sha256 || "Not established"}</code></p><p>Copy record: <code>{copy.id}</code></p>
      {copy.status === "removal_authorized" && <p>Authorization does not mean the copy has been removed. Recheck holds and policy before any external action.</p>}
      {copy.status === "removal_reported" && <p>The custodian report awaits confirmation by a different reviewer.</p>}
      {copy.evidence_reference && <p>Reported evidence: {copy.evidence_reference} · <code>{copy.evidence_sha256}</code></p>}
      {copy.status === "removal_confirmed" && <p>A different reviewer confirmed the custodian report. External erasure was not automatically verified.</p>}
      <details><summary>Custody review history</summary>{copy.history.map((event, index) => <p key={index}>{label(event.action)} · {formatDate(event.at)} · {event.actor}: {event.reason}</p>)}</details>
      {canManage && policy && copy.status === "retained" && <CopyAction copy={copy} action="request-removal" title={`Request removal ${copy.id}`} busy={busy} perform={perform} />}
      {user.role === "admin" && ["pending", "failed_unknown"].includes(copy.generation_status) && copy.location_reference.startsWith("workspace-backup") && <CopyAction copy={copy} action="inspect-backup" title={`Inspect backup ${copy.id}`} busy={busy} perform={perform} />}
      {canManage && copy.status === "removal_requested" && copy.removal_requested_by !== user.id && <CopyAction copy={copy} action="approve-removal" title={`Authorize removal ${copy.id}`} busy={busy} perform={perform} />}
      {canManage && copy.status === "removal_authorized" && <CopyAction copy={copy} action="report-removal" title={`Report removal ${copy.id}`} busy={busy} perform={perform} report />}
      {canManage && copy.status === "removal_reported" && copy.removal_reported_by !== user.id && policy && (copy.removal_policy_id === policy.id ? <CopyAction copy={copy} action="confirm-removal" title={`Confirm report ${copy.id}`} busy={busy} perform={perform} /> : <CopyAction copy={copy} action="review-reported-removal" title={`Review report under current policy ${copy.id}`} busy={busy} perform={perform} />)}
      {canManage && ["removal_requested", "removal_authorized"].includes(copy.status) && <CopyAction copy={copy} action="cancel-removal" title={`Cancel removal ${copy.id}`} busy={busy} perform={perform} />}
    </article>)}
  </section>;
}
