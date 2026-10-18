import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CheckCheck,
  Download,
  FileCheck2,
  Plus,
  ShieldAlert,
} from "lucide-react";
import {
  Badge,
  DecisionTable,
  Empty,
  ErrorNotice,
  Evidence,
  Field,
  formatDate,
  Loading,
  money,
  PageHeading,
  SearchBox,
  Submit,
  Success,
  useResource,
  verdictLabel,
} from "../components";
import { api } from "../services/api";

export function Decisions() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useResource(
    `/decisions?limit=50&offset=${offset}`,
  );
  const [search, setSearch] = useState("");
  const [verdict, setVerdict] = useState("all");
  const filtered = data?.filter(
    (r) =>
      `${r.transaction.transaction_id} ${r.transaction.sender} ${r.transaction.receiver}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (verdict === "all" || r.assessment.verdict === verdict),
  );
  return (
    <>
      <PageHeading
        eyebrow="DECISIONS, WITH CONTEXT"
        title="Every assessment. A clear trail."
        action={
          <Link className="button primary" to="/evaluate">
            <Plus size={17} /> New evaluation
          </Link>
        }
      >
        Revisit the reasoning, inspect the evidence, and record your review.
      </PageHeading>
      <ErrorNotice message={error} retry={reload} />
      <section className="panel">
        <div className="library-toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search this page by ID or party…"
          />
          <select
            value={verdict}
            onChange={(e) => setVerdict(e.target.value)}
            aria-label="Filter assessments by verdict"
          >
            <option value="all">All assessments</option>
            {["flag", "needs_review", "acceptable"].map((v) => (
              <option key={v} value={v}>
                {verdictLabel(v)}
              </option>
            ))}
          </select>
        </div>
        {loading ? (
          <Loading />
        ) : filtered?.length ? (
          <DecisionTable records={filtered} />
        ) : (
          <Empty
            icon={FileCheck2}
            title={
              data?.length
                ? "No matching assessments"
                : "A clean slate for clear decisions."
            }
          >
            {data?.length
              ? "Try another search or verdict filter."
              : "Completed transaction assessments will appear here. Failed requests never create substitute results."}
          </Empty>
        )}
        <div className="pagination">
          <span>
            Page {offset / 50 + 1} · search and filters apply to this page
          </span>
          <div>
            <button
              className="button secondary"
              disabled={!offset || loading}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              Previous
            </button>
            <button
              className="button secondary"
              disabled={!data || data.length < 50 || loading}
              onClick={() => setOffset(offset + 50)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </>
  );
}

export function DecisionDetail() {
  const { id } = useParams();
  const { data, loading, error, reload } = useResource(`/decisions/${id}`);
  const [reviewError, setReviewError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  async function review(event) {
    event.preventDefault();
    setBusy(true);
    setReviewError("");
    setSaved(false);
    const form = event.currentTarget;
    try {
      await api(`/decisions/${id}/reviews`, {
        method: "POST",
        body: Object.fromEntries(new FormData(form)),
      });
      form.reset();
      setSaved(true);
      reload();
    } catch (e) {
      setReviewError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (loading) return <Loading />;
  if (error) return <ErrorNotice message={error} retry={reload} />;
  const { transaction: t, assessment: a, screening, exchange } = data;
  return (
    <>
      <Link className="text-link back-link" to="/decisions">
        <ArrowLeft size={15} /> Decision history
      </Link>
      <PageHeading
        eyebrow="ASSESSMENT DETAIL"
        title={t.transaction_id}
        action={
          <a
            className="button secondary"
            href={`/api/decisions/${id}/export`}
            download
          >
            <Download size={16} /> Export audit JSON
          </a>
        }
      >
        {formatDate(data.created_at)} · {data.model} ·{" "}
        {(data.processing_time_ms / 1000).toFixed(1)}s
      </PageHeading>
      <div className="decision-layout">
        <div>
          <section className="panel assessment-panel">
            <div className="assessment-top">
              <div>
                <span className="eyebrow">AI ADVISORY ASSESSMENT</span>
                <h2>{verdictLabel(a.verdict)}</h2>
                <Badge value={a.verdict} />
              </div>
              <div className={`risk-score ${a.verdict}`}>
                <strong>
                  {a.risk_score}
                  <small>/100</small>
                </strong>
                <span>Estimated risk</span>
              </div>
            </div>
            <p className="reasoning">{a.reasoning}</p>
            {a.risk_factors.length > 0 && (
              <>
                <h3>What needs your attention</h3>
                <ul className="factor-list">
                  {a.risk_factors.map((f, i) => (
                    <li key={i}>
                      <ShieldAlert size={16} />
                      {f}
                    </li>
                  ))}
                </ul>
              </>
            )}
            <div className="notice warning">
              <div>
                <strong>Coverage & limitations</strong>
                <ul>
                  {a.limitations.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ul>
              </div>
            </div>
          </section>
          <section className="panel detail-section">
            <div className="panel-heading">
              <div>
                <h2>Policy evidence</h2>
                <p>
                  Verified quotations from the policy versions used at
                  assessment time.
                </p>
              </div>
              <span className="count-pill">{a.citations.length}</span>
            </div>
            <div className="section-padding">
              <Evidence citations={a.citations} />
            </div>
          </section>
          <section className="panel detail-section">
            <div className="panel-heading">
              <div>
                <h2>Sanctions screening</h2>
                <p>
                  Official OFAC SDN snapshot ·{" "}
                  {screening.source.count.toLocaleString()} entries
                </p>
              </div>
              <Badge
                value={screening.matches.length ? "needs_review" : "neutral"}
              >
                {screening.matches.length
                  ? `${screening.matches.length} potential matches`
                  : "No name matches"}
              </Badge>
            </div>
            <div className="section-padding">
              <p>{screening.scope}</p>
              {screening.matches.map((m, i) => (
                <div className="sanction-match" key={i}>
                  <strong>{m.name}</strong>
                  <p>
                    {m.party}: {m.input_name} · Matched name: {m.matched_name}
                  </p>
                  <small>
                    {(m.similarity * 100).toFixed(1)}% name similarity · OFAC ID{" "}
                    {m.entity_id} · {m.programs.join(", ")}
                  </small>
                </div>
              ))}
              <dl className="metadata">
                <div>
                  <dt>Fetched</dt>
                  <dd>{formatDate(screening.source.fetched_at)}</dd>
                </div>
                <div>
                  <dt>Published</dt>
                  <dd>
                    {screening.source.published_at || "Not supplied by source"}
                  </dd>
                </div>
              </dl>
              <details>
                <summary>Snapshot provenance</summary>
                <p className="mono hash-note">
                  SHA-256: {screening.source.sha256}
                </p>
                <a href={screening.source.url} target="_blank" rel="noreferrer">
                  Official feed ↗
                </a>
              </details>
            </div>
          </section>
          <section className="panel detail-section">
            <div className="panel-heading">
              <div>
                <h2>Human review</h2>
                <p>
                  Reviews are appended. The original AI assessment stays intact.
                </p>
              </div>
              <CheckCheck size={21} />
            </div>
            <div className="section-padding">
              {data.reviews.length > 0 && (
                <div className="reviews">
                  {data.reviews.map((r) => (
                    <article key={r.id}>
                      <div>
                        <strong>{r.reviewer}</strong>
                        <Badge value={r.verdict} />
                      </div>
                      <p>{r.notes}</p>
                      <small>{formatDate(r.created_at)}</small>
                    </article>
                  ))}
                </div>
              )}
              {saved && <Success>Review recorded.</Success>}
              <form onSubmit={review} className="review-form">
                <div className="form-grid">
                  <Field label="Reviewer name">
                    <input
                      name="reviewer"
                      minLength={2}
                      maxLength={100}
                      required
                      placeholder="Your name"
                    />
                  </Field>
                  <Field label="Your assessment">
                    <select name="verdict" defaultValue="needs_review">
                      {["needs_review", "flag", "acceptable"].map((v) => (
                        <option value={v} key={v}>
                          {verdictLabel(v)}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Review notes" wide>
                    <textarea
                      name="notes"
                      minLength={10}
                      maxLength={3000}
                      rows={3}
                      required
                      placeholder="Record the evidence checked and why you reached this conclusion…"
                    />
                  </Field>
                </div>
                <ErrorNotice message={reviewError} />
                <Submit busy={busy}>Record review</Submit>
              </form>
            </div>
          </section>
        </div>
        <aside>
          <section className="panel transaction-summary">
            <h2>Transaction at a glance</h2>
            <div className="summary-amount">{money(t.amount, t.currency)}</div>
            <dl className="metadata">
              {[
                ["Sender", t.sender],
                ["Origin", t.sender_country],
                ["Receiver", t.receiver],
                ["Destination", t.receiver_country],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
            <h3>Purpose & context</h3>
            <p>{t.description}</p>
            <div className="aside-rule" />
            <h3>USD reference</h3>
            <div className="usd-value">{money(exchange.amount_usd, "USD")}</div>
            <p className="muted">
              1 {exchange.base} = {exchange.rate} USD
              <br />
              Reference date: {exchange.date}
            </p>
            <small>
              {exchange.source === "identity"
                ? "USD identity conversion; no exchange-rate API required."
                : "Frankfurter daily reference rate. Not an execution price."}
            </small>
          </section>
          <div className="aside-caption">
            Risk scores are estimates, not calibrated probabilities. Review
            source evidence before acting.
          </div>
        </aside>
      </div>
    </>
  );
}
