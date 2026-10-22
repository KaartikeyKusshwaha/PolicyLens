import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import DeletionPreview from "./DeletionPreview";
import { api } from "../services/api";

vi.mock("../services/api", () => ({ api: vi.fn() }));
beforeEach(() => vi.clearAllMocks());
const result = { customer_id: "customer-one", generated_at: "2026-10-23T00:00:00Z", eligible_at: null, inventory_sha256: "inventory-hash",
  blockers: [{ code: "legal_hold", record_id: "hold-one" }, { code: "external_copy_reconciliation_required" }],
  candidates: [{ table: "records",kind: "customer",rowid: 1,record_id: "customer-one",sha256: "customer-content-hash" }],
  unresolved_references: [{ table: "records",kind: "adapter_import",rowid: 2,record_id: "shared-receipt",sha256: "shared-content-hash" }],
  retained_governance: [], retained_audit: { events: 25,scope: "Audit history may retain supplied names." },
  excluded_scope: ["Backups and exports"],limits: "Text mentions never authorize shared-row deletion.", execution_available: false };

test("populated preview shows holds, residual copies and audit limits without an execution button", async () => {
  api.mockResolvedValue(result);
  render(<DeletionPreview />);
  fireEvent.change(screen.getByLabelText("Customer ID for deletion preview"), { target: { value: "customer-one" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview customer deletion" }));
  await screen.findByText("inventory-hash");
  expect(screen.getByText(/An active or pending-release legal hold applies/)).toBeTruthy();
  expect(screen.getByText("shared-receipt")).toBeTruthy();
  expect(screen.getByText("Audit history may retain supplied names.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Execute|Approve deletion|Delete customer/i })).toBeNull();
  expect(api).toHaveBeenCalledWith("/retention/deletion-preview?customer_id=customer-one");
});

test("changing the selected customer clears the old inventory snapshot", async () => {
  api.mockResolvedValue(result);
  render(<DeletionPreview />);
  const input = screen.getByLabelText("Customer ID for deletion preview");
  fireEvent.change(input, { target: { value: "customer-one" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview customer deletion" }));
  await screen.findByText("inventory-hash");
  fireEvent.change(input, { target: { value: "customer-two" } });
  expect(screen.queryByText("inventory-hash")).toBeNull();
});

test("a failed refresh clears prior candidate evidence and shows the server failure", async () => {
  api.mockResolvedValueOnce(result).mockRejectedValueOnce(new Error("Inventory exceeds its bound; no partial plan."));
  render(<DeletionPreview />);
  fireEvent.change(screen.getByLabelText("Customer ID for deletion preview"), { target: { value: "customer-one" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview customer deletion" }));
  await screen.findByText("inventory-hash");
  fireEvent.click(screen.getByRole("button", { name: "Preview customer deletion" }));
  await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("no partial plan"));
  expect(screen.queryByText("inventory-hash")).toBeNull();
});
