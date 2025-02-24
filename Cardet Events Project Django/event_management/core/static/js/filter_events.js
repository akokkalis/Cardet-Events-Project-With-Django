document.addEventListener("DOMContentLoaded", function () {
    function fetchFilteredEvents() {
        let company = document.getElementById("company-filter").value;
        let status = document.getElementById("status-filter").value;
        let date = document.getElementById("date-filter").value;

        let url = `/events/filter/?company=${company}&status=${status}&date=${date}`;

        fetch(url)
            .then(response => response.json())
            .then(data => {
                let eventContainer = document.querySelector(".grid");
                eventContainer.innerHTML = "";

                if (data.events.length === 0) {
                    eventContainer.innerHTML = "<p class='text-gray-600 text-center'>No events found.</p>";
                    return;
                }

                data.events.forEach(event => {
                    let eventHtml = `
                        <div class="relative bg-white p-4 rounded-lg shadow-md flex flex-col items-center">
                            <!-- Event Status Ribbon -->
                            <div class="absolute top-8 right-[-10px] bg-gray-700 text-white px-5 py-1 text-sm font-semibold rounded-lg shadow-md transform rotate-45"
                                 style="background-color: ${event.status_color};">
                                ${event.status}
                            </div>

                            <!-- Event Image -->
                            ${event.image_url ? 
                                `<img src="${event.image_url}" alt="${event.event_name}" class="w-full h-48 object-cover rounded-lg mb-3">` :
                                `<div class="w-full h-48 bg-gray-300 flex items-center justify-center rounded-lg mb-3">
                                    <span class="text-gray-600">No Image</span>
                                </div>`}

                            <!-- Event Details -->
                            <h2 class="text-xl font-semibold text-center">${event.event_name}</h2>
                            <p class="text-gray-600">${event.event_date}</p>
                            <p class="text-gray-600">${event.start_time} - ${event.end_time}</p>
                            <p class="text-gray-600"><strong>Company:</strong> ${event.company}</p>

                            <!-- Action Buttons -->
                            <div class="mt-4 w-full flex justify-center space-x-3">
                                <a href="/events/${event.id}/" class="bg-blue-500 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-blue-700">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.2-4.2m-1.4-1.4a2.1 2.1 0 112.8 2.8L16.8 11m-4.2 4.2L7 21m-4-4l4.2-4.2" />
                                    </svg>
                                    View
                                </a>
                                <a href="/events/edit/${event.id}/" class="bg-yellow-500 text-white px-4 py-2 rounded-lg flex items-center gap-2 hover:bg-yellow-700">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2V5a2 2 0 012-2z" />
                                    </svg>
                                    Edit
                                </a>
                            </div>
                        </div>
                    `;
                    eventContainer.innerHTML += eventHtml;
                });
            })
            .catch(error => console.error("Error:", error));
    }

    // Event Listeners for Filters
    document.getElementById("company-filter").addEventListener("change", fetchFilteredEvents);
    document.getElementById("status-filter").addEventListener("change", fetchFilteredEvents);
    document.getElementById("date-filter").addEventListener("change", fetchFilteredEvents);

    // Clear Filters Button
    document.getElementById("clear-filters").addEventListener("click", function () {
        document.getElementById("company-filter").value = "";
        document.getElementById("status-filter").value = "";
        document.getElementById("date-filter").value = "";
        fetchFilteredEvents();
    });
});
