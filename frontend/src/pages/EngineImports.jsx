import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import { ErrorNotice, Field, PageHeading, Submit, useResource } from "../components";
import { label } from "../product-components";
import { useSession } from "../session";

export default function EngineImports() {
  const { user } = useSession();
  const customers = useResource("/customers");
  const [instance, setInstance] = useState("");
  const [cases, setCases] = useState('{"data": []}');
  const [decisions, setDecisions] = useState('{"data": []}');
  const [partial, setPartial] = useState(false);
  const [mappings, setMappings] = useState({});
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function changed(setter, value) { setter(value); setPreview(null); setMappings({}); setResult(null); setError(""); }
  function body() {
    return { schema_version: "policylens.marble-import.v1", source_instance: instance, cases: JSON.parse(cases), decisions: JSON.parse(decisions), acknowledge_partial_pages: partial, customer_mappings: Object.entries(mappings).filter(([, value]) => value).map(([key, customer_id]) => ({ object_type: key.split(":")[0], source_id: key.split(":")[1], customer_id })) };
  }
  async function inspect(event) {
    event.preventDefault(); setBusy(true); setError(""); setResult(null);
    try { setPreview(await api("/adapters/marble/preview", { method: "POST", body: { bundle: body() } })); }
    catch (failure) { setError(failure.message); setPreview(null); }
    finally { setBusy(false); }
  }
  async function imported() {
    setBusy(true); setError("");
    try { setResult(await api("/adapters/marble/import", { method: "POST", body: { bundle: body(), preview_sha256: preview.preview_sha256 } })); setPreview(null); }
    catch (failure) { setError(failure.message); setPreview(null); }
    finally { setBusy(false); }
  }
  return <>
    <PageHeading eyebrow="EVIDENCE FROM YOUR EXISTING ENGINE" title="Import engine records">Import Marble v1 decision and v1beta case export pages. Map source records to existing customers, preview, then retain the source evidence for human review.</PageHeading>
    <ErrorNotice message={error || customers.error} />
    {["admin", "analyst"].includes(user.role) ? <>
      <section className="panel section-padding">
        <p>These imports cover selected exported records. They do not infer transactions, activate controls, close local cases, block payments or write back to Marble.</p>
        <form className="form-grid" onSubmit={inspect}>
          <Field label="Marble instance label" hint="Use the same stable label for repeat imports from this instance."><input value={instance} onChange={event => changed(setInstance, event.target.value)} pattern="[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}" required disabled={busy} /></Field>
          <Field label="Case export JSON" wide><textarea rows={10} maxLength={2000000} value={cases} onChange={event => changed(setCases, event.target.value)} spellCheck={false} disabled={busy} /></Field>
          <Field label="Decision export JSON" wide><textarea rows={10} maxLength={2000000} value={decisions} onChange={event => changed(setDecisions, event.target.value)} spellCheck={false} disabled={busy} /></Field>
          <Field label="Acknowledge partial source pages" hint="Required when pagination.has_more is true. The import will not claim complete source history."><input type="checkbox" checked={partial} onChange={event => changed(setPartial, event.target.checked)} disabled={busy} /></Field>
          <div><Submit busy={busy}>Preview engine import</Submit></div>
        </form>
      </section>
      {preview && <section className="panel section-padding"><h2>Import preview</h2><p>{preview.scope}</p>
        <datalist id="import-customers">{customers.data?.map(c => <option value={c.id} key={c.id}>{c.name} · {c.external_id}</option>)}</datalist>
        {preview.objects.map(item => <div className="detail-section" key={item.id}><h3>{item.source_name || label(item.object_type)}</h3><p>{label(item.object_type)} {item.source_id} · {label(item.action)}{item.creates_alert ? " · Creates a local review alert" : ""}</p>
          {item.errors.length > 0 && <p>Needs review: {item.errors.map(label).join("; ")}.</p>}
          {item.object_type === "case" || !item.source_case_id ? <Field label={`Customer mapping for ${item.source_id}`} hint="Choose or paste an existing workspace customer ID."><input list="import-customers" value={mappings[`${item.object_type}:${item.source_id}`] ?? item.customer_id ?? ""} disabled={busy} onChange={event => { setMappings({ ...mappings, [`${item.object_type}:${item.source_id}`]: event.target.value }); setPreview({ ...preview, can_import: false, preview_sha256: "" }); }} /></Field> : <p>Customer mapping follows the referenced source case.</p>}
        </div>)}
        <p>After changing mappings, preview again before importing.</p><button className="button primary" disabled={busy || !preview.can_import || !preview.preview_sha256} onClick={imported}>Import reviewed engine records</button>
      </section>}
      {result && <section className="panel section-padding"><h2>{result.replayed ? "Existing engine import reused" : "Engine records imported"}</h2><p>Local investigations remain subject to human review. No upstream write was performed.</p>{[...new Set(result.objects.map(item => item.local_case_id).filter(Boolean))].map(id => <p key={id}><Link to={`/cases/${id}`}>Open imported investigation</Link></p>)}</section>}
    </> : <p>Your role can read investigations and evidence. Engine imports require an administrator or analyst.</p>}
  </>;
}
