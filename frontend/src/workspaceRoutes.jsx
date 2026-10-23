import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Inbox from "./pages/Inbox";
import Evaluate from "./pages/Evaluate";
import { Policies, PolicyEditor } from "./pages/Policies";
import Assistant from "./pages/Assistant";
import { Decisions, DecisionDetail } from "./pages/Decisions";
import Sources from "./pages/Sources";
import { Customers, CustomerEditor, CustomerDetail } from "./pages/Customers";
import Monitoring from "./pages/Monitoring";
import { Cases, CaseDetail } from "./pages/Cases";
import { AgentOperations, AgentRun } from "./pages/AgentOperations";
import { Controls, ControlEditor, ControlDetail } from "./pages/Controls";
import { PolicyChanges, ChangeDetail } from "./pages/PolicyChanges";
import AuditAnalytics from "./pages/AuditAnalytics";
import ActivityAnalytics from "./pages/ActivityAnalytics";
import WorkspaceSettings from "./pages/WorkspaceSettings";
import Traceability from "./pages/Traceability";
import ControlCode from "./pages/ControlCode";
import EngineImports from "./pages/EngineImports";
import Retention from "./pages/Retention";
import AgentKeys from "./pages/AgentKeys";
import { PageHeading } from "./components";
import { useSession } from "./session";
import { legacyDestination } from "./navigation";

function LegacyRedirect() {
  const location = useLocation();
  return (
    <Navigate
      replace
      to={legacyDestination(
        location.pathname + location.search + location.hash,
      )}
    />
  );
}
function Keys() {
  const { user } = useSession();
  return (
    <>
      <PageHeading eyebrow="GOVERNED ACCESS" title="Agent keys and permissions">
        Scoped credentials identify each agent. Agents prepare; human reviewers
        approve.
      </PageHeading>
      {user.role === "admin" ? (
        <AgentKeys />
      ) : (
        <p>Only workspace administrators can manage agent keys.</p>
      )}
    </>
  );
}
function Advanced() {
  return (
    <>
      <PageHeading eyebrow="ADVANCED" title="Diagnostics and detailed records">
        Inspect execution logs, activity breakdowns and source metadata.
      </PageHeading>
      <section className="panel section-padding">
        <div className="compact-records">
          <Link to="/advanced/agents">Raw agent operations and run logs</Link>
          <Link to="/advanced/analytics">Additional activity analytics</Link>
          <Link to="/advanced/sources">Per-source sanctions details</Link>
        </div>
      </section>
    </>
  );
}

export default function WorkspaceRoutes() {
  return (
    <Routes>
      <Route path="/inbox" element={<Inbox />} />
      <Route path="/inbox/alerts" element={<Inbox view="alerts" />} />
      <Route path="/inbox/approvals" element={<Inbox view="approvals" />} />
      <Route path="/inbox/cases" element={<Cases />} />
      <Route path="/inbox/cases/:id" element={<CaseDetail />} />
      <Route path="/inbox/customers" element={<Customers />} />
      <Route path="/inbox/customers/new" element={<CustomerEditor />} />
      <Route path="/inbox/customers/:id" element={<CustomerDetail />} />
      <Route path="/inbox/customers/:id/edit" element={<CustomerEditor />} />
      <Route path="/inbox/transactions" element={<Monitoring />} />
      <Route path="/policies" element={<Traceability />} />
      <Route path="/policies/library" element={<Policies />} />
      <Route path="/policies/library/new" element={<PolicyEditor />} />
      <Route path="/policies/library/:id/edit" element={<PolicyEditor />} />
      <Route path="/policies/controls" element={<Controls />} />
      <Route path="/policies/controls/new" element={<ControlEditor />} />
      <Route path="/policies/controls/:id" element={<ControlDetail />} />
      <Route path="/policies/controls/:id/edit" element={<ControlEditor />} />
      <Route path="/policies/controls/code" element={<ControlCode />} />
      <Route path="/policies/changes" element={<PolicyChanges />} />
      <Route path="/policies/changes/:id" element={<ChangeDetail />} />
      <Route path="/policies/assistant" element={<Assistant />} />
      <Route path="/evidence" element={<AuditAnalytics />} />
      <Route path="/evidence/assessments" element={<Decisions />} />
      <Route path="/evidence/assessments/:id" element={<DecisionDetail />} />
      <Route path="/evidence/evaluate" element={<Evaluate />} />
      <Route path="/settings" element={<WorkspaceSettings />} />
      <Route path="/settings/sources" element={<Sources />} />
      <Route path="/settings/agents" element={<Keys />} />
      <Route path="/settings/runs" element={<AgentOperations />} />
      <Route path="/settings/imports" element={<EngineImports />} />
      <Route path="/settings/retention" element={<Retention />} />
      <Route path="/advanced" element={<Advanced />} />
      <Route path="/advanced/agents" element={<AgentOperations advanced />} />
      <Route path="/advanced/agents/:id" element={<AgentRun />} />
      <Route path="/advanced/analytics" element={<ActivityAnalytics />} />
      <Route path="/advanced/sources" element={<Sources advanced />} />
      {[
        "/",
        "/customers/*",
        "/cases/*",
        "/monitoring",
        "/agents/*",
        "/rules/*",
        "/changes/*",
        "/audit",
        "/evaluate",
        "/policies/new",
        "/policies/:id/edit",
        "/policies/traceability",
        "/assistant",
        "/query",
        "/decisions/*",
        "/sources",
        "/external-data",
      ].map((path) => (
        <Route key={path} path={path} element={<LegacyRedirect />} />
      ))}
      <Route
        path="*"
        element={
          <div className="empty">
            <h1>Page not found</h1>
            <Link to="/inbox">Back to Inbox</Link>
          </div>
        }
      />
    </Routes>
  );
}
