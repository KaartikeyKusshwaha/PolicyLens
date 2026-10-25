import { ArrowRight, CheckCircle2, FileCheck2 } from "lucide-react";
import { Link } from "../navigation";
import { formatDate } from "../components";

function SignalFacts({ facts }) {
  if (facts.observed == null) return null;
  const amount = ["amount", "aggregate"].includes(facts.kind);
  const count = facts.kind === "velocity";
  return <p>Recorded observation: {String(facts.observed)}{amount && facts.currency ? ` ${facts.currency}` : count ? ` transaction${Number(facts.observed) === 1 ? "" : "s"}` : ""}{(amount || count) && facts.threshold != null ? ` · Configured threshold: ${facts.threshold}${count ? ` transaction${Number(facts.threshold) === 1 ? "" : "s"}` : facts.currency ? ` ${facts.currency}` : ""}` : ""}{["velocity", "aggregate"].includes(facts.kind) && facts.window_hours ? ` · Window: ${facts.window_hours} hour${Number(facts.window_hours) === 1 ? "" : "s"}` : ""}</p>;
}

export default function CaseReview({ review, completeTask, canEdit, showEvidence, onRequestEvidence, onDecide }) {
  if (!review) return <section className="panel section-padding"><h2>Review summary unavailable</h2><p>Open Evidence to inspect the original records.</p><button className="button secondary" onClick={showEvidence}>View evidence</button></section>;
  return <div className="review-stack">
    <section className="panel section-padding review-intro">
      <div className="review-kicker"><FileCheck2 size={18} /> Automatically prepared</div>
      <h2>Your case, ready to review</h2>
      <p>{review.next_action}</p>
      <small>Updated {formatDate(review.prepared_at)} · Calculated from recorded evidence</small>
      <div className="review-actions">
        {canEdit && onDecide && <button className="button primary" onClick={onDecide}>Record your decision</button>}
        {canEdit && onRequestEvidence && review.missing_evidence.length > 0 && <button className="button secondary" onClick={onRequestEvidence}>Prepare evidence request</button>}
      </div>
      <div className="review-metrics">
        <div><strong>{review.alert_count}</strong><span>Case alerts</span></div>
        <div><strong>{review.transaction_count}</strong><span>Transactions displayed of {review.total_customer_transactions}</span></div>
        <div><strong>{review.open_tasks.length}</strong><span>Open evidence tasks</span></div>
      </div>
      <dl className="review-totals">{Object.entries(review.totals_by_currency).map(([currency, total]) => <div key={currency}><dt>{currency} displayed total</dt><dd>{total}</dd></div>)}</dl>
      <p className="privacy-note">Totals cover displayed customer history, including payments without alerts. Different currencies are kept separate.</p>
    </section>
    <section className="panel section-padding">
      <h2>What needs your attention</h2>
      {review.missing_evidence.length ? <ul className="review-checklist">{review.missing_evidence.map(item => <li key={item}>{item}</li>)}</ul> : <p>No preparation gaps detected in the available records. Review the evidence before deciding.</p>}
      {review.open_tasks.map(task => <div className="task-row" key={task.id}><div><strong>{task.title}</strong><small>{task.due_at ? formatDate(task.due_at) : "No due date"}</small></div>{canEdit && <button className="button secondary" onClick={() => completeTask(task.id)}>Complete</button>}</div>)}
    </section>
    <section className="panel section-padding">
      <h2>Why this case needs review</h2>
      <p>Control hits are recorded signals. They need a human assessment.</p>
      {review.signals.length ? review.signals.map(signal => <article className="review-signal" key={signal.id}><strong>{signal.title}</strong><small>{signal.origin === "internal_control" ? `Policy version ${signal.policy_version || "unavailable"}` : "Imported source evidence"}</small><SignalFacts facts={signal.facts}/></article>) : <p>No control hits are attached. Review the case context and any screening evidence.</p>}
      <button className="text-link" onClick={showEvidence}>Inspect original evidence <ArrowRight size={14} /></button>
    </section>
    {review.policies.length > 0 && <section className="panel section-padding"><h2>Linked policy context</h2>{review.policies.map(policy => <details className="review-policy" key={`${policy.id}-${policy.version}`}><summary>{policy.title} · v{policy.version || "unavailable"}</summary><p className="preserve-lines">{policy.excerpt || "The archived version is unavailable."}</p><small>Opening excerpt from the archived version; not an identified breach.</small><Link className="text-link" to={`/policies/${policy.id}`}>Open policy</Link></details>)}</section>}
    <section className="panel section-padding"><h2><CheckCircle2 size={16} /> Preparation scope</h2><ul className="review-checklist">{review.limitations.map(item => <li key={item}>{item}</li>)}</ul><p>The evidence report includes this summary and the underlying records. Download it directly from the top of this case.</p></section>
  </div>;
}
