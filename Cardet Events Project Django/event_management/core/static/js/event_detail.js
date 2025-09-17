$(document).ready(function () {
    const participantsTable = $('#participantsTable');
    const participantCount = participantsTable.data('participant-count');
    const sendTicketUrl = participantsTable.data('send-ticket-url');
    const csrfToken = participantsTable.data('csrf-token');

    if (participantCount > 0 && !$.fn.DataTable.isDataTable('#participantsTable')) {
        // Add filter dropdowns before the table
        $('#participantsTable').before(`
            <div class="flex gap-4 mb-4">
                <div class="filter-group">
                    <label for="statusFilter" class="mr-2 font-medium text-gray-700">Status:</label>
                    <select id="statusFilter" class="rounded-lg border-gray-300 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                        <option value="">All</option>
                        <option value="pending">Pending</option>
                        <option value="approved">Approved</option>
                        <option value="rejected">Rejected</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label for="rsvpFilter" class="mr-2 font-medium text-gray-700">RSVP:</label>
                    <select id="rsvpFilter" class="rounded-lg border-gray-300 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50">
                        <option value="">All</option>
                        <option value="Yes">Yes</option>
                        <option value="No">No</option>
                        <option value="Maybe">Maybe</option>
                        <option value="Not Responded">Not Responded</option>
                    </select>
                </div>
            </div>
        `);

        // Initialize DataTable
        const table = participantsTable.DataTable({
            "paging": true,
            "searching": true,
            "ordering": true,
            "info": true,
            "responsive": true,
            "lengthMenu": [[10, 25, 50, -1], [10, 25, 50, "All"]],
            "pageLength": 10,
            "dom": '<"flex justify-between items-center mb-4"<"flex items-center"l>f>t<"mt-4"ip>'
        });

        // Add custom filtering functionality
        $('#statusFilter, #rsvpFilter').on('change', function() {
            table.draw();
        });

        // Custom filtering function
        $.fn.dataTable.ext.search.push(
            function(settings, data, dataIndex) {
                const statusFilter = $('#statusFilter').val();
                const rsvpFilter = $('#rsvpFilter').val();
                
                // Get values from the row
                const status = $(table.row(dataIndex).node()).find('td:eq(5)').text().toLowerCase().trim();
                const rsvp = $(table.row(dataIndex).node()).find('td:eq(6)').text().trim();

                // Check if row matches both filters
                const statusMatch = !statusFilter || status.includes(statusFilter.toLowerCase());
                const rsvpMatch = !rsvpFilter || rsvp === rsvpFilter;

                return statusMatch && rsvpMatch;
            }
        );
    }

    // Send ticket functionality moved to event_detail_modals.js

    // ✅ View Custom Data Modal Button
    $(".view-custom-data-btn").click(function () {
        let participantName = $(this).data("participant-name");
        let customDataString = $(this).data("custom-data");
        
        console.log('Raw custom data string:', customDataString);
        console.log('Type of custom data string:', typeof customDataString);
        
        // If it's already an object (jQuery parsed it), use it directly
        if (typeof customDataString === 'object') {
            console.log('Data is already an object:', customDataString);
            displayCustomDataModal(participantName, customDataString);
            return;
        }
        
        try {
            // Parse the custom data
            let customData;
            if (typeof customDataString === 'string') {
                if (customDataString.trim() === '' || customDataString.trim() === '{}') {
                    customData = {};
                } else {
                    customData = JSON.parse(customDataString);
                }
            } else {
                customData = customDataString || {};
            }
            
            console.log('Parsed custom data:', customData);
            displayCustomDataModal(participantName, customData);
            
        } catch (error) {
            console.error('Error parsing custom data:', error);
            console.error('Custom data string that caused error:', customDataString);
            Swal.fire({
                title: 'Error',
                text: `Unable to display custom data. Check console for details. Error: ${error.message}`,
                icon: 'error',
                confirmButtonText: 'Close'
            });
        }
    });

    // Function to display custom data modal
    function displayCustomDataModal(participantName, customData) {
        console.log('Displaying modal for:', participantName, 'with data:', customData);
        
        // Check if there's any data to display
        if (!customData || Object.keys(customData).length === 0) {
            Swal.fire({
                title: `Custom Data for ${participantName}`,
                html: '<div class="text-center text-gray-500">No custom data available</div>',
                icon: 'info',
                confirmButtonText: 'Close',
                confirmButtonColor: '#3085d6',
                width: '600px'
            });
            return;
        }
        
        // Build HTML content for the modal
        let htmlContent = '<div class="text-left">';
        
        for (let key in customData) {
            if (customData.hasOwnProperty(key)) {
                let value = customData[key];
                let displayValue;
                
                console.log(`Processing field: ${key}, value:`, value);
                
                // Check if this is a file field
                if (typeof value === 'object' && value !== null && value.is_file) {
                    displayValue = `<a href="/download-custom-file/${value.file_id}/" class="text-blue-600 hover:text-blue-800 underline" target="_blank">📁 ${value.filename}</a>`;
                } else {
                    displayValue = value || '-';
                }
                
                htmlContent += `
                    <div class="mb-3 p-3 bg-gray-50 rounded-lg border">
                        <div class="font-semibold text-gray-700 mb-1">${key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</div>
                        <div class="text-gray-900">${displayValue}</div>
                    </div>
                `;
            }
        }
        
        htmlContent += '</div>';
        
        // Show SweetAlert modal
        Swal.fire({
            title: `Custom Data for ${participantName}`,
            html: htmlContent,
            icon: 'info',
            confirmButtonText: 'Close',
            confirmButtonColor: '#3085d6',
            width: '600px',
            customClass: {
                popup: 'text-sm'
            }
        });
    }

    // ✅ Bulk RSVP Email Sending Functionality

    $("#sendRsvpBtn").click(function () {
        const eventId = $(this).data("event-id");
        
        Swal.fire({
            title: 'Send RSVP Notifications?',
            text: 'This will send RSVP emails to all approved participants who haven\'t responded yet.',
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Yes, send emails!',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                sendBulkRsvpEmails(eventId);
            }
        });
    });

    function sendBulkRsvpEmails(eventId) {
        // Show loading state
        Swal.fire({
            title: 'Queuing RSVP Emails...',
            text: 'Please wait while we queue the emails for processing.',
            icon: 'info',
            allowOutsideClick: false,
            showConfirmButton: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });

        $.ajax({
            url: `/events/${eventId}/send-bulk-rsvp/`,
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken
            },
            success: function (response) {
                if (response.success) {
                    // Show success message - emails queued for processing
                    Swal.fire({
                        title: 'RSVP Emails Queued Successfully!',
                        text: `Queued ${response.total_recipients} emails for processing. The emails will be sent in the background.`,
                        icon: 'success',
                        confirmButtonText: 'OK',
                        timer: 3000,
                        timerProgressBar: true
                    });
                } else {
                    Swal.fire({
                        title: 'Error',
                        text: response.error || 'Failed to queue emails for processing.',
                        icon: 'error',
                        confirmButtonText: 'Close'
                    });
                }
            },
            error: function (xhr) {
                let errorMessage = 'Failed to queue RSVP emails.';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMessage = xhr.responseJSON.error;
                }
                
                Swal.fire({
                    title: 'Error',
                    text: errorMessage,
                    icon: 'error',
                    confirmButtonText: 'Close'
                });
            }
        });
    }
}); 