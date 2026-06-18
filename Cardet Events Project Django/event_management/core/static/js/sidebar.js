document.addEventListener("DOMContentLoaded", function () {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("overlay");

    if (!sidebar) return;

    function openSidebar() {
        sidebar.classList.remove("-translate-x-full");
        sidebar.classList.add("translate-x-0");
        if (overlay) {
            overlay.classList.remove("hidden");
        }
    }

    function closeSidebar() {
        sidebar.classList.add("-translate-x-full");
        sidebar.classList.remove("translate-x-0");
        if (overlay) {
            overlay.classList.add("hidden");
        }
    }

    // Attach to ALL toggle buttons (base.html fixed button + any per-template ones)
    document.querySelectorAll('[id="sidebarToggle"]').forEach(function(btn) {
        btn.addEventListener("click", openSidebar);
    });

    // Close on overlay click
    if (overlay) {
        overlay.addEventListener("click", closeSidebar);
    }

    // Close sidebar when a nav link is clicked on mobile
    sidebar.querySelectorAll("a").forEach(function(link) {
        link.addEventListener("click", function() {
            if (window.innerWidth < 768) {
                closeSidebar();
            }
        });
    });

    // Close on Escape key
    document.addEventListener("keydown", function(e) {
        if (e.key === "Escape") {
            closeSidebar();
        }
    });
});
