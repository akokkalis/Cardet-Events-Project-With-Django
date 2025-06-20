$(document).ready(function () {
    const participantsTable = $('#participantsTable');
    const participantCount = participantsTable.data('participant-count');
    const sendTicketUrl = participantsTable.data('send-ticket-url');
    const csrfToken = participantsTable.data('csrf-token');

    if (participantCount > 0 && !$.fn.DataTable.isDataTable('#participantsTable')) {
        participantsTable.DataTable({
            "paging": true,
            "searching": true,
            "ordering": true,
            "info": true,
            "responsive": true,
            "lengthMenu": [[10, 25, 50, -1], [10, 25, 50, "All"]],
            "pageLength": 10,
            "dom":  '<"flex justify-between items-center mb-4"<"flex items-center"lB>f>t<"mt-4"ip>',
            "buttons": [
                { 
                    extend: 'csv', 
                    text: 'Export CSV', 
                    className: 'btn btn-outline-blue text-sm ml-4' 
                },
                { 
                    extend: 'pdfHtml5', 
                    text: 'Export PDF', 
                    className: 'btn btn-outline-blue text-sm' 
                }
            ]
        });
    }

    $(".send-ticket-btn").click(function () {
        let participantId = $(this).data("participant-id");
        Swal.fire({
            title: "Send Ticket?",
            text: "Are you sure you want to send the ticket?",
            icon: "question",
            showCancelButton: true,
            confirmButtonColor: "#0174b9",
            cancelButtonColor: "#d33",
            confirmButtonText: "Yes, Send"
        }).then((result) => {
            if (result.isConfirmed) {
                $.ajax({
                    url: sendTicketUrl,
                    method: "POST",
                    data: {
                        participant_id: participantId,
                        csrfmiddlewaretoken: csrfToken
                    },
                    success: function (response) {
                        Swal.fire("Success", response.message, "success");
                    },
                    error: function (xhr) {
                        Swal.fire("Error", "Failed to send ticket.", "error");
                    }
                });
            }
        });
    });
}); 