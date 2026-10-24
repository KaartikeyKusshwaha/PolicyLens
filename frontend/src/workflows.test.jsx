import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App";

const health = {
  ai: { status: "needs_key" },
  sanctions: { status: "not_synced", count: 0 },
};
const dashboard = {
  total: 0,
  flagged: 0,
  pending: 0,
  policies: 0,
  recent: [],
  events: [],
  health,
  operations: {
    transactions: 0,
    open_cases: 0,
    escalated: 0,
    overdue: 0,
    customers: 0,
    active_rules: 0,
  },
};
const user = {
  id: "user1",
  name: "Test Owner",
  email: "owner@example.invalid",
  org_id: "org1",
  workspace: "Test Workspace",
  role: "admin",
  csrf: "test-csrf",
};
const sources = {
  enabled_sources: ["ofac", "un", "uk"],
  feeds: ["ofac", "un", "uk"].map((id) => ({
    id,
    name: id.toUpperCase(),
    status: "not_synced",
    count: 0,
  })),
  groq: health.ai,
  max_age_hours: 24,
};
const response = (data, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => data,
});
const defaults = (url) =>
  url === "/api/evidence/digest"
    ? { generated_at: "2026-10-23T12:00:00Z", queues: Object.fromEntries(["open_cases", "overdue_cases", "control_drafts", "policy_changes"].map((name) => [name, { count: 0 }])), sources: [], source_warnings: 0, recent_alerts: 0, failed_runs: 0, invalid_due_dates: 0, scope: "Current workspace snapshot." }
    : url === "/api/traceability"
    ? { obligations: [], policies_without_current_analysis: [], available_controls: [], counts: { obligations: 0, with_gaps: 0, policies_without_current_analysis: 0 }, scope: "Explicit human mappings." }
    : url === "/api/retention"
    ? { active_policy: null, policies: [], holds: [], copies: [], deletion_requests: [] }
    : url.startsWith("/api/alerts?")
    ? { alerts: [], has_more: false, offset: 0, limit: 50 }
    : url === "/api/audit/checkpoints"
    ? { configured: false, status: "not_configured" }
    : url === "/api/auth/status"
    ? { setup_required: false }
    : url === "/api/auth/me"
      ? user
      : url === "/api/health"
        ? health
        : url === "/api/dashboard"
          ? dashboard
          : url === "/api/sources"
            ? sources
            : url === "/api/agents/catalog"
              ? { agents: [], daily_run_budget: 30 }
              : url === "/api/analytics"
                ? {
                    ...dashboard.operations,
                    resolved: 0,
                    jobs: {},
                    corridors: [],
                    dispositions: {},
                  }
                : url === "/api/audit"
                  ? {
                      events: [],
                      verification: {
                        valid: true,
                        entries_checked: 0,
                        head_hash: "0".repeat(64),
                        limitation: "Test checkpoint only.",
                      },
                    }
                  : url === "/api/preferences"
                    ? {
                        enabled_sources: ["ofac", "un", "uk"],
                        monitoring_enabled: false,
                        monitoring_interval_hours: 6,
                      }
                    : [];
function mockRoutes(routes) {
  fetch.mockImplementation(async (url, options) =>
    routes[url] ? routes[url](options) : response(defaults(url)),
  );
}
beforeEach(() => {
  window.history.replaceState({}, "", "/");
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url) => response(defaults(url))),
  );
});

test("signed audit download failures are visible to a read-only auditor", async () => {
  window.history.replaceState({}, "", "/audit");
  mockRoutes({
    "/api/auth/me": () => response({ ...user, role: "auditor" }),
    "/api/audit/checkpoints": () => response({ configured: true, status: "retained", fingerprint: "a".repeat(64), unanchored_events: 0 }),
    "/api/audit/checkpoints/export": () => response({ detail: { message: "Signed audit export is unavailable." } }, 409),
  });
  render(<App />);
  const button = await screen.findByRole("button", { name: "Export signed audit bundle" }, { timeout: 5000 });
  fireEvent.click(button);
  await screen.findByText("Signed audit export is unavailable.");
  expect(button.disabled).toBe(false);
});

test("ordinary sign-in sends only email and password", async () => {
  let signedIn = false;
  let submitted;
  mockRoutes({
    "/api/auth/me": () => response(signedIn ? user : { detail: "Sign in" }, signedIn ? 200 : 401),
    "/api/auth/login": (options) => { submitted = JSON.parse(options.body); signedIn = true; return response(user); },
  });
  render(<App />);
  const email = await screen.findByLabelText("Work email");
  expect(screen.queryByLabelText(/Authenticator|recovery code/i)).toBeNull();
  fireEvent.change(email, { target: { value: user.email } });
  fireEvent.change(screen.getByLabelText("Password", { exact: false }), { target: { value: "Test-only-password-2026" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign in", exact: true }));
  await waitFor(() => expect(submitted).toEqual({ email: user.email, password: "Test-only-password-2026" }));
});

test("unconfigured checkpoint storage never offers an unsigned substitute", async () => {
  window.history.replaceState({}, "", "/audit");
  render(<App />);
  await screen.findByText(/External checkpoint storage is not configured/);
  expect(screen.queryByRole("button", { name: "Export signed audit bundle" })).toBeNull();
  expect(screen.getByRole("button", { name: "Download sponsor evidence pack" }).disabled).toBe(true);
});

test("sponsor evidence pack failures remain visible and allow retry", async () => {
  window.history.replaceState({}, "", "/audit");
  mockRoutes({
    "/api/audit/checkpoints": () => response({ configured: true, status: "retained" }),
    "/api/evidence/sponsor-pack": () => response({ detail: { message: "Complete evidence exceeds the pilot export bound." } }, 413),
  });
  render(<App />);
  const button = await screen.findByRole("button", { name: "Download sponsor evidence pack" });
  await waitFor(() => expect(button.disabled).toBe(false));
  fireEvent.click(button);
  await screen.findByText("Complete evidence exceeds the pilot export bound.");
  expect(button.disabled).toBe(false);
});

const traceabilityFixture = {
  available_controls: [{ id: "control1", policy_id: "policy1", policy_version: "1", title: "Identity control", version: 1, status: "draft" }],
  obligations: [{ id: "obligation1", policy_id: "policy1", policy_version: "1", policy_title: "Identity policy", current_policy_version: true, analysis_job_id: "job1", analysis_at: "2026-10-22T00:00:00Z", obligation: "Verify the identity of sender and receiver.", citation: { quote: "Verify sender and receiver identity." }, analysis_scope: "Suggested obligations; not an exhaustive inventory.", analysis_coverage: { complete: false }, controls: [], gaps: ["no_linked_control"], status: "needs_review" }],
  policies_without_current_analysis: [], counts: { obligations: 1, with_gaps: 1, policies_without_current_analysis: 0 }, scope: "Explicit human mappings; observed alert volume does not measure accuracy.",
};

test("populated traceability shows citations, partial coverage and mapping failures", async () => {
  window.history.replaceState({}, "", "/policies/traceability");
  mockRoutes({
    "/api/traceability": () => response(traceabilityFixture),
    "/api/traceability/obligations/obligation1/links": () => response({ detail: { message: "Policy version changed. Refresh the matrix." } }, 409),
  });
  render(<App />);
  await screen.findByText("Verify the identity of sender and receiver.");
  expect(screen.getByText("Verify sender and receiver identity.")).toBeTruthy();
  expect(screen.getByText("The analysis used only part of the policy document.")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Control to map"), { target: { value: "control1" } });
  fireEvent.change(screen.getByLabelText(/Mapping rationale/), { target: { value: "Human-reviewed applicability mapping." } });
  fireEvent.click(screen.getByRole("button", { name: "Record mapping" }));
  await screen.findByText("Policy version changed. Refresh the matrix.");
});

test("auditors see traceability without mapping or model-run actions", async () => {
  window.history.replaceState({}, "", "/policies/traceability");
  mockRoutes({
    "/api/auth/me": () => response({ ...user, role: "auditor" }),
    "/api/traceability": () => response({ ...traceabilityFixture, policies_without_current_analysis: [{ id: "p2", title: "Unanalyzed current policy", version: "2" }] }),
  });
  render(<App />);
  await screen.findByText(/Unanalyzed current policy/);
  expect(screen.queryByRole("button", { name: "Record mapping" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Prepare cited obligation suggestions" })).toBeNull();
  expect(screen.queryByLabelText(/Mapping rationale/)).toBeNull();
});







test("imported alerts render source provenance without a fabricated control link", async () => {
  window.history.replaceState({}, "", "/cases/imported-case1");
  const external = { provider: "marble", instance: "fictional-instance", source_id: "source-case1", source_name: "Fictional upstream case", source_status: "closed", source_outcome: "false_positive", sha256: "a".repeat(64) };
  mockRoutes({
    "/api/cases/imported-case1": () => response({ id: "imported-case1", title: "Review imported Marble case", customer: { name: "Fictional customer", country: "IN", kyc_status: "pending" }, customer_id: "customer1", customer_name: "Fictional customer", created_at: "2026-10-01T00:00:00Z", due_at: "2026-10-23T00:00:00Z", status: "open", priority: "medium", description: "External source evidence for human review.", external_source: external, alerts: [{ id: "alert1", origin: "external_engine", external_source: { ...external, source_id: "source-decision1" }, rule_id: null, rule_title: "Imported Marble scenario", priority: "medium", facts: { source_outcome: "review", source_score: 70, trigger_object_id: "trigger1" }, created_at: "2026-10-01T00:00:00Z" }], screening_evidence: [], transactions: [], notes: [], tasks: [], agent_runs: [] }),
  });
  render(<App />);
  await screen.findByText("Imported source evidence");
  expect(screen.getByText("Fictional upstream case")).toBeTruthy();
  expect(screen.getByText(/Imported source outcome: review/)).toBeTruthy();
  expect(document.querySelector('a[href="/rules/null"]')).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url === "/api/customers/customer1/graph")).toBe(false);
  expect(screen.queryByRole("button", { name: "Relationships" })).toBeNull();
});

test("sponsor evidence download checks the archive type and releases its temporary URL", async () => {
  window.history.replaceState({}, "", "/audit");
  const archive = new Blob(["fixture zip bytes"], { type: "application/zip" });
  const create = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:fixture");
  const release = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  mockRoutes({
    "/api/audit/checkpoints": () => response({ configured: true, status: "retained" }),
    "/api/evidence/sponsor-pack": () => ({ ok: true, headers: new Headers({ "content-type": "application/zip" }), blob: async () => archive }),
  });
  render(<App />);
  const button = await screen.findByRole("button", { name: "Download sponsor evidence pack" });
  await waitFor(() => expect(button.disabled).toBe(false));
  fireEvent.click(button);
  await waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(create).toHaveBeenCalledWith(archive);
  expect(release).toHaveBeenCalledWith("blob:fixture");
  create.mockRestore();
  release.mockRestore();
  click.mockRestore();
});

test("empty inbox displays truthful zeroes and actionable setup", async () => {
  render(<App />);
  await screen.findByText("Work waiting for human review.");
  await screen.findByText("Prepare your workspace");
  expect(within(screen.getByRole("region", { name: "Workspace digest" })).getAllByText("0").length).toBe(6);
  expect(screen.getByRole("link", { name: "Connect evidence sources" }).getAttribute("href")).toBe("/settings/sources");
  expect(screen.getByRole("link", { name: "Prepare controls for independent approval" })).toBeTruthy();
  expect(screen.queryByText("API unreachable")).toBeNull();
});

test("private reset confirms passwords and removes the one-use token after completion", async () => {
  window.history.replaceState({}, "", "/reset-password#token=private-reset-token-for-tests-12345678901234567890&email=owner%40example.invalid");
  mockRoutes({"/api/auth/password-reset": () => response({password_reset: true, sessions_revoked: true})});
  render(<App />);
  await screen.findByText("Choose a new password");
  fireEvent.change(screen.getByLabelText(/^New password/), {target: {value: "New-private-password-2026"}});
  fireEvent.change(screen.getByLabelText("Confirm new password"), {target: {value: "Different-password-2026"}});
  fireEvent.click(screen.getByRole("button", {name: /Update password/}));
  await screen.findByText("The two passwords must match.");
  expect(fetch.mock.calls.filter(([url]) => url === "/api/auth/password-reset")).toHaveLength(0);
  fireEvent.change(screen.getByLabelText("Confirm new password"), {target: {value: "New-private-password-2026"}});
  fireEvent.click(screen.getByRole("button", {name: /Update password/}));
  await screen.findByText("Password updated");
  expect(window.location.hash).toBe("");
  const call = fetch.mock.calls.find(([url]) => url === "/api/auth/password-reset");
  expect(JSON.parse(call[1].body)).toEqual({email: "owner@example.invalid", token: "private-reset-token-for-tests-12345678901234567890", password: "New-private-password-2026"});
  expect(screen.getByRole("link", {name: "Sign in"}).getAttribute("href")).toBe("/");
});

test("evaluation surfaces provider failure and never shows a made-up verdict", async () => {
  window.history.replaceState({}, "", "/evaluate");
  mockRoutes({
    "/api/transactions/evaluate": () =>
      response(
        {
          detail: {
            code: "groq_rate_limited",
            message: "Provider limit reached. No decision recorded.",
          },
        },
        429,
      ),
  });
  render(<App />);
  await screen.findByLabelText("Amount");
  fireEvent.change(screen.getByLabelText("Amount"), {
    target: { value: "100" },
  });
  fireEvent.change(screen.getByLabelText("Sender’s full name"), {
    target: { value: "Test Sender" },
  });
  fireEvent.change(screen.getByLabelText("Sender’s country"), {
    target: { value: "India" },
  });
  fireEvent.change(screen.getByLabelText("Receiver’s full name"), {
    target: { value: "Test Receiver" },
  });
  fireEvent.change(screen.getByLabelText("Receiver’s country"), {
    target: { value: "UK" },
  });
  fireEvent.change(screen.getByLabelText(/Purpose & context/), {
    target: { value: "Documented services payment" },
  });
  fireEvent.submit(
    screen.getByRole("button", { name: /Run assessment/ }).closest("form"),
  );
  await screen.findByRole("alert");
  expect(
    screen.getByText("Provider limit reached. No decision recorded."),
  ).toBeTruthy();
  expect(window.location.pathname).toBe("/evidence/evaluate");
  expect(screen.queryByText("Advisory: no flag")).toBeNull();
});

test("sidebar navigation, theme, and policy input mode are interactive", async () => {
  render(<App />);
  await screen.findByText("Work waiting for human review.");
  fireEvent.click(screen.getByRole("button", { name: "Use dark theme" }));
  expect(localStorage.getItem("policylens-theme")).toBe("dark");
  fireEvent.click(screen.getByRole("link", { name: "Policies & Controls" }));
  fireEvent.click(await screen.findByRole("link", { name: "Policy library" }));
  fireEvent.click(await screen.findByRole("link", { name: /Add policy/ }));
  await screen.findByText("Add knowledge. Build clarity.");
  fireEvent.click(screen.getByRole("button", { name: /Upload document/ }));
  expect(screen.getByText("Choose a policy document")).toBeTruthy();
  expect(screen.queryByLabelText(/Policy content/)).toBeNull();
});

test("offline workspace offers a retry", async () => {
  fetch.mockRejectedValue(new Error("offline"));
  render(<App />);
  await screen.findByRole("alert");
  expect(
    screen.getByText(
      "Cannot reach PolicyLens. Check that the Python server is running.",
    ),
  ).toBeTruthy();
  expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
});

test("assistant uses server evidence and renders verified citations", async () => {
  window.history.replaceState({}, "", "/assistant");
  mockRoutes({
    "/api/query": () =>
      response({
        answer: "Your policy requires verified sender and receiver identity.",
        limitations: ["Only the supplied policies were considered."],
        citations: [
          {
            chunk_id: "test:1",
            title: "Identity policy",
            version: "1.0",
            quote: "Verify the identity of both parties.",
            source_url: "",
          },
        ],
      }),
  });
  render(<App />);
  await screen.findByLabelText("Your policy question");
  fireEvent.change(screen.getByLabelText("Your policy question"), {
    target: { value: "What identity checks are required?" },
  });
  fireEvent.submit(
    screen.getByRole("button", { name: /Ask assistant/ }).closest("form"),
  );
  await waitFor(() => expect(screen.getByText("Identity policy")).toBeTruthy());
  expect(screen.getByText("Verify the identity of both parties.")).toBeTruthy();
  const call = fetch.mock.calls.find(([url]) => url === "/api/query");
  expect(call[1].headers["X-CSRF-Token"]).toBe("test-csrf");
  expect(call[1].credentials).toBe("same-origin");
});

test("unauthenticated users must sign in before accessing customer records", async () => {
  window.history.replaceState({}, "", "/customers");
  mockRoutes({ "/api/auth/me": () => response({ detail: "Sign in" }, 401) });
  render(<App />);
  await screen.findByRole("heading", { name: "Welcome back." });
  expect(screen.getByLabelText(/^Password/).type).toBe("password");
  expect(fetch.mock.calls.some(([url]) => url === "/api/customers")).toBe(
    false,
  );
});

test("first owner setup requires the server bootstrap key", async () => {
  mockRoutes({ "/api/auth/status": () => response({ setup_required: true }) });
  render(<App />);
  await screen.findByRole("heading", { name: "Create your first workspace" });
  expect(screen.getByLabelText(/^Local bootstrap key/).required).toBe(true);
  expect(screen.getByLabelText("Workspace name").required).toBe(true);
});

test("static-only deployments show a clear missing API error", async () => {
  fetch.mockResolvedValue({
    ok: true,
    json: async () => {
      throw new SyntaxError("HTML");
    },
  });
  render(<App />);
  await screen.findByText(
    /This deployment needs the PolicyLens backend connected/,
  );
});

test("auditors can browse customers without a create action", async () => {
  window.history.replaceState({}, "", "/customers");
  mockRoutes({ "/api/auth/me": () => response({ ...user, role: "auditor" }) });
  render(<App />);
  await screen.findByText("Start with the people behind the payments.");
  expect(screen.queryByRole("link", { name: /Add customer/ })).toBeNull();
});

test.each([
  ["/rules/rule1/edit", "existing control"],
  ["/rules/new?policy=p1", "policy-linked new control"],
])("delayed policy options preserve the selected policy for %s (%s)", async (path) => {
  window.history.replaceState({}, "", path);
  let resolvePolicies;
  const pendingPolicies = new Promise((resolve) => { resolvePolicies = resolve; });
  mockRoutes({
    "/api/rules/rule1": () => response({ id: "rule1", title: "Existing control", kind: "amount", policy_id: "p1", threshold: "4000", currency: "USD", priority: "high", description: "Synthetic control rationale" }),
    "/api/policies": () => pendingPolicies,
  });
  render(<App />);
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url === "/api/policies")).toBe(true));
  await act(async () => {});
  await act(async () => {
    resolvePolicies(response([
      { id: "p2", title: "New unrelated policy", version: "1" },
      { id: "p1", title: "Original linked policy", version: "1.1" },
    ]));
  });
  expect((await screen.findByLabelText("Linked policy")).value).toBe("p1");
});

test("policy loading failures prevent saving a control against missing options", async () => {
  window.history.replaceState({}, "", "/rules/new");
  mockRoutes({ "/api/policies": () => response({ detail: { message: "Policy inventory unavailable." } }, 503) });
  render(<App />);
  await screen.findByText("Policy inventory unavailable.");
  expect(screen.queryByRole("button", { name: "Save draft for review" })).toBeNull();
});

test("editing a corridor control preserves its type and country list", async () => {
  window.history.replaceState({}, "", "/rules/rule1/edit");
  mockRoutes({
    "/api/rules/rule1": () =>
      response({
        id: "rule1",
        title: "Corridor review",
        kind: "corridor",
        countries: ["AE"],
        policy_id: "p1",
        description: "Internal corridor monitoring",
        priority: "high",
      }),
    "/api/policies": () =>
      response([{ id: "p1", title: "Internal policy", version: "1" }]),
  });
  render(<App />);
  expect((await screen.findByLabelText("Control type")).value).toBe("corridor");
  expect(screen.getByLabelText(/^Destination country codes/).value).toBe("AE");
  expect(screen.queryByLabelText("Amount threshold")).toBeNull();
});

test("failed agents expose the failure and never display an invented brief", async () => {
  window.history.replaceState({}, "", "/preparation/run1");
  mockRoutes({
    "/api/agents/jobs/run1": () =>
      response({
        id: "run1",
        kind: "screening",
        state: "failed",
        created_at: "2026-10-01T00:00:00Z",
        steps: [],
        payload: {
          model: "test-model",
          max_model_calls: 1,
          model_attempts: 1,
          error: {
            message: "Source evidence is stale. Refresh and start a new run.",
          },
        },
      }),
  });
  render(<App />);
  await screen.findByText(
    "Source evidence is stale. Refresh and start a new run.",
  );
  expect(screen.queryByText("A reviewable starting point.")).toBeNull();
  expect(screen.getByRole("button", { name: /Cancel/ })).toBeTruthy();
});

test.each([
  ["/monitoring", "Every transaction adds context."],
  ["/cases", "From alert to accountable decision."],
  ["/rules", "Controls your team can explain."],
  ["/changes", "Understand what changed. Track what follows."],
  ["/audit", "Evidence packs and audit trail"],
  ["/settings", "Make the workspace work for your team."],
  ["/sources", "Connections and freshness"],
])(
  "product route %s renders its empty workspace without errors",
  async (path, heading) => {
    window.history.replaceState({}, "", path);
    render(<App />);
    await screen.findByRole("heading", { name: heading });
    await waitFor(() => expect(fetch.mock.calls.length).toBeGreaterThan(2));
    expect(screen.queryByRole("alert")).toBeNull();
  },
);

test("account settings offer authenticated password rotation", async () => {
  window.history.replaceState({}, "", "/settings");
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Account" }));
  expect(screen.getByLabelText("Current password").type).toBe("password");
  expect(screen.getByLabelText("New password").minLength).toBe(12);
});

test("four primary areas remain active through populated review and evidence routes", async () => {
  const pending = { id: "pending-control", title: "Pending threshold proposal", version: 2, status: "draft", created_by: user.id, tuning_receipt_id: "receipt1" };
  mockRoutes({
    "/api/cases": () => response([{ id: "case-work", title: "Overdue fictional investigation", customer_name: "Fictional customer", status: "investigating", due_at: "2026-01-01T00:00:00Z" }]),
    "/api/rules": () => response([pending]),
    "/api/traceability": () => response(traceabilityFixture),
    "/api/audit/checkpoints": () => response({ configured: true, status: "retained", fingerprint: "a".repeat(64) }),
  });
  render(<App />);
  await screen.findByText("Overdue fictional investigation");
  expect(screen.getByText("Different reviewer required")).toBeTruthy();
  const primary = screen.getByRole("navigation", { name: "Main navigation" });
  expect(within(primary).getAllByRole("link").map(link => link.textContent)).toEqual(["Inbox", "Policies & Controls", "Evidence", "Settings"]);
  fireEvent.click(within(primary).getByRole("link", { name: "Policies & Controls" }));
  await screen.findByText("Verify the identity of sender and receiver.");
  expect(within(primary).getByRole("link", { name: "Policies & Controls" }).getAttribute("aria-current")).toBe("page");
  fireEvent.click(within(primary).getByRole("link", { name: "Evidence" }));
  await screen.findByText("Sponsor evidence pack");
  expect(screen.queryByText("Observed destination corridors")).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url === "/api/analytics")).toBe(false);
  fireEvent.click(within(primary).getByRole("link", { name: "Settings" }));
  await screen.findByText("Workspace members");
  fireEvent.click(screen.getByRole("link", { name: "Connections" }));
  await screen.findByRole("heading", { name: "Connections and freshness" });
  expect(within(primary).getByRole("link", { name: "Settings" }).getAttribute("aria-current")).toBe("page");
  expect(fetch.mock.calls.some(([url]) => url.startsWith("/api/inbox") || url.startsWith("/api/evidence/assessments"))).toBe(false);
});

test("legacy case bookmarks preserve customer context, query and fragment", async () => {
  window.history.replaceState({}, "", "/cases?customer=customer1#open");
  mockRoutes({ "/api/customers": () => response([{ id: "customer1", name: "Selected fictional customer" }]) });
  render(<App />);
  await screen.findByRole("heading", { name: "Open a customer investigation" });
  await waitFor(() => expect(screen.getByLabelText("Customer").value).toBe("customer1"));
  expect(window.location.pathname).toBe("/inbox/cases");
  expect(window.location.search).toBe("?customer=customer1");
  expect(window.location.hash).toBe("#open");
});

test("inbox failures do not masquerade as an empty queue or a zero case count", async () => {
  mockRoutes({ "/api/cases": () => response({ detail: { message: "Case inventory temporarily unavailable." } }, 503), "/api/evidence/digest": () => response({ detail: { message: "Complete digest unavailable." } }, 409) });
  render(<App />);
  await screen.findByText("Case inventory temporarily unavailable.");
  expect(screen.queryByText("No open investigations in the loaded queue.")).toBeNull();
  expect(screen.queryByText("Prepare your workspace")).toBeNull();
  await screen.findByText("Complete digest unavailable.");
  expect(within(screen.getByRole("region", { name: "Workspace digest" })).queryByText("0")).toBeNull();
  expect(screen.getAllByRole("button", { name: "Retry" }).length).toBe(2);
});

test("alert pagination keeps source provenance and a way back from an empty page", async () => {
  window.history.replaceState({}, "", "/inbox/alerts");
  mockRoutes({
    "/api/alerts?limit=50&offset=0": () => response({ alerts: [{ id: "a1", case_id: "c1", rule_title: "Imported review signal", origin: "external_engine", external_source: { provider: "marble" }, created_at: "2026-10-01T00:00:00Z" }, { id: "a2", case_id: "c2", rule_title: "Internal threshold signal", created_at: "2026-10-01T00:00:00Z" }], has_more: true }),
    "/api/alerts?limit=50&offset=50": () => response({ alerts: [], has_more: false }),
  });
  render(<App />);
  await screen.findByText("Imported review signal");
  expect(screen.getByText("marble")).toBeTruthy();
  expect(screen.getByText("Starter monitoring engine")).toBeTruthy();
  expect(document.querySelector('a[href="/inbox/cases/c1"]')).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Next alerts" }));
  await screen.findByText("No alerts on this page.");
  expect(screen.getByRole("button", { name: "Next alerts" }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Previous alerts" }));
  await screen.findByText("Imported review signal");
});

test("connection overview hides raw source metadata until advanced inspection", async () => {
  window.history.replaceState({}, "", "/settings/sources");
  mockRoutes({ "/api/sources": () => response({ ...sources, feeds: sources.feeds.map((feed, index) => ({ ...feed, status: index === 0 ? "ready" : "stale", sha256: "a".repeat(64) })) }) });
  render(<App />);
  await screen.findByText(/1 of 3 enabled feeds are fresh/);
  expect(screen.queryByText("Snapshot checksum")).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "Inspect per-source dates, checksums and sync controls" }));
  await screen.findByRole("heading", { name: "Sanctions source details" });
  expect(screen.getAllByText("Snapshot checksum").length).toBe(3);
  expect(window.location.pathname).toBe("/advanced/sources");
});

test("connection sync reports partial progress and stops after a feed failure", async () => {
  window.history.replaceState({}, "", "/settings/sources");
  let firstStored = false;
  mockRoutes({
    "/api/sources": () => response({ ...sources, feeds: sources.feeds.map((feed, index) => ({ ...feed, status: index === 0 && firstStored ? "ready" : "not_synced" })) }),
    "/api/sources/ofac/sync": () => { firstStored = true; return response({ count: 100 }); },
    "/api/sources/un/sync": () => response({ detail: { message: "Second feed validation failed." } }, 502),
  });
  render(<App />);
  const button = await screen.findByRole("button", { name: "Sync enabled feeds" });
  fireEvent.click(button);
  await screen.findByText("1 enabled feeds completed before the failure. Second feed validation failed.");
  await screen.findByText(/1 of 3 enabled feeds are fresh/);
  expect(fetch.mock.calls.some(([url]) => url === "/api/sources/uk/sync")).toBe(false);
  expect(screen.queryByText("3 enabled feeds downloaded and validated.")).toBeNull();
  expect(button.disabled).toBe(false);
});

test("additional analytics are reachable only through advanced navigation", async () => {
  window.history.replaceState({}, "", "/evidence");
  render(<App />);
  await screen.findByRole("heading", { name: "Evidence packs and audit trail" });
  expect(screen.queryByText("Observed destination corridors")).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "Advanced diagnostics" }));
  await screen.findByRole("heading", { name: "Diagnostics and detailed records" });
  fireEvent.click(screen.getByRole("link", { name: "Additional activity analytics" }));
  await screen.findByText("Observed destination corridors");
  expect(screen.queryByText("Sponsor evidence pack")).toBeNull();
  expect(window.location.pathname).toBe("/advanced/analytics");
});



test("case work shows a cited draft without exposing raw operations inline", async () => {
  window.history.replaceState({}, "", "/inbox/cases/case-brief");
  const brief = { summary: "Synthetic evidence-grounded brief remains a draft for independent human review.", recommendation: "investigate", citations: [{ chunk_id: "p1:1:0", policy_id: "p1", title: "Synthetic identity policy", version: "1", quote: "Verify sender and receiver identity.", source_url: "" }], limitations: ["Only the supplied evidence was inspected."] };
  mockRoutes({ "/api/cases/case-brief": () => response({ id: "case-brief", title: "Review the fictional transfer", customer_id: "customer1", customer_name: "Fictional customer", customer: { name: "Fictional customer", country: "IN", kyc_status: "pending" }, status: "open", priority: "medium", created_at: "2026-10-01T00:00:00Z", description: "Synthetic investigation context.", alerts: [], transactions: [], screening_evidence: [], notes: [], tasks: [], agent_runs: [{ id: "brief-run", kind: "investigation", state: "completed", created_at: "2026-10-01T00:00:00Z", payload: { result: brief } }] }) });
  render(<App />);
  await screen.findByRole("heading", { name: "Review the fictional transfer" });
  fireEvent.click(screen.getByRole("button", { name: "Drafts" }));
  await screen.findByText(brief.summary);
  expect(screen.getByText("Verify sender and receiver identity.")).toBeTruthy();
  expect(screen.getByText(/does not change the case disposition/)).toBeTruthy();
  expect(document.querySelector('a[href="/preparation/brief-run"]')).toBeTruthy();
  expect(screen.queryByText("Collected step outputs")).toBeNull();
    expect(screen.getByText(/final transaction selection summary was not retained/)).toBeTruthy();
});

test("case draft shows retained sample arithmetic and quotation-verification limits", async () => {
  window.history.replaceState({}, "", "/inbox/cases/case-sample");
  const brief = { summary: "The model claims five transactions; the retained sample contains four.", model_input_scope: { record_count: 4, totals_by_currency: { EUR: "0.30", USD: "9200.00" }, scope: "Latest four records, not full customer history." }, citations: [], limitations: [] };
  mockRoutes({ "/api/cases/case-sample": () => response({ id: "case-sample", title: "Review sample arithmetic", customer_id: "customer1", customer_name: "Fictional customer", customer: { name: "Fictional customer", country: "IN", kyc_status: "pending" }, status: "open", priority: "medium", created_at: "2026-10-01T00:00:00Z", description: "Synthetic context.", alerts: [], transactions: [], screening_evidence: [], notes: [], tasks: [], agent_runs: [{ id: "sample-run", kind: "investigation", state: "completed", created_at: "2026-10-01T00:00:00Z", payload: { result: brief } }] }) });
  render(<App />);
  await screen.findByRole("heading", { name: "Review sample arithmetic" });
  fireEvent.click(screen.getByRole("button", { name: "Drafts" }));
  const sample = await screen.findByRole("region", { name: "Transaction sample selected for this run" });
  expect(within(sample).getByText(/4 selected transaction records/)).toBeTruthy();
  expect(within(sample).getByText("0.30")).toBeTruthy();
  expect(within(sample).getByText("9200.00")).toBeTruthy();
  expect(screen.getByText(/Policy quotation checks do not verify/)).toBeTruthy();
  expect(screen.getByText(brief.summary)).toBeTruthy();
  expect(screen.queryByText(/final transaction selection summary was not retained/)).toBeNull();
});

test("navigation drawer traps keyboard focus and Escape restores its trigger", async () => {
  render(<App />);
  await screen.findByRole("heading", { name: "Work waiting for human review." });
  const trigger = screen.getByRole("button", { name: "Open navigation" });
  fireEvent.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "Workspace navigation" });
  const first = within(dialog).getByRole("button", { name: "Close workspace navigation" });
  const last = within(dialog).getByRole("link", { name: "Advanced diagnostics" });
  expect(document.activeElement).toBe(first);
  expect(document.querySelector(".main-shell").hasAttribute("inert")).toBe(true);
  fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
  expect(document.activeElement).toBe(last);
  fireEvent.keyDown(last, { key: "Tab" });
  expect(document.activeElement).toBe(first);
  fireEvent.keyDown(first, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(trigger);
  expect(trigger.getAttribute("aria-expanded")).toBe("false");
});

test("settings section links are shareable without key management", async () => {
  window.history.replaceState({}, "", "/settings");
  mockRoutes({ "/api/auth/me": () => response({ ...user, role: "auditor" }) });
  render(<App />);
  await screen.findByText("Make the workspace work for your team.");
  expect(fetch.mock.calls.some(([url]) => url === "/api/agent-keys")).toBe(false);
  fireEvent.click(screen.getByRole("link", { name: "Workspace & account" }));
  await screen.findByText("Make the workspace work for your team.");
  fireEvent.click(screen.getByRole("button", { name: "Account" }));
  expect(window.location.search).toBe("?section=Account");
  expect(screen.getByLabelText("Current password")).toBeTruthy();
});

test("a favorable assessment remains advisory and auditor access offers no review mutation", async () => {
  window.history.replaceState({}, "", "/evidence/assessments/advisory1");
  mockRoutes({
    "/api/auth/me": () => response({ ...user, role: "auditor" }),
    "/api/decisions/advisory1": () => response({ id: "advisory1", created_at: "2026-10-01T00:00:00Z", model: "test-model", processing_time_ms: 1000, transaction: { transaction_id: "FICTIONAL-ADVISORY", amount: "100", currency: "USD", sender: "Fictional sender", receiver: "Fictional receiver", sender_country: "India", receiver_country: "UK", description: "Synthetic assessment for interface verification." }, assessment: { verdict: "acceptable", risk_score: 10, reasoning: "No flag was identified within the supplied synthetic evidence scope.", risk_factors: [], citations: [], limitations: ["This is not legal approval or sanctions clearance."] }, screening: { matches: [], scope: "No match is not clearance.", source: { id: "ofac", name: "Synthetic source", sha256: "a".repeat(64), fetched_at: "2026-10-01T00:00:00Z", url: "https://example.invalid/feed" } }, exchange: { amount_usd: "100", base: "USD", rate: "1", date: "2026-10-01", source: "identity" }, reviews: [] }),
  });
  render(<App />);
  await screen.findByRole("heading", { name: "FICTIONAL-ADVISORY" });
  expect(screen.getByRole("heading", { name: "Advisory: no flag" })).toBeTruthy();
  expect(screen.getByText("No match is not clearance.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Record review" })).toBeNull();
  expect(screen.getByText(/only an authorized administrator or reviewer can append a review/)).toBeTruthy();
});
