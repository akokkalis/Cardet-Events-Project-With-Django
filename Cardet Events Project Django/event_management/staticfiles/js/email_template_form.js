// Email Template Form JavaScript Functionality

// Live preview functionality
document.addEventListener('DOMContentLoaded', function() {
    const subjectField = document.getElementById('id_subject');
    const subjectPreview = document.getElementById('subject-preview');
    const bodyPreview = document.getElementById('body-preview');

    function updateSubjectPreview() {
        const subjectValue = subjectField.value || '[Subject will appear here]';
        subjectPreview.textContent = subjectValue;
    }

    function updateBodyPreview() {
        // Get CKEditor instance for body field
        const editorName = 'id_body';
        if (window.CKEDITOR && window.CKEDITOR.instances[editorName]) {
            const editorData = window.CKEDITOR.instances[editorName].getData();
            const bodyValue = editorData || '[Email body will appear here]';
            bodyPreview.innerHTML = bodyValue;
        }
    }

    // Subject field listener
    if (subjectField) {
        subjectField.addEventListener('input', updateSubjectPreview);
    }

    // CKEditor listener - wait for CKEditor to be ready
    if (window.CKEDITOR) {
        window.CKEDITOR.on('instanceReady', function(evt) {
            const editorName = 'id_body';
            if (evt.editor.name === editorName) {
                // Update preview when CKEditor content changes
                evt.editor.on('change', updateBodyPreview);
                evt.editor.on('key', function() {
                    // Use setTimeout to ensure the content is updated
                    setTimeout(updateBodyPreview, 100);
                });
                // Initial update
                updateBodyPreview();
            }
        });
    }

    // Initial call to set previews on page load
    updateSubjectPreview();
});

// Function to copy RSVP template to clipboard
function copyRsvpTemplate() {
    const templateCode = document.getElementById('rsvp-template-code').textContent;
    const button = event.target;
    const originalText = button.textContent;
    
    // Try modern clipboard API first
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(templateCode).then(function() {
            // Show success feedback
            button.textContent = '✅ Copied!';
            button.classList.remove('bg-blue-500', 'hover:bg-blue-600');
            button.classList.add('bg-green-500');
            
            // SweetAlert success message
            Swal.fire({
                icon: 'success',
                title: 'Copied!',
                text: 'RSVP template copied to clipboard successfully.',
                timer: 2000,
                showConfirmButton: false,
                toast: true,
                position: 'top-end'
            });
            
            setTimeout(function() {
                button.textContent = originalText;
                button.classList.remove('bg-green-500');
                button.classList.add('bg-blue-500', 'hover:bg-blue-600');
            }, 2000);
        }).catch(function(err) {
            console.error('Clipboard API failed: ', err);
            fallbackCopyTextToClipboard(templateCode, button, originalText);
        });
    } else {
        // Fallback for older browsers or non-secure contexts
        fallbackCopyTextToClipboard(templateCode, button, originalText);
    }
}

// Fallback copy function
function fallbackCopyTextToClipboard(text, button, originalText) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        const successful = document.execCommand('copy');
        if (successful) {
            // Show success feedback
            button.textContent = '✅ Copied!';
            button.classList.remove('bg-blue-500', 'hover:bg-blue-600');
            button.classList.add('bg-green-500');
            
            // SweetAlert success message
            Swal.fire({
                icon: 'success',
                title: 'Copied!',
                text: 'RSVP template copied to clipboard successfully.',
                timer: 2000,
                showConfirmButton: false,
                toast: true,
                position: 'top-end'
            });
            
            setTimeout(function() {
                button.textContent = originalText;
                button.classList.remove('bg-green-500');
                button.classList.add('bg-blue-500', 'hover:bg-blue-600');
            }, 2000);
        } else {
            throw new Error('Copy command failed');
        }
    } catch (err) {
        console.error('Fallback copy failed: ', err);
        // Select the text for manual copying
        const codeElement = document.getElementById('rsvp-template-code');
        if (window.getSelection) {
            const selection = window.getSelection();
            const range = document.createRange();
            range.selectNodeContents(codeElement);
            selection.removeAllRanges();
            selection.addRange(range);
        }
        
        // SweetAlert error message with instructions
        Swal.fire({
            icon: 'info',
            title: 'Manual Copy Required',
            html: 'Automatic copying failed. The text has been selected for you.<br><br><strong>Please press Ctrl+C (or Cmd+C on Mac) to copy.</strong>',
            confirmButtonText: 'Got it!',
            confirmButtonColor: '#3b82f6'
        });
    } finally {
        document.body.removeChild(textArea);
    }
} 