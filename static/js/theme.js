(function () {
  const STORAGE_KEY = "pmo-theme";
  const SIDEBAR_STORAGE_KEY = "pmo-sidebar";
  const root = document.documentElement;
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) root.setAttribute("data-theme", saved);

  function applySidebarState(sidebar) {
    if (localStorage.getItem(SIDEBAR_STORAGE_KEY) === "collapsed") {
      sidebar.classList.add("collapsed");
    }
  }

  function toggleSidebar() {
    const sidebar = document.getElementById("app-sidebar");
    if (!sidebar) return;
    const collapsed = sidebar.classList.toggle("collapsed");
    localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? "collapsed" : "expanded");
  }

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : null;
  }

  function persistThemeToServer(theme) {
    const csrftoken = getCookie("csrftoken");
    if (!csrftoken) return;
    fetch("/accounts/preference/theme/", {
      method: "POST",
      headers: {
        "X-CSRFToken": csrftoken,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: "theme=" + encodeURIComponent(theme),
    }).catch(function () {});
  }

  function toggleTheme() {
    const current = root.getAttribute("data-theme") ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = current === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem(STORAGE_KEY, next);
    persistThemeToServer(next);
  }

  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.querySelector("[data-theme-toggle]");
    if (btn) btn.addEventListener("click", toggleTheme);

    const sidebar = document.getElementById("app-sidebar");
    if (sidebar) applySidebarState(sidebar);
    const sidebarToggle = document.getElementById("sidebar-toggle");
    if (sidebarToggle) sidebarToggle.addEventListener("click", toggleSidebar);
  });

  // 全フォーム共通の二重送信防止＋処理中表示。
  // 送信ボタンのname/valueが欠落しないよう disabled は使わず、
  // aria-busy と data-submitting フラグで多重送信を抑止する。
  document.addEventListener(
    "submit",
    function (e) {
      const form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      const confirmMsg = form.getAttribute("data-confirm");
      if (confirmMsg && !window.confirm(confirmMsg)) {
        e.preventDefault();
        return;
      }
      if (form.getAttribute("data-no-busy") !== null) return;
      if (form.dataset.submitting === "1") {
        e.preventDefault();
        return;
      }
      form.dataset.submitting = "1";
      const btn = e.submitter ||
        form.querySelector('button[type="submit"], input[type="submit"], button:not([type])');
      if (btn) {
        btn.setAttribute("aria-busy", "true");
        if (btn.tagName === "BUTTON") {
          btn.dataset.origHtml = btn.innerHTML;
          btn.textContent = "処理中…";
        }
      }
    },
    true
  );

  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      const input = document.getElementById("global-search-input");
      if (input) {
        e.preventDefault();
        input.focus();
      }
    }
  });
})();
