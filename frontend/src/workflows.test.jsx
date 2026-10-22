import React from "react";
import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  url === "/api/audit/checkpoints"
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
  const button = await screen.findByRole("button", { name: "Export signed audit bundle" });
  fireEvent.click(button);
  await screen.findByText("Signed audit export is unavailable.");
  expect(button.disabled).toBe(false);
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

test("control YAML export, preview and draft import preserve the review boundary", async () => {
  window.history.replaceState({}, "", "/rules/code?control_id=control1");
  const yaml = "schema_version: policylens.controls.v1\ncontrols: []\n";
  const item = { key: "control-key", policy: { version: "1.0" }, replaces: { id: "control1" }, configuration: { title: "Reviewed threshold draft", threshold: "250.00" } };
  mockRoutes({
    "/api/control-code/export?control_id=control1": () => ({ ok: true, headers: new Headers({ "content-type": "application/yaml; charset=utf-8" }), text: async () => yaml }),
    "/api/control-code/preview": () => response({ preview_sha256: "a".repeat(64), count: 1, controls: [item], scope: "Imported controls need independent in-app approval." }),
    "/api/control-code/import": () => response({ controls: [{ key: "control-key", control: { id: "draft2", title: "Reviewed threshold draft", version: 2 } }], replayed: false }, 201),
  });
  render(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Load control YAML" }));
  await waitFor(() => expect(screen.getByLabelText("Control YAML").value).toBe(yaml));
  fireEvent.click(screen.getByRole("button", { name: "Preview YAML" }));
  await screen.findByRole("heading", { name: "Preview: 1 control drafts" });
  fireEvent.click(screen.getByRole("button", { name: "Import reviewed drafts" }));
  await screen.findByText("These new drafts require independent approval before activation.");
  expect(screen.getByRole("link", { name: "Reviewed threshold draft" }).getAttribute("href")).toBe("/rules/draft2");
  const imported = fetch.mock.calls.find(([url]) => url === "/api/control-code/import");
  expect(JSON.parse(imported[1].body).preview_sha256).toBe("a".repeat(64));
});

test("changing YAML clears its preview and auditors cannot import", async () => {
  window.history.replaceState({}, "", "/rules/code");
  mockRoutes({
    "/api/control-code/preview": () => response({ preview_sha256: "b".repeat(64), count: 1, controls: [], scope: "Draft only." }),
  });
  const view = render(<App />);
  fireEvent.change(await screen.findByLabelText("Control YAML"), { target: { value: "test YAML content" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview YAML" }));
  await screen.findByRole("button", { name: "Import reviewed drafts" });
  fireEvent.change(screen.getByLabelText("Control YAML"), { target: { value: "changed after preview" } });
  expect(screen.queryByRole("button", { name: "Import reviewed drafts" })).toBeNull();
  view.unmount();
  mockRoutes({ "/api/auth/me": () => response({ ...user, role: "auditor" }) });
  render(<App />);
  await screen.findByRole("heading", { name: "Controls as code" });
  expect(screen.queryByRole("button", { name: "Preview YAML" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Import reviewed drafts" })).toBeNull();
});

test("engine imports require customer mapping and a fresh preview before commit", async () => {
  window.history.replaceState({}, "", "/settings/imports");
  const sourceId = "11111111-1111-4111-8111-111111111111";
  mockRoutes({
    "/api/customers": () => response([{ id: "customer1", name: "Fictional customer", external_id: "C-1" }]),
    "/api/adapters/marble/preview": options => {
      const mapped = JSON.parse(options.body).bundle.customer_mappings.length > 0;
      return response({ preview_sha256: "a".repeat(64), can_import: mapped, objects: [{ id: "object1", object_type: "case", source_id: sourceId, source_name: "Upstream fictional case", action: "new", creates_alert: false, errors: mapped ? [] : ["customer_mapping_required"], customer_id: mapped ? "customer1" : null }], scope: "Selected records; local cases stay open for review." });
    },
    "/api/adapters/marble/import": () => response({ replayed: false, objects: [{ local_case_id: "imported-case1" }] }, 201),
  });
  render(<App />);
  fireEvent.change(await screen.findByLabelText(/Marble instance label/), { target: { value: "fictional-instance" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview engine import" }));
  await screen.findByText(/Customer Mapping Required/);
  expect(screen.getByRole("button", { name: "Import reviewed engine records" }).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText(new RegExp(`Customer mapping for ${sourceId}`)), { target: { value: "customer1" } });
  expect(screen.getByRole("button", { name: "Import reviewed engine records" }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Preview engine import" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Import reviewed engine records" }).disabled).toBe(false));
  fireEvent.click(screen.getByRole("button", { name: "Import reviewed engine records" }));
  expect((await screen.findByRole("link", { name: "Open imported investigation" })).getAttribute("href")).toBe("/cases/imported-case1");
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

test("empty dashboard displays truthful zeroes and actionable onboarding", async () => {
  render(<App />);
  await screen.findByText("Your next decision, in context.");
  expect(screen.getByText("0 / 4")).toBeTruthy();
  expect(screen.getByText("Get your operation ready")).toBeTruthy();
  expect(screen.getByText("0 of 3 enabled feeds are fresh.")).toBeTruthy();
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
  expect(window.location.pathname).toBe("/evaluate");
  expect(screen.queryByText("Acceptable")).toBeNull();
});

test("sidebar navigation, theme, and policy input mode are interactive", async () => {
  render(<App />);
  await screen.findByText("Your next decision, in context.");
  fireEvent.click(screen.getByRole("button", { name: "Use dark theme" }));
  expect(localStorage.getItem("policylens-theme")).toBe("dark");
  fireEvent.click(screen.getByRole("link", { name: "Policy library" }));
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
  window.history.replaceState({}, "", "/agents/run1");
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
  ["/agents", "Your evidence desk, on demand."],
  ["/rules", "Controls your team can explain."],
  ["/changes", "Understand what changed. Track what follows."],
  ["/audit", "A clear view of the work—and its record."],
  ["/settings", "Make the workspace work for your team."],
  ["/sources", "Intelligence you can trace."],
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
