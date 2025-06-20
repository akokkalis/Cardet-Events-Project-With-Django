// <!-- JavaScript to Auto-Hide Messages -->

    document.addEventListener("DOMContentLoaded", function () {
        setTimeout(function () {
            const messageContainer = document.getElementById("messageContainer");
            if (messageContainer) {
                messageContainer.style.display = "none";
            }
        }, 3000); // Hide after 3 seconds
    });
