import { useState } from "react";
import {
  ArrowUpRight,
  Check,
  Database,
  ExternalLink,
  KeyRound,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  Badge,
  ErrorNotice,
  formatDate,
  Loading,
  PageHeading,
  Submit,
  Success,
  useResource,
} from "../components";
import { api } from "../services/api";
import { useWorkspace } from "../App";

export default function Sources() {
  const { data, error, loading, reload } = useResource("/sources");
  const { health } = useWorkspace();
  const [busy, setBusy] = useState(false);
  const [syncError, setSyncError] = useState("");
  const [success, setSuccess] = useState("");
  async function sync() {
    setBusy(true);
    setSyncError("");
    setSuccess("");
    try {
      const result = await api("/sources/ofac/sync", { method: "POST" });
      setSuccess(
        `${result.count.toLocaleString()} OFAC entries synced successfully, including their aliases.`,
      );
      reload();
      health.reload();
    } catch (e) {
      setSyncError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="CONNECTED INTELLIGENCE"
        title="Know where your evidence comes from."
        action={
          <button
            className="button secondary"
            onClick={() => {
              reload();
              health.reload();
            }}
          >
            <RefreshCw size={16} /> Refresh status
          </button>
        }
      >
        Official data, clear provenance, and an honest view of every connection.
      </PageHeading>
      <ErrorNotice message={error} retry={reload} />
      <ErrorNotice message={syncError} />
      {success && <Success>{success}</Success>}
      {loading ? (
        <Loading />
      ) : (
        data && (
          <>
            <div className="sources-grid">
              <section className="panel source-card">
                <div className="source-card-top">
                  <span className="source-logo groq-logo">g</span>
                  <Badge
                    value={
                      data.groq.status === "configured"
                        ? "ready"
                        : "needs_review"
                    }
                  >
                    {data.groq.status === "configured"
                      ? "Key configured"
                      : "Needs API key"}
                  </Badge>
                </div>
                <div className="eyebrow">AI ANALYSIS</div>
                <h2>Groq</h2>
                <p>
                  Policy-grounded explanations and transaction assessments, with
                  structured output and verified citations.
                </p>
                <dl>
                  <div>
                    <dt>Plan</dt>
                    <dd>Free tier · rate limits apply</dd>
                  </div>
                  <div>
                    <dt>Model</dt>
                    <dd className="mono">{data.groq.model}</dd>
                  </div>
                  <div>
                    <dt>Authentication</dt>
                    <dd>Server-side API key</dd>
                  </div>
                </dl>
                <a
                  className="text-link"
                  href="https://console.groq.com/keys"
                  target="_blank"
                  rel="noreferrer"
                >
                  Get a free API key <ArrowUpRight size={15} />
                </a>
              </section>
              <section className="panel source-card">
                <div className="source-card-top">
                  <span className="source-logo ofac-logo">
                    <ShieldCheck size={28} />
                  </span>
                  <Badge
                    value={
                      data.ofac.status === "ready" ? "ready" : "needs_review"
                    }
                  >
                    {
                      {
                        ready: "Fresh snapshot",
                        stale: "Sync required",
                        not_synced: "Not connected",
                      }[data.ofac.status]
                    }
                  </Badge>
                </div>
                <div className="eyebrow">SANCTIONS EVIDENCE</div>
                <h2>U.S. Treasury · OFAC</h2>
                <p>
                  Complete SDN primary names and aliases from the official XML
                  feed. A name match is a lead for human review.
                </p>
                <dl>
                  <div>
                    <dt>Entries</dt>
                    <dd>{data.ofac.count.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt>Last synced</dt>
                    <dd>{formatDate(data.ofac.fetched_at)}</dd>
                  </div>
                  <div>
                    <dt>Freshness window</dt>
                    <dd>{data.max_age_hours} hours</dd>
                  </div>
                </dl>
                <Submit type="button" busy={busy} onClick={sync}>
                  <RefreshCw size={15} />{" "}
                  {data.ofac.count ? "Sync latest list" : "Connect & sync"}
                </Submit>
              </section>
              <section className="panel source-card">
                <div className="source-card-top">
                  <span className="source-logo fx-logo">fx</span>
                  <Badge value="neutral">Fetched on demand</Badge>
                </div>
                <div className="eyebrow">CURRENCY CONTEXT</div>
                <h2>Frankfurter</h2>
                <p>
                  Daily reference exchange rates from public financial
                  institutions, used to express non-USD amounts in USD.
                </p>
                <dl>
                  <div>
                    <dt>Cost</dt>
                    <dd>Free · no API key</dd>
                  </div>
                  <div>
                    <dt>Frequency</dt>
                    <dd>Daily reference rates</dd>
                  </div>
                  <div>
                    <dt>Evidence</dt>
                    <dd>Rate and date saved per assessment</dd>
                  </div>
                </dl>
                <a
                  className="text-link"
                  href="https://frankfurter.dev/"
                  target="_blank"
                  rel="noreferrer"
                >
                  Explore the API <ArrowUpRight size={15} />
                </a>
              </section>
            </div>
            <div className="source-bottom-grid">
              <section className="panel setup-instructions">
                <div className="section-heading">
                  <span className="section-icon">
                    <KeyRound size={19} />
                  </span>
                  <div>
                    <h2>Connect your Groq key</h2>
                    <p>One key. Kept on your server.</p>
                  </div>
                </div>
                <ol>
                  <li>
                    Create a free key at{" "}
                    <a
                      href="https://console.groq.com/keys"
                      target="_blank"
                      rel="noreferrer"
                    >
                      console.groq.com/keys
                    </a>
                    .
                  </li>
                  <li>
                    Copy <code>backend/.env.example</code> to{" "}
                    <code>backend/.env</code> and set:
                  </li>
                </ol>
                <pre>
                  GROQ_API_KEY=gsk_your_key_here{`\n`}
                  GROQ_MODEL=openai/gpt-oss-20b
                </pre>
                <p>
                  Restart the Python server, then refresh this page. A
                  configured key means a key is present; successful analysis
                  confirms provider access.
                </p>
              </section>
              <section className="panel guidance-panel">
                <Database size={26} />
                <h2>Fresh evidence, visible limits.</h2>
                <p>
                  An evaluation requires a fresh OFAC snapshot and a valid
                  exchange rate. Failed downloads and invalid model responses
                  stop the operation.
                </p>
                <p>
                  OFAC coverage is limited to the SDN list and name similarity.
                  It does not cover every jurisdiction, beneficial ownership, or
                  all transliterations.
                </p>
                <a
                  href="https://ofac.treasury.gov/sanctions-list-service"
                  className="text-link"
                  target="_blank"
                  rel="noreferrer"
                >
                  Read about the official source <ExternalLink size={14} />
                </a>
              </section>
            </div>
            {data.ofac.sha256 && (
              <div className="subtle-note hash-note">
                <Check size={16} />
                <span>
                  Current OFAC snapshot SHA-256 <code>{data.ofac.sha256}</code>
                </span>
              </div>
            )}
          </>
        )
      )}
    </>
  );
}
