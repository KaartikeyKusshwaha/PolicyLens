import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import WorkDigest from "./WorkDigest";
import { api } from "../services/api";

vi.mock("../services/api", () => ({ api: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
const fixture = {
  generated_at: "2026-10-23T12:00:00Z",
  queues: Object.fromEntries(
    ["open_cases", "overdue_cases", "control_drafts", "policy_changes"].map(
      (name) => [name, { count: 5 }],
    ),
  ),
  sources: [
    { id: "ofac", name: "OFAC SDN", status: "stale" },
    { id: "un", name: "United Nations", status: "not_synced" },
  ],
  source_warnings: 2,
  recent_alerts: 12,
  failed_runs: 3,
  invalid_due_dates: 1,
  scope:
    "Refresh to detect changes; no email or background notification is sent.",
};
const show = () =>
  render(
    <MemoryRouter>
      <WorkDigest />
    </MemoryRouter>,
  );

test("digest exposes stale evidence, invalid dates and human follow-up links", async () => {
  api.mockResolvedValue(fixture);
  show();
  await screen.findByText("Sanctions evidence needs attention");
  expect(
    screen.getByText("OFAC SDN: stale or invalid retrieval time"),
  ).toBeTruthy();
  expect(screen.getByText("United Nations: not synced")).toBeTruthy();
  expect(screen.getByText(/cannot be classified as overdue/)).toBeTruthy();
  expect(
    screen
      .getByRole("link", { name: "Review and sync evidence sources" })
      .getAttribute("href"),
  ).toBe("/settings/sources");
  expect(screen.getByText("3")).toBeTruthy();
  expect(screen.queryByRole("link", { name: "3" })).toBeNull();
  expect(api.mock.calls[0][0]).toBe("/evidence/digest");
});

test("failed refresh hides previous counts and supports explicit retry", async () => {
  api
    .mockResolvedValueOnce(fixture)
    .mockRejectedValueOnce(new Error("Complete digest unavailable"))
    .mockResolvedValueOnce(fixture);
  show();
  await screen.findByText("12");
  fireEvent.click(screen.getByRole("button", { name: "Refresh digest" }));
  await screen.findByText("Complete digest unavailable");
  expect(screen.queryByText("12")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByText("12");
});

test("fresh retrieval wording keeps screening limits visible", async () => {
  api.mockResolvedValue({
    ...fixture,
    source_warnings: 0,
    invalid_due_dates: 0,
  });
  show();
  await screen.findByText(/No match is not clearance/);
  expect(screen.queryByText("Sanctions evidence needs attention")).toBeNull();
});
