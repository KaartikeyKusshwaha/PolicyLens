import { useState } from "react";
import { api } from "../services/api";
import { ErrorNotice, Field, Loading, Submit, Success, useResource } from "../components";

export default function AgentKeys() {
  const keys = useResource("/agent-keys");
  const registry = useResource("/agent-tools");
  const [scopes, setScopes] = useState([]);
  const [token, setToken] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function create(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    setBusy(true); setError(""); setToken(null); setMessage("");
    try {
      const result = await api("/agent-keys", { method: "POST", body: {
        name: values.name, password: values.password,
        scopes, expires_days: Number(values.expires_days), daily_runs: Number(values.daily_runs),
        requests_per_minute: Number(values.requests_per_minute), pseudonymize: values.pseudonymize === "on",
      } });
      setToken(result); form.reset(); setScopes([]); keys.reload();
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  async function revoke(id) {
    setBusy(true); setError(""); setMessage("");
    try {
      await api("/agent-keys/" + id + "/revoke", { method: "POST" });
      if (token?.id === id) setToken(null);
      setMessage("Agent key revoked. Pending runs were cancelled; a request already sent to the model cannot be recalled.");
      keys.reload();
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); }
  }
  if (keys.loading || registry.loading) return <Loading />;
  return <div className="settings-grid">
    <section className="panel section-padding">
      <h2>Governed agent access</h2>
      <p className="section-copy">Each agent gets a separate identity, tool permissions, expiry and budget. Agents can retrieve evidence, prepare drafts and request review. They cannot approve, activate controls, close cases or file reports.</p>
      <ErrorNotice message={error || keys.error || registry.error} />
      {message && <Success>{message}</Success>}
      {keys.data?.map((key) => <article className="integration-row" key={key.id}>
        <div><strong>{key.name}</strong><small>Expires {new Date(key.expires_at).toLocaleString()} · {key.daily_runs} runs/day · {key.requests_per_minute} requests/minute</small>
          <small>{key.scopes.join(", ")}</small><small>Model: {key.model} · revision: {key.model_revision}</small></div>
        {key.revoked ? <span>Revoked</span> : <button className="button secondary" disabled={busy} onClick={() => revoke(key.id)}>Revoke {key.name}</button>}
      </article>)}
      {!keys.data?.length && !keys.error && <p>No agent keys have been created.</p>}
      {token && <div className="generated-credential" role="region" aria-label="New agent credential">
        <h3>Save this agent key now</h3><p>Displayed once. Put it in the agent's private environment or credential file. Avoid chat messages and Git.</p>
        <code style={{ overflowWrap: "anywhere" }}>{token.token}</code>
        <button className="button secondary" onClick={() => setToken(null)}>I saved the key · hide</button>
      </div>}
    </section>
    <form className="panel section-padding" onSubmit={create}>
      <h2>Create an agent key</h2>
      <Field label="Agent name"><input name="name" required minLength={3} maxLength={80} /></Field>
      <Field label="Expires after (days)"><input name="expires_days" type="number" min={1} max={90} defaultValue={30} required /></Field>
      <Field label="Daily run budget"><input name="daily_runs" type="number" min={0} max={100} defaultValue={5} required /></Field>
      <Field label="Requests per minute"><input name="requests_per_minute" type="number" min={1} max={120} defaultValue={30} required /></Field>
      <fieldset><legend>Allowed tools</legend>{registry.data?.tools.map((tool) => <label className="checkbox-row" key={tool.name}>
        <input type="checkbox" checked={scopes.includes(tool.name)} onChange={(event) => setScopes((current) => event.target.checked ? [...current, tool.name] : current.filter((name) => name !== tool.name))} />
        <span>{tool.name} · {tool.class}<small>{tool.description}</small></span>
      </label>)}</fieldset>
      <label className="checkbox-row"><input type="checkbox" name="pseudonymize" defaultChecked /><span>Mask structured customer identifiers and omit private notes from tool responses and model calls.</span></label>
      <p className="privacy-note">Masking is not complete anonymization. Unrecognized information in free text may remain. Internal record and citation references remain usable. The workspace run budget also applies.</p>
      <Field label="Current password"><input name="password" type="password" required minLength={12} maxLength={128} autoComplete="current-password" /></Field>
      <Submit busy={busy} disabled={busy || !scopes.length || Boolean(registry.error)}>Create scoped key</Submit>
    </form>
  </div>;
}
