document.addEventListener("DOMContentLoaded", function () {
    // Function to initialize delete button functionality
    function initializeDeleteButtons() {
        document.querySelectorAll('.delete-event-btn').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const eventId = this.getAttribute('data-event-id');
                
                Swal.fire({
                    title: 'Are you sure?',
                    text: "You won't be able to revert this!",
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonColor: '#ce1f45',
                    cancelButtonColor: '#6c757d',
                    confirmButtonText: 'Yes, delete it!'
                }).then((result) => {
                    if (result.isConfirmed) {
                        // Create a form and submit it
                        const form = document.createElement('form');
                        form.method = 'POST';
                        form.action = `/events/delete/${eventId}/`;
                        
                        const csrfToken = document.createElement('input');
                        csrfToken.type = 'hidden';
                        csrfToken.name = 'csrfmiddlewaretoken';
                        csrfToken.value = window.csrfToken;
                        form.appendChild(csrfToken);
                        
                        document.body.appendChild(form);
                        form.submit();
                    }
                });
            });
        });
    }

    function applyFilters() {
        let company = document.getElementById("filter-company").value;
        let status = document.getElementById("filter-status").value;
        let date = document.getElementById("filter-date").value;
        let month = document.getElementById("filter-month").value;
        let year = document.getElementById("filter-year").value;

        let params = new URLSearchParams();
        if (company) params.append("company", company);
        if (status) params.append("status", status);
        if (date) params.append("date", date);
        if (month) params.append("month", month);
        if (year) params.append("year", year);

        // ✅ Fixed URL: Now matches Django's `urls.py`
        fetch(`${window.filterUrl}?${params.toString()}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': window.csrfToken || '',
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                let eventContainer = document.querySelector(".events-grid");
                eventContainer.innerHTML = "";

                let sortedEvents = data.events.sort((a, b) => {
                    if (a.priority !== b.priority) {
                        return a.priority - b.priority; // Sort by priority
                    }
                    return new Date(a.event_date) - new Date(b.event_date); // Sort by date
                });

                if (sortedEvents.length === 0) {
                    eventContainer.innerHTML = `
                        <div class="empty-state">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            <h3>No Events Found</h3>
                            <p>No events match your current filters.</p>
                        </div>`;
                } else {
                    sortedEvents.forEach(event => {
                        let eventHtml = `
                            <div class="event-card">
                                ${event.status ? `<div class="status-badge" style="background-color: ${event.status_color};">${event.status}</div>` : ''}
                                ${event.image_url ? `<img src="${event.image_url}" alt="${event.event_name}" class="event-image">` : `<div class="event-image-placeholder"><span>No Image</span></div>`}
                                <div class="event-content">
                                    <h2 class="event-title">${event.event_name}</h2>
                                    <p class="event-date">${event.event_date}</p>
                                    <p class="event-time">${event.start_time} - ${event.end_time}</p>
                                    <div class="event-actions">
                                        <a href="/events/${event.id}/" class="btn-secondary">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                            View
                                        </a>
                                        <a href="/events/${event.id}/edit/?next=${window.location.pathname}" class="btn-light">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                            </svg>
                                            Edit
                                        </a>
                                        <button data-event-id="${event.id}" class="delete-event-btn btn-danger">
                                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                            </svg>
                                            Delete
                                        </button>
                                    </div>
                                </div>
                                <div class="registration-badge">
                                    ${event.participant_count || 0}
                                    <div class="tooltip">Total Registrations</div>
                                </div>
                            </div>`;
                        eventContainer.innerHTML += eventHtml;
                    });
                    
                    // Reinitialize delete button functionality
                    initializeDeleteButtons();
                }
            })
            .catch(error => {
                console.error('Filter error:', error);
                // Reload the page if there's an authentication issue
                if (error.message.includes('404') || error.message.includes('403')) {
                    window.location.reload();
                }
            });
    }

    // Event Listeners for Filters
    const filterElements = [
        { id: "filter-company", element: document.getElementById("filter-company") },
        { id: "filter-status", element: document.getElementById("filter-status") },
        { id: "filter-date", element: document.getElementById("filter-date") },
        { id: "filter-month", element: document.getElementById("filter-month") },
        { id: "filter-year", element: document.getElementById("filter-year") }
    ];
    
    filterElements.forEach(({ id, element }) => {
        if (element) {
            element.addEventListener("change", applyFilters);
            console.log(`Event listener attached to ${id}`);
        } else {
            console.error(`Element with id ${id} not found`);
        }
    });
    
    // Clear Filters Button
    const clearButton = document.getElementById("clear-filters");
    if (clearButton) {
        clearButton.addEventListener("click", function () {
            console.log('Clear filters clicked');
            document.querySelectorAll("select, input").forEach(input => input.value = "");
            applyFilters();
        });
        console.log('Clear filters button event listener attached');
    } else {
        console.error('Clear filters button not found');
    }
    
    // Initialize delete buttons on page load
    initializeDeleteButtons();
});
