import { Activity, ArrowUpRight, Bot, Check, Workflow } from "lucide-react";
import { Link } from "../navigation";
import {
  Empty,
  ErrorNotice,
  Loading,
  PageHeading,
  useResource,
} from "../components";
import { label, Metric } from "../product-components";
export default function ActivityAnalytics() {
  const resource = useResource("/analytics");
  if (resource.loading) return <Loading />;
  if (resource.error)
    return <ErrorNotice message={resource.error} retry={resource.reload} />;
  const stats = resource.data;
  return (
    <>
      <PageHeading eyebrow="ADVANCED" title="Activity analytics">
        Recorded activity and dispositions describe the loaded workspace; they
        do not establish detection accuracy.
      </PageHeading>
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
    </>
  );
}
