import { useState } from "react";
import { api } from "../services/api";
import { ErrorNotice, Field, Loading, PageHeading, Submit, useResource } from "../components";
import { useSession } from "../session";
import { label } from "../product-components";
import DeletionPreview from "./DeletionPreview";

const periods = { customer_days: "Customer retention days", resolved_case_days: "Resolved case retention days", terminal_job_days: "Terminal agent run retention days", backup_days: "Backup retention days", audit_minimum_days: "Minimum audit retention days" };

function ReviewAction({ title, action, busy }) {
  const [reason, setReason] = useState("");
  return <form onSubmit={event => { event.preventDefault(); action(reason); }}>
    <Field label={`${title} reason`}><textarea value={reason} onChange={event => setReason(event.target.value)} minLength={10} maxLength={2000} required disabled={busy} /></Field>
    <Submit busy={busy}>{title}</Submit>
  </form>;
}

export default function Retention() {
  const { user } = useSession();
  const overview = useResource("/retention");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [holdScope, setHoldScope] = useState("workspace");
  async function perform(path, body) {
    setBusy(true); setError(""); setNotice("");
    try { await api(path, { method: "POST", body }); overview.reload(); setNotice("Retention governance change recorded. No data was deleted."); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  if (overview.loading && !overview.data) return <Loading />;
  const data = overview.data;
  const reviewer = ["admin", "reviewer"].includes(user.role);
  return <>
    <PageHeading eyebrow="SETTINGS & GOVERNANCE" title="Retention and legal holds">Choose documented retention periods for your organization. No statutory period is supplied. A different reviewer must approve policy activation and hold release.</PageHeading>
    <ErrorNotice message={error || overview.error} />
    {notice && <p role="status">{notice}</p>}
    {data && <>
      <p className="privacy-note">{data.limits}</p>
      {data.deletion_preview_available && <DeletionPreview />}
      <section className="panel section-padding"><h2>Active retention policy</h2>
        {data.active_policy ? <><h3>{data.active_policy.title}</h3><p>{data.active_policy.rationale}</p><p>{data.active_policy.external_copy_procedure}</p><dl>{Object.entries(periods).map(([key, title]) => <div key={key}><dt>{title}</dt><dd>{data.active_policy[key]}</dd></div>)}</dl></> : <p>No approved retention policy. Nothing is scheduled for deletion.</p>}
      </section>
      {user.role === "admin" && <section className="panel section-padding"><h2>Draft a retention policy</h2><form className="form-grid" onSubmit={event => {
        event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget));
        Object.keys(periods).forEach(key => { body[key] = Number(body[key]); });
        body.parent_id = data.active_policy?.id ?? null;
        perform("/retention/policies", body);
      }}>
        <Field label="Policy title"><input name="title" minLength={3} maxLength={160} required disabled={busy} /></Field>
        <Field label="Retention rationale" wide><textarea name="rationale" minLength={20} maxLength={3000} required disabled={busy} /></Field>
        {Object.entries(periods).map(([key, title]) => <Field label={title} key={key}><input name={key} type="number" min={1} max={36500} step={1} required disabled={busy} /></Field>)}
        <Field label="External copies and backup procedure" wide hint="Describe ownership and reconciliation for snapshots, exports and downstream copies."><textarea name="external_copy_procedure" minLength={20} maxLength={4000} required disabled={busy} /></Field>
        <div><Submit busy={busy}>Save retention draft</Submit></div>
      </form></section>}
      <section className="panel section-padding"><h2>Policy review history</h2>{data.policies.length === 0 && <p>No retention policy versions.</p>}
        {data.policies.map(policy => <article className="detail-section" key={policy.id}><h3>{policy.title} · {label(policy.status)}</h3><p>{policy.rationale}</p><p>{policy.external_copy_procedure}</p>
          <dl>{Object.entries(periods).map(([key, title]) => <div key={key}><dt>{title}</dt><dd>{policy[key]}</dd></div>)}</dl>
          <p>Author: {policy.created_by} · Version: {policy.id}</p>{policy.approved_by && <p>Approved by {policy.approved_by}: {policy.approval_reason}</p>}
          {policy.status === "draft" && reviewer && policy.created_by !== user.id && <ReviewAction title={`Approve policy ${policy.title}`} busy={busy} action={reason => perform(`/retention/policies/${policy.id}/approve`, { reason })} />}
          {policy.status === "draft" && policy.created_by === user.id && <p>A different reviewer must approve your draft.</p>}
        </article>)}
      </section>
      {reviewer && <section className="panel section-padding"><h2>Place a legal hold</h2><p>Holds take effect immediately and do not expire automatically. Release requires a request and approval by a different reviewer.</p><form className="form-grid" onSubmit={event => {
        event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget));
        if (holdScope === "workspace") body.target_id = "";
        perform("/retention/holds", body);
      }}>
        <Field label="Hold scope"><select name="scope" value={holdScope} onChange={event => setHoldScope(event.target.value)} disabled={busy}><option value="workspace">Entire workspace</option><option value="customer">Customer and linked records</option><option value="case">Case and linked records</option></select></Field>
        {holdScope !== "workspace" && <Field label="Target record ID"><input name="target_id" maxLength={100} required disabled={busy} /></Field>}
        <Field label="Hold reason" wide><textarea name="reason" minLength={10} maxLength={2000} required disabled={busy} /></Field>
        <Field label="Authority reference"><input name="authority_reference" minLength={3} maxLength={300} required disabled={busy} /></Field>
        <div><Submit busy={busy}>Place legal hold</Submit></div>
      </form></section>}
      <section className="panel section-padding"><h2>Legal hold history</h2>{data.holds.length === 0 && <p>No legal holds recorded.</p>}
        {data.holds.map(hold => <article className="detail-section" key={hold.id}><h3>{label(hold.scope)} hold · {label(hold.status)}</h3><p>{hold.target_id || "Entire workspace"} · {hold.authority_reference}</p><p>{hold.reason}</p><p>Placed by {hold.created_by} · {hold.id}</p>
          {hold.release_reason && <p>Release requested by {hold.release_requested_by}: {hold.release_reason}</p>}
          {hold.release_approval_reason && <p>Released by {hold.released_by}: {hold.release_approval_reason}</p>}
          {hold.status === "release_requested" && <p>Hold remains effective until independent release approval.</p>}
          {reviewer && hold.status === "active" && <ReviewAction title={`Request release ${hold.authority_reference}`} busy={busy} action={reason => perform(`/retention/holds/${hold.id}/request-release`, { reason })} />}
          {reviewer && hold.status === "release_requested" && hold.release_requested_by !== user.id && <ReviewAction title={`Approve release ${hold.authority_reference}`} busy={busy} action={reason => perform(`/retention/holds/${hold.id}/approve-release`, { reason })} />}
        </article>)}
      </section>
    </>}
  </>;
}
