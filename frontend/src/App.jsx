import { createContext, useContext, useEffect, useState } from "react";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  Database,
  FileCheck2,
  HelpCircle,
  LayoutDashboard,
  Menu,
  Moon,
  PanelLeftClose,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Sun,
  X,
  Users,
  Workflow,
  Bot,
  SlidersHorizontal,
  GitCompareArrows,
  Settings2,
  Fingerprint,
  LogOut,
} from "lucide-react";
import { useResource } from "./components";
import Evaluate from "./pages/Evaluate";
import { Policies, PolicyEditor } from "./pages/Policies";
import Assistant from "./pages/Assistant";
import { Decisions, DecisionDetail } from "./pages/Decisions";
import Sources from "./pages/Sources";
import { SessionProvider, AuthGate, useSession } from "./session";
import { api } from "./services/api";
import CommandCenter from "./pages/CommandCenter";
import { Customers, CustomerEditor, CustomerDetail } from "./pages/Customers";
import Monitoring from "./pages/Monitoring";
import { Cases, CaseDetail } from "./pages/Cases";
import { AgentOperations, AgentRun } from "./pages/AgentOperations";
import { Controls, ControlEditor, ControlDetail } from "./pages/Controls";
import { PolicyChanges, ChangeDetail } from "./pages/PolicyChanges";
import AuditAnalytics from "./pages/AuditAnalytics";
import WorkspaceSettings from "./pages/WorkspaceSettings";
import Traceability from "./pages/Traceability";
import ControlCode from "./pages/ControlCode";
import EngineImports from "./pages/EngineImports";
import Retention from "./pages/Retention";

const WorkspaceContext = createContext(null);
export const useWorkspace = () => useContext(WorkspaceContext);
const navigation = [
  { to: "/", label: "Command center", icon: LayoutDashboard },
  { to: "/customers", label: "Customers & entities", icon: Users },
  { to: "/monitoring", label: "Transaction monitoring", icon: Activity },
  { to: "/cases", label: "Investigations", icon: Workflow },
  { to: "/agents", label: "Agent operations", icon: Bot },
  { to: "/rules", label: "Control workbench", icon: SlidersHorizontal },
  { to: "/policies", label: "Policy library", icon: BookOpen },
  { to: "/changes", label: "Policy change impact", icon: GitCompareArrows },
  { to: "/assistant", label: "Policy assistant", icon: Sparkles },
  { to: "/sources", label: "Data sources", icon: Database },
  { to: "/audit", label: "Audit & analytics", icon: Fingerprint },
  { to: "/settings", label: "Workspace settings", icon: Settings2 },
];

function Workspace() {
  const session = useSession();
  const health = useResource("/health");
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(
    () => localStorage.getItem("policylens-theme") === "dark",
  );
  const location = useLocation();
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("policylens-theme", dark ? "dark" : "light");
  }, [dark]);
  const active = navigation.find((n) =>
    n.to === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(n.to),
  );
  const closeMenu = () => setOpen(false);
  return (
    <WorkspaceContext.Provider value={{ health }}>
      <div className="app-shell">
        {open && (
          <button
            className="sidebar-scrim"
            aria-label="Close navigation"
            onClick={closeMenu}
          />
        )}
        <aside className={`sidebar ${open ? "is-open" : ""}`}>
          <Link className="brand" to="/" onClick={closeMenu}>
            <span className="brand-mark">
              <ScanLine size={24} />
            </span>
            <span>
              Policy<span className="brand-light">Lens</span>
              <small>COMPLIANCE INTELLIGENCE</small>
            </span>
          </Link>
          <div className="workspace-picker">
            <span className="workspace-avatar">PL</span>
            <span>
              {session.user.workspace}
              <small>{session.user.role} · Cross-border compliance</small>
            </span>
          </div>
          <div className="nav-label">WORKSPACE</div>
          <nav aria-label="Main navigation">
            {navigation.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} end={to === "/"} onClick={closeMenu}>
                <Icon size={19} />
                <span>{label}</span>
                {to === "/assistant" && <span className="ai-tag">AI</span>}
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="sidebar-note">
              <ShieldCheck size={20} />
              <strong>Evidence at every step.</strong>
              <p>Trace an assessment back to the policy that supports it.</p>
              <Link to="/policies" onClick={closeMenu}>
                Explore your library <ArrowUpRight size={14} />
              </Link>
            </div>
            <div className="sidebar-footer">
              <span className={`status-dot ${health.data ? "green" : ""}`} />
              <span>
                {health.error
                  ? "API unreachable"
                  : health.data
                    ? "Local storage connected"
                    : "Connecting…"}
              </span>
              <span className="version">v3.0</span>
            </div>
          </div>
        </aside>
        <div className="main-shell">
          <div className="topbar">
            <div className="breadcrumbs">
              <button
                className="icon-button mobile-menu"
                aria-label="Open navigation"
                onClick={() => setOpen(true)}
              >
                <Menu size={20} />
              </button>
              <span>Workspace</span>
              <ChevronRight size={13} />
              <strong>{active?.label || "PolicyLens"}</strong>
            </div>
            <div className="topbar-actions">
              <Link className="connection-chip" to="/sources">
                <Activity size={14} />
                {health.data?.ai.status === "configured"
                  ? "AI configured"
                  : "Setup required"}
              </Link>
              {health.data?.api_docs_enabled !== false && (
                <a
                  href="/docs"
                  target="_blank"
                  rel="noreferrer"
                  className="icon-button"
                  aria-label="API documentation"
                >
                  <HelpCircle size={18} />
                </a>
              )}
              <button
                className="icon-button"
                aria-label={dark ? "Use light theme" : "Use dark theme"}
                onClick={() => setDark(!dark)}
              >
                {dark ? <Sun size={18} /> : <Moon size={18} />}
              </button>
              <span className="profile-avatar" title={session.user.name}>
                {session.user.name
                  .split(" ")
                  .map((v) => v[0])
                  .slice(0, 2)
                  .join("")}
              </span>
              <button
                className="icon-button"
                aria-label="Sign out"
                onClick={async () => {
                  await api("/auth/logout", { method: "POST" });
                  session.setUser(null);
                }}
              >
                <LogOut size={17} />
              </button>
            </div>
          </div>
          <main key={location.pathname} id="main-content">
            <Routes>
              <Route path="/" element={<CommandCenter />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/customers/new" element={<CustomerEditor />} />
              <Route path="/customers/:id" element={<CustomerDetail />} />
              <Route path="/customers/:id/edit" element={<CustomerEditor />} />
              <Route path="/monitoring" element={<Monitoring />} />
              <Route path="/cases" element={<Cases />} />
              <Route path="/cases/:id" element={<CaseDetail />} />
              <Route path="/agents" element={<AgentOperations />} />
              <Route path="/agents/:id" element={<AgentRun />} />
              <Route path="/rules" element={<Controls />} />
              <Route path="/rules/new" element={<ControlEditor />} />
              <Route path="/rules/:id" element={<ControlDetail />} />
              <Route path="/rules/:id/edit" element={<ControlEditor />} />
              <Route path="/changes" element={<PolicyChanges />} />
              <Route path="/changes/:id" element={<ChangeDetail />} />
              <Route path="/audit" element={<AuditAnalytics />} />
              <Route path="/settings" element={<WorkspaceSettings />} />
              <Route path="/evaluate" element={<Evaluate />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/rules/code" element={<ControlCode />} />
              <Route path="/settings/imports" element={<EngineImports />} />
              <Route path="/settings/retention" element={<Retention />} />
              <Route path="/policies/traceability" element={<Traceability />} />
              <Route path="/policies/new" element={<PolicyEditor />} />
              <Route path="/policies/:id/edit" element={<PolicyEditor />} />
              <Route path="/assistant" element={<Assistant />} />
              <Route path="/query" element={<Assistant />} />
              <Route path="/decisions" element={<Decisions />} />
              <Route path="/decisions/:id" element={<DecisionDetail />} />
              <Route path="/sources" element={<Sources />} />
              <Route path="/external-data" element={<Sources />} />
              <Route
                path="*"
                element={
                  <div className="empty">
                    <X size={30} />
                    <h1>Page not found</h1>
                    <Link to="/">Back to overview</Link>
                  </div>
                }
              />
            </Routes>
            <footer className="page-footer">
              <span>
                <ShieldCheck size={13} /> PolicyLens · Evidence-led compliance
              </span>
              <span>AI assessments require human review.</span>
            </footer>
          </main>
        </div>
      </div>
    </WorkspaceContext.Provider>
  );
}
export default function App() {
  return (
    <SessionProvider>
      <AuthGate>
        <BrowserRouter>
          <a className="skip-link" href="#main-content">
            Skip to content
          </a>
          <Workspace />
        </BrowserRouter>
      </AuthGate>
    </SessionProvider>
  );
}
