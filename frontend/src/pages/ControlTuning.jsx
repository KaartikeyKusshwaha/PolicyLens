import { useState } from "react";
import { Link } from "../navigation";
import { api } from "../services/api";
import { ErrorNotice, Field, Loading, Submit, Success, useResource } from "../components";

function Comparison({ value }) {
  return <>
    <p>{value.tested} historical transactions · Current threshold {value.current_threshold}: {value.before.match_count} matches.</p>
    <div className="table-scroll"><table><thead><tr><th>Candidate threshold</th><th>Matches</th><th>Distance from target</th><th>Proposal</th></tr></thead><tbody>
      {value.candidates.map(candidate => <tr key={candidate.threshold}><td>{candidate.threshold}</td><td>{candidate.match_count}</td><td>{candidate.distance_from_target}</td><td>{candidate.threshold === value.selected.threshold ? "Selected for draft" : "Compared"}</td></tr>)}
    </tbody></table></div>
    <p>{value.added_match_ids.length} added matches · {value.removed_match_ids.length} removed matches. {value.selection}</p>
    <p className="privacy-note">Match volume measures historical workload. It does not establish detection accuracy, false-positive rate, legal compliance, or an optimal risk threshold.</p>
    <details className="tuning-references"><summary>Matched transaction references and limitations</summary>
      <p>Before: {value.before.match_transaction_ids.join(", ") || "None"}</p>
      {value.candidates.map(candidate => <p key={candidate.threshold}>Threshold {candidate.threshold}: {candidate.match_transaction_ids.join(", ") || "None"}</p>)}
      <ul>{value.limitations.map(text => <li key={text}>{text}</li>)}</ul>
      <p>Pinned simulation: <code>{value.preview_sha256}</code></p>
    </details>
  </>;
}

export function TuningEvidence({ receiptId }) {
  const resource = useResource("/control-tuning/" + receiptId);
  if (resource.loading) return <Loading />;
  if (resource.error) return <ErrorNotice message={resource.error} retry={resource.reload} />;
  const { receipt, control_status: status } = resource.data;
  return <section className="panel section-padding">
    <h2>Retained tuning evidence</h2>
    <p>{receipt.preview.request.rationale}</p>
    <p>Control status: {status}. This is the proposal’s pinned historical comparison. Approval rechecks the control, policy and transaction/customer evidence.</p>
    {status === "draft" && <p><Link to={"/rules/" + receipt.preview.request.control_id}>Open the source control to prepare a fresh comparison</Link> if the evidence has changed.</p>}
    <Comparison value={receipt.preview} />
  </section>;
}

export default function ControlTuning({ control }) {
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function simulate(event) {
    event.preventDefault();
    const fields = Object.fromEntries(new FormData(event.currentTarget));
    setBusy(true); setError(""); setPreview(null); setResult(null);
    try {
      setPreview(await api("/control-tuning/preview", { method: "POST", body: {
        control_id: control.id,
        candidate_thresholds: fields.thresholds.split(",").map(value => value.trim()).filter(Boolean),
        target_match_count: Number(fields.target_match_count), rationale: fields.rationale,
      } }));
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function draft() {
    setBusy(true); setError(""); setResult(null);
    try {
      setResult(await api("/control-tuning/draft", { method: "POST", body: { ...preview.request, preview_sha256: preview.preview_sha256 } }));
    } catch (failure) { setError(failure.message); setPreview(null); }
    finally { setBusy(false); }
  }
  return <section className="panel section-padding">
    <h2>Threshold tuning</h2>
    <p className="section-copy">Compare up to eight internal thresholds. The deterministic playbook selects the closest match-count target; ties use your candidate order. It creates a separate draft for independent review.</p>
    <form onSubmit={simulate} onChange={() => { setPreview(null); setResult(null); setError(""); }}>
      <fieldset className="tuning-inputs" disabled={busy}>
        <Field label="Candidate thresholds" hint="Comma separated, different from the current threshold. Counts must be integers for velocity controls."><input name="thresholds" required maxLength={160} placeholder="150, 250, 500" /></Field>
        <Field label="Target historical match count"><input name="target_match_count" type="number" min="0" max="10000" step="1" required /></Field>
        <Field label="Tuning objective and rationale"><textarea name="rationale" minLength={20} maxLength={2000} required rows={3} /></Field>
        <Submit busy={busy}>Compare thresholds</Submit>
      </fieldset>
    </form>
    <ErrorNotice message={error} />
    {preview && <><Comparison value={preview} /><button className="button secondary" disabled={busy} onClick={draft}>Draft threshold change for review</button></>}
    {result && <Success>No control was activated. <Link to={"/rules/" + result.control.id}>Open the threshold-change draft</Link> for independent review.</Success>}
  </section>;
}
