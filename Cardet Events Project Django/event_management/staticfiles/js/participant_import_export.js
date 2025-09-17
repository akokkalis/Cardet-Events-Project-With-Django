$(document).ready(function() {
    // Import Participants Modal functionality
    const importModal = $('#importParticipantsModal');
    const importBtn = $('#importParticipantsBtn');
    const closeModalBtn = $('#closeImportModal');
    const cancelBtn = $('#cancelImport');
    const importForm = $('#csv-import-form');
    
    // Show modal when import button is clicked
    importBtn.on('click', function() {
        importModal.removeClass('hidden');
    });
    
    // Hide modal functions
    function hideModal() {
        importModal.addClass('hidden');
        // Reset form
        if (importForm.length) {
            importForm[0].reset();
        }
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
    
    // Note: Form submission is now handled by csv_import_progress.js
    
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