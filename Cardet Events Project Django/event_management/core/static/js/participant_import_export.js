$(document).ready(function() {
    // Import Participants Modal functionality
    const importModal = $('#importParticipantsModal');
    const importBtn = $('#importParticipantsBtn');
    const closeModalBtn = $('#closeImportModal');
    const cancelBtn = $('#cancelImport');
    const importForm = $('#importForm');
    
    // Show modal when import button is clicked
    importBtn.on('click', function() {
        importModal.removeClass('hidden');
    });
    
    // Hide modal functions
    function hideModal() {
        importModal.addClass('hidden');
        // Reset form
        importForm[0].reset();
    }
    
    // Close modal events
    closeModalBtn.on('click', hideModal);
    cancelBtn.on('click', hideModal);
    
    // Close modal when clicking outside
    importModal.on('click', function(e) {
        if (e.target === this) {
            hideModal();
        }
    });
    
    // Handle form submission with loading state
    importForm.on('submit', function(e) {
        const fileInput = $('#csv_file')[0];
        
        if (!fileInput.files.length) {
            e.preventDefault();
            Swal.fire('Error', 'Please select a CSV file to upload.', 'error');
            return;
        }
        
        const file = fileInput.files[0];
        if (!file.name.toLowerCase().endsWith('.csv')) {
            e.preventDefault();
            Swal.fire('Error', 'Please select a valid CSV file.', 'error');
            return;
        }
        
        // Show loading state
        Swal.fire({
            title: 'Importing Participants...',
            text: 'Please wait while we process your CSV file.',
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
        
        // Form will submit normally, loading will be closed by page reload or redirect
    });
    
    // File input validation
    $('#csv_file').on('change', function() {
        const file = this.files[0];
        if (file) {
            if (!file.name.toLowerCase().endsWith('.csv')) {
                Swal.fire('Error', 'Please select a valid CSV file.', 'error');
                this.value = '';
            } else if (file.size > 5 * 1024 * 1024) { // 5MB limit
                Swal.fire('Error', 'File size must be less than 5MB.', 'error');
                this.value = '';
            }
        }
    });
    
    // Add keyboard shortcuts
    $(document).on('keydown', function(e) {
        // Escape key to close modal
        if (e.key === 'Escape' && !importModal.hasClass('hidden')) {
            hideModal();
        }
    });
}); 