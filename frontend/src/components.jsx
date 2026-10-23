import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  Check,
  CircleAlert,
  FileText,
  LoaderCircle,
  Search,
} from "lucide-react";
import { Link } from "./navigation";
import { api } from "./services/api";

export function useResource(path) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!path) {
      setData(null);
      setError("");
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError("");
    api(path, { signal: controller.signal })
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [path, revision]);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  return {
    data,
    error,
    loading,
    reload,
  };
}

export const formatDate = (value) =>
  value
    ? new Date(value).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : "Not yet synced";
export const money = (amount, currency) =>
  new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(amount));
export const verdictLabel = (value) =>
  ({ flag: "Flagged", needs_review: "Needs review", acceptable: "Advisory: no flag" })[
    value
  ] || value;

export function Badge({ value, children }) {
  return (
    <span className={`badge ${value || ""}`}>
      <i />
      {children || verdictLabel(value)}
    </span>
  );
}
export function ErrorNotice({ message, retry }) {
  if (!message) return null;
  return (
    <div className="notice error" role="alert">
      <CircleAlert size={18} />
      <div>{message}</div>
      {retry && (
        <button className="text-button" onClick={retry}>
          Retry
        </button>
      )}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={22} /> Loading workspace…
    </div>
  );
}
export function Empty({ icon: Icon = FileText, title, children, action }) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <Icon size={25} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function PageHeading({ eyebrow, title, children, action }) {
  return (
    <header className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{children}</p>
      </div>
      {action}
    </header>
  );
}
export function Submit({ busy, children, ...props }) {
  return (
    <button className="button primary" disabled={busy} {...props}>
      {busy ? <LoaderCircle size={16} className="spin" /> : null}
      {busy ? "Working…" : children}
    </button>
  );
}
export function Field({ label, hint, children, wide }) {
  return (
    <label className={`field ${wide ? "wide" : ""}`}>
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function Evidence({ citations }) {
  return (
    <div className="evidence-list">
      {citations.map((c, i) => (
        <article className="evidence" key={`${c.chunk_id}-${i}`}>
          <div className="evidence-title">
            <span className="citation-number">{i + 1}</span>
            <strong>{c.title}</strong>
            <span className="muted">v{c.version}</span>
          </div>
          <blockquote>{c.quote}</blockquote>
          {c.source_url && (
            <a href={c.source_url} target="_blank" rel="noreferrer">
              View original source ↗
            </a>
          )}
        </article>
      ))}
    </div>
  );
}
export function DecisionTable({ records, compact = false }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Transaction</th>
            <th>Counterparty</th>
            <th>Amount</th>
            <th>Assessment</th>
            {!compact && <th>Created</th>}
            <th>
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id}>
              <td>
                <Link className="table-link" to={`/decisions/${r.id}`}>
                  {r.transaction.transaction_id}
                </Link>
                <small>
                  {r.transaction.sender_country} →{" "}
                  {r.transaction.receiver_country}
                </small>
              </td>
              <td>
                {r.transaction.receiver}
                <small>From {r.transaction.sender}</small>
              </td>
              <td className="numeric">
                {money(r.transaction.amount, r.transaction.currency)}
              </td>
              <td>
                <Badge value={r.assessment.verdict} />
              </td>
              {!compact && (
                <td className="muted nowrap">{formatDate(r.created_at)}</td>
              )}
              <td>
                <Link
                  className="icon-button"
                  aria-label={`Open ${r.transaction.transaction_id}`}
                  to={`/decisions/${r.id}`}
                >
                  <ArrowRight size={16} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function SearchBox({ value, onChange, placeholder = "Search…" }) {
  return (
    <div className="search-box">
      <Search size={17} />
      <input
        aria-label={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}
export function Success({ children }) {
  return (
    <div className="notice success" role="status">
      <Check size={18} />
      {children}
    </div>
  );
}
