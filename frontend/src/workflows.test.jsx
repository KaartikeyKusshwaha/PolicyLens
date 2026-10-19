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
  url === "/api/auth/status"
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
