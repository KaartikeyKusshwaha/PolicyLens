import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowUpRight, Check, GitCompareArrows } from "lucide-react";
import { api } from "../services/api";
import {
  Empty,
  ErrorNotice,
  Field,
  formatDate,
  Loading,
  PageHeading,
  Submit,
  Success,
  useResource,
} from "../components";
import { AgentButton, Status } from "../product-components";
import { useSession } from "../session";

export function PolicyChanges() {
  const r = useResource("/policy-changes");
  const tasks = useResource("/tasks");
  const [error, setError] = useState("");
  const { user } = useSession();
  async function complete(id) {
    try {
      await api("/tasks/" + id + "/complete", { method: "POST" });
      tasks.reload();
    } catch (e) {
      setError(e.message);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="POLICY CHANGES, WITH FOLLOW-THROUGH"
        title="Understand what changed. Track what follows."
      >
        Compare policy versions, investigate their implications, and assign
        applicability reviews.
      </PageHeading>
      <ErrorNotice message={r.error || error} />
      <section className="panel">
        <div className="panel-heading">
          <h2>Policy version changes</h2>
          <Link className="text-link" to="/policies">
            Open library <ArrowUpRight size={14} />
          </Link>
        </div>
        {r.loading ? (
          <Loading />
        ) : r.data?.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Policy</th>
                  <th>Version change</th>
                  <th>Status</th>
                  <th>Detected</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {r.data.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link className="table-link" to={"/changes/" + c.id}>
                        {c.title}
                      </Link>
                    </td>
                    <td>
                      {c.old_version} → {c.new_version}
                    </td>
                    <td>
                      <Status value={c.status} />
                    </td>
                    <td>{formatDate(c.created_at)}</td>
                    <td>
                      <Link className="icon-button" to={"/changes/" + c.id}>
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
            icon={GitCompareArrows}
            title="Changes should lead to clear next steps."
          >
            Save a new policy version to create a tracked change. Archived text
            remains available for comparison.
          </Empty>
        )}
      </section>
      <section className="panel detail-section">
        <div className="panel-heading">
          <div>
            <h2>Review and remediation tasks</h2>
            <p>Applicable obligations must be confirmed by a human.</p>
          </div>
          <span className="count-pill">
            {tasks.data?.filter((t) => t.status === "open").length || 0} open
          </span>
        </div>
        <div className="section-padding">
          {tasks.data?.length ? (
            tasks.data.map((t) => (
              <div className="task-row" key={t.id}>
                <div>
                  <strong>{t.title}</strong>
                  <small>
                    {t.due_at ? formatDate(t.due_at) : "No due date"}{" "}
                    {t.customer_id && (
                      <>
                        ·{" "}
                        <Link to={"/customers/" + t.customer_id}>
                          Customer profile
                        </Link>
                      </>
                    )}
                  </small>
                </div>
                <Status value={t.status} />
                {t.status === "open" && user.role !== "auditor" && (
                  <button
                    className="icon-button"
                    aria-label={"Complete " + t.title}
                    onClick={() => complete(t.id)}
                  >
                    <Check size={18} />
                  </button>
                )}
              </div>
            ))
          ) : (
            <p className="section-copy">No review tasks recorded.</p>
          )}
        </div>
      </section>
    </>
  );
}

export function ChangeDetail() {
  const { id } = useParams();
  const r = useResource("/policy-changes/" + id);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { user } = useSession();
  async function review(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/policy-changes/" + id + "/actions", {
        method: "POST",
        body: Object.fromEntries(new FormData(e.currentTarget)),
      });
      r.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (r.loading) return <Loading />;
  if (r.error) return <ErrorNotice message={r.error} />;
  const c = r.data;
  return (
    <>
      <Link className="text-link back-link" to="/changes">
        <ArrowLeft size={14} /> Policy changes
      </Link>
      <PageHeading
        eyebrow={"VERSION " + c.old_version + " → " + c.new_version}
        title={c.title}
        action={<Status value={c.status} />}
      >
        A traceable comparison of archived policy versions.
      </PageHeading>
      <ErrorNotice message={error} />
      <div className="policy-change-layout">
        <div>
          <section className="panel">
            <div className="panel-heading">
              <h2>Document comparison</h2>
              <span className="tiny-label">ARCHIVED VERSIONS</span>
            </div>
            <pre className="policy-diff">
              {c.diff ||
                "Text content is unchanged; metadata or version information changed."}
            </pre>
          </section>
          <section className="panel section-padding detail-section">
            <h2>Linked controls</h2>
            {c.linked_rules.length ? (
              c.linked_rules.map((rule) => (
                <Link
                  className="linked-record"
                  to={"/rules/" + rule.id}
                  key={rule.id}
                >
                  <div>
                    <strong>{rule.title}</strong>
                    <small>
                      Control v{rule.version} · linked policy v
                      {rule.policy_version}
                    </small>
                  </div>
                  <Status value={rule.status} />
                  <ArrowUpRight size={15} />
                </Link>
              ))
            ) : (
              <p className="section-copy">
                No controls currently reference this policy.
              </p>
            )}
          </section>
        </div>
        <aside>
          <section className="panel section-padding">
            <h2>Research the implications</h2>
            <p className="section-copy">
              Ask an agent to compare the versions and propose obligations. Its
              output is a draft for your team to interpret.
            </p>
            {user.role !== "auditor" && (
              <AgentButton kind="policy_change" targetId={id}>
                Analyze policy change
              </AgentButton>
            )}
            <div className="aside-rule" />
            <h3>{c.candidate_customers.length} candidate customers</h3>
            <p className="section-copy">{c.scope}</p>
          </section>
          {["admin", "reviewer"].includes(user.role) &&
            c.status === "pending_review" && (
              <form
                className="panel section-padding detail-section"
                onSubmit={review}
              >
                <h2>Record the impact decision</h2>
                <Field label="Action">
                  <select name="action">
                    <option value="approve">
                      Create applicability review tasks
                    </option>
                    <option value="dismiss">Record no further action</option>
                  </select>
                </Field>
                <Field label="Reasoning and scope">
                  <textarea
                    name="notes"
                    required
                    minLength={10}
                    maxLength={2000}
                    rows={4}
                  />
                </Field>
                <p className="privacy-note">
                  Approval creates one applicability-review task per candidate
                  customer, rather than declaring every customer affected. It
                  does not modify active controls.
                </p>
                <Submit busy={busy}>Record review</Submit>
              </form>
            )}
          {c.review_notes && (
            <section className="panel section-padding detail-section">
              <h2>Recorded human review</h2>
              <p className="section-copy">{c.review_notes}</p>
              <small>{c.review_tasks_created || 0} review tasks created.</small>
            </section>
          )}
        </aside>
      </div>
    </>
  );
}
