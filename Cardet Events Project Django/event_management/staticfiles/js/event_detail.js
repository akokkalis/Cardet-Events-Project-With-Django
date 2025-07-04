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
    let currentLogId = null;
    let statusCheckInterval = null;

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
            title: 'Sending RSVP Emails...',
            text: 'Please wait while we send the emails.',
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
                    currentLogId = response.log_id;
                    
                    // Show initial success message
                    Swal.fire({
                        title: 'RSVP Emails Started!',
                        text: `Started sending emails to ${response.total_recipients} participants. We'll track the progress for you.`,
                        icon: 'success',
                        confirmButtonText: 'Track Progress',
                        allowOutsideClick: false
                    }).then(() => {
                        // Start tracking progress
                        trackEmailProgress();
                    });
                } else {
                    Swal.fire({
                        title: 'Error',
                        text: response.error || 'Failed to start sending emails.',
                        icon: 'error',
                        confirmButtonText: 'Close'
                    });
                }
            },
            error: function (xhr) {
                let errorMessage = 'Failed to send RSVP emails.';
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

    function trackEmailProgress() {
        if (!currentLogId) return;

        // Show progress tracking modal
        Swal.fire({
            title: 'Email Sending Progress',
            html: `
                <div class="text-center">
                    <div class="mb-4">
                        <div class="text-lg font-semibold mb-2">Sending RSVP emails...</div>
                        <div class="w-full bg-gray-200 rounded-full h-2.5">
                            <div id="progressBar" class="bg-blue-600 h-2.5 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                    </div>
                    <div id="progressStats" class="text-sm text-gray-600">
                        Checking status...
                    </div>
                </div>
            `,
            icon: 'info',
            showCancelButton: true,
            confirmButtonText: 'Close',
            cancelButtonText: 'Run in Background',
            allowOutsideClick: false,
            didOpen: () => {
                // Start checking status every 2 seconds
                statusCheckInterval = setInterval(checkEmailStatus, 2000);
                // Check immediately
                checkEmailStatus();
            }
        }).then((result) => {
            // Clear interval when modal is closed
            if (statusCheckInterval) {
                clearInterval(statusCheckInterval);
                statusCheckInterval = null;
            }
            
            if (result.isDismissed && result.dismiss === Swal.DismissReason.cancel) {
                // User chose to run in background
                Swal.fire({
                    title: 'Running in Background',
                    text: 'Email sending will continue in the background. You can check the admin panel for final results.',
                    icon: 'info',
                    timer: 3000,
                    showConfirmButton: false
                });
            }
        });
    }

    function checkEmailStatus() {
        if (!currentLogId) return;

        $.ajax({
            url: `/rsvp-email-status/${currentLogId}/`,
            method: 'GET',
            success: function (response) {
                const progressPercent = response.total_recipients > 0 
                    ? Math.round((response.emails_sent + response.emails_failed) / response.total_recipients * 100)
                    : 0;

                // Update progress bar
                $('#progressBar').css('width', progressPercent + '%');

                // Update stats
                let statusText = '';
                if (response.status === 'completed') {
                    statusText = `✅ Completed! ${response.emails_sent} sent, ${response.emails_failed} failed`;
                    $('#progressBar').removeClass('bg-blue-600').addClass('bg-green-600');
                } else if (response.status === 'failed') {
                    statusText = `❌ Failed: ${response.error_message || 'Unknown error'}`;
                    $('#progressBar').removeClass('bg-blue-600').addClass('bg-red-600');
                } else {
                    statusText = `⏳ In progress: ${response.emails_sent}/${response.total_recipients} sent`;
                }

                $('#progressStats').html(statusText);

                // If completed or failed, stop checking and show final result
                if (response.status === 'completed' || response.status === 'failed') {
                    if (statusCheckInterval) {
                        clearInterval(statusCheckInterval);
                        statusCheckInterval = null;
                    }

                    // Show final result after a short delay
                    setTimeout(() => {
                        Swal.fire({
                            title: response.status === 'completed' ? 'RSVP Emails Sent!' : 'Email Sending Failed',
                            text: response.status === 'completed' 
                                ? `Successfully sent ${response.emails_sent} emails. ${response.emails_failed > 0 ? response.emails_failed + ' failed.' : ''}`
                                : `Email sending failed: ${response.error_message || 'Unknown error'}`,
                            icon: response.status === 'completed' ? 'success' : 'error',
                            confirmButtonText: 'Close'
                        });
                    }, 1000);
                }
            },
            error: function () {
                // Stop checking on error
                if (statusCheckInterval) {
                    clearInterval(statusCheckInterval);
                    statusCheckInterval = null;
                }
                
                $('#progressStats').html('❌ Error checking status');
            }
        });
    }
}); 