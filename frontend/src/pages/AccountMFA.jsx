import { useState } from "react";
import { api } from "../services/api";
import { ErrorNotice, Field, Loading, Submit, Success, useResource } from "../components";
import { useSession } from "../session";

export default function AccountMFA() {
  const resource = useResource("/auth/mfa");
  const session = useSession();
  const [enrollment, setEnrollment] = useState(null);
  const [recovery, setRecovery] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const action = event.nativeEvent.submitter?.value || (enrollment ? "confirm" : "enroll");
    const body = Object.fromEntries(new FormData(form));
    setBusy(true);
    setError("");
    setMessage("");
    setRecovery(null);
    try {
      const result = await api("/auth/mfa/" + action, { method: "POST", body });
      if (action === "enroll") setEnrollment(result);
      else {
        session.accept(result.user);
        setEnrollment(null);
        setRecovery(result.recovery_codes || null);
        setMessage(result.enabled ? "Two-factor authentication is enabled. Other sessions were signed out." : "Two-factor authentication is disabled. Other sessions were signed out.");
        resource.reload();
      }
      form.reset();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setBusy(false);
    }
  }
  if (resource.loading) return <Loading />;
  if (resource.error) return <ErrorNotice message={resource.error} retry={resource.reload} />;
  const enabled = resource.data.enabled;
  return <section className="panel form-panel editor-panel">
    <h2>Two-factor authentication</h2>
    <p className="section-copy">Add a six-digit code from your authenticator app to sign-in. Recovery codes work once. A password reset does not remove this protection.</p>
    <p>{enabled ? `Enabled · ${resource.data.recovery_codes_remaining} recovery codes remaining` : "Not enabled"}</p>
    <ErrorNotice message={error} />
    {message && <Success>{message}</Success>}
    {recovery && <div className="generated-credential" role="region" aria-label="One-time recovery codes">
      <h3>Save these recovery codes now</h3>
      <p>Store them separately from this account. This is the only time this list is displayed. Replacing the list invalidates all previous codes.</p>
      <pre>{recovery.join("\n")}</pre>
      <button className="button secondary" onClick={() => setRecovery(null)}>I saved the codes · hide</button>
    </div>}
    {enrollment && <div className="generated-credential">
      <h3>Add PolicyLens to your authenticator</h3>
      <p>Choose manual setup, enter the key below, and select time-based codes. Finish within ten minutes.</p>
      <code>{enrollment.secret}</code>
      <p>Issuer: PolicyLens · SHA1 · 6 digits · 30 seconds.</p>
      <button className="button secondary" onClick={() => setEnrollment(null)}>Cancel setup</button>
    </div>}
    <form onSubmit={submit}>
      <Field label="Current password"><input name="password" type="password" autoComplete="current-password" required minLength={12} maxLength={128} /></Field>
      {(enrollment || enabled) && <Field label="Authenticator or recovery code" hint={enrollment ? "Use the six-digit code from the newly added authenticator." : "Use a fresh authenticator code or an unused recovery code."}>
        <input name="code" aria-label="Authenticator or recovery code" autoComplete="one-time-code" required maxLength={64} />
      </Field>}
      {enabled ? <div className="button-row">
        <button type="submit" className="button secondary" value="recovery-codes" disabled={busy}>Replace recovery codes</button>
        <button type="submit" className="button secondary" value="disable" disabled={busy}>Disable two-factor authentication</button>
      </div> : <Submit busy={busy}>{enrollment ? "Verify and enable" : "Set up authenticator"}</Submit>}
    </form>
  </section>;
}
