document.addEventListener("DOMContentLoaded", function () {
    function confirmDelete(eventId) {
        Swal.fire({
            title: "Are you sure?",
            text: "This event will be permanently deleted!",
            icon: "warning",
            showCancelButton: true,
            confirmButtonColor: "#d33",
            cancelButtonColor: "#3085d6",
            confirmButtonText: "Yes, delete it!"
        }).then((result) => {
            if (result.isConfirmed) {
                window.location.href = `/delete/${eventId}/`;
            }
        });
    }

    // Attach event listeners dynamically
    document.querySelectorAll(".delete-event-btn").forEach((button) => {
        button.addEventListener("click", function () {
            const eventId = this.getAttribute("data-event-id");
            confirmDelete(eventId);
        });
    });
});
