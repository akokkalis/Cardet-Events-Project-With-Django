document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("search-input");
    const tableRows = document.querySelectorAll("#participant-table tr");

    searchInput.addEventListener("keyup", function () {
        const searchValue = searchInput.value.toLowerCase();

        tableRows.forEach(row => {
            const name = row.children[1].textContent.toLowerCase();
            const email = row.children[2].textContent.toLowerCase();

            if (name.includes(searchValue) || email.includes(searchValue)) {
                row.style.display = "";
            } else {
                row.style.display = "none";
            }
        });
    });


});
