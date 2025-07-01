$(document).ready(function() {
    let selectedParticipants = [];
    
    // Handle "Select All" checkbox
    $('#selectAllCheckbox').on('change', function() {
        const isChecked = $(this).is(':checked');
        $('.participant-checkbox').prop('checked', isChecked);
        
        if (isChecked) {
            selectedParticipants = [];
            $('.participant-checkbox').each(function() {
                selectedParticipants.push(parseInt($(this).data('participant-id')));
            });
        } else {
            selectedParticipants = [];
        }
        
        updateBulkActionsVisibility();
    });
    
    // Handle individual participant checkboxes
    $(document).on('change', '.participant-checkbox', function() {
        const participantId = parseInt($(this).data('participant-id'));
        const isChecked = $(this).is(':checked');
        
        if (isChecked) {
            if (!selectedParticipants.includes(participantId)) {
                selectedParticipants.push(participantId);
            }
        } else {
            selectedParticipants = selectedParticipants.filter(id => id !== participantId);
            // Uncheck "Select All" if individual item is unchecked
            $('#selectAllCheckbox').prop('checked', false);
        }
        
        // Update "Select All" checkbox state
        const totalCheckboxes = $('.participant-checkbox').length;
        const checkedCheckboxes = $('.participant-checkbox:checked').length;
        $('#selectAllCheckbox').prop('checked', totalCheckboxes === checkedCheckboxes);
        
        updateBulkActionsVisibility();
    });
    
    // Update bulk actions visibility and count
    function updateBulkActionsVisibility() {
        const selectedCount = selectedParticipants.length;
        
        if (selectedCount > 0) {
            $('#bulkActionsContainer').removeClass('hidden');
            $('#selectedCount').text(`${selectedCount} selected`);
        } else {
            $('#bulkActionsContainer').addClass('hidden');
        }
    }
    
    // Handle bulk approval
    $('#bulkApproveBtn').on('click', function() {
        if (selectedParticipants.length === 0) {
            Swal.fire('Error', 'No participants selected', 'error');
            return;
        }
        
        Swal.fire({
            title: 'Approve Selected Participants?',
            text: `Are you sure you want to approve ${selectedParticipants.length} participants?`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#10b981',
            cancelButtonColor: '#6b7280',
            confirmButtonText: 'Yes, approve them!'
        }).then((result) => {
            if (result.isConfirmed) {
                performBulkAction('approve');
            }
        });
    });
    
    // Handle bulk rejection
    $('#bulkRejectBtn').on('click', function() {
        if (selectedParticipants.length === 0) {
            Swal.fire('Error', 'No participants selected', 'error');
            return;
        }
        
        Swal.fire({
            title: 'Reject Selected Participants?',
            text: `Are you sure you want to reject ${selectedParticipants.length} participants?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#6b7280',
            confirmButtonText: 'Yes, reject them!'
        }).then((result) => {
            if (result.isConfirmed) {
                performBulkAction('reject');
            }
        });
    });
    
    // Handle bulk set to pending
    $('#bulkPendingBtn').on('click', function() {
        if (selectedParticipants.length === 0) {
            Swal.fire('Error', 'No participants selected', 'error');
            return;
        }
        
        Swal.fire({
            title: 'Set Selected Participants to Pending?',
            text: `Are you sure you want to set ${selectedParticipants.length} participants to pending status?`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#f59e0b',
            cancelButtonColor: '#6b7280',
            confirmButtonText: 'Yes, set to pending!'
        }).then((result) => {
            if (result.isConfirmed) {
                performBulkAction('pending');
            }
        });
    });
    
    // Clear selection
    $('#clearSelectionBtn').on('click', function() {
        selectedParticipants = [];
        $('.participant-checkbox').prop('checked', false);
        $('#selectAllCheckbox').prop('checked', false);
        updateBulkActionsVisibility();
    });
    
    // Perform bulk action
    function performBulkAction(action) {
        // Show loading state
        Swal.fire({
            title: 'Processing...',
            text: 'Please wait while we update the participants.',
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
        
        // Make AJAX request
        $.ajax({
            url: `/events/${window.EVENT_ID}/bulk-approve/`,
            type: 'POST',
            headers: {
                'X-CSRFToken': window.csrfToken,
                'Content-Type': 'application/json',
            },
            data: JSON.stringify({
                participant_ids: selectedParticipants,
                action: action
            }),
            success: function(response) {
                if (response.success) {
                    Swal.fire({
                        title: 'Success!',
                        text: response.message,
                        icon: 'success',
                        confirmButtonText: 'OK'
                    }).then(() => {
                        // Reload the page to show updated statuses
                        window.location.reload();
                    });
                } else {
                    Swal.fire('Error', response.error || 'An error occurred', 'error');
                }
            },
            error: function(xhr) {
                let errorMessage = 'An error occurred while processing the request.';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMessage = xhr.responseJSON.error;
                }
                Swal.fire('Error', errorMessage, 'error');
            }
        });
    }
}); 