// Event Detail Modals and Participant Management JavaScript
// Handles SweetAlert2 modals, participant approval/rejection, PDF generation monitoring, and ticket sending

$(document).ready(function() {
    const participantsBeingChecked = new Set();
    let currentProcessingAlert = null;

    // SweetAlert2 control functions
    function showProcessingAlert(title, message) {
        currentProcessingAlert = Swal.fire({
            title: title,
            html: message,
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
        return currentProcessingAlert;
    }

    function showSuccessAlert(title, message, autoReload = true) {
        if (currentProcessingAlert) {
            currentProcessingAlert.close();
        }
        
        Swal.fire({
            icon: 'success',
            title: title,
            html: message,
            confirmButtonText: 'OK',
            confirmButtonColor: '#10b981',
            timer: autoReload ? 3000 : null,
            timerProgressBar: autoReload,
            showConfirmButton: !autoReload
        }).then((result) => {
            if (autoReload || result.isConfirmed) {
                location.reload();
            }
        });
    }

    function showErrorAlert(title, message) {
        if (currentProcessingAlert) {
            currentProcessingAlert.close();
        }
        
        Swal.fire({
            icon: 'error',
            title: title,
            html: message,
            confirmButtonText: 'Close',
            confirmButtonColor: '#ef4444'
        }).then(() => {
            // Optionally reload on error too
            location.reload();
        });
    }

    // Function to check participant status
    function checkParticipantStatus(participantId, eventId) {
        if (participantsBeingChecked.has(participantId)) {
            return; // Already checking this participant
        }

        participantsBeingChecked.add(participantId);

        $.ajax({
            url: `/events/${eventId}/participants/${participantId}/status/`,
            method: 'GET',
            success: function(data) {
                updateParticipantRow(data);

                // If PDF is ready or status is not approved, stop checking
                if (data.has_pdf_ticket || data.approval_status !== 'approved') {
                    participantsBeingChecked.delete(participantId);
                }
            },
            error: function(xhr, status, error) {
                console.error('Error checking participant status:', error);
                participantsBeingChecked.delete(participantId);
            }
        });
    }

    // Function to update participant row with new data
    function updateParticipantRow(data) {
        const participantId = data.participant_id;
        const statusCell = $(`#status-cell-${participantId}`);
        const pdfCell = $(`#pdf-ticket-cell-${participantId}`);
        const sendTicketCell = $(`#send-ticket-cell-${participantId}`);

        if (statusCell.length) {
            statusCell.html(data.status_badge_html);
            pdfCell.html(data.pdf_download_html);
            sendTicketCell.html(data.send_ticket_html);

            // Re-bind send ticket button event if it was created
            if (data.has_pdf_ticket) {
                bindSendTicketEvent();
            }
        }
    }

    // Function to start checking a specific participant
    function startCheckingParticipant(participantId, eventId) {
        // Check immediately
        checkParticipantStatus(participantId, eventId);

        // Set up interval to check every 2 seconds for up to 30 seconds
        let checkCount = 0;
        const maxChecks = 15; // 30 seconds total

        const interval = setInterval(function() {
            checkCount++;

            if (checkCount >= maxChecks || !participantsBeingChecked.has(participantId)) {
                clearInterval(interval);
                participantsBeingChecked.delete(participantId);
                return;
            }

            checkParticipantStatus(participantId, eventId);
        }, 2000);
    }

    // Function to monitor PDF generation with modal feedback
    function monitorPDFGeneration(participantId, eventId, participantName) {
        let checkCount = 0;
        const maxChecks = 30; // 60 seconds total
        let hasPDF = false;

        const checkInterval = setInterval(function() {
            $.ajax({
                url: `/events/${eventId}/participants/${participantId}/status/`,
                method: 'GET',
                success: function(data) {
                    if (data.has_pdf_ticket) {
                        hasPDF = true;
                        clearInterval(checkInterval);
                        
                        // Show success alert
                        showSuccessAlert(
                            'Success!',
                            `<strong>${participantName}</strong> has been approved and PDF ticket generated successfully!<br><br>Page will reload in 3 seconds...`
                        );
                    } else {
                        checkCount++;
                        
                        // Update progress message with dots animation
                        const dots = '.'.repeat((checkCount % 3) + 1);
                        if (currentProcessingAlert) {
                            Swal.update({
                                html: `Generating PDF ticket for <strong>${participantName}</strong>${dots}`
                            });
                        }
                        
                        if (checkCount >= maxChecks) {
                            clearInterval(checkInterval);
                            showErrorAlert(
                                'Generation Taking Longer Than Expected',
                                `PDF generation is taking longer than usual. The participant <strong>${participantName}</strong> has been approved, but the PDF ticket may still be generating.<br><br>Please refresh the page in a few moments.`
                            );
                        }
                    }
                },
                error: function() {
                    checkCount++;
                    if (checkCount >= maxChecks) {
                        clearInterval(checkInterval);
                        showErrorAlert(
                            'Generation Error',
                            'Unable to check PDF generation status. Please refresh the page to see the current status.'
                        );
                    }
                }
            });
        }, 2000); // Check every 2 seconds
    }

    // Intercept approval button clicks
    $(document).on('click', 'a[href*="/approve/"]', function(e) {
        e.preventDefault(); // Prevent default navigation
        
        const href = $(this).attr('href');
        const matches = href.match(/\/events\/(\d+)\/participants\/(\d+)\/approve\//);

        if (matches) {
            const eventId = matches[1];
            const participantId = matches[2];
            const participantName = $(this).closest('tr').find('td:nth-child(2)').text();
            
            // Check if event requires tickets
            const requiresTickets = window.EVENT_REQUIRES_TICKETS;
            
            // Only show processing alert if tickets are required
            if (requiresTickets) {
                showProcessingAlert(
                    'Approving Participant', 
                    `Approving <strong>${participantName}</strong> and generating PDF ticket...`
                );
            }

            // Make the approval request
            $.ajax({
                url: href,
                method: 'GET',
                success: function(response) {
                    if (requiresTickets) {
                        // Start monitoring PDF generation only if tickets are required
                        monitorPDFGeneration(participantId, eventId, participantName);
                    } else {
                        // Show immediate success for events without tickets (no processing message)
                        showSuccessAlert(
                            'Success!',
                            `<strong>${participantName}</strong> has been approved successfully!<br><br>Page will reload in 3 seconds...`
                        );
                    }
                },
                error: function(xhr, status, error) {
                    showErrorAlert(
                        'Approval Failed',
                        'Failed to approve participant. Please try again.'
                    );
                }
            });
        }
    });

    // Intercept reject button clicks
    $(document).on('click', 'a[href*="/reject/"]', function(e) {
        e.preventDefault();
        
        const href = $(this).attr('href');
        const participantName = $(this).closest('tr').find('td:nth-child(2)').text();
        
        showProcessingAlert(
            'Rejecting Participant',
            `Rejecting <strong>${participantName}</strong>...`
        );

        $.ajax({
            url: href,
            method: 'GET',
            success: function(response) {
                showSuccessAlert(
                    'Participant Rejected',
                    `<strong>${participantName}</strong> has been rejected.<br><br>Page will reload in 3 seconds...`
                );
            },
            error: function() {
                showErrorAlert(
                    'Rejection Failed',
                    'Failed to reject participant. Please try again.'
                );
            }
        });
    });

    // Intercept pending button clicks
    $(document).on('click', 'a[href*="/pending/"]', function(e) {
        e.preventDefault();
        
        const href = $(this).attr('href');
        const participantName = $(this).closest('tr').find('td:nth-child(2)').text();
        
        showProcessingAlert(
            'Setting Participant to Pending',
            `Setting <strong>${participantName}</strong> to pending status...`
        );

        $.ajax({
            url: href,
            method: 'GET',
            success: function(response) {
                showSuccessAlert(
                    'Status Updated',
                    `<strong>${participantName}</strong> has been set to pending.<br><br>Page will reload in 3 seconds...`
                );
            },
            error: function() {
                showErrorAlert(
                    'Update Failed',
                    'Failed to update participant status. Please try again.'
                );
            }
        });
    });

    // Function to bind send ticket events (for dynamically created buttons)
    function bindSendTicketEvent() {
        $('.send-ticket-btn').off('click').on('click', function() {
            const participantId = $(this).data('participant-id');
            const participantName = $(this).closest('tr').find('td:nth-child(2)').text();

            showProcessingAlert(
                'Sending Ticket',
                `Sending PDF ticket to <strong>${participantName}</strong> via email...`
            );

            $.ajax({
                url: window.sendTicketUrl, // This will be set from the template
                method: 'POST',
                data: {
                    'participant_id': participantId,
                    'csrfmiddlewaretoken': window.csrfToken // This will be set from the template
                },
                success: function(response) {
                    if (response.status === 'success') {
                        showSuccessAlert(
                            'Ticket Sent!',
                            `PDF ticket has been sent to <strong>${participantName}</strong> successfully!`,
                            false // Don't auto-reload for send ticket
                        );
                    } else {
                        showErrorAlert(
                            'Send Failed',
                            response.message || 'Failed to send ticket email'
                        );
                    }
                },
                error: function(xhr, status, error) {
                    let errorMessage = 'Failed to send ticket email. Please try again.';
                    
                    // Try to get error message from server response
                    if (xhr.responseJSON && xhr.responseJSON.message) {
                        errorMessage = xhr.responseJSON.message;
                    }
                    
                    showErrorAlert(
                        'Send Failed',
                        errorMessage
                    );
                }
            });
        });
    }

    // Initialize send ticket button events
    bindSendTicketEvent();

    // Email templates button loading handler
    const emailTemplatesBtn = document.getElementById('emailTemplatesBtn');
    const loadingOverlay = document.getElementById('loadingOverlay');
    
    if (emailTemplatesBtn) {
        emailTemplatesBtn.addEventListener('click', function(e) {
            // Show loading overlay
            if (loadingOverlay) {
                loadingOverlay.style.display = 'flex';
            }
            
            // Add loading state to button
            this.style.opacity = '0.7';
            this.style.pointerEvents = 'none';
        });
    }
    
    // Hide loading on page unload (in case of errors)
    window.addEventListener('beforeunload', function() {
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    });
    
    // Handle page errors - hide loading if there's an error
    window.addEventListener('error', function() {
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
        if (emailTemplatesBtn) {
            emailTemplatesBtn.style.opacity = '1';
            emailTemplatesBtn.style.pointerEvents = 'auto';
        }
    });
}); 