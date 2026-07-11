(function () {
  const STORAGE_KEY = "pmo-theme";
  const root = document.documentElement;
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) root.setAttribute("data-theme", saved);

  function toggleTheme() {
    const current = root.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem(STORAGE_KEY, next);
  }

  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.querySelector("[data-theme-toggle]");
    if (btn) btn.addEventListener("click", toggleTheme);
  });
})();
