import { beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AccountMFA from "./AccountMFA";
import { api } from "../services/api";

const { accept } = vi.hoisted(() => ({ accept: vi.fn() }));
vi.mock("../session", () => ({ useSession: () => ({ accept }) }));
vi.mock("../services/api", () => ({ api: vi.fn() }));

beforeEach(() => {
  vi.clearAllMocks();
});

test("enrollment keeps recovery codes out of persistent storage and refreshes the session", async () => {
  let enabled = false;
  api.mockImplementation(async (path) => {
    if (path === "/auth/mfa") return { enabled, recovery_codes_remaining: enabled ? 2 : 0 };
    if (path === "/auth/mfa/enroll") return { secret: "TEST-SETUP-KEY" };
    if (path === "/auth/mfa/confirm") {
      enabled = true;
      return { enabled: true, user: { csrf: "rotated" }, recovery_codes: ["code-one", "code-two"] };
    }
    throw new Error("Unexpected path");
  });
  render(<AccountMFA />);
  await screen.findByText("Not enabled");
  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "Test-password-long" } });
  fireEvent.click(screen.getByRole("button", { name: "Set up authenticator" }));
  await screen.findByText("TEST-SETUP-KEY");
  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "Test-password-long" } });
  fireEvent.change(screen.getByLabelText("Authenticator or recovery code"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify and enable" }));
  await screen.findByText("Save these recovery codes now");
  expect(accept).toHaveBeenCalledWith({ csrf: "rotated" });
  expect(api).toHaveBeenCalledWith("/auth/mfa/confirm", { method: "POST", body: { password: "Test-password-long", code: "123456" } });
  expect(localStorage.getItem("recovery_codes")).toBeNull();
  expect(sessionStorage.getItem("recovery_codes")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /I saved the codes/ }));
  expect(screen.queryByRole("region", { name: "One-time recovery codes" })).toBeNull();
});

test("failed enrollment confirmation stays visible without claiming MFA enabled", async () => {
  api.mockImplementation(async (path) => {
    if (path === "/auth/mfa") return { enabled: false };
    if (path === "/auth/mfa/enroll") return { secret: "TEST-SETUP-KEY" };
    throw new Error("Enter a fresh authenticator code.");
  });
  render(<AccountMFA />);
  await screen.findByText("Not enabled");
  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "Test-password-long" } });
  fireEvent.click(screen.getByRole("button", { name: "Set up authenticator" }));
  await screen.findByText("TEST-SETUP-KEY");
  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "Test-password-long" } });
  fireEvent.change(screen.getByLabelText("Authenticator or recovery code"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify and enable" }));
  await screen.findByText("Enter a fresh authenticator code.");
  expect(screen.getByText("TEST-SETUP-KEY")).toBeTruthy();
  expect(accept).not.toHaveBeenCalled();
});

test("recovery replacement uses its own action and requires password and factor fields", async () => {
  api.mockImplementation(async (path) => path === "/auth/mfa" ? { enabled: true, recovery_codes_remaining: 3 } : { enabled: true, user: {}, recovery_codes: ["new-code"] });
  render(<AccountMFA />);
  await screen.findByText(/3 recovery codes remaining/);
  fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "Test-password-long" } });
  fireEvent.change(screen.getByLabelText("Authenticator or recovery code"), { target: { value: "old-code" } });
  fireEvent.click(screen.getByRole("button", { name: "Replace recovery codes" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("/auth/mfa/recovery-codes", { method: "POST", body: { password: "Test-password-long", code: "old-code" } }));
});
