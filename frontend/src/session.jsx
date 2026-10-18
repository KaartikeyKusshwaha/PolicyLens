import { createContext, useContext, useEffect, useState } from "react";
import {
  ArrowRight,
  Globe2,
  LockKeyhole,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import { api, setSessionToken } from "./services/api";
import { ErrorNotice, Field, Loading, Submit } from "./components";

const SessionContext = createContext(null);
export const useSession = () => useContext(SessionContext);

export function SessionProvider({ children }) {
  const [user, setUser] = useState(null);
  const [setup, setSetup] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  async function reload() {
    setError("");
    try {
      const status = await api("/auth/status");
      setSetup(status.setup_required);
      if (!status.setup_required) {
        try {
          const value = await api("/auth/me");
          setUser(value);
          setSessionToken(value.csrf);
        } catch (e) {
          if (e.status !== 401) throw e;
          setUser(null);
          setSessionToken("");
        }
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    reload();
    const expire = () => {
      setUser(null);
      setSessionToken("");
    };
    window.addEventListener("policylens-session-expired", expire);
    return () =>
      window.removeEventListener("policylens-session-expired", expire);
  }, []);
  return (
    <SessionContext.Provider
      value={{
        user,
        setup,
        loading,
        error,
        reload,
        setUser,
        accept(value) {
          setSessionToken(value.csrf);
          setUser(value);
          setSetup(false);
        },
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function AuthGate({ children }) {
  const session = useSession();
  if (session.loading) return <Loading />;
  if (session.error)
    return (
      <div className="auth-retry">
        <ErrorNotice message={session.error} retry={session.reload} />
      </div>
    );
  if (!session.user || window.location.pathname === "/join") return <SignIn />;
  return children;
}

function SignIn() {
  const session = useSession();
  const invite =
    window.location.pathname === "/join"
      ? decodeURIComponent(window.location.hash.slice(1))
      : "";
  const setup = session.setup && !invite;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    if (invite) data.token = invite;
    try {
      const user = await api(
        setup ? "/auth/setup" : invite ? "/auth/join" : "/auth/login",
        { method: "POST", body: data },
      );
      session.accept(user);
      if (invite) window.location.assign("/");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-shell">
      <aside className="auth-story">
        <div className="auth-brand">
          <ScanLine size={28} />
          PolicyLens<span>OPERATIONS</span>
        </div>
        <div>
          <span className="eyebrow">BUILT FOR CROSS-BORDER COMPLIANCE</span>
          <h1>
            Every corridor.
            <br />
            One clear picture.
          </h1>
          <p>
            Connect your policies, customer activity, and investigations in a
            workspace built around evidence.
          </p>
          <div className="auth-orbit">
            <Globe2 size={120} strokeWidth={0.6} />
            <span>
              <ShieldCheck size={17} /> Evidence-led investigations
            </span>
          </div>
        </div>
        <small>Human decisions. Traceable evidence. Accountable AI.</small>
      </aside>
      <main className="auth-main">
        <div className="auth-form-wrap">
          <span className="section-icon">
            <LockKeyhole size={21} />
          </span>
          <div className="eyebrow">YOUR COMPLIANCE WORKSPACE</div>
          <h1>
            {setup
              ? "Create your first workspace"
              : invite
                ? "Join your team"
                : "Welcome back."}
          </h1>
          <p>
            {setup
              ? "Set up the owner account. Future team members join by invitation."
              : invite
                ? "Use the invited email. Existing members should enter their current password."
                : "Sign in to pick up where your team left off."}
          </p>
          <form onSubmit={submit}>
            {setup && (
              <Field
                label="Local bootstrap key"
                hint="Open backend/data/.bootstrap-token on the server. The key is consumed after setup."
              >
                <input
                  name="bootstrap_token"
                  type="password"
                  autoComplete="off"
                  required
                  minLength={20}
                  maxLength={100}
                />
              </Field>
            )}
            {(setup || invite) && (
              <Field label="Your full name">
                <input
                  name="name"
                  autoComplete="name"
                  required
                  minLength={2}
                  maxLength={100}
                />
              </Field>
            )}
            {setup && (
              <Field label="Workspace name">
                <input
                  name="workspace"
                  placeholder="Your company or team"
                  required
                  minLength={3}
                  maxLength={100}
                />
              </Field>
            )}
            <Field label="Work email">
              <input
                type="email"
                name="email"
                autoComplete="username"
                required
                maxLength={254}
              />
            </Field>
            <Field label="Password" hint="At least 12 characters.">
              <input
                name="password"
                type="password"
                autoComplete={
                  setup || invite ? "new-password" : "current-password"
                }
                minLength={12}
                maxLength={128}
                required
              />
            </Field>
            <ErrorNotice message={error} />
            <Submit busy={busy}>
              {setup
                ? "Create workspace"
                : invite
                  ? "Accept invitation"
                  : "Sign in"}
              <ArrowRight size={16} />
            </Submit>
          </form>
          <p className="auth-disclosure">
            AI workflows send selected evidence to your configured Groq
            provider. Sanctions and company reference data come from named
            public sources. No payment execution or automatic regulatory filing.
          </p>
        </div>
      </main>
    </div>
  );
}
