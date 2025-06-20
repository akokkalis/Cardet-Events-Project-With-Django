document.addEventListener("DOMContentLoaded", function () {
    function applyFilters() {
        let company = document.getElementById("filter-company").value;
        let status = document.getElementById("filter-status").value;
        let date = document.getElementById("filter-date").value;
        let month = document.getElementById("filter-month").value;
        let year = document.getElementById("filter-year").value;

        let params = new URLSearchParams();
        if (company) params.append("company", company);
        if (status) params.append("status", status);
        
        if (date) {
            // Convert date from dd/mm/yyyy to YYYY-MM-DD for the backend
            const parts = date.split('/');
            if (parts.length === 3) {
                const formattedDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
                params.append("date", formattedDate);
            }
        }

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
                let eventContainer = document.querySelector(".grid");
                eventContainer.innerHTML = "";

                let sortedEvents = data.events.sort((a, b) => {
                    if (a.priority !== b.priority) {
                        return a.priority - b.priority; // Sort by priority
                    }
                    return new Date(a.event_date) - new Date(b.event_date); // Sort by date
                });

                sortedEvents.forEach(event => {
                    // Date formatting
                    const eventDate = new Date(event.event_date + 'T00:00:00'); // Ensure correct parsing
                    const formattedDate = eventDate.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
                    
                    // URLs
                    const detailUrl = `${window.eventDetailUrlBase}${event.id}/`;
                    const editUrl = `${window.eventEditUrlBase}${event.id}/?next=${window.location.pathname + window.location.search}`;

                    let eventHtml = `
                        <div class="event-card bg-white p-8 rounded-lg shadow-md flex flex-col">
                            <!-- Event Image and Status Badge -->
                            <div class="relative w-full mb-3">
                                ${event.image_url ? 
                                    `<img src="${event.image_url}" alt="${event.event_name}" class="w-full h-48 object-cover rounded-lg">` : 
                                    `<div class="w-full h-48 bg-[#e6f0f6] rounded-lg"></div>`
                                }
                                ${event.status ? `
                                    <div class="absolute inset-y-0 right-0 flex items-center">
                                        <span class="bg-[#00b8c4] text-white text-sm font-semibold px-4 py-1 rounded-l-full shadow-lg">
                                            ${event.status}
                                        </span>
                                    </div>` : ''
                                }
                            </div>

                            <!-- Event Details -->
                            <div class="w-full text-left">
                                <h2 class="text-xl font-semibold mb-1">${event.event_name}</h2>
                                <p class="text-brand-blue text-sm inline-block px-3 py-1 rounded-full -ml-3">
                                    ${formattedDate} | ${event.start_time} - ${event.end_time}
                                </p>
                            </div>

                            <!-- Action Buttons -->
                            <div class="mt-4 w-full flex justify-start space-x-2">
                                <a href="${detailUrl}" class="btn btn-outline-blue">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z" /><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd" /></svg>
                                    <span>View</span>
                                </a>
                                <a href="${editUrl}" class="btn btn-outline-blue">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" /><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" /></svg>
                                    <span>Edit</span>
                                </a>
                                <button data-event-id="${event.id}" class="btn btn-outline-pink delete-event-btn">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                                    <span>Delete</span>
                                </button>
                            </div>
                        </div>`;
                    eventContainer.innerHTML += eventHtml;
                });
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
    document.getElementById("filter-company").addEventListener("change", applyFilters);
    document.getElementById("filter-status").addEventListener("change", applyFilters);
    document.getElementById("filter-date").addEventListener("change", applyFilters);
    document.getElementById("filter-month").addEventListener("change", applyFilters);
    document.getElementById("filter-year").addEventListener("change", applyFilters);
    
    // Clear Filters Button
    document.getElementById("clear-filters").addEventListener("click", function () {
        document.querySelectorAll("select, input").forEach(input => input.value = "");
        applyFilters();
    });
});
