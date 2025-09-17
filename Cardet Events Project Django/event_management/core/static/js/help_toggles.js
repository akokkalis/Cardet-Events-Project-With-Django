// Help Page Toggle Functionality
// Handles accordion-style sections with smooth animations

function toggleSection(sectionId) {
    const content = document.getElementById(sectionId);
    const header = content.previousElementSibling;
    const icon = header.querySelector('.toggle-icon');
    
    if (content.classList.contains('hidden')) {
        // Open section
        content.classList.remove('hidden');
        content.style.maxHeight = content.scrollHeight + 'px';
        icon.style.transform = 'rotate(180deg)';
        
        // Add smooth animation
        setTimeout(() => {
            content.style.maxHeight = 'none';
        }, 300);
    } else {
        // Close section
        content.style.maxHeight = content.scrollHeight + 'px';
        setTimeout(() => {
            content.style.maxHeight = '0px';
            icon.style.transform = 'rotate(0deg)';
        }, 10);
        
        setTimeout(() => {
            content.classList.add('hidden');
            content.style.maxHeight = '';
        }, 300);
    }
}

// Optional: Open first section by default
document.addEventListener('DOMContentLoaded', function() {
    // Uncomment the line below if you want the first section to be open by default
    // toggleSection('event-status');
    
    // Add keyboard accessibility
    document.querySelectorAll('.toggle-header').forEach(header => {
        header.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                const sectionId = this.nextElementSibling.id;
                toggleSection(sectionId);
            }
        });
        
        // Make headers focusable for keyboard navigation
        header.setAttribute('tabindex', '0');
        header.setAttribute('role', 'button');
        header.setAttribute('aria-expanded', 'false');
    });
});

// Update aria-expanded attribute for accessibility
function updateAriaExpanded(sectionId, isExpanded) {
    const content = document.getElementById(sectionId);
    const header = content.previousElementSibling;
    header.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
}

// Enhanced toggle function with accessibility
function toggleSectionWithA11y(sectionId) {
    const content = document.getElementById(sectionId);
    const isHidden = content.classList.contains('hidden');
    
    toggleSection(sectionId);
    updateAriaExpanded(sectionId, isHidden);
} 