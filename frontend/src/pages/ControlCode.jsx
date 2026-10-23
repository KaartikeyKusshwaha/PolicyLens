import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Link } from "../navigation";
import { api } from "../services/api";
import { ErrorNotice, Field, PageHeading, Submit } from "../components";
import { useSession } from "../session";

export default function ControlCode() {
  const [parameters] = useSearchParams();
  const [yaml, setYaml] = useState("");
  const [commit, setCommit] = useState("");
  const [path, setPath] = useState("");
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { user } = useSession();
  const canImport = ["admin", "analyst"].includes(user.role);
  function edit(setter, value) { setter(value); setPreview(null); setResult(null); setError(""); }
  async function exported() {
    setBusy(true); setError(""); setPreview(null); setResult(null);
    try {
      const id = parameters.get("control_id");
      setYaml(await api(`/control-code/export${id ? `?control_id=${encodeURIComponent(id)}` : ""}`, { responseType: "text" }));
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function loadFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    setBusy(true); setError(""); setPreview(null); setResult(null);
    try {
      if (file.size > 256000) throw new Error("Control YAML files are limited to 256 KB.");
      setYaml(await file.text());
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); event.target.value = ""; }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([yaml], { type: "application/yaml" }));
    const link = document.createElement("a"); link.href = url; link.download = "policylens-controls.yaml"; link.click(); URL.revokeObjectURL(url);
  }
  const body = { yaml, source_commit: commit, source_path: path };
  async function inspect(event) {
    event.preventDefault(); setBusy(true); setError(""); setResult(null); setPreview(null);
    try { setPreview(await api("/control-code/preview", { method: "POST", body })); }
    catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function imported() {
    setBusy(true); setError("");
    try { setResult(await api("/control-code/import", { method: "POST", body: { ...body, preview_sha256: preview.preview_sha256 } })); setPreview(null); }
    catch (failure) { setError(failure.message); setPreview(null); }
    finally { setBusy(false); }
  }
  return <>
    <PageHeading eyebrow="REVIEW CONFIGURATION IN GIT" title="Controls as code">Export configuration, review edits in Git, then import drafts. Approval and activation stay in the independent in-app review workflow.</PageHeading>
    <ErrorNotice message={error} />
    <section className="panel section-padding">
      <div className="panel-heading"><h2>YAML configuration</h2><button className="button secondary" disabled={busy} onClick={exported}>{parameters.get("control_id") ? "Load control YAML" : "Load workspace YAML"}</button></div>
      <p>Exports omit approval and author credentials. Policy versions and content hashes are pinned. Superseded controls are excluded from workspace exports.</p>
      <Field label="Read YAML file"><input type="file" accept=".yaml,.yml,application/yaml,text/yaml" disabled={busy} onChange={loadFile} /></Field>
      <form className="form-grid" onSubmit={inspect}>
        <Field label="Control YAML" wide><textarea value={yaml} onChange={event => edit(setYaml, event.target.value)} rows={20} maxLength={256000} spellCheck={false} disabled={busy} required style={{ fontFamily: "monospace" }} /></Field>
        {canImport && <>
          <Field label="Git commit" hint="Optional full commit SHA. Supplied provenance; the server does not fetch or verify Git."><input value={commit} maxLength={64} onChange={event => edit(setCommit, event.target.value)} disabled={busy} /></Field>
          <Field label="Repository file path" hint="Optional provenance label; this does not read a server file."><input value={path} maxLength={240} onChange={event => edit(setPath, event.target.value)} disabled={busy} /></Field>
        </>}
        <div className="form-actions"><button className="button secondary" type="button" disabled={!yaml || busy} onClick={download}>Download YAML for Git</button>{canImport && <Submit busy={busy} disabled={!yaml || busy}>Preview YAML</Submit>}</div>
      </form>
    </section>
    {preview && <section className="panel section-padding">
      <h2>Preview: {preview.count} control drafts</h2><p>{preview.scope}</p>
      <code style={{ overflowWrap: "anywhere" }}>{preview.preview_sha256}</code>
      {preview.controls.map(item => <div className="detail-section" key={item.key}><h3>{item.configuration.title}</h3><p>{item.replaces ? `Replaces control ${item.replaces.id}` : "Creates a new control"} · Policy version {item.policy.version}</p><pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{JSON.stringify(item.configuration, null, 2)}</pre></div>)}
      <button className="button primary" disabled={busy} onClick={imported}>Import reviewed drafts</button>
    </section>}
    {result && <section className="panel section-padding"><h2>{result.replayed ? "Existing import reused" : "Drafts imported"}</h2><p>{result.replayed ? "No duplicate controls were created. Open each control to see its current review status." : "These new drafts require independent approval before activation."}</p>{result.controls.map(item => <p key={item.key}><Link to={`/rules/${item.control.id}`}>{item.control.title}</Link> · Version {item.control.version}</p>)}</section>}
  </>;
}
