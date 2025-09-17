document.addEventListener("DOMContentLoaded", function () {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("overlay");
    const toggleButton = document.getElementById("sidebarToggle");

    function openSidebar() {
        sidebar.classList.remove("-translate-x-full");
        sidebar.classList.add("translate-x-0");
        overlay.classList.remove("hidden");

        // ✅ Ensure sidebar is always on top of events
        sidebar.style.zIndex = "50";
        overlay.style.zIndex = "40";
    }

    function closeSidebar() {
        sidebar.classList.add("-translate-x-full");
        sidebar.classList.remove("translate-x-0");
        overlay.classList.add("hidden");
    }

    if (toggleButton) {
        toggleButton.addEventListener("click", openSidebar);
    }
    
    if (overlay) {
        overlay.addEventListener("click", closeSidebar);
    }
});
