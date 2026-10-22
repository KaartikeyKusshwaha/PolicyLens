import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import Retention from "./Retention";
import { api } from "../services/api";

vi.mock("../services/api", () => ({ api: vi.fn() }));
vi.mock("../session", () => ({ useSession: () => ({ user: { id: "reviewer", role: "reviewer" } }) }));
beforeEach(() => vi.clearAllMocks());

const policy = { id: "policy-1", title: "Fictional retention policy", status: "draft", created_by: "author",
  rationale: "Synthetic records only.", external_copy_procedure: "Review exported copies with their custodians.",
  customer_days: 400, resolved_case_days: 450, terminal_job_days: 30, backup_days: 45, audit_minimum_days: 800 };
const hold = { id: "hold-1", scope: "customer", target_id: "customer-1", reason: "Preserve this fictional investigation.",
  authority_reference: "TEST-HOLD", status: "release_requested", created_by: "author", release_requested_by: "reviewer", release_reason: "Fictional investigation has concluded." };
const overview = { active_policy: null, policies: [policy], holds: [hold], limits: "Deletion is not yet enabled." };

test("populated review shows retention periods and pending holds without offering self-release", async () => {
  api.mockResolvedValue(overview);
  render(<Retention />);
  await screen.findByText("Customer hold · Release Requested");
  expect(screen.getByText("Hold remains effective until independent release approval.")).toBeTruthy();
  expect(screen.getByText("400")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Approve release TEST-HOLD" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Save retention draft" })).toBeNull();
  expect(screen.getByRole("button", { name: "Approve policy Fictional retention policy" })).toBeTruthy();
});

test("failed approval remains visible without reporting success", async () => {
  api.mockImplementation(async (path, options) => { if (options?.method === "POST") throw new Error("The active policy changed."); return overview; });
  render(<Retention />);
  await screen.findByText("Customer hold · Release Requested");
  fireEvent.change(screen.getByLabelText("Approve policy Fictional retention policy reason"), { target: { value: "Reviewed the complete policy and copy procedure." } });
  fireEvent.click(screen.getByRole("button", { name: "Approve policy Fictional retention policy" }));
  await screen.findByText("The active policy changed.");
  expect(screen.queryByText(/Retention governance change recorded/)).toBeNull();
  expect(screen.getByText("Hold remains effective until independent release approval.")).toBeTruthy();
});

test("release approval sends only its review and refreshes authoritative hold status", async () => {
  api.mockImplementation(async (path, options) => {
    if (options?.method === "POST") return { ...hold, status: "released" };
    return { ...overview, holds: [{ ...hold, release_requested_by: "author" }] };
  });
  render(<Retention />);
  await screen.findByText("Customer hold · Release Requested");
  fireEvent.change(screen.getByLabelText("Approve release TEST-HOLD reason"), { target: { value: "Independently verified the authority to release." } });
  fireEvent.click(screen.getByRole("button", { name: "Approve release TEST-HOLD" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/retention/holds/hold-1/approve-release", { method: "POST", body: { reason: "Independently verified the authority to release." } }));
  await screen.findByText("Retention governance change recorded. No data was deleted.");
});
