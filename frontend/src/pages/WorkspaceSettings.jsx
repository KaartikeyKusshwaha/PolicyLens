import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Link } from "../navigation";
import {
  ArrowUpRight,
  Copy,
  KeyRound,
  Plus,
  Settings2,
  ShieldCheck,
  Users,
  Webhook,
} from "lucide-react";
import { api } from "../services/api";
import {
  ErrorNotice,
  Field,
  formatDate,
  Loading,
  PageHeading,
  Submit,
  Success,
  useResource,
} from "../components";
import { Status } from "../product-components";
import { useSession } from "../session";

export default function WorkspaceSettings() {
  const { user } = useSession();
  const [params, setParams] = useSearchParams();
  const team = useResource("/team");
  const prefs = useResource("/preferences");
  const workspaces = useResource("/auth/workspaces");
  const sections = ["Team", "Monitoring", "Integrations", "Workspaces", "Account"];
  const tab = sections.includes(params.get("section")) ? params.get("section") : "Team";
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [invite, setInvite] = useState(null);
  const [integration, setIntegration] = useState(null);
  const [copied, setCopied] = useState(false);
  async function perform(path, body, onResult) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const value = await api(path, { method: "POST", body });
      if (onResult) onResult(value);
      else setSuccess("Change saved.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function switchWorkspace(id) {
    await perform("/auth/workspaces/" + id + "/switch", undefined, () =>
      window.location.assign("/"),
    );
  }
  async function copy(value) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {
      setError(
        "Copy is unavailable in this browser. Select and copy the value manually.",
      );
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="TEAM & OPERATING CONTROLS"
        title="Make the workspace work for your team."
      >
        Manage membership, monitoring schedules, and signed transaction
        ingestion.
      </PageHeading>
      <div className="settings-identity">
        <span className="workspace-avatar">
          {user.name
            .split(" ")
            .map((v) => v[0])
            .slice(0, 2)
            .join("")}
        </span>
        <div>
          <strong>{user.name}</strong>
          <small>
            {user.email} · {user.workspace}
          </small>
        </div>
        <Status value={user.role} />
      </div>
      <div className="page-tabs">
        {sections.map(
          (t) => (
            <button
              key={t}
              className={tab === t ? "active" : ""}
              onClick={() => {
                setParams({ section: t });
                setError("");
                setSuccess("");
              }}
            >
              {t}
            </button>
          ),
        )}
      </div>
      <ErrorNotice message={error} />
      {success && <Success>{success}</Success>}
      {copied && <Success>Copied.</Success>}
      {tab === "Account" && (
        <form
          className="panel form-panel editor-panel"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            perform(
              "/auth/password",
              Object.fromEntries(new FormData(form)),
              () => {
                form.reset();
                setSuccess("Password updated. Other sessions were revoked.");
              },
            );
          }}
        >
          <h2>Change your password</h2>
          <p className="section-copy">
            Updating your password signs out your other sessions.
          </p>
          <Field label="Current password">
            <input
              name="current_password"
              type="password"
              autoComplete="current-password"
              required
              minLength={12}
              maxLength={128}
            />
          </Field>
          <Field label="New password">
            <input
              name="new_password"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={128}
            />
          </Field>
          <Submit busy={busy}>Update password</Submit>
        </form>
      )}
      {tab === "Team" && (
        <div className="settings-grid">
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Workspace members</h2>
                <p>Controls and case decisions use authenticated identities.</p>
              </div>
              <Users size={20} />
            </div>
            {team.loading ? (
              <Loading />
            ) : (
              <div className="team-list">
                {team.data?.map((member) => (
                  <div key={member.id}>
                    <span className="entity-avatar">
                      {member.name.slice(0, 2).toUpperCase()}
                    </span>
                    <div>
                      <strong>{member.name}</strong>
                      <small>{member.email}</small>
                    </div>
                    {user.role === "admin" ? (
                      <select
                        className="member-role-select"
                        aria-label={"Access for " + member.name}
                        value={member.role}
                        disabled={busy}
                        onChange={(e) =>
                          perform(
                            "/team/" + member.id + "/access",
                            { role: e.target.value },
                            () => {
                              team.reload();
                              if (member.id === user.id)
                                window.location.reload();
                            },
                          )
                        }
                      >
                        {["admin", "analyst", "reviewer", "auditor"].map(
                          (role) => (
                            <option key={role} value={role}>
                              {role}
                            </option>
                          ),
                        )}
                        <option value="revoked">Revoke access</option>
                      </select>
                    ) : (
                      <Status value={member.role} />
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
          <aside>
            {user.role === "admin" ? (
              <form
                className="panel section-padding"
                onSubmit={(e) => {
                  e.preventDefault();
                  perform(
                    "/team/invites",
                    Object.fromEntries(new FormData(e.currentTarget)),
                    (value) => {
                      setInvite(value);
                      setCopied(false);
                    },
                  );
                }}
              >
                <h2>Invite a teammate</h2>
                <p className="section-copy">
                  Create a single-use invitation valid for 48 hours. Share it
                  directly with the intended recipient.
                </p>
                <Field label="Teammate email">
                  <input name="email" type="email" required maxLength={254} />
                </Field>
                <Field label="Workspace role">
                  <select name="role" defaultValue="analyst">
                    <option value="analyst">
                      Analyst · investigate and draft
                    </option>
                    <option value="reviewer">
                      Reviewer · approve and resolve
                    </option>
                    <option value="auditor">
                      Auditor · read-only evidence access
                    </option>
                    <option value="admin">
                      Administrator · manage workspace
                    </option>
                  </select>
                </Field>
                <Submit busy={busy}>
                  <Plus size={15} /> Create invitation
                </Submit>
                {invite && (
                  <div className="generated-credential">
                    <strong>Invitation for {invite.email}</strong>
                    <p>Expires {formatDate(invite.expires_at)}</p>
                    <code>
                      {window.location.origin + "/join#" + invite.token}
                    </code>
                    <button
                      className="button secondary"
                      type="button"
                      onClick={() =>
                        copy(window.location.origin + "/join#" + invite.token)
                      }
                    >
                      <Copy size={14} /> Copy invitation
                    </button>
                  </div>
                )}
              </form>
            ) : (
              <section className="panel guidance-panel">
                <ShieldCheck size={26} />
                <h2>Access follows responsibility.</h2>
                <p>
                  Administrators manage membership. Analysts prepare evidence
                  and draft controls. Reviewers approve controls and make
                  independent case decisions. Auditors inspect records without
                  mutation access.
                </p>
              </section>
            )}
          </aside>
        </div>
      )}
      {tab === "Monitoring" &&
        (prefs.loading ? (
          <Loading />
        ) : (
          <MonitoringPreferences
            initial={prefs.data}
            isAdmin={user.role === "admin"}
            onSaved={() => {
              prefs.reload();
              setSuccess(
                "Monitoring preferences saved. New alerts appear in the Inbox.",
              );
            }}
            onError={setError}
          />
        ))}
      {tab === "Integrations" &&
        (user.role === "admin" ? (
          <Integrations
            busy={busy}
            perform={perform}
            integration={integration}
            setIntegration={(value) => {
              setIntegration(value);
              setCopied(false);
            }}
            copy={copy}
          />
        ) : (
          <section className="panel guidance-panel">
            <KeyRound size={25} />
            <h2>Administrator access required.</h2>
            <p>
              Only workspace administrators can create or revoke ingestion
              credentials.
            </p>
          </section>
        ))}
      {tab === "Workspaces" && (
        <div className="settings-grid">
          <section className="panel section-padding">
            <h2>Your workspaces</h2>
            <p className="section-copy">
              Each workspace has a separate SQLite database. Switching reloads
              the app and clears the previous workspace from the interface.
            </p>
            {workspaces.data?.map((w) => (
              <div className="workspace-row" key={w.id}>
                <div>
                  <strong>{w.name}</strong>
                  <small>{w.role}</small>
                </div>
                {w.id === user.org_id ? (
                  <Status value="active" />
                ) : (
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => switchWorkspace(w.id)}
                  >
                    Switch workspace
                  </button>
                )}
              </div>
            ))}
          </section>
          {user.role === "admin" && (
            <form
              className="panel section-padding"
              onSubmit={(e) => {
                e.preventDefault();
                perform(
                  "/auth/workspaces",
                  Object.fromEntries(new FormData(e.currentTarget)),
                  () => {
                    workspaces.reload();
                    setSuccess(
                      "New workspace created. Switch into it to configure its own policies and controls.",
                    );
                  },
                );
              }}
            >
              <h2>Create another workspace</h2>
              <p className="section-copy">
                Existing policies, customers, source snapshots, and integration
                credentials are not copied.
              </p>
              <Field label="Workspace name">
                <input name="name" required minLength={3} maxLength={100} />
              </Field>
              <Submit busy={busy}>Create workspace</Submit>
            </form>
          )}
        </div>
      )}
    </>
  );
}

function MonitoringPreferences({ initial, isAdmin, onSaved, onError }) {
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    const form = new FormData(e.currentTarget);
    try {
      await api("/preferences", {
        method: "PUT",
        body: {
          enabled_sources: form.getAll("sources"),
          monitoring_enabled: form.get("monitoring") === "on",
          monitoring_interval_hours: Number(form.get("interval")),
        },
      });
      onSaved();
    } catch (e) {
      onError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="panel form-panel editor-panel" onSubmit={submit}>
      <h2>Intelligence coverage and recurring screening</h2>
      <p className="section-copy">
        Each enabled source must be fresh before an AI assessment or screening
        agent can complete. Scheduled runs refresh the selected lists and
        rescreen customer names.
      </p>
      <fieldset disabled={!isAdmin}>
        <legend>Enabled official sources</legend>
        {[
          ["ofac", "OFAC SDN · United States"],
          ["un", "United Nations consolidated list"],
          ["uk", "UK Sanctions List"],
        ].map(([id, name]) => (
          <label className="checkbox-row" key={id}>
            <input
              type="checkbox"
              name="sources"
              value={id}
              defaultChecked={initial.enabled_sources.includes(id)}
            />
            <span>{name}</span>
          </label>
        ))}
        <div className="aside-rule" />
        <label className="checkbox-row">
          <input
            type="checkbox"
            name="monitoring"
            defaultChecked={initial.monitoring_enabled}
          />
          <span>Enable recurring list refresh and customer screening</span>
        </label>
        <Field label="Refresh interval">
          <select
            name="interval"
            defaultValue={initial.monitoring_interval_hours}
          >
            {[6, 12, 24, 48, 72].map((h) => (
              <option value={h} key={h}>
                {h} hours
              </option>
            ))}
          </select>
        </Field>
        <p className="privacy-note">
          The server must be running. Failures are recorded visibly; stale
          evidence never becomes a successful screening result. This deployment
          supports up to 2,000 customers per scheduled run.
        </p>
      </fieldset>
      {isAdmin && <Submit busy={busy}>Save monitoring preferences</Submit>}
    </form>
  );
}

function Integrations({ busy, perform, integration, setIntegration, copy }) {
  const r = useResource("/integrations");
  return (
    <div className="settings-grid">
      <div>
        <section className="panel section-padding">
          <h2>Signed transaction ingestion</h2>
          <p className="section-copy">
            Your backend can send transactions directly to PolicyLens. Requests
            require HMAC-SHA256 signatures, a timestamp within five minutes, and
            a unique event ID.
          </p>
          {r.data?.map((i) => (
            <div className="integration-row" key={i.id}>
              <div>
                <strong>{i.name}</strong>
                <small>{i.id}</small>
              </div>
              <Status value={i.active ? "active" : "disabled"} />
              {i.active && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() =>
                    perform(
                      "/integrations/" + i.id + "/revoke",
                      undefined,
                      () => r.reload(),
                    )
                  }
                >
                  Revoke
                </button>
              )}
            </div>
          ))}
          {!r.data?.length && (
            <p className="section-copy">No ingestion credentials created.</p>
          )}
          <details className="integration-docs">
            <summary>Request format and signing instructions</summary>
            <pre>{`POST /api/webhooks/{workspace_id}/{integration_id}\nX-PolicyLens-Timestamp: <unix_seconds>\nX-PolicyLens-Event-Id: <unique_event_id>\nX-PolicyLens-Signature: sha256=<hex_digest>\n\nhex_digest = HMAC_SHA256(secret, timestamp + "." + raw_body)\n\nBody: monitoring transaction JSON.\nUse customer_id from the same workspace.\nRepeated event IDs must carry the same payload.\nKeep the secret on your backend, never in a browser.`}</pre>
          </details>
        </section>
      </div>
      <aside>
        <form
          className="panel section-padding"
          onSubmit={(e) => {
            e.preventDefault();
            perform(
              "/integrations",
              Object.fromEntries(new FormData(e.currentTarget)),
              (value) => {
                setIntegration(value);
                r.reload();
              },
            );
          }}
        >
          <h2>Create an ingestion credential</h2>
          <Field label="Integration name">
            <input
              name="name"
              required
              minLength={3}
              maxLength={100}
              placeholder="Your payments backend"
            />
          </Field>
          <Submit busy={busy}>
            <Webhook size={15} /> Create credential
          </Submit>
        </form>
        {integration && (
          <section className="panel section-padding detail-section generated-credential">
            <h2>Save this secret securely</h2>
            <p className="section-copy">
              The secret is displayed once. Revoking it immediately blocks new
              requests.
            </p>
            <small>Webhook path</small>
            <code>{integration.webhook_path}</code>
            <small>Signing secret</small>
            <code>{integration.secret}</code>
            <button
              className="button secondary"
              onClick={() => copy(integration.secret)}
            >
              <Copy size={14} /> Copy signing secret
            </button>
          </section>
        )}
      </aside>
    </div>
  );
}
