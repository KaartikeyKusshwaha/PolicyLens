import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Link } from "../navigation";
import { Activity, ArrowUpRight, Download, Plus, Upload } from "lucide-react";
import { api } from "../services/api";
import {
  Empty,
  ErrorNotice,
  Field,
  formatDate,
  Loading,
  money,
  PageHeading,
  SearchBox,
  Submit,
  Success,
  useResource,
} from "../components";
import {
  CountryInput,
  CountryOptions,
  currencies,
  Status,
} from "../product-components";
import { useSession } from "../session";

export default function Monitoring() {
  const [params] = useSearchParams();
  const r = useResource("/monitor/transactions");
  const customers = useResource("/customers");
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState(params.get("mode") === "csv" ? "csv" : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [importResult, setImportResult] = useState(null);
  const { user } = useSession();
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const data = Object.fromEntries(new FormData(e.currentTarget));
      if (!data.occurred_at) delete data.occurred_at;
      else data.occurred_at = new Date(data.occurred_at).toISOString();
      const result = await api("/monitor/transactions", {
        method: "POST",
        body: data,
      });
      setSuccess(
        result.duplicate
          ? "This transaction is already recorded."
          : `Transaction received. ${result.alerts.length} control alerts created.`,
      );
      r.reload();
      if (!result.duplicate) setMode("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function importCsv(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setImportResult(null);
    try {
      const result = await api("/monitor/import", {
        method: "POST",
        body: new FormData(e.currentTarget),
      });
      setImportResult(result);
      r.reload();
    } catch (e) {
      setError(
        e.message +
          (e.details?.rows
            ? " Rows: " + e.details.rows.map((v) => v.row).join(", ")
            : ""),
      );
    } finally {
      setBusy(false);
    }
  }
  const filtered = r.data?.filter((t) =>
    `${t.external_id} ${t.counterparty} ${t.counterparty_country}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <CountryOptions />
      <PageHeading
        eyebrow="CONTINUOUS CONTROL MONITORING"
        title="Every transaction adds context."
        action={
          user.role !== "auditor" && (
            <div className="button-row">
              <button
                className="button secondary"
                onClick={() => setMode(mode === "csv" ? "" : "csv")}
              >
                <Upload size={15} /> Import CSV
              </button>
              <button
                className="button primary"
                onClick={() => setMode(mode === "single" ? "" : "single")}
              >
                <Plus size={16} /> Add transaction
              </button>
            </div>
          )
        }
      >
        Approved internal controls evaluate incoming activity. Related alerts
        join a customer investigation.
      </PageHeading>
      <ErrorNotice message={error || r.error} />
      {success && <Success>{success}</Success>}
      {mode === "single" && (
        <form className="panel form-panel monitoring-form" onSubmit={submit}>
          <div className="panel-title-row">
            <h2>Record a transaction</h2>
            <button
              type="button"
              className="text-button"
              onClick={() => setMode("")}
            >
              Close
            </button>
          </div>
          <div className="form-grid">
            <Field label="Customer">
              <select name="customer_id" required defaultValue="">
                <option value="" disabled>
                  Select a customer
                </option>
                {customers.data?.map((c) => (
                  <option value={c.id} key={c.id}>
                    {c.name} · {c.external_id}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Transaction reference">
              <input
                name="external_id"
                required
                maxLength={100}
                placeholder="Unique reference from your system"
              />
            </Field>
            <Field label="Amount">
              <input
                name="amount"
                type="number"
                min="0.01"
                step="0.01"
                required
              />
            </Field>
            <Field label="Currency">
              <select name="currency">
                {currencies.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
            <Field label="Counterparty name">
              <input
                name="counterparty"
                required
                minLength={3}
                maxLength={180}
              />
            </Field>
            <Field label="Counterparty country">
              <CountryInput name="counterparty_country" />
            </Field>
            <Field label="Account reference (optional)">
              <input name="account_reference" maxLength={100} />
            </Field>
            <Field
              label="Transaction time (optional)"
              hint="Your local time; converted to UTC. Blank means now."
            >
              <input name="occurred_at" type="datetime-local" />
            </Field>
            <Field label="Purpose and context" wide>
              <textarea
                name="description"
                required
                minLength={5}
                maxLength={2000}
                rows={3}
              />
            </Field>
          </div>
          <div className="form-actions">
            <Link className="text-link" to="/rules">
              Review active controls <ArrowUpRight size={14} />
            </Link>
            <Submit busy={busy}>Record & monitor</Submit>
          </div>
        </form>
      )}
      {mode === "csv" && (
        <form className="panel form-panel monitoring-form" onSubmit={importCsv}>
          <div className="panel-title-row">
            <h2>Import a transaction batch</h2>
            <a className="text-link" href="/api/monitor/template" download>
              <Download size={15} /> CSV template
            </a>
          </div>
          <p className="section-copy">
            Use customer IDs from your customer profiles, ISO country codes, and
            timezone-aware timestamps. Up to 500 rows / 1 MB. Invalid fields are
            checked before ingestion; any later conflicts are reported per row.
          </p>
          <Field label="CSV file">
            <input name="file" type="file" accept=".csv,text/csv" required />
          </Field>
          <div className="form-actions">
            <span className="muted">
              Existing references are checked for identical details.
            </span>
            <Submit busy={busy}>Import & monitor</Submit>
          </div>
          {importResult && (
            <div className="notice success">
              <div>
                <strong>
                  {importResult.imported} imported · {importResult.duplicates}{" "}
                  duplicates · {importResult.errors.length} errors
                </strong>
                {importResult.errors.map((e) => (
                  <p key={e.row}>
                    Row {e.row}: {e.message}
                  </p>
                ))}
              </div>
            </div>
          )}
        </form>
      )}
      <section className="panel">
        <div className="library-toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search transaction references or counterparties…"
          />
          <Link className="text-link" to="/settings">
            Connect signed ingestion <ArrowUpRight size={14} />
          </Link>
        </div>
        {r.loading ? (
          <Loading />
        ) : filtered?.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Customer</th>
                  <th>Counterparty</th>
                  <th>Amount</th>
                  <th>Occurred</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((t) => (
                  <tr key={t.id}>
                    <td className="mono">{t.external_id}</td>
                    <td>
                      <Link to={"/customers/" + t.customer_id}>
                        {customers.data?.find((c) => c.id === t.customer_id)
                          ?.name || t.customer_id}
                      </Link>
                    </td>
                    <td>
                      {t.counterparty}
                      <small>{t.counterparty_country}</small>
                    </td>
                    <td className="numeric">{money(t.amount, t.currency)}</td>
                    <td className="muted nowrap">
                      {formatDate(t.occurred_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty icon={Activity} title="Your transaction stream starts here.">
            Add activity manually, import a CSV, or connect a signed webhook.
            Monitoring controls run without requiring an AI call.
          </Empty>
        )}
      </section>
      <div className="subtle-note">
        <p>
          Showing up to 200 recent transactions. No transfers are executed.{" "}
          <Link to="/evaluate">Open an individual AI assessment</Link> or{" "}
          <Link to="/decisions">view past assessments</Link>.
        </p>
      </div>
    </>
  );
}
