import { useParams } from "react-router-dom";
import { useState } from "react";
import { api } from "../services/api";
import { useSession } from "../session";
import { Link, useNavigate } from "../navigation";
import { ErrorNotice, Evidence, Loading, PageHeading } from "../components";
import { Status, label, useLiveResource } from "../product-components";

export default function PreparationResult() {
  const { id } = useParams();
  const { user } = useSession();
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState(false);
  const navigate = useNavigate();
  const resource = useLiveResource(`/agents/jobs/${id}`, job => ["queued", "running"].includes(job.state));
  if (resource.loading && !resource.data) return <Loading />;
  if (resource.error) return <ErrorNotice message={resource.error} retry={resource.reload} />;
  const job = resource.data;
  if (!job) return null;
  const result = job.payload.result;
  const target = job.kind === "policy_analyst" ? `/policies/library/${job.target_id}/workflow` : job.kind === "policy_change" ? `/changes/${job.target_id}` : job.kind === "screening" ? `/customers/${job.target_id}` : `/cases/${job.target_id}`;
  return <>
    <Link to={target}>Back to the source record</Link>
    <PageHeading title="Prepared evidence for review" eyebrow={label(job.kind)} action={<Status value={job.state} />}>
      Review the cited evidence and interpretation before making a decision. Preparation does not approve or resolve work.
    </PageHeading>
    <ErrorNotice message={error || job.payload.error?.message} />
    {user.role !== "auditor" && ["failed", "interrupted", "cancelled"].includes(job.state) && job.kind !== "maintenance" && <div className="detail-section"><p>A retry starts a new preparation with current evidence and uses one run from your daily budget. This run stays in the history.</p><button className="button primary" disabled={retrying} onClick={async()=>{
      setRetrying(true);setError("");
      try {const next=await api("/agents/jobs",{method:"POST",body:{kind:job.kind,target_id:job.target_id}});navigate(`/preparation/${next.id}`);}
      catch(failure){setError(failure.message);}finally{setRetrying(false);}
    }}>{retrying ? "Starting…" : "Retry preparation"}</button></div>}
    {user.role !== "auditor" && !["completed", "cancelled"].includes(job.state) && <button className="button secondary" onClick={async () => {
      try { await api(`/agents/jobs/${id}/control`, { method: "POST", body: { action: "cancel" } }); resource.reload(); }
      catch (failure) { setError(failure.message); }
    }}>Cancel preparation</button>}
    {result ? <section className="panel section-padding">
      <h2>Draft for human review</h2>
      {result.summary && <p className="preserve-lines">{result.summary}</p>}
      {result.recommendation && <Status value={result.recommendation} />}
      {["findings", "missing_evidence", "limitations"].map(key => result[key]?.length ? <div key={key}><h3>{label(key)}</h3><ul>{result[key].map((item, index) => <li key={index}>{item}</li>)}</ul></div> : null)}
      {result.citations && <><h3>Policy evidence</h3><Evidence citations={result.citations} /></>}
      {result.obligations?.map((item, index) => <article className="detail-section" key={index}><h3>{item.obligation}</h3><Evidence citations={[item.citation]} /></article>)}
      {result.output_scope && <p>{result.output_scope}</p>}
      {result.coverage && <p>Document coverage: {result.coverage.included_characters} of {result.coverage.document_characters} characters. {result.coverage.complete ? "Complete supplied document." : "Partial document; review the remaining text."}</p>}
      <p>Matching quotations do not establish factual correctness or complete policy coverage.</p>
    </section> : <section className="panel section-padding"><p>{["queued", "running"].includes(job.state) ? "Preparing evidence. This page updates automatically." : "No completed draft is available. Return to the source record to review the evidence."}</p></section>}
  </>;
}
