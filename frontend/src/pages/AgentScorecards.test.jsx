import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AgentScorecards from "./AgentScorecards";
import { api } from "../services/api";
import retainedReport from "../../../evaluation/results/20261023-gpt-oss-20b/scorecard.json";

vi.mock("../services/api", () => ({ api: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
const fixture = {
  report: retainedReport,
  verification: { terminal_runs_recomputed: 50, trusted_scorecard_sha256: retainedReport.scorecard_sha256, dataset_sha256: retainedReport.dataset_sha256, scope: "Retained-run recomputation, not provider or label authentication." },
  notice: "Public synthetic reference. This does not measure this workspace's customers or current model behavior.",
  workspace_measurement: false, promotion_allowed: false,
};

test("live synthetic reference keeps failures, denominator limits and failed promotion visible", async () => {
  api.mockResolvedValue(fixture);
  render(<AgentScorecards />);
  await screen.findByRole("heading", { name: "Agent scorecard" });
  expect(screen.getByText(/automatic preparation remains disabled/)).toBeTruthy();
  expect(screen.getByText(/does not measure this workspace's customers/)).toBeTruthy();
  expect(screen.getByText("109/109")).toBeTruthy();
  expect(screen.getByText("86.0%")).toBeTruthy();
  expect(screen.getByText(/4 failed or incomplete runs · 4 without an inspectable draft/)).toBeTruthy();
  expect(screen.getByRole("heading", { name: "Quality gate: not passed" })).toBeTruthy();
  expect(screen.getAllByText("invalid_ai_response").length).toBe(4);
  expect(screen.getByText(/raw model token hallucination rates/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Enable|Approve|Promote|Activate/ })).toBeNull();
});

test("an unavailable complete result shows retry and no cached substitute metrics", async () => {
  api.mockRejectedValueOnce(new Error("The complete retained evaluation could not be verified.")).mockResolvedValueOnce(fixture);
  render(<AgentScorecards />);
  await screen.findByText("The complete retained evaluation could not be verified.");
  expect(screen.queryByText("109/109")).toBeNull();
  expect(screen.queryByRole("button", { name: "Download reference report" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByText("109/109");
  expect(api.mock.calls.every(([path]) => path === "/evidence/scorecards/reference")).toBe(true);
});

test("reference download preserves the original scorecard fields and revokes its URL", async () => {
  api.mockResolvedValue(fixture);
  const create = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:scorecard");
  const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<AgentScorecards />);
  fireEvent.click(await screen.findByRole("button", { name: "Download reference report" }));
  await waitFor(() => expect(create).toHaveBeenCalledOnce());
  expect(create.mock.calls[0][0].type).toBe("application/json");
  expect(click).toHaveBeenCalledOnce();
  expect(revoke).toHaveBeenCalledWith("blob:scorecard");
  expect(api.mock.calls.length).toBe(1);
  create.mockRestore(); revoke.mockRestore(); click.mockRestore();
});
