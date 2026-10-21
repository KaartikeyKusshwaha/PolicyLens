import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowUpRight,
  Bot,
  Check,
  CircleAlert,
  Clock3,
  Pause,
  Play,
  X,
} from "lucide-react";
import { api } from "../services/api";
import {
  Empty,
  ErrorNotice,
  Evidence,
  formatDate,
  Loading,
  PageHeading,
  Submit,
  useResource,
} from "../components";
import {
  AgentButton,
  label,
  Status,
  useLiveResource,
} from "../product-components";
import { useSession } from "../session";

export function AgentOperations() {
  const catalog = useResource("/agents/catalog");
  const jobs = useLiveResource("/agents/jobs");
  const cases = useResource("/cases");
  const customers = useResource("/customers");
  const policies = useResource("/policies");
  const changes = useResource("/policy-changes");
  const [selected, setSelected] = useState("");
  const [target, setTarget] = useState("");
  const { user } = useSession();
  const targets = {
    case: cases.data || [],
    customer: customers.data || [],
    policy: policies.data || [],
    policy_change: changes.data || [],
  };
  const agent = catalog.data?.agents.find((a) => a.id === selected);
  return (
    <>
      <PageHeading
        eyebrow="AGENTS WITH ACCOUNTABILITY"
        title="Your evidence desk, on demand."
      >
        Purpose-built workflows collect facts, prepare drafts, and show their
        work. Your team owns the decisions.
      </PageHeading>
      <ErrorNotice message={catalog.error || jobs.error} />
      <div className="agent-budget">
        <span>
          <Bot size={18} /> Bounded workflows · one model call per AI run
        </span>
        <span>
          {catalog.data?.daily_run_budget || "—"} runs / workspace / day
        </span>
        <span>Human approval required</span>
      </div>
      {catalog.loading ? (
        <Loading />
      ) : (
        <div className="agent-catalog">
          {catalog.data?.agents.map((a) => (
            <article className="panel agent-card" key={a.id}>
              <div className="agent-card-top">
                <span className="agent-avatar">
                  <Bot size={23} />
                </span>
                <span className="tiny-label">
                  {a.model_calls ? "GROQ + TOOLS" : "EVIDENCE CHECKS"}
                </span>
              </div>
              <h2>{a.name}</h2>
              <p>{a.description}</p>
              {a.target === "automatic" ? (
                <span className="agent-card-foot">
                  Included in relevant workflows <Check size={14} />
                </span>
              ) : user.role !== "auditor" ? (
                <button
                  className="text-link text-button"
                  onClick={() => {
                    setSelected(selected === a.id ? "" : a.id);
                    setTarget("");
                  }}
                >
                  Choose a target <ArrowUpRight size={15} />
                </button>
              ) : (
                <span className="muted">Read-only access</span>
              )}
            </article>
          ))}
        </div>
      )}
      {agent && (
        <section className="panel form-panel agent-launch">
          <div>
            <span className="eyebrow">NEW AGENT RUN</span>
            <h2>{agent.name}</h2>
            <p className="section-copy">
              Select the {agent.target.replace("_", " ")} to investigate.
              Evidence sent to Groq is limited to this workspace.
            </p>
          </div>
          <select
            aria-label="Agent target"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          >
            <option value="">Choose a target</option>
            {targets[agent.target]?.map((t) => (
              <option value={t.id} key={t.id}>
                {t.name || t.title}
                {t.new_version
                  ? " · " + t.old_version + " → " + t.new_version
                  : ""}
              </option>
            ))}
          </select>
          {target && (
            <AgentButton kind={agent.id} targetId={target}>
              Start {agent.name.toLowerCase()}
            </AgentButton>
          )}
          <button
            className="icon-button"
            onClick={() => setSelected("")}
            aria-label="Close agent setup"
          >
            <X size={18} />
          </button>
        </section>
      )}
      <section className="panel detail-section">
        <div className="panel-heading">
          <div>
            <h2>Execution history</h2>
            <p>
              Completed steps remain available after interruptions and failures.
            </p>
          </div>
          <button className="text-button" onClick={jobs.reload}>
            Refresh
          </button>
        </div>
        {jobs.loading && !jobs.data ? (
          <Loading />
        ) : jobs.data?.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Workflow</th>
                  <th>Run</th>
                  <th>State</th>
                  <th>Updated</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {jobs.data.map((j) => (
                  <tr key={j.id}>
                    <td>
                      <Link className="table-link" to={"/agents/" + j.id}>
                        {label(j.kind)}
                      </Link>
                    </td>
                    <td className="mono">{j.id.slice(0, 8)}</td>
                    <td>
                      <Status value={j.state} />
                    </td>
                    <td>{formatDate(j.updated_at)}</td>
                    <td>
                      <Link
                        className="icon-button"
                        to={"/agents/" + j.id}
                        aria-label={"Open run " + j.id}
                      >
                        <ArrowUpRight size={17} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty icon={Bot} title="A clear record of every run.">
            Start an agent from a customer, policy, or investigation. Scheduled
            intelligence refreshes also appear here.
          </Empty>
        )}
      </section>
    </>
  );
}

export function AgentRun() {
  const { id } = useParams();
  const r = useLiveResource("/agents/jobs/" + id, (j) =>
    ["queued", "running"].includes(j.state),
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { user } = useSession();
  async function control(action) {
    setBusy(true);
    setError("");
    try {
      await api("/agents/jobs/" + id + "/control", {
        method: "POST",
        body: { action },
      });
      r.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (r.loading && !r.data) return <Loading />;
  if (r.error) return <ErrorNotice message={r.error} retry={r.reload} />;
  const j = r.data;
  if (!j) return null;
  const result = j.payload.result;
  return (
    <>
      <Link className="text-link back-link" to="/agents">
        <ArrowLeft size={14} /> Agent operations
      </Link>
      <PageHeading
        eyebrow={"RUN " + id.slice(0, 8).toUpperCase()}
        title={label(j.kind) + " workflow"}
        action={<Status value={j.state} />}
      >
        Requested {formatDate(j.created_at)} · {j.payload.model} · Maximum{" "}
        {j.payload.max_model_calls} model call per run
      </PageHeading>
      <ErrorNotice message={error || j.payload.error?.message} />
      <div className="agent-run-layout">
        <section className="panel section-padding">
          <div className="panel-title-row">
            <h2>Execution trail</h2>
            <Bot size={20} />
          </div>
          <p className="section-copy">
            Task outputs and evidence are recorded at each completed step.
            Pausing takes effect at a step boundary.
          </p>
          <ol className="agent-step-list">
            {j.steps.map((s, i) => (
              <li key={s.step}>
                <span>
                  <Check size={15} />
                </span>
                <div>
                  <strong>{label(s.step)}</strong>
                  <small>{formatDate(s.created_at)}</small>
                  <details>
                    <summary>Inspect recorded evidence</summary>
                    <pre className="json-evidence">
                      {JSON.stringify(s.output, null, 2)}
                    </pre>
                  </details>
                </div>
              </li>
            ))}
            {["queued", "running"].includes(j.state) && (
              <li>
                <span className="pending-step">
                  <Clock3 size={15} />
                </span>
                <div>
                  <strong>
                    {j.state === "queued"
                      ? "Waiting for the worker"
                      : "Working on the next step"}
                  </strong>
                  <small>This page refreshes while the run is active.</small>
                </div>
              </li>
            )}
          </ol>
          {!j.steps.length && !["queued", "running"].includes(j.state) && (
            <p className="muted">No steps completed.</p>
          )}
          {user.role !== "auditor" && (
            <div className="button-row">
              {["queued", "running"].includes(j.state) && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => control("pause")}
                >
                  <Pause size={15} /> Pause
                </button>
              )}
              {["paused", "failed", "interrupted"].includes(j.state) &&
                !(
                  j.payload.model_attempts &&
                  (j.state === "failed" ||
                    !j.steps.some((s) => s.step === "draft_analysis"))
                ) && (
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={() => control("resume")}
                  >
                    <Play size={15} /> Resume
                  </button>
                )}
              {!["completed", "cancelled"].includes(j.state) && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => control("cancel")}
                >
                  <X size={15} /> Cancel
                </button>
              )}
            </div>
          )}
          <p className="privacy-note">
            Evidence checks validate references, dates, and allowed outputs.
            They do not guarantee the correctness of every interpretation.
          </p>
        </section>
        <div>
          {result ? (
            <section className="panel section-padding agent-result">
              <span className="eyebrow">DRAFT FOR HUMAN REVIEW</span>
              <h2>
                {j.kind === "maintenance"
                  ? "Intelligence refresh results"
                  : "A reviewable starting point."}
              </h2>
              {result.summary && <p className="reasoning">{result.summary}</p>}
              {result.recommendation && (
                <Status value={result.recommendation} />
              )}
              <ResultList title="Findings" items={result.findings} />
              <ResultList
                title="Missing evidence"
                items={result.missing_evidence}
              />
              {result.citations && (
                <>
                  <h3>Verified policy evidence</h3>
                  <Evidence citations={result.citations} />
                </>
              )}
              {result.obligations && (
                <>
                  <h3>Proposed obligations</h3>
                  <p className="section-copy">
                    {result.output_scope ||
                      "Prioritized suggestions for human review; review the full source policy."}
                  </p>
                  {result.obligations.map((o, i) => (
                    <article className="obligation-card" key={i}>
                      <span className="count-pill">{i + 1}</span>
                      <p>{o.obligation}</p>
                      <Status value={o.control_kind} />
                      <Evidence citations={[o.citation]} />
                    </article>
                  ))}
                  <Link className="button secondary" to="/rules/new">
                    Draft a control for human approval{" "}
                    <ArrowUpRight size={15} />
                  </Link>
                </>
              )}
              {result.coverage && (
                <div className="notice warning">
                  <div>
                    Policy coverage:{" "}
                    {result.coverage.included_characters?.toLocaleString()} of{" "}
                    {result.coverage.document_characters?.toLocaleString()}{" "}
                    characters.{" "}
                    {result.coverage.complete
                      ? "The complete supplied document was in scope."
                      : "This is a partial-document analysis; review the remaining text separately."}
                  </div>
                </div>
              )}
              {result.screened !== undefined && (
                <>
                  <p className="section-copy">
                    {result.screened} customers screened ·{" "}
                    {result.customers_with_matches} with potential matches
                  </p>
                  <p>No AI call was used for the scheduled refresh.</p>
                </>
              )}
              <ResultList title="Limitations" items={result.limitations} />
            </section>
          ) : (
            <section className="panel">
              <Empty
                icon={j.state === "failed" ? CircleAlert : Bot}
                title={
                  j.state === "failed"
                    ? "This run needs attention."
                    : "The evidence comes first."
                }
              >
                {j.state === "failed"
                  ? j.payload.model_attempts
                    ? "This run used its model attempt. Review the error and evidence, then start a new workflow from Agent operations."
                    : "Read the error and completed steps. Resume after resolving the missing dependency or evidence issue."
                  : "The result will appear when the workflow completes. Agents prepare drafts; your team approves consequential actions."}
              </Empty>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
function ResultList({ title, items }) {
  return items?.length ? (
    <div className="result-list">
      <h3>{title}</h3>
      <ul>
        {items.map((v, i) => (
          <li key={i}>{v}</li>
        ))}
      </ul>
    </div>
  ) : null;
}
