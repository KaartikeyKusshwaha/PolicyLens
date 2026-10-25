import { useState } from "react";
import { useParams } from "react-router-dom";
import { Link } from "../navigation";
import { api } from "../services/api";
import { ErrorNotice, Loading, PageHeading, formatDate, useAutoRefresh, useResource } from "../components";
import { Status } from "../product-components";
import PolicyActions from "../policy-actions";
import { useSession } from "../session";

export default function PolicyWorkflow() {
  const {id}=useParams(),{user}=useSession();
  const resource=useResource(`/policies/${id}/workflow`);
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  useAutoRefresh(resource.reload);
  async function review() {setBusy(true);setError("");try {await api(`/policies/${id}/review`,{method:"POST"});resource.reload();}catch(e){setError(e.message);}finally{setBusy(false);}}
  if(!resource.data) return resource.error ? <ErrorNotice message={resource.error} retry={resource.reload}/> : <Loading/>;
  const {policy,review:result,preparations,archived}=resource.data;
  const stale=result && result.policy_version!==policy.version;
  return <>
    <Link className="text-link" to="/policies/library">Back to company policies</Link>
    <PageHeading eyebrow={`POLICY · VERSION ${policy.version}`} title={policy.title} action={<PolicyActions policy={policy} archived={archived} onChanged={resource.reload}/>}>Requirements, transaction reviews and updates for this policy.</PageHeading>
    <ErrorNotice message={error || resource.error}/>
    <ErrorNotice message={resource.data.automation?.preparation_error?.message || resource.data.automation?.review_error?.message}/>
    <ErrorNotice message={resource.data.refresh_error?.message}/>
    {resource.data.refresh_pending && resource.data.automation_enabled && <div className="notice" role="status">Activity or checks changed. Transaction review is refreshing automatically.</div>}
    {archived && <div className="notice" role="status"><div><strong>This policy is archived.</strong><p>Its checks are disabled. Existing evidence is preserved.</p>{user.role==="admin" && <button className="button secondary" onClick={async()=>{try {await api(`/policies/${id}/restore`,{method:"POST"});resource.reload();} catch(e){setError(e.message);}}}>Restore policy</button>}</div></div>}
    <section className="panel section-padding"><h2>Policy preparation</h2><p>On upload, automatic preparation proposes cited requirements using the configured Groq model. Proposed requirements still need interpretation and approved checks.</p>
      {preparations.length ? preparations.map(job=><div className="workspace-row" key={job.id}><div><strong>Cited policy preparation</strong><small>{formatDate(job.created_at)}</small></div><Status value={job.state}/><Link className="text-link" to={`/preparation/${job.id}`}>View {job.state === "completed" ? "requirements" : "progress"}</Link></div>) : <p>No preparation has been recorded. Use the policy actions menu to start it.</p>}
      {!resource.data.automation_enabled && <p className="privacy-note">Automatic policy preparation is not enabled on this installation.</p>}
      <Link className="text-link" to={`/rules/new?policy=${id}`}>Create a monitoring check for this policy</Link>
    </section>
    <section className="panel section-padding detail-section"><div className="panel-title-row"><h2>Transaction review</h2>{user.role!=="auditor" && !archived && <button className="button primary" disabled={busy} onClick={review}>{busy ? "Reviewing…" : "Review all transactions"}</button>}</div>
      {result ? <><p>Reviewed {formatDate(result.reviewed_at)} · Policy v{result.policy_version} · {result.active_controls} approved checks</p>{stale && <div className="notice error" role="alert">This result uses an older policy version. Run a new review.</div>}
        {result.active_controls===0 && <div className="notice" role="status">No approved checks cover this policy version yet. Transactions are marked not covered, never cleared.</div>}
        <dl className="review-totals">{[["Transactions reviewed",result.total],["Flagged",result.flagged],["No control hit",result.no_control_hit],["Not covered",result.not_covered]].map(([name,value])=><div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl>
        <p className="privacy-note">{result.scope}</p>
        <div className="table-scroll"><table><thead><tr><th>Transaction</th><th>Result</th><th>Evidence</th></tr></thead><tbody>{result.transactions.map(t=><tr key={t.transaction_id}><td><Link to={`/customers/${t.customer_id}`}>{t.external_id}</Link></td><td><Status value={t.status}/></td><td>{t.hits.length ? t.hits.map(hit=><div key={hit.control_id}>{hit.control_title} · v{hit.control_version} · observed {hit.facts.observed}</div>) : t.status==="not_covered" ? "No approved check available" : "No configured check triggered"}</td></tr>)}</tbody></table></div>
      </> : <p>No transaction review recorded yet. Run a review to evaluate recorded activity against approved checks for this policy version.</p>}
    </section>
    <Link className="text-link" to={`/policies/${id}/edit`}>Read the full policy or update its version</Link>
  </>;
}
