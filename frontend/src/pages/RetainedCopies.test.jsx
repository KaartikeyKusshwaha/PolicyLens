import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import RetainedCopies from "./RetainedCopies";
import { api } from "../services/api";

vi.mock("../services/api", () => ({ api: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
const user = { id: "reviewer", role: "reviewer" };
const copy = { id: "copy-one", category: "backup", status: "removal_requested", custodian: "Fictional custodian", location_reference: "TEST-COPY",scope: "workspace",target_id: "",content_sha256: "a".repeat(64),preserve_until: "2026-10-01T00:00:00Z",history: [],removal_requested_by: "author" };
const policy = { id: "policy-one" };

test("copy authorization is distinct from reported removal and hides self-approval", () => {
  const { rerender } = render(<RetainedCopies copies={[copy]} user={user} policy={policy} reload={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Authorize removal copy-one" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Report removal copy-one" })).toBeNull();
  rerender(<RetainedCopies copies={[{ ...copy,removal_requested_by: user.id }]} user={user} policy={policy} reload={vi.fn()} />);
  expect(screen.queryByRole("button", { name: "Authorize removal copy-one" })).toBeNull();
  expect(screen.getByRole("button", { name: "Cancel removal copy-one" })).toBeTruthy();
});

test("custodian report sends evidence metadata and does not claim external deletion", async () => {
  api.mockResolvedValue({});
  const reload = vi.fn();
  render(<RetainedCopies copies={[{ ...copy,status: "removal_authorized" }]} user={user} policy={policy} reload={reload} />);
  fireEvent.change(screen.getByLabelText("Report removal copy-one reason"), { target: { value: "Custodian reports removal; evidence requires review." } });
  fireEvent.change(screen.getByLabelText("Removal evidence reference"), { target: { value: "TEST-REMOVAL-REPORT" } });
  fireEvent.change(screen.getByLabelText("Removal evidence SHA-256"), { target: { value: "b".repeat(64) } });
  fireEvent.click(screen.getByRole("button", { name: "Report removal copy-one" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/retention/copies/copy-one/report-removal", { method: "POST",body: { reason: "Custodian reports removal; evidence requires review.",evidence_reference: "TEST-REMOVAL-REPORT",evidence_sha256: "b".repeat(64) } }));
  await screen.findByText("Custody review recorded. PolicyLens did not delete an external file or verify its absence.");
  expect(reload).toHaveBeenCalledOnce();
});

test("new hold denial stays visible and the copy is not shown as removed", async () => {
  api.mockRejectedValue(new Error("A pending-release legal hold applies."));
  const reload = vi.fn();
  render(<RetainedCopies copies={[copy]} user={user} policy={policy} reload={reload} />);
  fireEvent.change(screen.getByLabelText("Authorize removal copy-one reason"), { target: { value: "Review the requested removal for this backup." } });
  fireEvent.click(screen.getByRole("button", { name: "Authorize removal copy-one" }));
  await screen.findByText("A pending-release legal hold applies.");
  expect(reload).not.toHaveBeenCalled();
  expect(screen.queryByText(/Custody review recorded/)).toBeNull();
});

test("auditors can inspect confirmed reports without custody mutation controls", () => {
  render(<RetainedCopies copies={[{ ...copy,status: "removal_confirmed",evidence_reference: "TEST-REPORT",evidence_sha256: "b".repeat(64) }]} user={{ id: "auditor",role: "auditor" }} policy={policy} reload={vi.fn()} />);
  expect(screen.getByText(/External erasure was not automatically verified/)).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
  expect(screen.queryByText("Register a retained copy")).toBeNull();
});


test("a changed policy requires explicit rereview of reported facts before confirmation", () => {
  const reported = { ...copy,status: "removal_reported",removal_reported_by: "custodian",removal_policy_id: "old-policy" };
  const { rerender } = render(<RetainedCopies copies={[reported]} user={user} policy={policy} reload={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Review report under current policy copy-one" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Confirm report copy-one" })).toBeNull();
  rerender(<RetainedCopies copies={[{ ...reported,removal_policy_id: policy.id }]} user={user} policy={policy} reload={vi.fn()} />);
  expect(screen.getByRole("button", { name: "Confirm report copy-one" })).toBeTruthy();
});
