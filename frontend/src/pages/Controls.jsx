import { useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowLeft,
  ArrowUpRight,
  FlaskConical,
  Plus,
  SlidersHorizontal,
} from "lucide-react";
import { api } from "../services/api";
import {
  Empty,
  ErrorNotice,
  Field,
  Loading,
  PageHeading,
  SearchBox,
  Submit,
  useResource,
} from "../components";
import {
  currencies,
  DefinitionList,
  label,
  Status,
} from "../product-components";
import { useSession } from "../session";

const kinds = {
  amount: "Single transaction amount",
  velocity: "Transaction count in a window",
  aggregate: "Same-currency total in a window",
  corridor: "Cross-border destination",
  kyc: "Due diligence not verified",
};

export function Controls() {
  const r = useResource("/rules");
  const [search, setSearch] = useState("");
  const { user } = useSession();
  const filtered = r.data?.filter((c) =>
    `${c.title} ${c.kind} ${c.status}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageHeading
        eyebrow="YOUR POLICY, IN OPERATION"
        title="Controls your team can explain."
        action={
          ["admin", "analyst"].includes(user.role) && (
            <Link className="button primary" to="/rules/new">
              <Plus size={16} /> Draft control
            </Link>
          )
        }
      >
        Configure explicit conditions, test historical impact, and approve each
        version before it runs.
      </PageHeading>
      <p><Link className="button secondary" to="/rules/code">Controls as code: export or import YAML</Link></p>
      <div className="notice neutral">
        <SlidersHorizontal size={18} />
        <div>
          These are your internal controls. No regulatory thresholds are
          preconfigured or inferred. Drafts require an independent reviewer
          before activation.
        </div>
      </div>
      <ErrorNotice message={r.error} />
      <section className="panel">
        <div className="library-toolbar">
          <SearchBox
            value={search}
            onChange={setSearch}
            placeholder="Search controls, types, or states…"
          />
          <span className="muted">
            {r.data?.filter((c) => c.status === "active").length || 0} active
          </span>
        </div>
        {r.loading ? (
          <Loading />
        ) : filtered?.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Control</th>
                  <th>Condition</th>
                  <th>Policy</th>
                  <th>Version</th>
                  <th>State</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link className="table-link" to={"/rules/" + c.id}>
                        {c.title}
                      </Link>
                    </td>
                    <td>{kinds[c.kind]}</td>
                    <td>
                      {c.policy_title}
                      <small>Policy v{c.policy_version}</small>
                    </td>
                    <td>{c.version}</td>
                    <td>
                      <Status value={c.status} />
                    </td>
                    <td>
                      <Link className="icon-button" to={"/rules/" + c.id}>
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
            icon={SlidersHorizontal}
            title="Turn your policy into a monitored control."
          >
            Start with a documented requirement, define its conditions, and test
            it before a second person approves it.
          </Empty>
        )}
      </section>
    </>
  );
}

export function ControlEditor() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const resource = useResource(id ? "/rules/" + id : "/rules");
  const policies = useResource("/policies");
  const [chosenKind, setKind] = useState(null);
  const kind = chosenKind || (id && resource.data?.kind) || "amount";
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(e.currentTarget));
    data.kind = kind;
    data.window_hours = Number(data.window_hours || 24);
    data.countries = (data.countries || "")
      .split(",")
      .map((v) => v.trim().toUpperCase())
      .filter(Boolean);
    if (!data.threshold) data.threshold = "10000";
    if (!data.currency) data.currency = "USD";
    try {
      const rule = await api(id ? "/rules/" + id : "/rules", {
        method: id ? "PUT" : "POST",
        body: data,
      });
      navigate("/rules/" + rule.id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (id && resource.loading) return <Loading />;
  if (resource.error) return <ErrorNotice message={resource.error} />;
  const rule = id ? resource.data : null;
  return (
    <>
      <PageHeading
        eyebrow="CONTROL WORKBENCH"
        title={
          id
            ? "Propose the next control version."
            : "Make a policy requirement explicit."
        }
      >
        A new draft does not replace an active version until a second person
        approves it.
      </PageHeading>
      <form className="panel form-panel editor-panel" onSubmit={submit}>
        <div className="form-grid">
          <Field label="Control title" wide>
            <input
              name="title"
              minLength={3}
              maxLength={160}
              required
              defaultValue={rule?.title}
            />
          </Field>
          <Field label="Linked policy">
            <select
              name="policy_id"
              required
              defaultValue={rule?.policy_id || params.get("policy") || ""}
            >
              <option value="" disabled>
                Choose the source policy
              </option>
              {policies.data?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title} · v{p.version}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Control type">
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {Object.entries(kinds).map(([v, name]) => (
                <option key={v} value={v}>
                  {name}
                </option>
              ))}
            </select>
          </Field>
          {["amount", "velocity", "aggregate"].includes(kind) && (
            <Field
              label={
                kind === "velocity"
                  ? "Minimum transaction count"
                  : "Amount threshold"
              }
            >
              <input
                name="threshold"
                type="number"
                min="1"
                step={kind === "velocity" ? "1" : ".01"}
                defaultValue={rule?.threshold}
                required
                placeholder="Set your internal threshold"
              />
            </Field>
          )}
          {["amount", "aggregate"].includes(kind) && (
            <Field label="Currency">
              <select name="currency" defaultValue={rule?.currency || "USD"}>
                {currencies.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
          )}
          {["velocity", "aggregate"].includes(kind) && (
            <Field label="Window (hours)">
              <input
                type="number"
                min="1"
                max="720"
                name="window_hours"
                defaultValue={rule?.window_hours || 24}
                required
              />
            </Field>
          )}
          {kind === "corridor" && (
            <Field
              label="Destination country codes"
              hint="Comma-separated ISO codes, e.g. GB, AE. This is an internal list, not a sanctions designation."
              wide
            >
              <input
                name="countries"
                defaultValue={rule?.countries.join(", ")}
                required
                maxLength={200}
              />
            </Field>
          )}
          <Field label="Alert priority">
            <select name="priority" defaultValue={rule?.priority || "medium"}>
              {["low", "medium", "high", "critical"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </Field>
          <Field
            label="Requirement and rationale"
            wide
            hint="Explain the policy requirement, interpretation, and any limitations."
          >
            <textarea
              name="description"
              minLength={10}
              maxLength={2000}
              rows={5}
              required
              defaultValue={rule?.description}
            />
          </Field>
        </div>
        <ErrorNotice message={error} />
        <div className="form-actions">
          <Link className="text-link" to="/rules">
            <ArrowLeft size={15} /> Control library
          </Link>
          <Submit busy={busy}>Save draft for review</Submit>
        </div>
      </form>
    </>
  );
}

export function ControlDetail() {
  const { id } = useParams();
  const r = useResource("/rules/" + id);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [test, setTest] = useState(null);
  const { user } = useSession();
  async function backtest() {
    setBusy(true);
    setError("");
    try {
      setTest(await api("/rules/" + id + "/backtest", { method: "POST" }));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function action(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/rules/" + id + "/actions", {
        method: "POST",
        body: Object.fromEntries(new FormData(e.currentTarget)),
      });
      r.reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (r.loading) return <Loading />;
  if (r.error) return <ErrorNotice message={r.error} />;
  const c = r.data;
  return (
    <>
      <Link className="text-link back-link" to="/rules">
        <ArrowLeft size={14} /> Controls
      </Link>
      <PageHeading
        eyebrow={"CONTROL VERSION " + c.version}
        title={c.title}
        action={
          ["admin", "analyst"].includes(user.role) && (
            <Link className="button secondary" to={"/rules/" + id + "/edit"}>
              Draft next version
            </Link>
          )
        }
      >
        {kinds[c.kind]} · {c.policy_title} v{c.policy_version}
      </PageHeading>
      <p><Link className="button secondary" to={`/rules/code?control_id=${encodeURIComponent(id)}`}>Export this control as YAML</Link></p>
      <ErrorNotice message={error} />
      <div className="control-detail-grid">
        <section className="panel section-padding">
          <div className="panel-title-row">
            <h2>Configured condition</h2>
            <Status value={c.status} />
          </div>
          <p className="section-copy preserve-lines">{c.description}</p>
          <DefinitionList
            items={[
              ["Type", kinds[c.kind]],
              ["Threshold", c.threshold],
              ["Currency", c.currency],
              ["Window", c.window_hours + " hours"],
              ["Destinations", c.countries.join(", ")],
              ["Priority", c.priority],
            ]}
          />
          <p className="privacy-note">
            Amount and aggregate controls compare original-currency amounts.
            Historical simulations use the customer’s current recorded KYC
            status.
          </p>
          <button
            className="button secondary"
            disabled={busy}
            onClick={backtest}
          >
            <FlaskConical size={16} /> Run historical simulation
          </button>
        </section>
        <aside className="panel section-padding">
          <h2>Activation and governance</h2>
          <p className="section-copy">
            Only approved controls evaluate new transactions. A second
            authorized person must approve a draft tied to the current policy
            version.
          </p>
          {c.created_by === user.id && c.status === "draft" && (
            <div className="notice warning">
              You authored this version. Invite a reviewer from Workspace
              settings to approve it.
            </div>
          )}
          {["admin", "reviewer"].includes(user.role) &&
            ["draft", "active"].includes(c.status) && (
              <form onSubmit={action}>
                <input
                  type="hidden"
                  name="action"
                  value={c.status === "draft" ? "approve" : "disable"}
                />
                <Field label="Review notes">
                  <textarea
                    name="notes"
                    minLength={10}
                    maxLength={2000}
                    required
                    rows={4}
                  />
                </Field>
                <Submit busy={busy}>
                  {c.status === "draft"
                    ? "Approve & activate"
                    : "Disable control"}
                </Submit>
              </form>
            )}
          {c.approval_notes && (
            <>
              <h3>Recorded review</h3>
              <p className="section-copy">{c.approval_notes}</p>
            </>
          )}
        </aside>
      </div>
      {test && (
        <section className="panel detail-section">
          <div className="panel-heading">
            <div>
              <h2>Historical simulation</h2>
              <p>
                {test.match_count} matches across {test.tested} transactions ·
                No alerts or cases were created.
              </p>
            </div>
            <span className="tiny-label">SHADOW RESULTS</span>
          </div>
          <p className="section-padding privacy-note">{test.limitation}</p>
          {test.matches.length > 0 && (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Transaction</th>
                    <th>Observed</th>
                    <th>Threshold</th>
                  </tr>
                </thead>
                <tbody>
                  {test.matches.slice(0, 100).map((m) => (
                    <tr key={m.transaction_id}>
                      <td>{m.external_id}</td>
                      <td>{m.facts.observed}</td>
                      <td>{m.facts.threshold}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </>
  );
}
