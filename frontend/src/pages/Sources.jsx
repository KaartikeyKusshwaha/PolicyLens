import { useState } from "react";
import { Link } from "../navigation";
import {
  ArrowUpRight,
  Building2,
  Database,
  Globe2,
  KeyRound,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { api } from "../services/api";
import {
  ErrorNotice,
  formatDate,
  Loading,
  PageHeading,
  Success,
  useResource,
} from "../components";
import { Status } from "../product-components";
import { useSession } from "../session";
import { useWorkspace } from "../App";

export default function Sources({ advanced = false }) {
  const r = useResource("/sources");
  const { health } = useWorkspace();
  const { user } = useSession();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  async function sync(id) {
    setBusy(id);
    setError("");
    setSuccess("");
    try {
      const data = await api("/sources/" + id + "/sync", { method: "POST" });
      setSuccess(
        `${data.name}: ${data.count.toLocaleString()} entries downloaded and validated.`,
      );
      r.reload();
      health.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  async function syncEnabled() {
    setBusy("enabled"); setError(""); setSuccess("");
    let completed = 0;
    try {
      for (const id of r.data.enabled_sources) {
        await api("/sources/" + id + "/sync", { method: "POST" });
        completed += 1;
      }
      setSuccess(`${completed} enabled feeds downloaded and validated.`);
    } catch (failure) { setError(`${completed} enabled feeds completed before the failure. ${failure.message}`); }
    finally { r.reload(); health.reload(); setBusy(""); }
  }
  if (!advanced) return <>
    <PageHeading eyebrow="SETTINGS & AGENTS" title="Connections and freshness" action={<button className="button secondary" onClick={() => { r.reload(); health.reload(); }}>Refresh connection status</button>}>Review source availability before preparing investigations. No match is not clearance.</PageHeading>
    <ErrorNotice message={r.error || error} retry={r.error ? r.reload : undefined} />
    {success && <Success>{success}</Success>}
    {r.loading ? <Loading /> : r.data && <>
      <section className="panel section-padding"><h2>Sanctions coverage</h2><p>{r.data.feeds.filter(feed => r.data.enabled_sources.includes(feed.id) && feed.status === "ready").length} of {r.data.enabled_sources.length} enabled feeds are fresh. Every enabled feed must be fresh before screening completes.</p><p>Freshness window: {r.data.max_age_hours} hours after download. Potential matches require human investigation.</p>
        {["admin", "analyst"].includes(user.role) && <button className="button primary" disabled={Boolean(busy) || !r.data.enabled_sources.length} onClick={syncEnabled}>{busy ? "Downloading enabled feeds…" : "Sync enabled feeds"}</button>}
        <p><Link to="/settings?section=Monitoring">Choose coverage and recurring screening</Link></p><Link to="/advanced/sources">Inspect per-source dates, checksums and sync controls</Link>
      </section>
      <section className="panel section-padding"><h2>AI service</h2><Status value={r.data.groq.status} /><p>Model: <code>{r.data.groq.model || "Not reported"}</code>. A configured key indicates presence; a successful run confirms access. Provider limits and workspace run budgets still apply.</p><p className="privacy-note">Selected policy, customer and transaction evidence is sent to Groq. Structured masking can be configured per agent key; free text may still contain personal data.</p><Link to="/settings/agents">Review scoped agent access</Link></section>
      <section className="panel section-padding"><h2>Engine and transaction connections</h2><p>Import existing engine records with explicit customer mapping, or configure signed webhook ingestion. The built-in monitoring engine is a starter option.</p><Link to="/settings/imports">Review engine imports</Link><p><Link to="/settings?section=Integrations">Configure signed transaction ingestion</Link></p></section>
    </>}
  </>;
  return (
    <>
      <PageHeading
        eyebrow="OFFICIAL SOURCES. VISIBLE COVERAGE."
        title="Sanctions source details"
        action={
          <button
            className="button secondary"
            onClick={() => {
              r.reload();
              health.reload();
            }}
          >
            <RefreshCw size={15} /> Refresh status
          </button>
        }
      >
        Know what each connection covers, when it was downloaded, and where its
        limits begin.
      </PageHeading>
      <ErrorNotice message={r.error || error} />
      {success && <Success>{success}</Success>}
      {r.loading ? (
        <Loading />
      ) : (
        r.data && (
          <>
            <div className="notice neutral">
              <ShieldCheck size={19} />
              <div>
                Every enabled sanctions feed must be fresh before screening can
                complete.{" "}
                <Link to="/settings">
                  Configure coverage and recurring screening →
                </Link>
              </div>
            </div>
            <div className="sources-grid">
              {r.data.feeds.map((feed) => (
                <section className="panel source-card" key={feed.id}>
                  <div className="source-card-top">
                    <span className="source-logo ofac-logo">
                      <Globe2 size={25} />
                    </span>
                    <Status value={feed.status} />
                  </div>
                  <div className="eyebrow">
                    {r.data.enabled_sources.includes(feed.id)
                      ? "ENABLED FOR SCREENING"
                      : "AVAILABLE · NOT ENABLED"}
                  </div>
                  <h2>{feed.name}</h2>
                  <p>
                    The complete supported primary names and aliases from this
                    official public XML feed. Potential matches require human
                    investigation.
                  </p>
                  <dl>
                    <div>
                      <dt>Entries</dt>
                      <dd>{feed.count.toLocaleString()}</dd>
                    </div>
                    <div>
                      <dt>Fetched</dt>
                      <dd>{formatDate(feed.fetched_at)}</dd>
                    </div>
                    <div>
                      <dt>Publication</dt>
                      <dd>{feed.published_at || "Not supplied"}</dd>
                    </div>
                    <div>
                      <dt>Freshness</dt>
                      <dd>{r.data.max_age_hours} hours after download</dd>
                    </div>
                  </dl>
                  {["admin", "analyst"].includes(user.role) && (
                    <button
                      className="button primary"
                      disabled={Boolean(busy)}
                      onClick={() => sync(feed.id)}
                    >
                      <RefreshCw
                        size={15}
                        className={busy === feed.id ? "spin" : ""}
                      />
                      {busy === feed.id
                        ? "Downloading…"
                        : feed.count
                          ? "Sync latest snapshot"
                          : "Connect & sync"}
                    </button>
                  )}
                  <a
                    className="text-link source-reference"
                    href={feed.docs}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Official documentation <ArrowUpRight size={14} />
                  </a>
                  {feed.sha256 && (
                    <details>
                      <summary>Snapshot checksum</summary>
                      <code className="hash-note">{feed.sha256}</code>
                    </details>
                  )}
                </section>
              ))}
            </div>
            <div className="source-bottom-grid">
              <section className="panel setup-instructions">
                <div className="section-heading">
                  <span className="section-icon">
                    <KeyRound size={20} />
                  </span>
                  <div>
                    <h2>Groq · AI workflows</h2>
                    <p>Free-tier access with your server-side key.</p>
                  </div>
                  <Status value={r.data.groq.status} />
                </div>
                <p className="section-copy">
                  Configured model: <code>{r.data.groq.model}</code>. A
                  configured key indicates presence; a successful agent run
                  confirms provider access. Requests are bounded by workspace
                  run budgets and provider limits.
                </p>
                <a
                  className="text-link"
                  href="https://console.groq.com/keys"
                  target="_blank"
                  rel="noreferrer"
                >
                  Manage your API key <ArrowUpRight size={15} />
                </a>
                <p className="privacy-note">
                  Set GROQ_API_KEY in backend/.env and restart after changes.
                  Your key never appears in frontend code. Selected policy,
                  customer, and transaction evidence is sent to Groq.
                </p>
              </section>
              <section className="panel section-padding">
                <h2>Reference data, fetched when needed</h2>
                <div className="reference-source">
                  <span className="source-logo fx-logo">fx</span>
                  <div>
                    <strong>Frankfurter</strong>
                    <p>
                      Free daily currency reference rates. Original rate and
                      date are saved with individual AI assessments.
                    </p>
                    <a
                      href="https://frankfurter.dev/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      API documentation ↗
                    </a>
                  </div>
                </div>
                <div className="reference-source">
                  <span className="source-logo ofac-logo">
                    <Building2 size={22} />
                  </span>
                  <div>
                    <strong>GLEIF</strong>
                    <p>
                      Key-free legal-entity reference lookup by LEI from company
                      profiles. It is not full beneficial-ownership or identity
                      verification.
                    </p>
                    <a
                      href="https://www.gleif.org/en/lei-data/gleif-api/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      API documentation ↗
                    </a>
                  </div>
                </div>
              </section>
            </div>
            <div className="subtle-note">
              <Database size={17} />
              <p>
                Coverage is limited to the configured lists and normalized name
                matching. No PEP, adverse-media, beneficial-ownership, or
                global-clearance claim is made. Sources that fail validation
                remain unavailable.
              </p>
            </div>
          </>
        )
      )}
    </>
  );
}
