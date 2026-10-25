export const THEME_VERSION = "midnight-purple-v1";

export function initializeTheme() {
  try {
    // Apply this owner-selected palette once; subsequent theme choices persist.
    if (localStorage.getItem("policylens-theme-version") !== THEME_VERSION) {
      localStorage.setItem("policylens-theme", "dark");
      localStorage.setItem("policylens-theme-version", THEME_VERSION);
    }
    document.documentElement.dataset.theme = localStorage.getItem("policylens-theme") === "light" ? "light" : "dark";
  } catch {
    document.documentElement.dataset.theme = "dark";
  }
}
