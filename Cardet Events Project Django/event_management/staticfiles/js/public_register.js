// Public Registration Form JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('Public registration form loaded');
    console.log('Flatpickr available:', typeof flatpickr !== 'undefined');
    console.log('jQuery available:', typeof $ !== 'undefined');
    console.log('Select2 available:', typeof $.fn.select2 !== 'undefined');
    
    // Initialize Flatpickr for date fields
    const dateFields = document.querySelectorAll('.flatpickr-date');
    console.log('Found date fields:', dateFields.length);
    dateFields.forEach(field => {
        flatpickr(field, {
            dateFormat: "Y-m-d",
            allowInput: true,
            clickOpens: true,
            theme: "light",
            locale: "default"
        });
    });

    // Initialize Flatpickr for time fields
    const timeFields = document.querySelectorAll('.flatpickr-time');
    console.log('Found time fields:', timeFields.length);
    timeFields.forEach(field => {
        flatpickr(field, {
            enableTime: true,
            noCalendar: true,
            dateFormat: "H:i",
            time_24hr: true,
            allowInput: true,
            clickOpens: true,
            theme: "light"
        });
    });

    // Initialize Flatpickr for datetime fields
    const datetimeFields = document.querySelectorAll('.flatpickr-datetime');
    console.log('Found datetime fields:', datetimeFields.length);
    datetimeFields.forEach(field => {
        flatpickr(field, {
            enableTime: true,
            dateFormat: "Y-m-d H:i",
            time_24hr: true,
            allowInput: true,
            clickOpens: true,
            theme: "light"
        });
    });
    
    console.log('Flatpickr initialization complete');
    
    // Initialize Select2 for multiselect fields
    if (typeof $ !== 'undefined' && typeof $.fn.select2 !== 'undefined') {
        const multiselectFields = $('.select2-multiselect');
        console.log('Found multiselect fields:', multiselectFields.length);
        
        multiselectFields.each(function() {
            $(this).select2({
                theme: 'default',
                placeholder: 'Choose options...',
                allowClear: true,
                width: '100%',
                closeOnSelect: false,
                tags: false,
                tokenSeparators: [','],
                escapeMarkup: function (markup) {
                    return markup;
                }
            });
        });
        
        console.log('Select2 initialization complete');
    } else {
        console.error('jQuery or Select2 not available');
    }
}); 