import React from "react";
import { expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CaseReview from "./CaseReview";

const review = {
  prepared_at: "2026-10-25T10:00:00Z", next_action: "Review outstanding evidence.",
  alert_count: 1, transaction_count: 2, total_customer_transactions: 2,
  totals_by_currency: { USD: "150.30", EUR: "1.00" },
  missing_evidence: ["Customer due diligence is not recorded as verified."],
  open_tasks: [{ id: "task-1", title: "Request invoice", status: "open" }],
  signals: [{ id: "signal-1", title: "Amount check", origin: "internal_control", policy_version: "1", facts: { observed: "150.10", threshold: "100.00", currency: "USD" } }],
  policies: [], limitations: ["This is not a final decision."],
};

test("prepared review connects gaps, tasks and original evidence without starting AI", () => {
  const completeTask = vi.fn(), showEvidence = vi.fn();
  render(<MemoryRouter><CaseReview review={review} canEdit completeTask={completeTask} showEvidence={showEvidence} /></MemoryRouter>);
  expect(screen.getByText("150.30")).toBeTruthy();
  expect(screen.getByText("EUR displayed total")).toBeTruthy();
  expect(screen.getByText(review.missing_evidence[0])).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Complete" }));
  expect(completeTask).toHaveBeenCalledWith("task-1");
  fireEvent.click(screen.getByRole("button", { name: /Inspect original evidence/ }));
  expect(showEvidence).toHaveBeenCalledOnce();
});

test("read-only reviewers can inspect preparation without completing tasks", () => {
  render(<MemoryRouter><CaseReview review={review} canEdit={false} /></MemoryRouter>);
  expect(screen.getByText("Request invoice")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "Complete" })).toBeNull();
});
