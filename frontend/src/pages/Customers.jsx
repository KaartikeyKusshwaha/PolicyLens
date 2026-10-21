import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowUpRight,
  Building2,
  Globe2,
  Plus,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";
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
  useResource,
} from "../components";
import {
  AgentButton,
  CountryInput,
  CountryOptions,
  DefinitionList,
  Status,
} from "../product-components";
import { useSession } from "../session";

export function Customers() {
  const resource = useResource("/customers");
  const [search, setSearch] = useState("");
  const { user } = useSession();
  const filtered = resource.data?.filter((c) =>
    `${c.name} ${c.external_id} ${c.country}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeading
        eyebrow="KNOW THE CONTEXT"
        title="Customers, connected to their activity."
        action={
          user.role !== "auditor" && (
            <Link className="button primary" to="/customers/new">
              <Plus size={16} /> Add customer
            </Link>
          )
        }
      >
        A shared profile for the facts, records, and investigations behind each
        relationship.
      </PageHeading>
      <ErrorNotice message={resource.error} retry={resource.reload} />
      <section className="panel">
        <div className="library-toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search names, references, or countries…"
          />
          <span className="muted">{resource.data?.length || 0} profiles</span>
        </div>
        {resource.loading ? (
          <Loading />
        ) : filtered?.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Customer</th>
                  <th>Reference</th>
                  <th>Country</th>
                  <th>Due diligence</th>
                  <th>Internal risk tier</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link
                        className="table-link entity-name"
                        to={"/customers/" + c.id}
                      >
                        <span className="entity-avatar">
                          {c.kind === "company" ? (
                            <Building2 size={16} />
                          ) : (
                            <Users size={16} />
                          )}
                        </span>
                        {c.name}
                      </Link>
                    </td>
                    <td className="mono">{c.external_id}</td>
                    <td>{c.country}</td>
                    <td>
                      <Status value={c.kyc_status} />
                    </td>
                    <td>
                      <Status value={c.risk_tier} />
                    </td>
                    <td>
                      <Link
                        className="icon-button"
                        to={"/customers/" + c.id}
                        aria-label={"Open " + c.name}
                      >
                        <ArrowUpRight size={17} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            icon={Users}
            title="Start with the people behind the payments."
          >
            Add a customer or company to connect transactions, sanctions
            screening, and investigations.
          </Empty>
        )}
      </section>
    </>
  );
}

export function CustomerEditor() {
  const { id } = useParams();
  const resource = useResource(id ? "/customers/" + id : "/customers");
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = Object.fromEntries(new FormData(e.currentTarget));
      const c = await api(id ? "/customers/" + id : "/customers", {
        method: id ? "PUT" : "POST",
        body: data,
      });
      navigate("/customers/" + c.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (id && resource.loading) return <Loading />;
  if (id && resource.error) return <ErrorNotice message={resource.error} />;
  const c = id ? resource.data : null;
  return (
    <>
      <CountryOptions />
      <PageHeading
        eyebrow="CUSTOMER RECORD"
        title={
          id
            ? "Keep the customer context current."
            : "Build a clearer customer picture."
        }
      >
        Record what your team knows. A manually recorded due diligence status is
        not automated identity verification.
      </PageHeading>
      <form className="panel form-panel editor-panel" onSubmit={submit}>
        <div className="form-grid">
          <Field label="Legal or full name" wide>
            <input
              name="name"
              required
              minLength={3}
              maxLength={180}
              defaultValue={c?.name}
            />
          </Field>
          <Field label="Customer reference">
            <input
              name="external_id"
              required
              maxLength={100}
              defaultValue={c?.external_id}
              placeholder="Your internal identifier"
            />
          </Field>
          <Field label="Entity type">
            <select name="kind" defaultValue={c?.kind || "individual"}>
              <option value="individual">Individual</option>
              <option value="company">Company</option>
            </select>
          </Field>
          <Field label="Country (ISO code)">
            <CountryInput name="country" defaultValue={c?.country} />
          </Field>
          <Field label="Internal risk tier">
            <select name="risk_tier" defaultValue={c?.risk_tier || "medium"}>
              {["low", "medium", "high"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>
          <Field label="Due diligence status">
            <select name="kyc_status" defaultValue={c?.kyc_status || "pending"}>
              {["pending", "verified", "expired"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>
          <Field
            label="LEI (optional)"
            hint="Company reference lookup; 20 characters."
          >
            <input
              name="lei"
              defaultValue={c?.lei}
              maxLength={20}
              pattern="[A-Z0-9]{18}[0-9]{2}|"
            />
          </Field>
          <Field label="Address (optional)" wide>
            <input name="address" defaultValue={c?.address} maxLength={500} />
          </Field>
          <Field label="Evidence and review notes" wide>
            <textarea
              name="notes"
              defaultValue={c?.notes}
              rows={4}
              maxLength={3000}
              placeholder="Describe your evidence and its limitations…"
            />
          </Field>
        </div>
        <ErrorNotice message={error} />
        <div className="form-actions">
          <Link className="text-link" to="/customers">
            <ArrowLeft size={15} /> Customer directory
          </Link>
          <Submit busy={busy}>Save profile</Submit>
        </div>
      </form>
    </>
  );
}

function RelationshipGraph({ id }) {
  const { data, error, loading } = useResource("/customers/" + id + "/graph");
  if (loading) return <Loading />;
  if (error) return <ErrorNotice message={error} />;
  const others = data.nodes.filter((n) => n.id !== id).slice(0, 18);
  const positions = { [id]: { x: 340, y: 220 } };
  others.forEach((n, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, others.length);
    positions[n.id] = {
      x: 340 + 260 * Math.cos(angle),
      y: 220 + 160 * Math.sin(angle),
    };
  });
  return (
    <>
      <div className="entity-graph">
        <svg
          viewBox="0 0 680 440"
          role="img"
          aria-label="Observed customer transaction relationships"
        >
          {data.links
            .filter((l) => positions[l.source] && positions[l.target])
            .map((l, i) => (
              <line
                key={i}
                x1={positions[l.source].x}
                y1={positions[l.source].y}
                x2={positions[l.target].x}
                y2={positions[l.target].y}
                stroke="var(--graph-line)"
                strokeWidth="1.5"
              >
                <title>{l.label}</title>
              </line>
            ))}
          {data.nodes
            .filter((n) => positions[n.id])
            .map((n) => (
              <g
                key={n.id}
                transform={`translate(${positions[n.id].x},${positions[n.id].y})`}
              >
                <circle
                  r={n.id === id ? 32 : 22}
                  fill={n.id === id ? "#285f46" : "var(--soft)"}
                  stroke="var(--graph-line)"
                />
                <text
                  y="5"
                  textAnchor="middle"
                  fill={n.id === id ? "white" : "var(--text)"}
                  fontSize="11"
                >
                  {n.kind === "account_reference"
                    ? "#"
                    : n.name
                        .split(" ")
                        .map((v) => v[0])
                        .slice(0, 2)
                        .join("")}
                </text>
                <text
                  y={n.id === id ? 51 : 40}
                  textAnchor="middle"
                  fill="var(--muted)"
                  fontSize="9"
                >
                  {n.name.length > 24 ? n.name.slice(0, 23) + "…" : n.name}
                </text>
                <title>{n.name}</title>
              </g>
            ))}
        </svg>
      </div>
      <p className="subtle-note">
        {data.scope} Showing up to 18 connected nodes.
      </p>
    </>
  );
}

export function CustomerDetail() {
  const { id } = useParams();
  const r = useResource("/customers/" + id);
  const [tab, setTab] = useState("Overview");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { user } = useSession();
  async function action(path) {
    setBusy(true);
    setError("");
    try {
      await api("/customers/" + id + path, { method: "POST" });
      r.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (r.loading) return <Loading />;
  if (r.error) return <ErrorNotice message={r.error} retry={r.reload} />;
  const c = r.data;
  const latest = c.screenings[0];
  return (
    <>
      <Link className="text-link back-link" to="/customers">
        <ArrowLeft size={14} /> Customers
      </Link>
      <PageHeading
        eyebrow={c.kind.toUpperCase() + " · " + c.external_id}
        title={c.name}
        action={
          user.role !== "auditor" && (
            <Link
              className="button secondary"
              to={"/customers/" + id + "/edit"}
            >
              Edit profile
            </Link>
          )
        }
      >
        {c.country} · Added {formatDate(c.created_at)}
      </PageHeading>
      <div className="entity-summary">
        <Status value={c.kyc_status} />
        <Status value={c.risk_tier} />
        <span>{c.transactions.length} recent transactions</span>
        <span>{c.cases.length} investigations</span>
      </div>
      <div className="page-tabs">
        {["Overview", "Activity", "Relationships"].map((t) => (
          <button
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      <ErrorNotice message={error} />
      {tab === "Relationships" ? (
        <section className="panel section-padding">
          <h2>Observed relationships</h2>
          <RelationshipGraph id={id} />
        </section>
      ) : tab === "Activity" ? (
        <section className="panel">
          <div className="panel-heading">
            <h2>Recent customer transactions</h2>
          </div>
          {c.transactions.length ? (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Counterparty</th>
                    <th>Amount</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {c.transactions.map((t) => (
                    <tr key={t.id}>
                      <td>{t.external_id}</td>
                      <td>
                        {t.counterparty}
                        <small>{t.counterparty_country}</small>
                      </td>
                      <td>{money(t.amount, t.currency)}</td>
                      <td>{formatDate(t.occurred_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty title="No transactions yet">
              Add transactions in the monitoring workspace.
            </Empty>
          )}
        </section>
      ) : (
        <div className="customer-detail-grid">
          <div>
            <section className="panel section-padding">
              <h2>Customer context</h2>
              <DefinitionList
                items={[
                  ["Reference", c.external_id],
                  ["Country", c.country],
                  ["Address", c.address],
                  ["LEI", c.lei],
                ]}
              />
              <h3>Team notes</h3>
              <p className="preserve-lines">
                {c.notes || "No notes recorded."}
              </p>
            </section>
            <section className="panel detail-section">
              <div className="panel-heading">
                <h2>Investigations</h2>
                <Link className="text-link" to={"/cases?customer=" + id}>
                  Open a case <Plus size={14} />
                </Link>
              </div>
              {c.cases.length ? (
                <div className="compact-records">
                  {c.cases.map((k) => (
                    <Link to={"/cases/" + k.id} key={k.id}>
                      <div>
                        <strong>{k.title}</strong>
                        <small>{formatDate(k.updated_at)}</small>
                      </div>
                      <Status value={k.status} />
                    </Link>
                  ))}
                </div>
              ) : (
                <Empty title="No investigations recorded">
                  Customer activity and screening findings can be grouped into a
                  case.
                </Empty>
              )}
            </section>
          </div>
          <aside>
            <section className="panel section-padding">
              <div className="section-heading">
                <ShieldCheck size={23} />
                <h2>Sanctions evidence</h2>
              </div>
              {latest ? (
                <>
                  <Status
                    value={
                      latest.screening.matches.length
                        ? "needs_review"
                        : "completed"
                    }
                  />
                  <p className="section-copy">
                    {latest.screening.matches.length} potential name matches ·{" "}
                    {formatDate(latest.created_at)}
                  </p>
                  <p className="privacy-note">{latest.screening.scope}</p>
                  {latest.screening.matches.slice(0, 8).map((m, i) => (
                    <div className="sanction-match" key={i}>
                      <strong>{m.name}</strong>
                      <p>
                        {m.source_id.toUpperCase()} · ID {m.entity_id} ·{" "}
                        {(m.similarity * 100).toFixed(1)}% name similarity
                      </p>
                    </div>
                  ))}
                </>
              ) : (
                <p className="section-copy">
                  Screening has not been run for this customer.
                </p>
              )}
              {user.role !== "auditor" && (
                <>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => action("/screen")}
                  >
                    <RefreshCw size={15} /> Screen now
                  </button>
                  <div className="aside-rule" />
                  <AgentButton kind="screening" targetId={id}>
                    Research with an agent
                  </AgentButton>
                </>
              )}
            </section>
            {c.lei && (
              <section className="panel section-padding detail-section">
                <h2>Company reference data</h2>
                {c.company_intelligence[0] ? (
                  <>
                    <DefinitionList
                      items={[
                        [
                          "GLEIF legal name",
                          c.company_intelligence[0].data.legal_name,
                        ],
                        [
                          "Entity status",
                          c.company_intelligence[0].data.status,
                        ],
                        [
                          "Retrieved",
                          formatDate(c.company_intelligence[0].data.fetched_at),
                        ],
                      ]}
                    />
                    <p className="privacy-note">
                      {c.company_intelligence[0].data.scope}
                    </p>
                  </>
                ) : (
                  <p className="section-copy">
                    Look up this LEI in GLEIF’s public legal-entity database.
                  </p>
                )}
                {user.role !== "auditor" && (
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => action("/company-intelligence")}
                  >
                    <Building2 size={15} /> Fetch GLEIF record
                  </button>
                )}
              </section>
            )}
          </aside>
        </div>
      )}
    </>
  );
}
