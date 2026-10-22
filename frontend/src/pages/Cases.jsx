import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowUpRight,
  Download,
  MessageSquare,
  Plus,
  Workflow,
} from "lucide-react";
import { api } from "../services/api";
import {
  Empty,
  ErrorNotice,
  Field,
  formatDate,
  Loading,
  money,
  PageHeading,
  SearchBox,
  Submit,
  Success,
  useResource,
} from "../components";
import {
  AgentButton,
  DefinitionList,
  label,
  Status,
} from "../product-components";
import { useSession } from "../session";
import RelationshipGraph from "./RelationshipGraph";

export function Cases() {
  const r = useResource("/cases");
  const customers = useResource("/customers");
  const [params] = useSearchParams();
  const [creating, setCreating] = useState(Boolean(params.get("customer")));
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { user } = useSession();
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/cases", {
        method: "POST",
        body: Object.fromEntries(new FormData(e.currentTarget)),
      });
      r.reload();
      setCreating(false);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const filtered = r.data?.filter(
    (c) =>
      `${c.title} ${c.customer_name}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (status === "all" || c.status === status),
  );
  return (
    <>
      <PageHeading
        eyebrow="INVESTIGATION WORKSPACE"
        title="From alert to accountable decision."
        action={
          user.role !== "auditor" && (
            <button
              className="button primary"
              onClick={() => setCreating(!creating)}
            >
              <Plus size={16} /> Open investigation
            </button>
          )
        }
      >
        Group the signals, gather the evidence, and give each case a clear
        owner.
      </PageHeading>
      <ErrorNotice message={error || r.error} />
      {creating && (
        <form className="panel form-panel monitoring-form" onSubmit={submit}>
          <h2>Open a customer investigation</h2>
          <div className="form-grid">
            <Field label="Customer">
              <select
                name="customer_id"
                required
                defaultValue={params.get("customer") || ""}
              >
                <option value="" disabled>
                  Choose a customer
                </option>
                {customers.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Priority">
              <select name="priority" defaultValue="medium">
                {["low", "medium", "high", "critical"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </Field>
            <Field label="Case title" wide>
              <input name="title" minLength={5} maxLength={180} required />
            </Field>
            <Field label="Reason for investigation" wide>
              <textarea
                name="description"
                minLength={10}
                maxLength={4000}
                required
                rows={3}
              />
            </Field>
          </div>
          <p className="privacy-note">
            New signals are grouped into an existing open case for the same
            customer.
          </p>
          <div className="form-actions">
            <button
              type="button"
              className="text-button"
              onClick={() => setCreating(false)}
            >
              Cancel
            </button>
            <Submit busy={busy}>Open case</Submit>
          </div>
        </form>
      )}
      <section className="panel">
        <div className="library-toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search investigations or customers…"
          />
          <select
            aria-label="Case status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="all">All statuses</option>
            {["open", "investigating", "escalated", "resolved"].map((v) => (
              <option value={v} key={v}>
                {label(v)}
              </option>
            ))}
          </select>
        </div>
        {r.loading ? (
          <Loading />
        ) : filtered?.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Investigation</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Alerts</th>
                  <th>Review due</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link className="table-link" to={"/cases/" + c.id}>
                        {c.title}
                      </Link>
                      <small>{c.customer_name}</small>
                    </td>
                    <td>
                      <Status value={c.priority} />
                    </td>
                    <td>
                      <Status value={c.status} />
                    </td>
                    <td>{c.alert_count}</td>
                    <td
                      className={
                        new Date(c.due_at) < new Date() &&
                        c.status !== "resolved"
                          ? "overdue-text"
                          : "muted"
                      }
                    >
                      {formatDate(c.due_at)}
                    </td>
                    <td>
                      <Link
                        className="icon-button"
                        to={"/cases/" + c.id}
                        aria-label={"Open " + c.title}
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
          <Empty
            icon={Workflow}
            title="Every investigation starts with context."
          >
            Cases open when controls trigger or your team starts a review.
            Related alerts stay together.
          </Empty>
        )}
      </section>
    </>
  );
}

export function CaseDetail() {
  const { id } = useParams();
  const r = useResource("/cases/" + id);
  const team = useResource("/team");
  const [tab, setTab] = useState("Evidence");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [action, setAction] = useState("note");
  const { user } = useSession();
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    const form = e.currentTarget;
    const body = Object.fromEntries(new FormData(form));
    body.action = action;
    if (!body.assignee_id) delete body.assignee_id;
    if (!body.disposition) delete body.disposition;
    try {
      await api("/cases/" + id + "/actions", { method: "POST", body });
      form.reset();
      setSaved(true);
      r.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function completeTask(taskId) {
    try {
      await api("/tasks/" + taskId + "/complete", { method: "POST" });
      r.reload();
    } catch (e) {
      setError(e.message);
    }
  }
  if (r.loading) return <Loading />;
  if (r.error) return <ErrorNotice message={r.error} retry={r.reload} />;
  const c = r.data;
  const assignee = team.data?.find((u) => u.id === c.assignee_id);
  return (
    <>
      <Link className="text-link back-link" to="/cases">
        <ArrowLeft size={14} /> Investigations
      </Link>
      <PageHeading
        eyebrow={"CASE " + id.slice(0, 8).toUpperCase()}
        title={c.title}
        action={
          <a
            className="button secondary"
            href={"/api/cases/" + id + "/export"}
            download
          >
            <Download size={15} /> Export evidence pack
          </a>
        }
      >
        {c.customer_name} · Opened {formatDate(c.created_at)}
      </PageHeading>
      <div className="entity-summary">
        <Status value={c.status} />
        <Status value={c.priority} />
        <span>{c.alerts.length} alerts</span>
        <span>Owner: {assignee?.name || "Unassigned"}</span>
        <span>Due {formatDate(c.due_at)}</span>
      </div>
      <div className="case-layout">
        <div>
          <div className="page-tabs">
            {["Evidence", "Relationships", "Activity", "Tasks", "Agent work"].map((v) => (
              <button
                key={v}
                className={tab === v ? "active" : ""}
                aria-pressed={tab === v}
                onClick={() => setTab(v)}
              >
                {v}
              </button>
            ))}
          </div>
          {tab === "Relationships" && (
            <section className="panel section-padding">
              <h2>Observed customer relationships</h2>
              <p className="section-copy">Customer transaction context for this investigation. Links may include activity outside this case; they do not establish verified identity or wrongdoing.</p>
              <RelationshipGraph id={c.customer_id} />
            </section>
          )}
          {tab === "Evidence" && (
            <>
              <section className="panel section-padding">
                <h2>Investigation context</h2>
                <p className="section-copy preserve-lines">{c.description}</p>
                {c.external_source && <><h3>Imported source evidence</h3><DefinitionList items={[["Provider", c.external_source.provider], ["Instance", c.external_source.instance], ["Source record", c.external_source.source_id], ["Source name", c.external_source.source_name], ["Upstream status", c.external_source.source_status], ["Upstream outcome", c.external_source.source_outcome]]} /><p>Upstream status and outcome are retained as source evidence. The local investigation requires independent human review.</p><code style={{ overflowWrap: "anywhere" }}>{c.external_source.sha256}</code></>}
                <Link className="text-link" to={"/customers/" + c.customer_id}>
                  Open customer profile <ArrowUpRight size={14} />
                </Link>
              </section>
              <section className="panel detail-section">
                <div className="panel-heading">
                  <h2>Control hits and imported engine signals</h2>
                  <span className="count-pill">{c.alerts.length}</span>
                </div>
                {c.alerts.length ? (
                  <div className="control-hit-list">
                    {c.alerts.map((a) => (
                      <article key={a.id}>
                        <div className="panel-title-row">
                          {a.origin === "external_engine" ? <strong>{a.rule_title}</strong> : <Link to={"/rules/" + a.rule_id}>
                            <strong>{a.rule_title}</strong>
                          </Link>}
                          <Status value={a.priority} />
                        </div>
                        {a.origin === "external_engine" ? <><p>Imported source outcome: {a.facts.source_outcome}. This is external engine evidence; local disposition requires human review.</p><DefinitionList items={[["Source", a.external_source.provider], ["Instance", a.external_source.instance], ["Source decision", a.external_source.source_id], ["Source score", a.facts.source_score], ["Trigger object reference", a.facts.trigger_object_id]]} /></> : <><p>
                          Control version {a.rule_version} ·{" "}
                          {a.rule_snapshot.policy_title} v
                          {a.rule_snapshot.policy_version}
                        </p>
                        <DefinitionList
                          items={[
                            ["Observed", a.facts.observed],
                            ["Configured threshold", a.facts.threshold],
                            ["Currency", a.facts.currency],
                            ["Window", a.facts.window_hours + " hours"],
                          ]}
                        /></>}
                        <small>{formatDate(a.created_at)}</small>
                      </article>
                    ))}
                  </div>
                ) : (
                  <Empty title="No automated control hits">
                    This investigation was opened by your team or a screening
                    workflow.
                  </Empty>
                )}
              </section>
              {c.screening_evidence.map((ev, i) => (
                <section
                  className="panel section-padding detail-section"
                  key={ev.id}
                >
                  <h2>Sanctions evidence {i + 1}</h2>
                  <p className="section-copy">{ev.screening.scope}</p>
                  {ev.screening.matches.map((m, j) => (
                    <div className="sanction-match" key={j}>
                      <strong>{m.name}</strong>
                      <p>
                        {m.source_id.toUpperCase()} · ID {m.entity_id} · matched
                        “{m.matched_name}” · {(m.similarity * 100).toFixed(1)}%
                      </p>
                    </div>
                  ))}
                </section>
              ))}
              <section className="panel detail-section">
                <div className="panel-heading">
                  <h2>Customer transaction history</h2>
                  <small>Latest 200 records</small>
                </div>
                {c.transactions.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Reference</th>
                          <th>Counterparty</th>
                          <th>Amount</th>
                        </tr>
                      </thead>
                      <tbody>
                        {c.transactions.map((t) => (
                          <tr key={t.id}>
                            <td>{t.external_id}</td>
                            <td>
                              {t.counterparty}
                              <small>{t.counterparty_country}</small>
                            </td>
                            <td>{money(t.amount, t.currency)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Empty title="No monitored transactions">
                    Add activity to connect this review to transaction history.
                  </Empty>
                )}
              </section>
            </>
          )}
          {tab === "Activity" && (
            <section className="panel section-padding">
              <h2>Case activity</h2>
              {c.notes.length ? (
                <div className="case-timeline">
                  {c.notes.map((n) => (
                    <article key={n.id}>
                      <span className="activity-icon">
                        <MessageSquare size={16} />
                      </span>
                      <div>
                        <div>
                          <strong>{n.author}</strong>
                          <Status value={n.action} />
                        </div>
                        <p className="preserve-lines">{n.notes}</p>
                        <small>{formatDate(n.created_at)}</small>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <Empty title="A clear trail starts with your first note">
                  Case actions and investigator notes are recorded here.
                </Empty>
              )}
            </section>
          )}
          {tab === "Tasks" && (
            <section className="panel section-padding">
              <h2>Evidence tasks</h2>
              {c.tasks.length ? (
                c.tasks.map((t) => (
                  <div className="task-row" key={t.id}>
                    <div>
                      <strong>{t.title}</strong>
                      <small>
                        {t.due_at ? formatDate(t.due_at) : "No due date"}
                      </small>
                    </div>
                    <Status value={t.status} />
                    {user.role !== "auditor" && t.status === "open" && (
                      <button
                        className="button secondary"
                        onClick={() => completeTask(t.id)}
                      >
                        Complete
                      </button>
                    )}
                  </div>
                ))
              ) : (
                <Empty title="No tasks recorded">
                  Choose “Create task” in the case action form to request more
                  evidence.
                </Empty>
              )}
            </section>
          )}
          {tab === "Agent work" && (
            <section className="panel">
              <div className="panel-heading">
                <h2>Agent investigations and drafts</h2>
              </div>
              {c.agent_runs.length ? (
                <div className="compact-records">
                  {c.agent_runs.map((j) => (
                    <Link key={j.id} to={"/agents/" + j.id}>
                      <div>
                        <strong>{label(j.kind)}</strong>
                        <small>{formatDate(j.created_at)}</small>
                      </div>
                      <Status value={j.state} />
                      <ArrowUpRight size={15} />
                    </Link>
                  ))}
                </div>
              ) : (
                <Empty title="No agent work yet">
                  Start an investigation or reporting agent to collect a
                  reviewable draft.
                </Empty>
              )}
            </section>
          )}
        </div>
        <aside>
          <section className="panel section-padding">
            <h2>Investigation support</h2>
            <p className="section-copy">
              Collect current evidence and prepare a cited brief. Agents do not
              resolve cases.
            </p>
            {user.role !== "auditor" && (
              <div className="stack-actions">
                <AgentButton kind="investigation" targetId={id}>
                  Investigate with an agent
                </AgentButton>
                <AgentButton kind="report" targetId={id}>
                  Draft investigation report
                </AgentButton>
              </div>
            )}
            <div className="aside-rule" />
            <h3>Customer due diligence</h3>
            <DefinitionList
              items={[
                ["Name", c.customer.name],
                ["Country", c.customer.country],
                ["Recorded KYC status", c.customer.kyc_status],
              ]}
            />
          </section>
          {user.role !== "auditor" && (
            <form
              className="panel section-padding detail-section"
              onSubmit={submit}
            >
              <h2>Move the investigation forward</h2>
              <Field label="Action">
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                >
                  <option value="note">Add a note</option>
                  <option value="assign">Assign investigator</option>
                  <option value="start">Start investigation</option>
                  <option value="escalate">Escalate</option>
                  <option value="task">Create task</option>
                  {["admin", "reviewer"].includes(user.role) && (
                    <option value="resolve">Resolve after review</option>
                  )}
                  <option value="reopen">Reopen investigation</option>
                </select>
              </Field>
              {action === "assign" && (
                <Field label="Investigator">
                  <select name="assignee_id" required defaultValue="">
                    <option value="" disabled>
                      Choose a team member
                    </option>
                    {team.data
                      ?.filter((u) => u.role !== "auditor")
                      .map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.name} · {u.role}
                        </option>
                      ))}
                  </select>
                </Field>
              )}
              {action === "resolve" && (
                <>
                  <Field label="Disposition">
                    <select name="disposition" required defaultValue="">
                      <option value="" disabled>
                        Choose your conclusion
                      </option>
                      <option value="confirmed">Confirmed concern</option>
                      <option value="false_positive">False positive</option>
                      <option value="insufficient_evidence">
                        Insufficient evidence
                      </option>
                    </select>
                  </Field>
                  <p className="privacy-note">
                    The assigned investigator cannot resolve their own case.
                  </p>
                </>
              )}
              <Field label="Notes or evidence request">
                <textarea
                  name="notes"
                  rows={4}
                  minLength={5}
                  maxLength={4000}
                  required
                />
              </Field>
              <ErrorNotice message={error} />
              {saved && <Success>Case action recorded.</Success>}
              <Submit busy={busy}>Record action</Submit>
            </form>
          )}
          {c.status === "resolved" && (
            <div className="notice success">
              <div>
                <strong>{label(c.disposition)}</strong>
                <p>
                  Final human decision recorded {formatDate(c.resolved_at)}.
                </p>
              </div>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
