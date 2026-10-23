import { useState } from "react";
import { api } from "../services/api";
import { ErrorNotice, Field, Submit, formatDate } from "../components";
import { label } from "../product-components";

export default function DeletionRequests({ requests, user, reload }) {
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function inspect(id) {
    setBusy(true); setError(""); setDetail(null); setNotice("");
    try { setDetail(await api(`/retention/deletion-requests/${id}`)); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function review(event, action) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    const body = Object.fromEntries(new FormData(event.currentTarget));
    if (action === "approve") {
      body.acknowledge_retained_audit = body.acknowledge_retained_audit === "on";
      body.acknowledge_physical_and_restore_limits = body.acknowledge_physical_and_restore_limits === "on";
    }
    try { await api(`/retention/deletion-requests/${detail.request.id}/${action}`, { method:"POST",body }); setDetail(null); reload(); setNotice("Deletion plan review recorded. No records or files were deleted."); }
    catch (failure) { setError(failure.message); setDetail(null); }
    finally { setBusy(false); }
  }
  const canReview = ["admin", "reviewer"].includes(user.role);
  const request = detail?.request;
  return <section className="panel section-padding"><h2>Deletion request reviews</h2>
    <p>Review is limited to the pinned logical plan. Execution requires the stopped-installation operator command, encrypted storage and external recovery state. Discovery evidence and acknowledgements do not prove physical erasure. Restores require the independently pinned current deletion guard.</p>
    <ErrorNotice message={error} />{notice && <p role="status">{notice}</p>}
    {!requests.length && <p>No deletion requests recorded.</p>}
    {requests.map(item => <article className="detail-section" key={item.id}><h3>{label(item.status)} · {item.customer_id}</h3><p>{item.reason}</p><p>Expires {formatDate(item.expires_at)} · Author {item.created_by}</p><button className="button secondary" disabled={busy} onClick={() => inspect(item.id)}>Inspect request {item.id}</button></article>)}
    {request && <div className="detail-section"><h3>Current request evidence</h3><p>Request <code>{request.id}</code> · {label(request.status)}</p>
      <p>Approved inventory: <code>{request.inventory_sha256}</code></p><p>Current inventory: <code>{detail.current_inventory_sha256}</code></p>
      {detail.stale && <p role="alert">The inventory changed. Cancel this request and submit a fresh preview.</p>}
      {detail.expired && <p role="alert">The review window expired. Obtain a fresh preview and review.</p>}
      <h4>Current blockers</h4><ul>{detail.current_blockers.map((block,index) => <li key={index}>{label(block.code)} {block.record_id}</li>)}</ul>
      <h4>Pinned candidate records ({request.snapshot.candidates.length})</h4><div className="table-scroll"><table><thead><tr><th>Storage</th><th>Record</th><th>Hash</th></tr></thead><tbody>{request.snapshot.candidates.map(item => <tr key={`${item.table}:${item.rowid}`}><td>{label(item.kind)}</td><td>{item.record_id}</td><td><code>{item.sha256}</code></td></tr>)}</tbody></table></div>
      <p>{request.snapshot.retained_audit.scope}</p><ul>{request.snapshot.excluded_scope.map(scope => <li key={scope}>{scope}</li>)}</ul>
      <details><summary>Complete pinned inventory and copy evidence</summary><pre className="code-block">{JSON.stringify(request.snapshot,null,2)}</pre></details>
      <p>{request.scope}</p>{request.discovery_reference && <p>Reviewed discovery evidence: {request.discovery_reference} · <code>{request.discovery_evidence_sha256}</code></p>}
      {detail.receipt && <section className="detail-section" aria-label="Logical deletion receipt"><h4>Logical deletion recorded</h4><p>Receipt <code>{detail.receipt.id}</code> · {formatDate(detail.receipt.created_at)}</p><p>{detail.receipt.deleted_records.length} operational rows removed. {detail.receipt.scope}</p><details><summary>Retained execution receipt</summary><pre className="code-block">{JSON.stringify(detail.receipt,null,2)}</pre></details></section>}
      <details><summary>Review history</summary>{request.history.map((event,index) => <p key={index}>{label(event.action)} · {event.actor} · {formatDate(event.at)}: {event.reason}</p>)}</details>
      {canReview && request.status === "requested" && request.created_by !== user.id && !detail.stale && !detail.expired && detail.current_blockers.every(block => block.code === "external_copy_reconciliation_required") && <form className="form-grid" onSubmit={event => review(event,"approve")}>
        <Field label="Deletion review reason"><textarea name="reason" minLength={20} maxLength={2000} required disabled={busy} /></Field>
        <Field label="Copy discovery evidence reference"><input name="discovery_reference" minLength={3} maxLength={500} required disabled={busy} /></Field>
        <Field label="Copy discovery evidence SHA-256"><input name="discovery_evidence_sha256" pattern="[a-f0-9]{64}" required disabled={busy} /></Field>
        <Field label="I reviewed retained audit history"><input name="acknowledge_retained_audit" type="checkbox" required disabled={busy} /></Field>
        <Field label="I reviewed physical and restore limitations"><input name="acknowledge_physical_and_restore_limits" type="checkbox" required disabled={busy} /></Field>
        <div><Submit busy={busy}>Approve logical deletion plan</Submit></div>
      </form>}
      {canReview && ["requested","approved"].includes(request.status) && request.created_by !== user.id && <form onSubmit={event => review(event,"reject")}><Field label="Deletion rejection reason"><textarea name="reason" minLength={20} maxLength={2000} required disabled={busy} /></Field><Submit busy={busy}>Reject deletion request</Submit></form>}
      {canReview && ["requested","approved"].includes(request.status) && (request.created_by === user.id || user.role === "admin") && <form onSubmit={event => review(event,"cancel")}><Field label="Deletion cancellation reason"><textarea name="reason" minLength={20} maxLength={2000} required disabled={busy} /></Field><Submit busy={busy}>Cancel deletion request</Submit></form>}
      <p>No execution action is available.</p>
    </div>}
  </section>;
}
