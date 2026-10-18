import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Bot,
  Check,
  Clock3,
  Globe2,
  Plus,
  ShieldCheck,
  Users,
  Workflow,
} from "lucide-react";
import {
  Empty,
  ErrorNotice,
  formatDate,
  Loading,
  PageHeading,
  useResource,
} from "../components";
import { Metric, Status, useLiveResource } from "../product-components";
import { useSession } from "../session";

export default function CommandCenter() {
  const { data, error, loading, reload } = useResource("/dashboard");
  const cases = useResource("/cases");
  const jobs = useLiveResource("/agents/jobs");
  const sources = useResource("/sources");
  const { user } = useSession();
  if (loading) return <Loading />;
  if (error) return <ErrorNotice message={error} retry={reload} />;
  const stats = data.operations;
  const ready =
    sources.data?.feeds.filter(
      (s) =>
        sources.data.enabled_sources.includes(s.id) && s.status === "ready",
    ).length || 0;
  const enabled = sources.data?.enabled_sources.length || 3;
  const steps = [
    {
      title: "Connect official intelligence",
      done: ready === enabled,
      to: "/sources",
      text: `${ready} of ${enabled} enabled feeds are fresh.`,
    },
    {
      title: "Add your operating policies",
      done: data.policies > 0,
      to: "/policies/new",
      text: "Use the actual policy documents your team follows.",
    },
    {
      title: "Build your customer context",
      done: stats.customers > 0,
      to: "/customers/new",
      text: "Add customers, countries, and due diligence status.",
    },
    {
      title: "Approve monitoring controls",
      done: stats.active_rules > 0,
      to: "/rules",
      text: "A second authorized person approves each new control.",
    },
  ];
  return (
    <>
      <PageHeading
        eyebrow="CROSS-BORDER COMPLIANCE OPERATIONS"
        title="Your next decision, in context."
        action={
          user.role !== "auditor" && (
            <Link className="button primary" to="/monitoring">
              <Plus size={17} /> Add transaction
            </Link>
          )
        }
      >
        A connected view of your customers, controls, investigations, and agent
        activity.
      </PageHeading>
      <section className="operations-hero">
        <div>
          <span className="hero-label">
            <span className="status-dot green" /> {user.workspace.toUpperCase()}
          </span>
          <h2>
            Follow the evidence.
            <br />
            Keep your team moving.
          </h2>
          <p>
            Bring every corridor into view, investigate the exceptions,
            <br className="desktop-break" /> and keep a clear record of the
            decisions that follow.
          </p>
          <Link className="button hero-button" to="/cases">
            Open investigations <ArrowUpRight size={16} />
          </Link>
        </div>
        <div className="corridor-art" aria-hidden="true">
          <Globe2 size={150} strokeWidth={0.55} />
          <span className="corridor-chip c-one">POLICY → CONTROL</span>
          <span className="corridor-chip c-two">ACTIVITY → EVIDENCE</span>
          <span className="corridor-chip c-three">
            <Bot size={13} /> AGENTS + YOUR TEAM
          </span>
        </div>
      </section>
      <div className="product-metrics">
        <Metric
          label="Monitored transactions"
          value={stats.transactions.toLocaleString()}
          icon={Activity}
          detail="Records received through monitoring"
        />
        <Metric
          label="Open investigations"
          value={stats.open_cases}
          icon={Workflow}
          detail={`${stats.escalated} escalated · ${stats.overdue} overdue`}
        />
        <Metric
          label="Customer profiles"
          value={stats.customers}
          icon={Users}
          detail="In this workspace"
        />
        <Metric
          label="Active controls"
          value={stats.active_rules}
          icon={ShieldCheck}
          detail="Approved by a second person"
        />
      </div>
      {steps.some((s) => !s.done) && (
        <section className="panel product-onboarding">
          <div className="panel-heading">
            <div>
              <h2>Get your operation ready</h2>
              <p>Connect evidence and put your first control to work.</p>
            </div>
            <span className="count-pill">
              {steps.filter((s) => s.done).length} / 4
            </span>
          </div>
          <div className="onboarding-grid">
            {steps.map((s, i) => (
              <Link to={s.to} key={s.title} className={s.done ? "done" : ""}>
                <span className="step-number">
                  {s.done ? (
                    <Check size={15} />
                  ) : (
                    String(i + 1).padStart(2, "0")
                  )}
                </span>
                <strong>{s.title}</strong>
                <p>{s.text}</p>
                <ArrowUpRight size={15} />
              </Link>
            ))}
          </div>
        </section>
      )}
      <div className="operations-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Investigation queue</h2>
              <p>Work that needs a human decision.</p>
            </div>
            <Link className="text-link" to="/cases">
              View all <ArrowRight size={14} />
            </Link>
          </div>
          {cases.data?.length ? (
            <div className="compact-records">
              {cases.data
                .filter((c) => c.status !== "resolved")
                .slice(0, 5)
                .map((c) => (
                  <Link to={"/cases/" + c.id} key={c.id}>
                    <span className={"priority-line " + c.priority} />
                    <div>
                      <strong>{c.title}</strong>
                      <small>
                        {c.customer_name} · {c.alert_count} control alerts
                      </small>
                    </div>
                    <Status value={c.status} />
                    <ArrowUpRight size={15} />
                  </Link>
                ))}
            </div>
          ) : (
            <Empty icon={Workflow} title="Ready for your first investigation">
              Monitoring alerts create cases. You can also open a case from a
              customer profile.
            </Empty>
          )}
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Agent desk</h2>
              <p>Evidence gathering, with a visible trail.</p>
            </div>
            <Link className="text-link" to="/agents">
              Open desk <ArrowRight size={14} />
            </Link>
          </div>
          {jobs.data?.length ? (
            <div className="compact-records">
              {jobs.data.slice(0, 5).map((j) => (
                <Link to={"/agents/" + j.id} key={j.id}>
                  <span className="agent-list-icon">
                    <Bot size={18} />
                  </span>
                  <div>
                    <strong>{j.kind.replaceAll("_", " ")} run</strong>
                    <small>{formatDate(j.updated_at)}</small>
                  </div>
                  <Status value={j.state} />
                </Link>
              ))}
            </div>
          ) : (
            <Empty icon={Bot} title="A research team, on demand">
              Agents collect policy and screening evidence and prepare drafts
              for your review.
            </Empty>
          )}
        </section>
      </div>
      <section className="operations-bottom">
        <div>
          <Globe2 size={20} />
          <strong>
            {ready}/{enabled} intelligence feeds fresh
          </strong>
          <Link to="/sources">
            Check coverage <ArrowRight size={13} />
          </Link>
        </div>
        <div>
          <Clock3 size={19} />
          <strong>Every action leaves a trail</strong>
          <Link to="/audit">
            Open audit workspace <ArrowRight size={13} />
          </Link>
        </div>
      </section>
    </>
  );
}
