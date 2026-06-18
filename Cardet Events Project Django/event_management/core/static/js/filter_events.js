/**
 * filter_events.js
 * Handles all filtering, badge rendering, and table rebuilding for events.html.
 * Requires: flatpickr, SweetAlert2, window.filterUrl, window.csrfToken,
 *           window.eventDetailUrlBase, window.eventEditUrlBase
 */
document.addEventListener("DOMContentLoaded", function () {

    // ── Element references ────────────────────────────────────────
    const els = {
        search:        document.getElementById("filter-search"),
        status:        document.getElementById("filter-status"),
        company:       document.getElementById("filter-company"),
        dateRange:     document.getElementById("filter-date-range"),
        month:         document.getElementById("filter-month"),
        year:          document.getElementById("filter-year"),
        btnMore:       document.getElementById("btn-more-filters"),
        morePanel:     document.getElementById("more-filters-panel"),
        moreBadge:     document.getElementById("more-filters-badge"),
        clearBtn:      document.getElementById("clear-filters"),
        badges:        document.getElementById("filter-badges"),
        tbody:         document.getElementById("events-tbody"),
        count:         document.getElementById("events-count"),
        footerCount:   document.getElementById("events-footer-count"),
    };

    // ── Date range picker ─────────────────────────────────────────
    let dateRangePicker = null;
    if (els.dateRange && typeof flatpickr !== "undefined") {
        dateRangePicker = flatpickr(els.dateRange, {
            mode: "range",
            dateFormat: "Y-m-d",
            altInput: true,
            altFormat: "M j, Y",
            onClose: function () { applyFilters(); },
        });
    }

    // ── More Filters toggle ───────────────────────────────────────
    if (els.btnMore && els.morePanel) {
        els.btnMore.addEventListener("click", function () {
            const open = !els.morePanel.classList.contains("hidden");
            els.morePanel.classList.toggle("hidden", open);
            els.btnMore.classList.toggle("border-indigo-400", !open);
            els.btnMore.classList.toggle("text-indigo-600", !open);
        });
    }

    // ── Client-side name search (instant, no AJAX) ────────────────
    if (els.search) {
        els.search.addEventListener("input", function () {
            const q = this.value.toLowerCase().trim();
            let visible = 0;
            els.tbody.querySelectorAll("tr[data-event-name]").forEach(function (row) {
                const match = row.getAttribute("data-event-name").toLowerCase().includes(q);
                row.style.display = match ? "" : "none";
                if (match) visible++;
            });
            updateCountDisplay(visible);
            updateClearVisibility();
        });
    }

    // ── AJAX filter triggers ──────────────────────────────────────
    [els.status, els.company, els.month, els.year].forEach(function (el) {
        if (el) el.addEventListener("change", applyFilters);
    });

    // ── Clear all filters ─────────────────────────────────────────
    if (els.clearBtn) {
        els.clearBtn.addEventListener("click", function () {
            if (els.search)  els.search.value = "";
            if (els.status)  els.status.value = "";
            if (els.company) els.company.value = "";
            if (els.month)   els.month.value = "";
            if (els.year)    els.year.value = "";
            if (dateRangePicker) dateRangePicker.clear();

            // Show all hidden rows (reset search)
            els.tbody.querySelectorAll("tr[data-event-name]").forEach(r => r.style.display = "");

            applyFilters();
        });
    }

    // ── Main AJAX filter function ─────────────────────────────────
    function applyFilters() {
        if (!window.filterUrl) return;

        const params = new URLSearchParams();

        const status  = els.status  ? els.status.value  : "";
        const company = els.company ? els.company.value : "";
        const month   = els.month   ? els.month.value   : "";
        const year    = els.year    ? els.year.value    : "";

        let dateFrom = "";
        let dateTo   = "";
        if (dateRangePicker && dateRangePicker.selectedDates.length > 0) {
            const fmt = d => d.toISOString().split("T")[0];
            dateFrom = fmt(dateRangePicker.selectedDates[0]);
            dateTo   = dateRangePicker.selectedDates.length > 1
                        ? fmt(dateRangePicker.selectedDates[1])
                        : dateFrom;
        }

        if (status)   params.append("status",    status);
        if (company)  params.append("company",   company);
        if (dateFrom) params.append("date_from", dateFrom);
        if (dateTo && dateTo !== dateFrom) params.append("date_to", dateTo);
        if (month)    params.append("month",     month);
        if (year)     params.append("year",      year);

        fetch(`${window.filterUrl}?${params.toString()}`, {
            method: "GET",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": window.csrfToken || "",
            },
        })
        .then(function (res) {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res.json();
        })
        .then(function (data) {
            rebuildTable(data.events || []);
            updateBadges({ status, company, dateFrom, dateTo, month, year });
            updateClearVisibility();
        })
        .catch(function (err) {
            console.error("Filter error:", err);
        });
    }

    // ── Rebuild tbody from AJAX data ──────────────────────────────
    function rebuildTable(events) {
        const sorted = events.slice().sort(function (a, b) {
            if (a.priority !== b.priority) return a.priority - b.priority;
            return new Date(a.event_date) - new Date(b.event_date);
        });

        if (sorted.length === 0) {
            els.tbody.innerHTML =
                `<tr id="empty-row"><td colspan="7" class="px-4 py-12 text-center text-gray-400 text-sm">No events found.</td></tr>`;
            updateCountDisplay(0);
            return;
        }

        els.tbody.innerHTML = "";

        sorted.forEach(function (event, idx) {
            const date    = new Date(event.event_date + "T00:00:00");
            const fmtDate = date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
            const detail  = `${window.eventDetailUrlBase}${event.id}/`;
            const edit    = `${window.eventEditUrlBase}${event.id}/?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
            const { cls, icon } = statusBadge(event.status || "");

            const tr = document.createElement("tr");
            tr.className = "hover:bg-gray-50/50 transition-colors";
            tr.setAttribute("data-event-name", event.event_name);
            tr.innerHTML = `
                <td class="px-4 py-3 text-gray-400 text-xs">${idx + 1}</td>
                <td class="px-4 py-3 font-medium text-gray-900">${escHtml(event.event_name)}</td>
                <td class="px-4 py-3 text-gray-600">${fmtDate}</td>
                <td class="px-4 py-3 text-gray-600 whitespace-nowrap">${event.start_time} – ${event.end_time}</td>
                <td class="px-4 py-3">
                    <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${cls}">
                        ${icon}${escHtml(event.status)}
                    </span>
                </td>
                <td class="px-4 py-3 text-center">
                    <span class="inline-flex items-center justify-center w-7 h-7 rounded-full bg-indigo-50 text-indigo-600 text-xs font-semibold"
                          title="Total Registrations (excluding rejected)">
                        ${event.participant_count}
                    </span>
                </td>
                <td class="px-4 py-3">
                    <div class="flex items-center justify-end gap-3">
                        <a href="${detail}" class="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-medium transition-colors text-sm">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/><path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/></svg>View
                        </a>
                        <a href="${edit}" class="inline-flex items-center gap-1 text-gray-500 hover:text-gray-700 font-medium transition-colors text-sm">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z"/><path fill-rule="evenodd" d="M2 6a2 2 0 012-2h4a1 1 0 010 2H4v10h10v-4a1 1 0 112 0v4a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" clip-rule="evenodd"/></svg>Edit
                        </a>
                        <button data-event-id="${event.id}"
                                class="delete-event-btn inline-flex items-center gap-1 text-red-500 hover:text-red-700 font-medium transition-colors text-sm">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>Delete
                        </button>
                    </div>
                </td>`;
            els.tbody.appendChild(tr);
        });

        // Re-apply any active text search
        const searchQ = els.search ? els.search.value.toLowerCase().trim() : "";
        let visible = 0;
        els.tbody.querySelectorAll("tr[data-event-name]").forEach(function (row) {
            const match = searchQ === "" || row.getAttribute("data-event-name").toLowerCase().includes(searchQ);
            row.style.display = match ? "" : "none";
            if (match) visible++;
        });

        updateCountDisplay(visible);
        attachDeleteListeners();
    }

    // ── Active filter badges ──────────────────────────────────────
    function updateBadges({ status, company, dateFrom, dateTo, month, year }) {
        if (!els.badges) return;
        els.badges.innerHTML = "";

        const addBadge = function (label, clearFn) {
            const span = document.createElement("span");
            span.className = "inline-flex items-center gap-1.5 bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs font-medium px-2.5 py-1 rounded-full";
            span.innerHTML = `${escHtml(label)}<button type="button" class="hover:text-indigo-900 ml-0.5" aria-label="Remove filter">✕</button>`;
            span.querySelector("button").addEventListener("click", function () {
                clearFn();
                applyFilters();
                updateClearVisibility();
            });
            els.badges.appendChild(span);
        };

        if (status && els.status) {
            const label = els.status.options[els.status.selectedIndex]?.text || status;
            addBadge("Status: " + label, () => { els.status.value = ""; });
        }
        if (company && els.company) {
            const label = els.company.options[els.company.selectedIndex]?.text || company;
            addBadge("Company: " + label, () => { els.company.value = ""; });
        }
        if (dateFrom) {
            const label = dateTo && dateTo !== dateFrom
                ? `Date: ${dateFrom} → ${dateTo}`
                : `Date: ${dateFrom}`;
            addBadge(label, () => { if (dateRangePicker) dateRangePicker.clear(); });
        }
        if (month && els.month) {
            const label = els.month.options[els.month.selectedIndex]?.text || month;
            addBadge("Month: " + label, () => { els.month.value = ""; });
        }
        if (year && els.year) {
            addBadge("Year: " + year, () => { els.year.value = ""; });
        }

        // Show badge indicator on "More Filters" button if month/year active
        const moreActive = !!(month || year);
        if (els.moreBadge) els.moreBadge.classList.toggle("hidden", !moreActive);
    }

    // ── Show/hide "Clear all" button ──────────────────────────────
    function updateClearVisibility() {
        if (!els.clearBtn) return;
        const hasSearch  = els.search  && els.search.value.trim() !== "";
        const hasStatus  = els.status  && els.status.value  !== "";
        const hasCompany = els.company && els.company.value !== "";
        const hasMonth   = els.month   && els.month.value   !== "";
        const hasYear    = els.year    && els.year.value    !== "";
        const hasDate    = dateRangePicker && dateRangePicker.selectedDates.length > 0;
        const anyActive  = hasSearch || hasStatus || hasCompany || hasMonth || hasYear || hasDate;
        els.clearBtn.classList.toggle("hidden", !anyActive);
    }

    // ── Update visible-count displays ─────────────────────────────
    function updateCountDisplay(visible) {
        const total = window.totalEvents || 0;
        const suffix = visible === 1 ? "event" : "events";
        if (els.count)       els.count.textContent       = `${visible} ${suffix} total`;
        if (els.footerCount) els.footerCount.textContent = `Showing ${visible} of ${total} ${suffix}`;
    }

    // ── (Re-)attach delete-confirmation listeners ─────────────────
    function attachDeleteListeners() {
        els.tbody.querySelectorAll(".delete-event-btn").forEach(function (btn) {
            btn.addEventListener("click", function () {
                const id = this.getAttribute("data-event-id");
                Swal.fire({
                    title: "Are you sure?",
                    text: "This event will be permanently deleted!",
                    icon: "warning",
                    showCancelButton: true,
                    confirmButtonColor: "#d33",
                    cancelButtonColor: "#3085d6",
                    confirmButtonText: "Yes, delete it!",
                }).then(function (result) {
                    if (result.isConfirmed) window.location.href = `/delete/${id}/`;
                });
            });
        });
    }

    // ── Helpers ───────────────────────────────────────────────────
    function statusBadge(name) {
        const s = name.toLowerCase();
        let cls, icon;
        if (s.includes("complet")) {
            cls  = "bg-green-100 text-green-700";
            icon = `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>`;
        } else if (s.includes("pending")) {
            cls  = "bg-orange-100 text-orange-700";
            icon = `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/></svg>`;
        } else if (s.includes("cancel")) {
            cls  = "bg-red-100 text-red-700";
            icon = `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/></svg>`;
        } else {
            cls  = "bg-blue-100 text-blue-700";
            icon = `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"/></svg>`;
        }
        return { cls, icon };
    }

    function escHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    // Initial delete listener attachment for server-rendered rows
    attachDeleteListeners();
});
