(function () {
  var legacyNavigation = {
    student: [
      ["Overview", [["Dashboard", "/home", "layout-dashboard"], ["My courses", "/mycourse", "book-open"]]],
      ["Campus", [["Institution", "/institution", "building-2"], ["Faculty chat", "/chat", "messages-square"]]],
      ["Academic", [["Attendance", "/attendance", "calendar-check"], ["Assignments", "/student/assignments", "clipboard-list"], ["Timetable", "/timetable", "calendar"]]],
      ["Coding", [["Tracks", "/coding_tracks", "route"], ["Practice", "/myverse", "code-2"], ["Compiler", "/compiler", "terminal"], ["Assessments", "/student_coding_assesment", "file-code"], ["Code rooms", "/code_room", "users"]]],
      ["Tools", [["AI assistant", "/ai_code_assistant", "sparkles"], ["Code review", "/code-review", "scan-search"], ["Job match", "/job_match_recomender", "briefcase"], ["Leaderboard", "/student%20leaderboard", "trophy"]]]
    ],
    faculty: [
      ["Overview", [["Dashboard", "/faculty", "layout-dashboard"], ["Student chat", "/faculty_chat", "messages-square"]]],
      ["Academic", [["Attendance", "/faculty/attendance", "calendar-check"], ["Timetable", "/timetable/faculty", "calendar"], ["Assignments", "/faculty/assignments", "clipboard-list"]]],
      ["Coding", [["Coding assessments", "/faculty/coding_assessment", "file-code"], ["Code rooms", "/code_room", "users"]]]
    ],
    admin: [
      ["Overview", [["Dashboard", "/dashboard/admin", "layout-dashboard"]]],
      ["People", [["Faculty", "/faculty/admin", "graduation-cap"], ["Students", "/students/admin", "users"]]]
    ]
  };

  var iconPaths = {
    "layout-dashboard": '<rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="5" rx="1"/><rect x="13" y="10" width="8" height="11" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/>',
    "book-open": '<path d="M12 7v14M3 18V5a2 2 0 0 1 2-2h3a4 4 0 0 1 4 4 4 4 0 0 1 4-4h3a2 2 0 0 1 2 2v13a1 1 0 0 1-1 1h-4a4 4 0 0 0-4 2 4 4 0 0 0-4-2H4a1 1 0 0 1-1-1Z"/>',
    "building-2": '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-2M10 6h4M10 10h4M10 14h4M10 18h4"/>',
    "messages-square": '<path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8A8.5 8.5 0 0 1 8.7 3.9a8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z"/>',
    "calendar-check": '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M8 15l2 2 5-5"/>',
    "clipboard-list": '<rect x="5" y="4" width="14" height="18" rx="2"/><path d="M9 4h6M9 11h6M9 15h6M9 19h3"/>',
    "calendar": '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "route": '<circle cx="6" cy="19" r="3"/><path d="M9 19h2a4 4 0 0 0 4-4V9a4 4 0 0 1 4-4h2m-3-3 3 3-3 3"/><circle cx="6" cy="5" r="3"/>',
    "code-2": '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6M14 4l-4 16"/>',
    "terminal": '<rect x="2" y="3" width="20" height="18" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/>',
    "file-code": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z M14 2v6h6M10 13l-2 2 2 2M14 17l2-2-2-2"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M10 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM20 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    "sparkles": '<path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3ZM19 14l1.2 2.8L23 18l-2.8 1.2L19 22l-1.2-2.8L15 18l2.8-1.2L19 14Z"/>',
    "scan-search": '<circle cx="11" cy="11" r="6"/><path d="m20 20-4-4M3 7V4a1 1 0 0 1 1-1h3M17 3h3a1 1 0 0 1 1 1v3M21 17v3a1 1 0 0 1-1 1h-3M7 21H4a1 1 0 0 1-1-1v-3"/>',
    "briefcase": '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v3M3 12h18M10 12v2h4v-2"/>',
    "trophy": '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4ZM7 7H4v2a4 4 0 0 0 4 4M17 7h3v2a4 4 0 0 1-4 4"/>',
    "key-round": '<circle cx="8" cy="15" r="5"/><path d="m21 2-9.6 9.6M15.5 7.5l3 3L22 7l-3-3"/>',
    "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
    "graduation-cap": '<path d="m2 10 10-6 10 6-10 6-10-6ZM6 12.5v5c3.8 2.7 8.2 2.7 12 0v-5M22 10v6"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "panel-left": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M14 9l-3 3 3 3"/>'
  };

  function iconMarkup(name) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (iconPaths[name] || iconPaths["layout-dashboard"]) + "</svg>";
  }

  function currentPath() {
    try { return decodeURIComponent(window.location.pathname).replace(/\/$/, "") || "/"; }
    catch (_) { return window.location.pathname.replace(/\/$/, "") || "/"; }
  }

  function renderLegacyNavigation(role) {
    var groups = legacyNavigation[role];
    if (!groups) return "";
    var path = currentPath();
    var aliases = {
      "/c_plus_plus": "/coding_tracks", "/python": "/coding_tracks",
      "/c": "/coding_tracks", "/java": "/coding_tracks",
      "/assignment": "/student/assignments"
    };
    var activePath = aliases[path] || path;
    return groups.map(function (group) {
      var links = group[1].map(function (link) {
        var linkPath = decodeURIComponent(link[1]);
        var active = activePath === linkPath || (path.indexOf("/problem/") === 0 && linkPath === "/myverse") ? " is-active active" : "";
        return '<a href="' + link[1] + '" class="nav-item' + active + '"' + (active ? ' aria-current="page"' : "") + '>' + iconMarkup(link[2]) + '<span class="nav-label">' + link[0] + "</span></a>";
      }).join("");
      return '<div class="nav-section"><span class="nav-section-label">' + group[0] + "</span>" + links + "</div>";
    }).join("");
  }

  function initLegacyNavigation() {
    var role = document.body && document.body.getAttribute("data-user-role");
    if (!legacyNavigation[role]) return;
    var sidebars = document.querySelectorAll(".sidebar:not(.app-sidebar)");
    sidebars.forEach(function (sidebar) {
      var nav = sidebar.querySelector(".sidebar-nav");
      if (!nav) return;

      nav.innerHTML = renderLegacyNavigation(role);
      nav.setAttribute("aria-label", role.charAt(0).toUpperCase() + role.slice(1) + " navigation");

      var toggle = sidebar.querySelector("#sidebarToggle");
      var header = sidebar.querySelector(".sidebar-header");
      if (!header) {
        header = document.createElement("div");
        header.className = "sidebar-header shared-sidebar-header";
        sidebar.insertBefore(header, sidebar.firstChild);
      }
      header.innerHTML = '<a class="shared-sidebar-brand" href="' + (role === "student" ? "/home" : role === "faculty" ? "/faculty" : "/dashboard/admin") + '"><span class="shared-brand-mark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m2 10 10-6 10 6-10 6-10-6Z"/><path d="M6 12.5v5c3.8 2.7 8.2 2.7 12 0v-5M22 10v6"/></svg></span><span>Campus Bridge</span></a>';
      if (toggle) {
        toggle.classList.add("shared-collapse-toggle");
        toggle.setAttribute("aria-label", "Collapse sidebar");
        header.appendChild(toggle);
      } else {
        toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "sidebar-toggle shared-collapse-toggle";
        toggle.setAttribute("aria-label", "Collapse sidebar");
        toggle.innerHTML = iconMarkup("panel-left");
        toggle.addEventListener("click", function () {
          sidebar.classList.toggle("collapsed");
          var container = sidebar.closest(".dashboard-container");
          if (container) container.classList.toggle("sidebar-collapsed", sidebar.classList.contains("collapsed"));
        });
        header.appendChild(toggle);
      }

      var oldFooter = sidebar.querySelector(".sidebar-footer");
      if (oldFooter) oldFooter.remove();
      var footer = document.createElement("div");
      footer.className = "sidebar-footer shared-sidebar-footer";
      footer.innerHTML = '<a href="/change_password" class="nav-item">' + iconMarkup("key-round") + '<span class="nav-label">Password</span></a><a href="/logout" class="nav-item">' + iconMarkup("log-out") + '<span class="nav-label">Sign out</span></a>';
      sidebar.appendChild(footer);
      sidebar.setAttribute("aria-label", role.charAt(0).toUpperCase() + role.slice(1) + " sidebar");

      var menuToggle = document.getElementById("menuToggle") || document.getElementById("sharedMenuToggle");
      if (!menuToggle) {
        menuToggle = document.createElement("button");
        menuToggle.type = "button";
        menuToggle.id = "sharedMenuToggle";
        menuToggle.className = "shared-menu-toggle";
        menuToggle.setAttribute("aria-label", "Open navigation");
        menuToggle.innerHTML = iconMarkup("menu");
        menuToggle.addEventListener("click", function () {
          sidebar.classList.toggle("active");
        });
        document.body.appendChild(menuToggle);
      }
      if (menuToggle) {
        menuToggle.classList.add("shared-menu-toggle");
        menuToggle.innerHTML = iconMarkup("menu");
        menuToggle.setAttribute("aria-expanded", sidebar.classList.contains("active") ? "true" : "false");
        var backdrop = document.querySelector(".shared-sidebar-backdrop");
        if (!backdrop) {
          backdrop = document.createElement("button");
          backdrop.type = "button";
          backdrop.className = "shared-sidebar-backdrop";
          backdrop.setAttribute("aria-label", "Close navigation");
          document.body.appendChild(backdrop);
        }
        function closeMenu() {
          sidebar.classList.remove("active");
          backdrop.classList.remove("is-visible");
          menuToggle.setAttribute("aria-expanded", "false");
        }
        menuToggle.addEventListener("click", function () {
          window.setTimeout(function () {
            var isOpen = sidebar.classList.contains("active");
            backdrop.classList.toggle("is-visible", isOpen);
            menuToggle.setAttribute("aria-expanded", String(isOpen));
          }, 0);
        });
        backdrop.addEventListener("click", closeMenu);
        nav.addEventListener("click", function (event) {
          if (event.target.closest("a")) closeMenu();
        });
        document.addEventListener("keydown", function (event) {
          if (event.key === "Escape") closeMenu();
        });
      }
    });
  }

  function wrapWideTables() {
    document.querySelectorAll("table").forEach(function (table) {
      if (table.closest(".table-responsive, .shared-table-scroll")) return;
      var wrapper = document.createElement("div");
      wrapper.className = "shared-table-scroll";
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });
  }

  function initIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  }

  function initShell() {
    var shell = document.querySelector(".app-shell");
    var sidebar = document.getElementById("appSidebar");
    var backdrop = document.getElementById("sidebarBackdrop");
    var menuToggle = document.getElementById("menuToggle");
    var collapseToggle = document.getElementById("sidebarCollapse");

    if (!sidebar) return;

    function openMobile() {
      sidebar.classList.add("is-open");
      if (backdrop) backdrop.classList.add("is-visible");
      if (menuToggle) menuToggle.setAttribute("aria-expanded", "true");
    }

    function closeMobile() {
      sidebar.classList.remove("is-open");
      if (backdrop) backdrop.classList.remove("is-visible");
      if (menuToggle) menuToggle.setAttribute("aria-expanded", "false");
    }

    if (menuToggle) {
      menuToggle.addEventListener("click", function () {
        if (sidebar.classList.contains("is-open")) closeMobile();
        else openMobile();
      });
    }

    if (backdrop) {
      backdrop.addEventListener("click", closeMobile);
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeMobile();
    });

    if (collapseToggle && shell) {
      collapseToggle.addEventListener("click", function () {
        var collapsed = sidebar.classList.toggle("is-collapsed");
        shell.classList.toggle("sidebar-collapsed", collapsed);
        collapseToggle.setAttribute("aria-expanded", String(!collapsed));
        collapseToggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
      });
    }

    window.addEventListener("resize", function () {
      if (window.innerWidth > 768) closeMobile();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initLegacyNavigation();
    wrapWideTables();
    initIcons();
    initShell();
  });
})();
