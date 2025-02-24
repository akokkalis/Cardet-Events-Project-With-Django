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
        if (date) params.append("date", date);
        if (month) params.append("month", month);
        if (year) params.append("year", year);

        // ✅ Fixed URL: Now matches Django's `urls.py`
        fetch(`/events/filter/?${params.toString()}`)
            .then(response => response.json())
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
                    let eventHtml = `
                        <div class="relative bg-white p-4 rounded-lg shadow-md flex flex-col items-center">
                            ${event.status ? `<div class="absolute top-8 right-[-10px] bg-gray-700 text-white px-5 py-1 text-sm font-semibold rounded-lg shadow-md transform rotate-45" style="background-color: ${event.status_color};">${event.status}</div>` : ''}
                            ${event.image_url ? `<img src="${event.image_url}" alt="${event.event_name}" class="w-full h-48 object-cover rounded-lg mb-3">` : `<div class="w-full h-48 bg-gray-300 flex items-center justify-center rounded-lg mb-3"><span class="text-gray-600">No Image</span></div>`}
                            <h2 class="text-xl font-semibold text-center">${event.event_name}</h2>
                            <p class="text-gray-600">${event.event_date}</p>
                            <p class="text-gray-600">${event.start_time} - ${event.end_time}</p>
                            <div class="mt-4 w-full flex justify-center space-x-3">
                                <a href="/events/${event.id}/" class="bg-blue-500 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-blue-700">View</a>
                                <a href="/events/edit/${event.id}/" class="bg-yellow-500 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-yellow-700">Edit</a>
                                <button data-event-id="${event.id}" class="delete-event-btn bg-red-500 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-red-700">Delete</button>
                            </div>
                        </div>`;
                    eventContainer.innerHTML += eventHtml;
                });
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
