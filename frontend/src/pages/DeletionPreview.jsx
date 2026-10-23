import { useState } from "react";
import { api } from "../services/api";
import { ErrorNotice, Field, Submit, formatDate } from "../components";
import { label } from "../product-components";

const messages = {
  approved_retention_policy_required: "Approve a retention policy before deletion review.",
  legal_hold: "An active or pending-release legal hold applies.",
  open_case: "A linked investigation is still open.",
  open_task: "A linked task is still open.",
  nonterminal_agent_run: "A linked agent run can still run or resume.",
  retention_period_not_elapsed: "The approved retention period has not elapsed for all candidate records.",
  external_copy_reconciliation_required: "Backups, exports, recovery copies and downstream copies still require reconciliation.",
  registered_copy_outstanding: "A registered copy has no independently confirmed removal report.",
  unresolved_shared_or_text_references: "Shared records or text references need review; they are not authorized deletion candidates.",
  retention_timestamp_missing: "A record has no usable retention timestamp.",
  resolved_case_timestamp_missing: "A resolved case has no resolution timestamp.",
  inconsistent_customer_reference: "A candidate has a conflicting customer reference.",
  inconsistent_case_reference: "A candidate has a conflicting case reference.",
};

function Inventory({ title, rows }) {
  return <><h3>{title} ({rows.length})</h3>{rows.length ? <div className="table-scroll"><table><thead><tr><th>Storage</th><th>Record</th><th>Content hash</th></tr></thead><tbody>{rows.map(row => <tr key={`${row.table}:${row.rowid}`}><td>{label(row.kind)}</td><td><code>{row.record_id}</code></td><td><code>{row.sha256}</code></td></tr>)}</tbody></table></div> : <p>No records in this category.</p>}</>;
}

export default function DeletionPreview({ canRequest = false, onCreated = () => {} }) {
  const [customerId, setCustomerId] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function inspect(event) {
    event.preventDefault(); setBusy(true); setError(""); setResult(null);
    try { setResult(await api(`/retention/deletion-preview?customer_id=${encodeURIComponent(customerId)}`)); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  return <section className="panel section-padding"><h2>Customer deletion inventory</h2>
    <p>Inspect linked records, retention eligibility and holds. This preview does not authorize deletion. Independently approved execution requires the stopped-installation operator command.</p>
    <form className="form-grid" onSubmit={inspect}><Field label="Customer ID for deletion preview"><input value={customerId} maxLength={100} required disabled={busy} onChange={event => { setCustomerId(event.target.value); setResult(null); setError(""); }} /></Field><div><Submit busy={busy}>Preview customer deletion</Submit></div></form>
    <ErrorNotice message={error} />
    {result && <><h3>Inventory snapshot</h3><p>Customer: {result.customer_id} · Generated: {formatDate(result.generated_at)}</p>
      <p>Latest candidate eligibility: {result.eligible_at ? formatDate(result.eligible_at) : "Not established"}. Eligibility does not override holds or other blockers.</p>
      <p>Inventory hash: <code>{result.inventory_sha256}</code></p>
      <h3>Deletion blockers ({result.blockers.length})</h3><ul>{result.blockers.map((block, index) => <li key={`${block.code}:${index}`}>{messages[block.code] || label(block.code)}{block.record_id && <> Record: <code>{block.record_id}</code></>}</li>)}</ul>
      <Inventory title="Operational candidates" rows={result.candidates} />
      <Inventory title="Unresolved retained references" rows={result.unresolved_references} />
      <Inventory title="Retained governance" rows={result.retained_governance} />
      {result.external_copies?.length > 0 && <><h3>Applicable registered copies</h3><ul>{result.external_copies.map(copy => <li key={copy.id}>{label(copy.category)} · {label(copy.status)} · <code>{copy.id}</code></li>)}</ul></>}
      <h3>Retained audit and external scope</h3><p>{result.retained_audit.scope}</p><p>{result.retained_audit.events} audit events remain retained.</p>
      <ul>{result.excluded_scope.map(scope => <li key={scope}>{scope}</li>)}</ul><p>{result.limits}</p>
      <p>No data was deleted. A new preview is needed after policy, hold or business-record changes.</p>
      {canRequest && <form onSubmit={async event => {
        event.preventDefault(); const reason = new FormData(event.currentTarget).get("reason"); setBusy(true); setError("");
        try { await api("/retention/deletion-requests", { method:"POST",body:{ customer_id:result.customer_id,inventory_sha256:result.inventory_sha256,reason } }); setResult(null); onCreated(); }
        catch (failure) { setError(failure.message); setResult(null); }
        finally { setBusy(false); }
      }}><Field label="Deletion request reason"><textarea name="reason" minLength={20} maxLength={2000} required disabled={busy} /></Field><Submit busy={busy}>Submit plan for independent review</Submit><p>Submitting preserves current blockers. Approval cannot bypass holds, retention or outstanding registered copies.</p></form>}
    </>}
  </section>;
}
