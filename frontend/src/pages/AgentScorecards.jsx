import { useState } from "react";
import { Empty, ErrorNotice, Loading, PageHeading, useResource } from "../components";

const percent = value => value == null ? "Not observed" : (value * 100).toFixed(1) + "%";
const disposition = value => String(value || "Abstained / failed").replaceAll("_", " ");

function Metrics({ data }) {
  return <div className="table-scroll"><table><thead><tr><th>Labeled cases</th><th>Completed</th><th>Citations checked</th><th>Citation validity</th><th>Unsupported quote rate</th><th>Disposition agreement</th></tr></thead><tbody><tr><td>{data.labeled_cases}</td><td>{data.completed_runs}</td><td>{data.valid_citations}/{data.citation_count}</td><td>{percent(data.citation_validity)}</td><td>{percent(data.fabricated_quote_rate)}</td><td>{percent(data.disposition_agreement)}</td></tr></tbody></table></div>;
}

export default function AgentScorecards() {
  const resource = useResource("/evidence/scorecards/reference");
  const [error, setError] = useState("");
  function download() {
    setError("");
    let url;
    try {
      const value = resource.data.report;
      url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "policylens-synthetic-reference-scorecard.json";
      anchor.click();
    } catch { setError("The reference report could not be downloaded. Retry or inspect the retained repository artifacts."); }
    finally { if (url) URL.revokeObjectURL(url); }
  }
  if (resource.loading) return <Loading />;
  if (resource.error) return <ErrorNotice message={resource.error} retry={resource.reload} />;
  if (!resource.data) return <Empty title="No verified scorecard is available.">A complete retained result is required.</Empty>;
  const { report, verification, notice } = resource.data;
  return <>
    <PageHeading eyebrow="EVIDENCE · SYNTHETIC REFERENCE" title="Agent scorecard" action={<button className="button secondary" onClick={download}>Download reference report</button>}>Observed model work with explicit failure and coverage limits.</PageHeading>
    <ErrorNotice message={error} />
    <div className="notice warning"><div><strong>Reference evaluation; automatic preparation remains disabled.</strong><p>{notice}</p></div></div>
    <section className="panel section-padding"><h2>{report.dataset_title}</h2><p>Origin: {report.data_origin} · Execution: {disposition(report.execution_mode)} · Labels: {report.label_author}</p><Metrics data={report.metrics} /><p>{report.metrics.labeled_cases - report.metrics.completed_runs} failed or incomplete runs · {report.metrics.runs_without_retained_draft} without an inspectable draft · {report.metrics.unknown_citation_ids} unknown citation IDs. Disposition agreement includes every labeled case; citation rates include only observed retained citations.</p></section>
    <section className="panel section-padding"><h2>Quality gate: {report.gate.draft_preparation_quality_passed ? "passed for this retained report" : "not passed"}</h2><p>Gate checks never grant approval authority or enable automatic preparation. Different provider fingerprints are separate identity groups; unreported revisions do not establish immutable model weights.</p><ul>{Object.entries(report.gate.checks).map(([name, passed]) => <li key={name}>{name.replaceAll("_", " ")}: <strong>{passed ? "Passed" : "Not passed"}</strong></li>)}</ul></section>
    <section className="panel section-padding"><h2>Recorded model and provider identities</h2>{report.models.map((group, index) => <details key={index}><summary>{group.identity.model} · {group.identity.model_revision} · {group.metrics.labeled_cases} cases · {group.identity.provider_identity?.system_fingerprint || "Provider identity unavailable"}</summary><p>Prompt: {group.identity.prompt_version}</p><Metrics data={group.metrics} /></details>)}</section>
    <section className="panel section-padding"><h2>Scenario results</h2>{Object.entries(report.categories).map(([name, metrics]) => <details key={name}><summary>{name.replaceAll("_", " ")} · {metrics.labeled_cases} cases</summary><Metrics data={metrics} /></details>)}</section>
    <section className="panel section-padding"><h2>Disposition comparison</h2><div className="table-scroll"><table><thead><tr><th>Expected label</th><th>Confirmed draft</th><th>False-positive draft</th><th>Insufficient-evidence draft</th><th>Abstained / failed</th></tr></thead><tbody>{Object.entries(report.metrics.confusion_matrix).map(([name, values]) => <tr key={name}><th>{disposition(name)}</th><td>{values.confirmed}</td><td>{values.false_positive}</td><td>{values.insufficient_evidence}</td><td>{values.abstained_or_failed}</td></tr>)}</tbody></table></div></section>
    <section className="panel section-padding"><h2>Case outcomes</h2><div className="table-scroll"><table><thead><tr><th>Synthetic case</th><th>State</th><th>Expected</th><th>Draft</th><th>Agreement</th><th>Failure</th></tr></thead><tbody>{report.cases.map(row => <tr key={row.case_id}><td>{row.case_id}</td><td>{row.state}</td><td>{disposition(row.expected_disposition)}</td><td>{disposition(row.draft_disposition)}</td><td>{row.agreement ? "Yes" : "No"}</td><td>{row.error_code || "—"}</td></tr>)}</tbody></table></div></section>
    <section className="panel section-padding"><h2>Verification and measurement limits</h2><p>{verification.terminal_runs_recomputed} retained terminal runs recomputed successfully. {verification.scope}</p><p className="hash-note">Scorecard SHA-256: {verification.trusted_scorecard_sha256}</p><p className="hash-note">Dataset SHA-256: {verification.dataset_sha256}</p><ul>{report.limitations.map(text => <li key={text}>{text}</li>)}</ul><p>The download contains the original reference scorecard. Its digest covers canonical JSON excluding the scorecard_sha256 field. Full recomputation also requires the retained dataset and 50 run artifacts in the repository.</p></section>
  </>;
}
