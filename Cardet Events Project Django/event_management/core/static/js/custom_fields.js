// Custom Fields Page JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded');
    console.log('SweetAlert2 available:', typeof Swal !== 'undefined');
    
    // Try multiple selectors to find the field type select
    const fieldTypeSelect = document.querySelector('select[name="field_type"]') || 
                           document.querySelector('#id_field_type') ||
                           document.querySelector('select[id*="field_type"]');
    
    // Try multiple selectors to find the options textarea
    const optionsTextarea = document.querySelector('textarea[name="options"]') || 
                            document.querySelector('#id_options') ||
                            document.querySelector('textarea[id*="options"]');
    
    // Find the form group/field container (try multiple crispy forms patterns)
    let optionsField = null;
    if (optionsTextarea) {
        optionsField = optionsTextarea.closest('.form-group') || 
                      optionsTextarea.closest('.field') ||
                      optionsTextarea.closest('div[class*="form"]') ||
                      optionsTextarea.closest('.mb-3') ||
                      optionsTextarea.closest('.form-field') ||
                      optionsTextarea.closest('.control-group') ||
                      optionsTextarea.parentElement;
        
        // If still not found, try going up more levels
        if (!optionsField || optionsField === optionsTextarea) {
            let parent = optionsTextarea.parentElement;
            for (let i = 0; i < 5 && parent; i++) {
                if (parent.querySelector('label') || parent.classList.length > 0) {
                    optionsField = parent;
                    break;
                }
                parent = parent.parentElement;
            }
        }
    }
    
    console.log('Found elements:', {
        fieldTypeSelect: fieldTypeSelect,
        optionsTextarea: optionsTextarea,
        optionsField: optionsField
    });
    
    function toggleOptionsField() {
        if (!fieldTypeSelect || !optionsField) {
            console.log('Missing elements for toggle function');
            return;
        }
        
        const fieldType = fieldTypeSelect.value;
        console.log('Current field type:', fieldType);
        
        // Add the options-field class if not already present
        if (!optionsField.classList.contains('options-field')) {
            optionsField.classList.add('options-field');
        }
        
        if (fieldType === 'select' || fieldType === 'multiselect') {
            console.log('Showing options for select/multiselect');
            showOptionsField();
            if (optionsTextarea) {
                optionsTextarea.placeholder = 'Enter comma-separated options (e.g., Option 1, Option 2, Option 3)';
                optionsTextarea.rows = 3;
            }
        } else if (fieldType === 'range') {
            console.log('Showing options for range');
            showOptionsField();
            if (optionsTextarea) {
                optionsTextarea.placeholder = 'Enter min and max values separated by comma (e.g., 0,100)';
                optionsTextarea.rows = 1;
            }
        } else {
            console.log('Hiding options field for:', fieldType);
            hideOptionsField();
        }
    }
    
    function showOptionsField() {
        if (!optionsField) return;
        
        // Reset any inline styles that might interfere
        optionsField.style.display = '';
        optionsField.style.maxHeight = '';
        optionsField.style.opacity = '';
        
        optionsField.classList.remove('hidden', 'hiding');
        optionsField.classList.add('visible');
        
        console.log('Options field shown with classes:', optionsField.classList.toString());
    }
    
    function hideOptionsField() {
        if (!optionsField) return;
        
        optionsField.classList.remove('visible');
        optionsField.classList.add('hiding');
        
        // Wait for animation to complete before hiding
        setTimeout(() => {
            optionsField.classList.remove('hiding');
            optionsField.classList.add('hidden');
        }, 300);
        
        console.log('Options field hidden with classes:', optionsField.classList.toString());
    }
    
    if (fieldTypeSelect) {
        // Set initial state
        toggleOptionsField();
        // Add event listener for changes
        fieldTypeSelect.addEventListener('change', toggleOptionsField);
        console.log('Event listener added to field type select');
    } else {
        console.error('Could not find field type select element');
    }
    
    if (!optionsField) {
        console.error('Could not find options field container');
    }
    
    // Alternative approach: Use label-based targeting if crispy forms structure is different
    if (!optionsField && optionsTextarea) {
        const alternativeOptionsField = document.querySelector('label[for*="options"]')?.parentElement ||
                                       document.querySelector('label[for*="id_options"]')?.parentElement ||
                                       Array.from(document.querySelectorAll('label')).find(label => 
                                           label.textContent.toLowerCase().includes('options')
                                       )?.parentElement;
        
        if (alternativeOptionsField) {
            console.log('Using alternative options field detection');
            optionsField = alternativeOptionsField;
            
            // Re-run the setup with the alternative field
            if (fieldTypeSelect) {
                toggleOptionsField();
                fieldTypeSelect.addEventListener('change', toggleOptionsField);
                console.log('Alternative event listener added');
            }
        }
    }
    

    // Handle delete field with SweetAlert2
    const deleteButtons = document.querySelectorAll('.delete-field-btn');
    console.log('Found delete buttons:', deleteButtons.length);
    
    deleteButtons.forEach((button, index) => {
        console.log(`Setting up button ${index}`, button);
        button.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Delete button clicked', this);
            
            const fieldName = this.dataset.fieldName;
            const fieldId = this.dataset.fieldId;
            console.log('Field name:', fieldName, 'Field ID:', fieldId);
            
            // Find the form by its unique class name
            const deleteForm = document.querySelector(`.delete-form-${fieldId}`);
            console.log('Found form:', deleteForm);
            
            if (!deleteForm) {
                console.error('Delete form not found for field ID:', fieldId);
                return;
            }
            
            Swal.fire({
                title: 'Delete Custom Field?',
                text: `Are you sure you want to delete the field "${fieldName}"? This action cannot be undone.`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#ef4444',
                cancelButtonColor: '#6b7280',
                confirmButtonText: 'Yes, Delete',
                cancelButtonText: 'Cancel',
                reverseButtons: true
            }).then((result) => {
                if (result.isConfirmed) {
                    console.log('Submitting form...');
                    // Submit the hidden form
                    deleteForm.submit();
                } else {
                    console.log('Delete cancelled');
                }
            });
        });
    });
}); 