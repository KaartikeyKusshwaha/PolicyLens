import { Link } from "react-router-dom";
import { useCallback, useState } from "react";
import {
  Empty,
  ErrorNotice,
  formatDate,
  Loading,
  PageHeading,
  useResource,
  useAutoRefresh,
} from "../components";
import { Status } from "../product-components";
import { useSession } from "../session";
import WorkDigest from "./WorkDigest";

function Queue({ title, resource, rows, children, empty, footer }) {
  return (
    <section className="panel section-padding">
      <h2>{title}</h2>
      {resource.error ? (
        <ErrorNotice message={resource.error} retry={resource.reload} />
      ) : resource.loading && !resource.data ? (
        <Loading />
      ) : rows.length ? (
        children
      ) : (
        <Empty title={empty}>Refresh after new work is recorded.</Empty>
      )}
      {footer}
    </section>
  );
}

function RetentionApprovals() {
  const resource = useResource("/retention");
  const data = resource.data;
  const rows = data
    ? [
        ...(data.policies || [])
          .filter((item) => item.status === "draft")
          .map((item) => ({
            id: item.id,
            title: "Retention policy: " + item.title,
          })),
        ...(data.holds || [])
          .filter((item) => item.status === "release_requested")
          .map((item) => ({
            id: item.id,
            title: "Hold release: " + item.scope,
          })),
        ...(data.copies || [])
          .filter((item) =>
            ["removal_requested", "removal_reported"].includes(item.status),
          )
          .map((item) => ({
            id: item.id,
            title: "Retained copy: " + item.status.replaceAll("_", " "),
          })),
        ...(data.deletion_requests || [])
          .filter((item) => item.status === "requested")
          .map((item) => ({ id: item.id, title: "Deletion plan review" })),
      ]
    : [];
  return (
    <Queue
      title="Retention reviews"
      resource={resource}
      rows={rows}
      empty="No pending retention reviews in the loaded inventory."
    >
      <div className="compact-records">
        {rows.slice(0, 20).map((item) => (
          <Link key={item.id} to="/settings/retention">
            <strong>{item.title}</strong>
            <span>Open governance review</span>
          </Link>
        ))}
      </div>
      <p className="subtle-note">
        Showing up to 20. Legal holds remain effective during release review; a
        reviewed deletion plan does not establish physical erasure.
      </p>
    </Queue>
  );
}

function AlertQueue({ caseById }) {
  const [offset, setOffset] = useState(0);
  const resource = useResource(`/alerts?limit=50&offset=${offset}`);
  useAutoRefresh(resource.reload);
  const rows = resource.data?.alerts || [];
  const pagination = (
    <div className="button-row">
      <button
        className="button secondary"
        disabled={offset === 0 || resource.loading}
        onClick={() => setOffset((value) => Math.max(0, value - 50))}
      >
        Previous alerts
      </button>
      <span>Page {Math.floor(offset / 50) + 1} · up to 50 alerts</span>
      <button
        className="button secondary"
        disabled={
          !resource.data?.has_more || resource.loading || offset >= 100000
        }
        onClick={() => setOffset((value) => value + 50)}
      >
        Next alerts
      </button>
    </div>
  );
  return (
    <Queue
      title="Recorded alerts"
      resource={resource}
      rows={rows}
      empty="No alerts on this page."
      footer={pagination}
    >
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Signal</th>
              <th>Origin</th>
              <th>Case</th>
              <th>Recorded</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.id}>
                <td>{item.rule_title || "Recorded signal"}</td>
                <td>
                  {item.origin === "external_engine"
                    ? item.external_source?.provider || "External engine"
                    : "Starter monitoring engine"}
                </td>
                <td>
                  <Link to={"/inbox/cases/" + item.case_id}>
                    {caseById[item.case_id]?.title ||
                      "Open linked investigation"}
                  </Link>
                </td>
                <td>{formatDate(item.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Queue>
  );
}

export default function Inbox({ view = "overview" }) {
  const [revision, setRevision] = useState(0);
  const cases = useResource("/cases");
  const rules = useResource("/rules");
  const changes = useResource("/policy-changes");
  const reloadCases = cases.reload, reloadRules = rules.reload, reloadChanges = changes.reload;
  const refresh = useCallback(() => {
    reloadCases(); reloadRules(); reloadChanges();
  }, [reloadCases, reloadRules, reloadChanges]);
  useAutoRefresh(refresh);
  const { user } = useSession();
  const open = (cases.data || []).filter((item) => item.status !== "resolved");
  const controls = (rules.data || []).filter((item) => item.status === "draft");
  const policyChanges = (changes.data || []).filter(
    (item) => item.status === "pending_review",
  );
  const caseById = Object.fromEntries(
    (cases.data || []).map((item) => [item.id, item]),
  );
  const titles = {
    overview: "Work waiting for human review.",
    alerts: "Alerts and their investigation context.",
    approvals: "Decisions reserved for your team.",
  };
  return (
    <>
      <PageHeading
        eyebrow="INBOX"
        title={titles[view]}
        action={
          <button
            className="button secondary"
            onClick={() => { refresh(); setRevision((value) => value + 1); }}
          >
            Refresh work queue
          </button>
        }
      >
        Cases assemble their evidence automatically. Review what needs your attention and decide what happens next. This queue updates while you work.
      </PageHeading>
      {view === "overview" && (
        <>
          {!cases.loading &&
            !rules.loading &&
            !cases.error &&
            !rules.error &&
            !cases.data?.length &&
            !rules.data?.length &&
            ["admin", "analyst"].includes(user.role) && (
              <section className="panel section-padding">
                <h2>Prepare your workspace</h2>
                <p>
                  Connect evidence, add the policies your team follows, and
                  submit controls for independent review.
                </p>
                <div className="button-row">
                  <Link to="/settings/sources">Connect evidence sources</Link>
                  <Link to="/policies/library/new">
                    Add an operating policy
                  </Link>
                  <Link to="/inbox/customers/new">Add a customer</Link>
                  <Link to="/policies/controls">
                    Prepare controls for independent approval
                  </Link>
                </div>
              </section>
            )}
          <WorkDigest key={revision} />
          <Queue
            title="Investigation queue"
            resource={cases}
            rows={open}
            empty="No open investigations in the loaded queue."
          >
            <div className="compact-records">
              {[...open]
                .sort(
                  (a, b) =>
                    ({ critical: 0, high: 1, medium: 2, low: 3 }[a.priority] ?? 4) -
                    ({ critical: 0, high: 1, medium: 2, low: 3 }[b.priority] ?? 4) ||
                    new Date(a.due_at || "9999").getTime() -
                    new Date(b.due_at || "9999").getTime(),
                )
                .slice(0, 20)
                .map((item) => (
                  <Link key={item.id} to={"/inbox/cases/" + item.id}>
                    <div>
                      <strong>{item.title}</strong>
                      <small>
                        {item.customer_name} · Due {formatDate(item.due_at)}
                      </small>
                    </div>
                    <div className="queue-context"><span>{item.alert_count || 0} signals</span><Status value={item.status} /></div>
                  </Link>
                ))}
            </div>
            <Link className="text-link" to="/inbox/cases">
              Open all loaded cases
            </Link>
          </Queue>
        </>
      )}
      {view === "alerts" && <AlertQueue key={revision} caseById={caseById} />}
      {(view === "overview" || view === "approvals") && (
        <>
          <Queue
            title="Control approvals"
            resource={rules}
            rows={controls}
            empty="No control drafts in the loaded inventory."
          >
            <div className="compact-records">
              {controls.slice(0, 20).map((item) => (
                <Link key={item.id} to={"/policies/controls/" + item.id}>
                  <div>
                    <strong>{item.title}</strong>
                    <small>
                      Version {item.version} ·{" "}
                      {item.tuning_receipt_id
                        ? "Pinned tuning proposal"
                        : "Control draft"}
                    </small>
                  </div>
                  <span>
                    {[item.created_by, item.tuning_maker_id].includes(user.id)
                      ? "Different reviewer required"
                      : "Open for review"}
                  </span>
                </Link>
              ))}
            </div>
          </Queue>
          <Queue
            title="Policy-change reviews"
            resource={changes}
            rows={policyChanges}
            empty="No pending policy changes in the loaded inventory."
          >
            <div className="compact-records">
              {policyChanges.slice(0, 20).map((item) => (
                <Link key={item.id} to={"/policies/changes/" + item.id}>
                  <strong>{item.title}</strong>
                  <span>
                    {item.old_version} → {item.new_version}
                  </span>
                </Link>
              ))}
            </div>
          </Queue>
          {["admin", "reviewer", "auditor"].includes(user.role) && (
            <RetentionApprovals key={revision} />
          )}
        </>
      )}
      <p className="subtle-note">
        Pilot inventory limits apply: up to 2,000 cases and 1,000 controls are
        loaded. Queue previews show up to 20 items; counts describe loaded
        records. Alerts are paged separately in groups of 50.
      </p>
    </>
  );
}
