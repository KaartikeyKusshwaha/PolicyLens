import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  Clock3,
  FileCheck2,
  Plus,
  ScanLine,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";
import {
  Badge,
  DecisionTable,
  Empty,
  ErrorNotice,
  formatDate,
  Loading,
  PageHeading,
  useResource,
} from "../components";

export default function Overview() {
  const { data, loading, error, reload } = useResource("/dashboard");
  if (loading) return <Loading />;
  if (error) return <ErrorNotice message={error} retry={reload} />;
  const steps = [
    {
      done: data.policies > 0,
      title: "Build your policy library",
      text: "Add the documents your assessments should follow.",
      to: "/policies/new",
      action: "Add a policy",
    },
    {
      done: data.health.ai.status === "configured",
      title: "Connect your AI provider",
      text: "Add a free Groq API key to enable analysis.",
      to: "/sources",
      action: "View setup",
    },
    {
      done: data.health.sanctions.status === "ready",
      title: "Sync official sanctions data",
      text: "Fetch the full OFAC SDN list and its aliases.",
      to: "/sources",
      action: "Connect data",
    },
  ];
  const complete = steps.filter((s) => s.done).length;
  return (
    <>
      <PageHeading
        eyebrow="YOUR WORKSPACE, AT A GLANCE"
        title="Clarity in every decision."
        action={
          <Link className="button primary" to="/evaluate">
            <Plus size={17} /> New evaluation
          </Link>
        }
      >
        Your policies, transactions, and evidence. All in one place.
      </PageHeading>
      <section className="hero-banner">
        <div className="hero-copy">
          <span className="hero-label">
            <span className="status-dot green" /> YOUR NEXT DECISION STARTS HERE
          </span>
          <h2>
            Turn complex policies
            <br />
            into clear next steps.
          </h2>
          <p>
            Evaluate transactions against your policy library
            <br className="desktop-break" /> with traceable citations and
            current sanctions evidence.
          </p>
          <Link to="/evaluate" className="button hero-button">
            Evaluate a transaction <ArrowUpRight size={17} />
          </Link>
        </div>
        <div className="lens-art" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <div className="orbit orbit-three" />
          <div className="lens-center">
            <ScanLine size={53} strokeWidth={1.1} />
          </div>
          <span className="art-label label-one">
            <BookOpen size={13} /> Policy evidence
          </span>
          <span className="art-label label-two">
            <Check size={13} /> Clearer decisions
          </span>
          <i className="art-star">✦</i>
        </div>
      </section>
      <div className="stats-grid">
        {[
          {
            label: "Transactions assessed",
            value: data.total,
            icon: ScanLine,
            sub: "All recorded assessments",
            color: "sage",
          },
          {
            label: "Flagged assessments",
            value: data.flagged,
            icon: ShieldAlert,
            sub: "Potential policy violations",
            color: "rose",
          },
          {
            label: "Awaiting human review",
            value: data.pending,
            icon: Clock3,
            sub: "No review recorded yet",
            color: "amber",
          },
          {
            label: "Policies in library",
            value: data.policies,
            icon: BookOpen,
            sub: "Documents ready for retrieval",
            color: "blue",
          },
        ].map(({ label, value, icon: Icon, sub, color }) => (
          <section className="stat-card" key={label}>
            <div className="stat-top">
              <span>{label}</span>
              <span className={`stat-icon ${color}`}>
                <Icon size={17} />
              </span>
            </div>
            <div className="stat-value">{value.toLocaleString()}</div>
            <small>{sub}</small>
          </section>
        ))}
      </div>
      {complete < 3 && (
        <section className="panel setup-panel">
          <div className="panel-heading">
            <div>
              <h2>
                Make yourself at home{" "}
                <span className="tiny-label">GET STARTED</span>
              </h2>
              <p>Three steps to your first evidence-backed assessment.</p>
            </div>
            <span className="setup-count">{complete} of 3 complete</span>
          </div>
          <div className="setup-steps">
            {steps.map((step, i) => (
              <div
                className={`setup-step ${step.done ? "done" : ""}`}
                key={step.title}
              >
                <span className="step-number">
                  {step.done ? <Check size={16} /> : `0${i + 1}`}
                </span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
                <Link to={step.to}>
                  {step.done ? "View details" : step.action}
                  <ArrowRight size={14} />
                </Link>
              </div>
            ))}
          </div>
        </section>
      )}
      <div className="overview-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Recent assessments</h2>
              <p>A clear trail of your latest decisions.</p>
            </div>
            <Link className="text-link" to="/decisions">
              View all <ArrowRight size={14} />
            </Link>
          </div>
          {data.recent.length ? (
            <DecisionTable records={data.recent} compact />
          ) : (
            <Empty
              icon={FileCheck2}
              title="Your first decision starts here"
              action={
                <Link className="button secondary" to="/evaluate">
                  Create an evaluation <ArrowRight size={15} />
                </Link>
              }
            >
              Assess a transaction to see its result and supporting evidence
              here.
            </Empty>
          )}
        </section>
        <section className="panel activity-panel">
          <div className="panel-heading">
            <div>
              <h2>Workspace activity</h2>
              <p>Updates that matter.</p>
            </div>
            <span className="live-tag">AUDIT LOG</span>
          </div>
          {data.events.length ? (
            <div className="activity-list">
              {data.events.map((event) => (
                <div className="activity-item" key={event.id}>
                  <span className="activity-icon">
                    {event.kind.includes("policy") ? (
                      <BookOpen size={16} />
                    ) : event.kind.includes("source") ? (
                      <Sparkles size={16} />
                    ) : (
                      <ScanLine size={16} />
                    )}
                  </span>
                  <div>
                    <strong>
                      {
                        {
                          policy_added: "Policy added",
                          policy_updated: "Policy updated",
                          source_synced: "OFAC data synced",
                          source_failed: "OFAC sync failed",
                          transaction_assessed: "Transaction assessed",
                        }[event.kind]
                      }
                    </strong>
                    <p>
                      {event.payload.title ||
                        event.payload.transaction_id ||
                        (event.payload.count
                          ? `${event.payload.count.toLocaleString()} sanctions entries`
                          : "Retry from Data sources")}
                    </p>
                    <small>{formatDate(event.created_at)}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="activity-empty">
              <span className="activity-icon">
                <Clock3 size={19} />
              </span>
              <p>A fresh start.</p>
              <small>
                Your policy and assessment activity will appear here.
              </small>
            </div>
          )}
          <Link className="activity-bottom" to="/sources">
            <span>Data connection status</span>
            <Badge
              value={
                data.health.sanctions.status === "ready"
                  ? "ready"
                  : "needs_review"
              }
            >
              {data.health.sanctions.status === "ready"
                ? "Synced"
                : "Needs setup"}
            </Badge>
          </Link>
        </section>
      </div>
      <section className="assistant-strip">
        <div className="assistant-strip-icon">
          <Sparkles size={23} />
        </div>
        <div>
          <h3>A question about your policies?</h3>
          <p>
            Ask in plain language. Get an answer grounded in your documents.
          </p>
        </div>
        <Link className="text-link" to="/assistant">
          Open policy assistant <ArrowUpRight size={16} />
        </Link>
      </section>
    </>
  );
}
