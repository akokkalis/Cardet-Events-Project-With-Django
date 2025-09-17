// Wait for the DOM to be ready
document.addEventListener('DOMContentLoaded', () => {
    // Get the loading indicator and its data
    const loadingIndicator = document.getElementById('loading-indicator');
    if (!loadingIndicator) {
        console.error('Loading indicator not found');
        return;
    }

    // Get configuration from data attributes
    const config = {
        csrfToken: loadingIndicator.dataset.csrfToken,
        filterUrl: loadingIndicator.dataset.filterUrl,
        detailUrl: loadingIndicator.dataset.detailUrl,
        editUrl: loadingIndicator.dataset.editUrl,
        hasMore: loadingIndicator.dataset.hasMore === 'true'
    };

    // Check if required configuration is available
    if (!config.csrfToken || !config.filterUrl) {
        console.error('Required configuration not found');
        return;
    }

    let currentPage = 1;
    let isLoading = false;
    let hasMore = config.hasMore;

    // Create IntersectionObserver for infinite scroll
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !isLoading && hasMore) {
                loadMoreEvents();
            }
        });
    }, { threshold: 0.1 });

    // Observe the loading indicator
    observer.observe(loadingIndicator);

    async function loadMoreEvents() {
        if (isLoading || !hasMore) return;
        
        isLoading = true;
        loadingIndicator.classList.remove('hidden');
        currentPage++;

        try {
            // Get current filter values
            const statusFilter = document.getElementById('filter-status').value;
            const companyFilter = document.getElementById('filter-company').value;
            const dateFilter = document.getElementById('filter-date').value;
            const monthFilter = document.getElementById('filter-month').value;
            const yearFilter = document.getElementById('filter-year').value;

            const params = new URLSearchParams({
                page: currentPage,
                status: statusFilter,
                company: companyFilter,
                date: dateFilter,
                month: monthFilter,
                year: yearFilter
            });

            const response = await fetch(`${config.filterUrl}?${params}`, {
                headers: {
                    'X-CSRFToken': config.csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const data = await response.json();
            
            if (data.events.length > 0) {
                const eventsGrid = document.getElementById('events-grid');
                data.events.forEach(event => {
                    const eventCard = createEventCard(event);
                    eventsGrid.appendChild(eventCard);
                });
            }

            hasMore = data.has_more;
            if (!hasMore) {
                loadingIndicator.classList.add('hidden');
            }

        } catch (error) {
            console.error('Error loading more events:', error);
            loadingIndicator.classList.add('hidden');
        } finally {
            isLoading = false;
        }
    }

    function createEventCard(event) {
        const card = document.createElement('div');
        card.className = 'event-card bg-white p-6 rounded-md shadow-md flex flex-col items-center relative';
        
        // Format the event date and times
        const eventDate = new Date(event.event_date);
        const formattedDate = eventDate.toLocaleDateString('en-US', { 
            month: 'long', 
            day: 'numeric', 
            year: 'numeric' 
        });

        const imageHtml = event.image 
            ? `<img src="${event.image}" alt="${event.event_name}" class="block">`
            : `<div class="bg-[#e6f0f6] img-placeholder flex items-center justify-center">
                   <span class="text-gray-500">No Image</span>
               </div>`;

        const statusHtml = event.status
            ? `<div class="absolute top-1/2 -translate-y-1/2 right-[-0px] mt-10">
                   <span class="status-badge-shape bg-[#00b8c4] text-white text-sm font-semibold pl-4 pr-6 py-2 shadow-lg">
                       ${event.status.name}
                   </span>
               </div>`
            : '';

        card.innerHTML = `
            <div class="mb-3">
                <div class="relative inline-block my-2.5">
                    ${imageHtml}
                    ${statusHtml}
                </div>
            </div>
            <div class="text-left" style="width: 361px;">
                <h2 class="text-xl font-semibold mb-1">${event.event_name}</h2>
                <p class="text-brand-blue text-sm inline-block px-3 py-1 rounded-full -ml-3">
                    ${formattedDate} | ${event.start_time || ''} - ${event.end_time || ''}
                </p>
            </div>
            <div class="mt-5 flex justify-start space-x-3" style="width: 361px;">
                <a href="${config.detailUrl}${event.id}" class="btn btn-outline-blue" style="width: 109px; height: 44.5px; border-radius: 6px;">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd" />
                    </svg>
                    <span>View</span>
                </a>
                <a href="${config.editUrl}${event.id}" class="btn btn-outline-blue" style="width: 93px; height: 44.5px; border-radius: 6px;">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />
                        <path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd" />
                    </svg>
                    <span>Edit</span>
                </a>
                <button data-event-id="${event.id}" class="btn btn-outline-pink delete-event-btn" style="width: 109px; height: 44.5px; border-radius: 6px;">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
                    </svg>
                    <span>Delete</span>
                </button>
            </div>
            <div class="absolute bottom-2 right-2 group">
                <div class="bg-brand-blue text-white text-sm font-bold w-8 h-8 flex items-center justify-center rounded-full shadow-lg cursor-pointer">
                    ${event.participant_count || 0}
                </div>
                <div class="absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 w-max bg-gray-800 text-white text-xs rounded py-1 px-3 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    Total Registrations
                </div>
            </div>
        `;

        // Add event listener for delete button
        const deleteButton = card.querySelector('.delete-event-btn');
        if (deleteButton) {
            deleteButton.addEventListener('click', function(e) {
                e.preventDefault();
                if (window.handleDeleteEvent) {
                    window.handleDeleteEvent(e);
                }
            });
        }

        return card;
    }

    // Reset infinite scroll when filters change
    document.querySelectorAll('.filter-select, .filter-date').forEach(filter => {
        filter.addEventListener('change', () => {
            currentPage = 1;
            hasMore = true;
            const eventsGrid = document.getElementById('events-grid');
            eventsGrid.innerHTML = '';
            loadingIndicator.classList.remove('hidden');
            loadMoreEvents();
        });
    });
}); 