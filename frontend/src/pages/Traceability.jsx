import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { Empty, ErrorNotice, Field, formatDate, Loading, PageHeading, Submit, useResource } from "../components";
import { AgentButton, label, Status } from "../product-components";
import { useSession } from "../session";

function Obligation({ item, controls, canMap, reload }) {
  const [selected, setSelected] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const candidates = controls.filter(c => c.policy_id === item.policy_id && c.policy_version === item.policy_version && !item.controls.some(link => link.control.id === c.id));
  async function change(controlId, linked) {
    setBusy(true);
    setError("");
    try {
      await api(`/traceability/obligations/${item.id}/links`, { method: "PUT", body: { control_id: controlId, linked, notes } });
      setNotes("");
      setSelected("");
      reload();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }
  return <article className="panel section-padding">
    <div className="panel-heading"><h2>{item.obligation}</h2><Status value={item.status} /></div>
    <p><Link to={`/policies/${item.policy_id}/edit`}>{item.policy_title}</Link> · Version {item.policy_version} · <Link to={`/agents/${item.analysis_job_id}`}>Analysis {formatDate(item.analysis_at)}</Link></p>
    <blockquote>{item.citation.quote}</blockquote>
    <p className="privacy-note">{item.analysis_scope}</p>
    {item.analysis_coverage.complete === false && <p className="notice neutral">The analysis used only part of the policy document.</p>}
    {item.gaps.length > 0 && <p>Coverage gaps: {item.gaps.map(label).join("; ")}.</p>}
    {!item.current_policy_version && <p className="notice neutral">Historical policy version. New mappings require analysis of the current version.</p>}
    {item.controls.map(link => <section key={link.control.id} className="detail-section">
      <h3><Link to={`/rules/${link.control.id}`}>{link.control.title}</Link> · v{link.control.version}</h3>
      <Status value={link.control.status} />
      <p>{link.alert_count} recorded alerts · {link.evidence.length} linked screening evidence records.</p>
      <p>{link.latest_simulation ? `Latest recorded simulation: ${formatDate(link.latest_simulation.created_at)}; ${link.latest_simulation.match_count} matches across ${link.latest_simulation.tested} transactions.` : "No simulation recorded for this control version."}</p>
      <p>Human mapping: {link.mapping.notes}</p>
      {link.evidence.map(e => <p key={e.id}><Link to={`/cases/${e.case_id}`}>Open evidence case</Link> · {formatDate(e.created_at)}</p>)}
      {canMap && <button className="button secondary" disabled={busy || notes.trim().length < 10} onClick={() => change(link.control.id, false)}>Remove mapping</button>}
    </section>)}
    <ErrorNotice message={error} />
    {canMap && <form className="form-grid" onSubmit={event => { event.preventDefault(); change(selected, true); }}>
      {item.current_policy_version && <Field label="Control to map"><select value={selected} onChange={event => setSelected(event.target.value)}><option value="">Choose a control from this policy version</option>{candidates.map(c => <option key={c.id} value={c.id}>{c.title} · v{c.version} · {label(c.status)}</option>)}</select></Field>}
      <Field label="Mapping rationale" hint="Required when adding or removing a mapping. This records applicability; control activation still requires independent approval."><textarea value={notes} onChange={event => setNotes(event.target.value)} minLength={10} maxLength={2000} /></Field>
      {item.current_policy_version && <div><Submit busy={busy} disabled={busy || !selected || notes.trim().length < 10}>Record mapping</Submit></div>}
    </form>}
  </article>;
}

export default function Traceability() {
  const resource = useResource("/traceability");
  const { user } = useSession();
  const canMap = ["admin", "analyst", "reviewer"].includes(user.role);
  if (resource.loading) return <Loading />;
  if (resource.error) return <ErrorNotice message={resource.error} retry={resource.reload} />;
  const data = resource.data;
  return <>
    <PageHeading eyebrow="POLICY TO OBSERVED WORK" title="Policy-to-control traceability" action={<button className="button secondary" onClick={resource.reload}>Refresh matrix</button>}>{data.scope}</PageHeading>
    <p>{data.counts.obligations} suggested obligations · {data.counts.with_gaps} with recorded gaps · {data.counts.policies_without_current_analysis} policies awaiting current analysis.</p>
    <section className="panel section-padding"><h2>Policies awaiting current analysis</h2>{data.policies_without_current_analysis.length ? data.policies_without_current_analysis.map(p => <div className="detail-section" key={p.id}><h3>{p.title} · Version {p.version}</h3><p>No current extracted obligation inventory is available. Review the full document.</p>{canMap && <AgentButton kind="policy_analyst" targetId={p.id}>Prepare cited obligation suggestions</AgentButton>}</div>) : <p>No policy is missing a current analysis. Suggested obligations still require full-document review.</p>}</section>
    {data.obligations.length ? data.obligations.map(item => <Obligation key={item.id} item={item} controls={data.available_controls} canMap={canMap} reload={resource.reload} />) : <Empty title="No extracted obligations yet.">Run the policy analyst on an operating policy to prepare cited suggestions for human interpretation.</Empty>}
  </>;
}
