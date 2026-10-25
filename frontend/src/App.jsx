import { createContext, lazy, Suspense, useContext, useEffect, useRef, useState } from "react";
import { BrowserRouter, Link, NavLink, useLocation } from "react-router-dom";
import {
  Activity,
  BookOpen,
  ChevronRight,
  FileCheck2,
  HelpCircle,
  Inbox as InboxIcon,
  LogOut,
  Menu,
  Moon,
  ScanLine,
  Settings2,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react";
import { Loading, useResource } from "./components";
import { SessionProvider, AuthGate, useSession } from "./session";
import { api } from "./services/api";
import { AREAS, areaFor } from "./navigation";
const WorkspaceRoutes = lazy(() => import("./workspaceRoutes"));
import { useScrollReveal } from "./motion";
import WorkspaceBoundary from "./WorkspaceBoundary";

const WorkspaceContext = createContext(null);
export const useWorkspace = () => useContext(WorkspaceContext);
const icons = [InboxIcon, BookOpen, FileCheck2, Settings2];
const advancedLinks = [
  ["/advanced", "Diagnostics"],
  ["/advanced/analytics", "Analytics"],
  ["/advanced/sources", "Source details"],
];

function Workspace() {
  const session = useSession();
  const health = useResource("/health");
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(
    () => localStorage.getItem("policylens-theme") === "dark",
  );
  const menu = useRef(null);
  const sidebar = useRef(null);
  const page = useRef(null);
  const location = useLocation();
  useScrollReveal(page, location.pathname);
  const active = areaFor(location.pathname);
  const advanced =
    location.pathname === "/advanced" ||
    location.pathname.startsWith("/advanced/");
  const links = advanced ? advancedLinks : active?.links || [];
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    localStorage.setItem("policylens-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    if (!open) return;
    const focusable = () =>
      [...sidebar.current.querySelectorAll("a, button")].filter(
        (node) => !node.disabled,
      );
    focusable()[0]?.focus();
    function keydown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      const first = items[0],
        last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", keydown);
    const trigger = menu.current;
    return () => {
      document.removeEventListener("keydown", keydown);
      trigger?.focus();
    };
  }, [open]);
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
        <aside
          ref={sidebar}
          id="workspace-navigation"
          className={`sidebar ${open ? "is-open" : ""}`}
          role={open ? "dialog" : undefined}
          aria-modal={open ? "true" : undefined}
          aria-label={open ? "Workspace navigation" : undefined}
        >
          {open && (
            <button
              className="icon-button drawer-close"
              aria-label="Close workspace navigation"
              onClick={closeMenu}
            >
              <X size={20} />
            </button>
          )}
          <Link className="brand" to="/inbox" onClick={closeMenu}>
            <span className="brand-mark">
              <ScanLine size={24} />
            </span>
            <span>
              Policy<span className="brand-light">Lens</span>
              <small>GOVERNANCE & EVIDENCE</small>
            </span>
          </Link>
          <Link className="workspace-picker" to="/workspace" onClick={closeMenu} aria-label={`Open ${session.user.workspace} workspace`}>
            <span className="workspace-avatar">PL</span>
            <span>
              {session.user.workspace}
              <small>{session.user.role} · Human review required</small>
            </span>
          </Link>
          <div className="nav-label">WORKSPACE</div>
          <nav aria-label="Main navigation">
            {AREAS.map((area, index) => {
              const Icon = icons[index];
              return (
                <Link
                  key={area.path}
                  to={area.path}
                  className={active?.path === area.path ? "active" : undefined}
                  aria-current={active?.path === area.path ? "page" : undefined}
                  onClick={closeMenu}
                >
                  <Icon size={19} />
                  <span>{area.title}</span>
                </Link>
              );
            })}
          </nav>
          <div className="sidebar-bottom">
            <p className="subtle-note">Humans decide. Agents prepare.</p>
            <Link className="text-link" to="/advanced" onClick={closeMenu}>
              Advanced diagnostics
            </Link>
            <div className="sidebar-footer">
              <span className={`status-dot ${health.data ? "green" : ""}`} />
              <span>
                {health.error
                  ? "API unreachable"
                  : health.data
                    ? "Workspace connected"
                    : "Connecting…"}
              </span>
              <span className="version">v3.0</span>
            </div>
          </div>
        </aside>
        <div className="main-shell" inert={open ? true : undefined}>
          <div className="topbar">
            <div className="breadcrumbs">
              <button
                ref={menu}
                className="icon-button mobile-menu"
                aria-label="Open navigation"
                aria-controls="workspace-navigation"
                aria-expanded={open}
                onClick={() => setOpen(true)}
              >
                <Menu size={20} />
              </button>
              <Link to="/workspace">{session.user.workspace}</Link>
              <ChevronRight size={13} />
              <strong>
                {active?.title || "PolicyLens"}
                {advanced ? " · Advanced" : ""}
              </strong>
            </div>
            <div className="topbar-actions">
              <Link className="connection-chip" to="/settings/sources">
                <Activity size={14} />
                Connections
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
                  .map((value) => value[0])
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
          {active && location.pathname !== "/workspace" && (
            <nav
              className="area-navigation"
              aria-label={
                advanced ? "Advanced navigation" : active.title + " navigation"
              }
            >
              {links
                .filter(
                  ([path]) =>
                    path !== "/settings/retention" ||
                    ["admin", "reviewer", "auditor"].includes(
                      session.user.role,
                    ),
                )
                .map(([path, title], index) => (
                  <NavLink key={path} to={path} end={index === 0 || path === "/inbox"}>
                    {title}
                  </NavLink>
                ))}
            </nav>
          )}
          <main key={location.pathname} ref={page} id="main-content" className="page-enter" tabIndex={-1}>
            <WorkspaceBoundary><Suspense fallback={<Loading />}><WorkspaceRoutes /></Suspense></WorkspaceBoundary>
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
