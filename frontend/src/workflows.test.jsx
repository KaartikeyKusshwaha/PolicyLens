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
};
beforeEach(() => {
  window.history.replaceState({}, "", "/");
  localStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url) => ({
      ok: true,
      json: async () =>
        url === "/api/health"
          ? health
          : url === "/api/dashboard"
            ? dashboard
            : [],
    })),
  );
});

test("empty dashboard displays truthful zeroes and actionable onboarding", async () => {
  render(<App />);
  await screen.findByText("Clarity in every decision.");
  expect(screen.getByText("0 of 3 complete")).toBeTruthy();
  expect(screen.getByText("Your first decision starts here")).toBeTruthy();
  expect(screen.queryByText("API unreachable")).toBeNull();
});

test("evaluation surfaces provider failure and never shows a made-up verdict", async () => {
  window.history.replaceState({}, "", "/evaluate");
  fetch.mockImplementation(async (url) => ({
    ok: url === "/api/health",
    json: async () =>
      url === "/api/health"
        ? health
        : {
            detail: {
              code: "groq_rate_limited",
              message: "Provider limit reached. No decision recorded.",
            },
          },
  }));
  render(<App />);
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
  await screen.findByText("Clarity in every decision.");
  fireEvent.click(screen.getByRole("button", { name: "Use dark theme" }));
  expect(localStorage.getItem("policylens-theme")).toBe("dark");
  fireEvent.click(screen.getByRole("link", { name: "Add a policy" }));
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
  fetch.mockImplementation(async (url) => ({
    ok: true,
    json: async () =>
      url === "/api/health"
        ? health
        : {
            answer:
              "Your policy requires verified sender and receiver identity.",
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
          },
  }));
  render(<App />);
  fireEvent.change(screen.getByLabelText("Your policy question"), {
    target: { value: "What identity checks are required?" },
  });
  fireEvent.submit(
    screen.getByRole("button", { name: /Ask assistant/ }).closest("form"),
  );
  await waitFor(() => expect(screen.getByText("Identity policy")).toBeTruthy());
  expect(screen.getByText("Verify the identity of both parties.")).toBeTruthy();
});
