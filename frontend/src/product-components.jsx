import { useEffect, useState } from "react";
import { useNavigate } from "./navigation";
import { Bot, CircleAlert, LoaderCircle } from "lucide-react";
import { api } from "./services/api";
import { ErrorNotice, useResource } from "./components";

export const countryNames = {
  US: "United States",
  GB: "United Kingdom",
  IN: "India",
  AE: "United Arab Emirates",
  SG: "Singapore",
  CA: "Canada",
  AU: "Australia",
  DE: "Germany",
  FR: "France",
  NL: "Netherlands",
  CH: "Switzerland",
  JP: "Japan",
  HK: "Hong Kong",
  ZA: "South Africa",
  NG: "Nigeria",
  KE: "Kenya",
  BR: "Brazil",
  MX: "Mexico",
  CN: "China",
  SA: "Saudi Arabia",
  QA: "Qatar",
  PK: "Pakistan",
  BD: "Bangladesh",
  LK: "Sri Lanka",
  NZ: "New Zealand",
  IE: "Ireland",
  ES: "Spain",
  IT: "Italy",
  SE: "Sweden",
  NO: "Norway",
};
export const currencies = [
  "USD",
  "EUR",
  "GBP",
  "INR",
  "AED",
  "SGD",
  "CAD",
  "AUD",
  "JPY",
  "CHF",
  "ZAR",
  "NGN",
  "KES",
  "BRL",
  "MXN",
  "CNY",
  "HKD",
  "SAR",
];
export const label = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
export function Status({ value }) {
  return (
    <span className={`product-status ${value}`}>
      <i />
      {label(value)}
    </span>
  );
}
export function CountryOptions() {
  return (
    <datalist id="country-options">
      {Object.entries(countryNames).map(([code, name]) => (
        <option value={code} key={code}>
          {name}
        </option>
      ))}
    </datalist>
  );
}
export function CountryInput(props) {
  return (
    <input
      {...props}
      list="country-options"
      pattern="[A-Z]{2}"
      maxLength={2}
      minLength={2}
      placeholder="e.g. GB"
      required
      onInput={(e) => {
        e.currentTarget.value = e.currentTarget.value.toUpperCase();
      }}
    />
  );
}
export function useLiveResource(
  path,
  predicate = (value) =>
    Array.isArray(value) &&
    value.some((v) => ["queued", "running"].includes(v.state)),
) {
  const resource = useResource(path);
  const active = resource.data && predicate(resource.data);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(resource.reload, 2500);
    return () => clearInterval(timer);
  }, [active, resource.reload]);
  return resource;
}
export function AgentButton({ kind, targetId, children }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  async function run() {
    setBusy(true);
    setError("");
    try {
      const job = await api("/agents/jobs", {
        method: "POST",
        body: { kind, target_id: targetId },
      });
      navigate("/agents/" + job.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="agent-action">
      <button className="button primary" disabled={busy} onClick={run}>
        {busy ? <LoaderCircle size={15} className="spin" /> : <Bot size={16} />}{" "}
        {children || "Start agent"}
      </button>
      <ErrorNotice message={error} />
    </div>
  );
}
export function Metric({ label: title, value, icon: Icon, detail }) {
  return (
    <div className="product-metric">
      <div>
        <span>{title}</span>
        {Icon && <Icon size={18} />}
      </div>
      <strong>{value ?? "—"}</strong>
      <small>{detail}</small>
    </div>
  );
}
export function ActionNotice({ error, children }) {
  return (
    <>
      {error && <ErrorNotice message={error} />} {children}
    </>
  );
}
export function DefinitionList({ items }) {
  return (
    <dl className="metadata">
      {items.map(([name, value]) => (
        <div key={name}>
          <dt>{name}</dt>
          <dd>{value || "Not supplied"}</dd>
        </div>
      ))}
    </dl>
  );
}
