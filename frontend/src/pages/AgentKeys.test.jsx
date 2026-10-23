import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AgentKeys from "./AgentKeys";
import { api } from "../services/api";

vi.mock("../services/api", () => ({ api: vi.fn() }));
beforeEach(() => vi.clearAllMocks());

const registry = { tools: [{ name: "search_policy", class: "read", description: "Search documented policy evidence." }] };

test("keys expose only selected scopes and the new credential is displayed once", async () => {
  api.mockImplementation(async (path, options) => {
    if (path === "/agent-tools") return registry;
    if (path === "/agent-keys" && options?.method === "POST") return { id: "key-one", token: "test-private-key" };
    return [];
  });
  render(<AgentKeys />);
  await screen.findByText("No agent keys have been created.");
  expect(screen.queryByLabelText(/Authenticator|recovery code/i)).toBeNull();
  expect(screen.getByRole("button", { name: "Create scoped key" }).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText(/search_policy/));
  fireEvent.change(screen.getByLabelText("Agent name"), { target: { value: "Research agent" } });
  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "Test-password-long" } });
  fireEvent.click(screen.getByRole("button", { name: "Create scoped key" }));
  await screen.findByText("test-private-key");
  const body = api.mock.calls.find(([path, options]) => path === "/agent-keys" && options?.method === "POST")[1].body;
  expect(body.scopes).toEqual(["search_policy"]);
  expect(body.pseudonymize).toBe(true);
  expect(body.password).toBe("Test-password-long");
  expect(body).not.toHaveProperty("second_factor");
  expect(screen.getByLabelText("Current password").value).toBe("");
  fireEvent.click(screen.getByRole("button", { name: /I saved the key/ }));
  expect(screen.queryByText("test-private-key")).toBeNull();
});

test("revocation calls the server and a denied change never claims success", async () => {
  api.mockImplementation(async (path) => {
    if (path === "/agent-tools") return registry;
    if (path === "/agent-keys") return [{ id: "key-one", name: "Review bot", scopes: ["search_policy"], expires_at: "2026-11-01T00:00:00Z", daily_runs: 2, requests_per_minute: 10 }];
    throw new Error("Revocation could not be recorded.");
  });
  render(<AgentKeys />);
  await screen.findByText("Review bot");
  fireEvent.click(screen.getByRole("button", { name: "Revoke Review bot" }));
  await screen.findByText("Revocation could not be recorded.");
  await waitFor(() => expect(api).toHaveBeenCalledWith("/agent-keys/key-one/revoke", { method: "POST" }));
  expect(screen.queryByText(/Pending runs were cancelled/)).toBeNull();
});
