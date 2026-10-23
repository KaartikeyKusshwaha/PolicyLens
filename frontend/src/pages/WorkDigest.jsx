import { Link } from "react-router-dom";
import { ErrorNotice, formatDate, Loading, useResource } from "../components";

export default function WorkDigest() {
  const resource = useResource("/evidence/digest");
  const data = resource.data;
  return (
    <section className="panel section-padding" aria-label="Workspace digest">
      <h2>Workspace digest</h2>
      {resource.error ? (
        <ErrorNotice message={resource.error} retry={resource.reload} />
      ) : resource.loading ? (
        <Loading />
      ) : (
        data && (
          <>
            <p>
              Snapshot at {formatDate(data.generated_at)} · zero model calls
            </p>
            <dl className="detail-grid">
              {[
                ["Open cases", "open_cases"],
                ["Overdue cases", "overdue_cases"],
                ["Control drafts", "control_drafts"],
                ["Policy-change reviews", "policy_changes"],
              ].map(([label, name]) => (
                <div key={name}>
                  <dt>{label}</dt>
                  <dd>{data.queues[name].count}</dd>
                </div>
              ))}
              <div>
                <dt>Alerts in the last 24 hours</dt>
                <dd>{data.recent_alerts}</dd>
              </div>
              <div>
                <dt>Failed runs in the last 24 hours</dt>
                <dd>
                  <Link to="/advanced/agents">{data.failed_runs}</Link>
                </dd>
              </div>
            </dl>
            {data.source_warnings > 0 ? (
              <div className="notice error" role="alert">
                <div>
                  <strong>Sanctions evidence needs attention</strong>
                  <ul>
                    {data.sources
                      .filter((source) => source.status !== "ready")
                      .map((source) => (
                        <li key={source.id}>
                          {source.name}:{" "}
                          {source.status === "not_synced"
                            ? "not synced"
                            : "stale or invalid retrieval time"}
                        </li>
                      ))}
                  </ul>
                  <Link to="/settings/sources">
                    Review and sync evidence sources
                  </Link>
                </div>
              </div>
            ) : (
              <p>
                Enabled sanctions sources are within the retrieval-age limit. No
                match is not clearance.
              </p>
            )}
            {data.invalid_due_dates > 0 && (
              <p role="alert">
                {data.invalid_due_dates} open cases have invalid due times and
                cannot be classified as overdue.
              </p>
            )}
            <p className="subtle-note">{data.scope}</p>
          </>
        )
      )}
      <button className="button secondary" onClick={resource.reload}>
        Refresh digest
      </button>
    </section>
  );
}
