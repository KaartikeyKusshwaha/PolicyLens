import { beforeEach, expect, test } from "vitest";
import { initializeTheme, THEME_VERSION } from "./theme";
beforeEach(() => localStorage.clear());
test("new palette applies to returning users and sign-in before rendering", () => {
  localStorage.setItem("policylens-theme", "light");
  initializeTheme();
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("policylens-theme-version")).toBe(THEME_VERSION);
});
test("later explicit light preference is retained", () => {
  initializeTheme();
  localStorage.setItem("policylens-theme", "light");
  initializeTheme();
  expect(document.documentElement.dataset.theme).toBe("light");
});
