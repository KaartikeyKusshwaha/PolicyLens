import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  Bot,
  Check,
  Clock3,
  Download,
  Fingerprint,
  Workflow,
} from "lucide-react";
import { api } from "../services/api";
import {
  Empty,
  ErrorNotice,
  formatDate,
  Loading,
  PageHeading,
  useResource,
} from "../components";
import { label, Metric, Status } from "../product-components";
import { useSession } from "../session";

export default function AuditAnalytics() {
  const r = useResource("/analytics");
  const audit = useResource("/audit");
  const team = useResource("/team");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { user } = useSession();
  async function backup() {
    setBusy(true);
    setError("");
    try {
      const value = await api("/backups", { method: "POST" });
      window.location.assign(value.download_url);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (r.loading) return <Loading />;
  if (r.error) return <ErrorNotice message={r.error} />;
  const stats = r.data;
  return (
    <>
      <PageHeading
        eyebrow="OPERATIONS YOU CAN ACCOUNT FOR"
        title="A clear view of the work—and its record."
        action={
          <a className="button secondary" href="/api/audit/export" download>
            <Download size={15} /> Export audit checkpoint
          </a>
        }
      >
        Measured activity, documented human outcomes, and a verifiable chain of
        recorded events.
      </PageHeading>
      <ErrorNotice message={error || audit.error} />
      <div className="product-metrics">
        <Metric
          label="Transactions received"
          value={stats.transactions}
          icon={Activity}
          detail="Across monitored corridors"
        />
        <Metric
          label="Open investigations"
          value={stats.open_cases}
          icon={Workflow}
          detail={`${stats.escalated} escalated · ${stats.overdue} overdue`}
        />
        <Metric
          label="Human-reviewed cases"
          value={stats.resolved}
          icon={Check}
          detail="Recorded case dispositions"
        />
        <Metric
          label="Completed agent runs"
          value={stats.jobs.completed || 0}
          icon={Bot}
          detail={`${stats.jobs.failed || 0} failed · ${stats.jobs.queued || 0} queued`}
        />
      </div>
      <div className="analytics-grid">
        <section className="panel section-padding">
          <h2>Observed destination corridors</h2>
          <p className="section-copy">
            Transaction counts by supplied destination country. This does not
            measure country risk.
          </p>
          {stats.corridors.length ? (
            <div className="corridor-bars">
              {stats.corridors.map((c) => (
                <div key={c.country}>
                  <strong>{c.country}</strong>
                  <span>
                    <i
                      style={{
                        width: `${(c.transactions / Math.max(...stats.corridors.map((v) => v.transactions))) * 100}%`,
                      }}
                    />
                  </span>
                  <b>{c.transactions}</b>
                </div>
              ))}
            </div>
          ) : (
            <Empty title="Activity will bring this view to life.">
              Corridor counts appear after monitoring receives transactions.
            </Empty>
          )}
        </section>
        <section className="panel section-padding">
          <h2>Recorded case outcomes</h2>
          <p className="section-copy">
            Human dispositions for resolved cases. These labels alone do not
            establish detection accuracy or recall.
          </p>
          {Object.entries(stats.dispositions).map(([key, count]) => (
            <div className="outcome-row" key={key}>
              <span>{label(key)}</span>
              <strong>{count}</strong>
            </div>
          ))}
          <Link className="text-link" to="/cases">
            Review investigations <ArrowUpRight size={14} />
          </Link>
        </section>
      </div>
      <section className="panel detail-section">
        <div className="panel-heading">
          <div>
            <h2>Audit workspace</h2>
            <p>
              Authenticated actors and agent actions share a chronological event
              record.
            </p>
          </div>
          <Status
            value={audit.data?.verification.valid ? "verified" : "needs_review"}
          />
        </div>
        {audit.data && (
          <>
            <div className="audit-checkpoint">
              <Fingerprint size={24} />
              <div>
                <strong>
                  {audit.data.verification.entries_checked} entries checked
                </strong>
                <code>{audit.data.verification.head_hash}</code>
                <p>{audit.data.verification.limitation}</p>
              </div>
            </div>
            {audit.data.events.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Sequence</th>
                      <th>Action</th>
                      <th>Actor</th>
                      <th>Time</th>
                      <th>Recorded details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {audit.data.events.map((e) => (
                      <tr key={e.seq}>
                        <td className="mono">#{e.seq}</td>
                        <td>{label(e.action)}</td>
                        <td>
                          {team.data?.find((u) => u.id === e.actor)?.name ||
                            e.actor.slice(0, 24)}
                        </td>
                        <td className="nowrap">{formatDate(e.at)}</td>
                        <td>
                          <details>
                            <summary>Inspect event</summary>
                            <pre className="json-evidence">
                              {JSON.stringify(e.data, null, 2)}
                            </pre>
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="Your workspace’s record starts here.">
                Changes to records, control approvals, cases, and agent runs
                produce audit events.
              </Empty>
            )}
          </>
        )}
      </section>
      <section className="assistant-strip">
        <span className="assistant-strip-icon">
          <Clock3 size={21} />
        </span>
        <div>
          <h3>Keep evidence available.</h3>
          <p>
            Download checkpoints to a trusted external location. Workspace
            backups include private data and integration secrets.
          </p>
        </div>
        {user.role === "admin" && (
          <button className="button secondary" disabled={busy} onClick={backup}>
            {busy ? "Creating backup…" : "Download verified SQLite backup"}
          </button>
        )}
        <Link className="text-link" to="/decisions">
          Individual AI assessments <ArrowUpRight size={14} />
        </Link>
      </section>
    </>
  );
}
