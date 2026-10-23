import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ControlTuning, { TuningEvidence } from "./ControlTuning";
import { api } from "../services/api";

vi.mock("../services/api", () => ({ api: vi.fn() }));
beforeEach(() => vi.clearAllMocks());

const request = { control_id: "parent1", candidate_thresholds: ["200", "300"], target_match_count: 1, rationale: "Compare historical workload against stated review capacity." };
const preview = { request, tested: 3, current_threshold: "100", before: { match_count: 2, match_transaction_ids: ["txn1", "txn2"] }, candidates: [{ threshold: "200", match_count: 1, distance_from_target: 0, match_transaction_ids: ["txn2"] }, { threshold: "300", match_count: 0, distance_from_target: 1, match_transaction_ids: [] }], selected: { threshold: "200" }, added_match_ids: [], removed_match_ids: ["txn1"], preview_sha256: "a".repeat(64), selection: "Ties use caller candidate order.", limitations: ["No live alerts or cases are created."] };

function fill() {
  fireEvent.change(screen.getByLabelText(/Candidate thresholds/), { target: { value: "200, 300" } });
  fireEvent.change(screen.getByLabelText("Target historical match count"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Tuning objective and rationale"), { target: { value: request.rationale } });
  fireEvent.click(screen.getByRole("button", { name: "Compare thresholds" }));
}

test("comparison uses the server-pinned request and creates only a review draft", async () => {
  api.mockResolvedValueOnce(preview).mockResolvedValueOnce({ control: { id: "draft1", status: "draft" } });
  render(<MemoryRouter><ControlTuning control={{ id: "parent1" }} /></MemoryRouter>);
  fill();
  await screen.findByText("Selected for draft");
  expect(api.mock.calls[0]).toEqual(["/control-tuning/preview", { method: "POST", body: request }]);
  expect(screen.getByText(/does not establish detection accuracy/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Draft threshold change for review" }));
  await screen.findByText(/No control was activated/);
  expect(api.mock.calls[1]).toEqual(["/control-tuning/draft", { method: "POST", body: { ...request, preview_sha256: "a".repeat(64) } }]);
  expect(screen.getByRole("link", { name: "Open the threshold-change draft" }).getAttribute("href")).toBe("/policies/controls/draft1");
  expect(api.mock.calls.some(([path]) => path.includes("/actions"))).toBe(false);
});

test("editing inputs or a stale draft refusal clears the old comparison", async () => {
  api.mockResolvedValue(preview);
  render(<MemoryRouter><ControlTuning control={{ id: "parent1" }} /></MemoryRouter>);
  fill();
  await screen.findByText("Selected for draft");
  fireEvent.change(screen.getByLabelText("Target historical match count"), { target: { value: "2" } });
  expect(screen.queryByRole("button", { name: "Draft threshold change for review" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Compare thresholds" }));
  await screen.findByText("Selected for draft");
  api.mockRejectedValueOnce(new Error("Evidence changed. Inspect a fresh comparison."));
  fireEvent.click(screen.getByRole("button", { name: "Draft threshold change for review" }));
  await screen.findByText("Evidence changed. Inspect a fresh comparison.");
  expect(screen.queryByText(/No control was activated/)).toBeNull();
  expect(screen.queryByRole("button", { name: "Draft threshold change for review" })).toBeNull();
});

test("retained evidence exposes before and after without approval authority", async () => {
  api.mockResolvedValue({ receipt: { preview }, control_status: "draft" });
  render(<MemoryRouter><TuningEvidence receiptId="receipt1" /></MemoryRouter>);
  await screen.findByText("Retained tuning evidence");
  await waitFor(() => expect(api).toHaveBeenCalledWith("/control-tuning/receipt1", expect.anything()));
  expect(screen.getByText(/Approval rechecks the control, policy/)).toBeTruthy();
  expect(screen.getByText(/Current threshold 100: 2 matches/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Approve|activate/ })).toBeNull();
});
