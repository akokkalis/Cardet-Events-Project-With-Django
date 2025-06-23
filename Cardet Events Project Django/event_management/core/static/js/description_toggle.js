document.addEventListener('DOMContentLoaded', function () {
    const readMoreBtn = document.getElementById('read-more-btn');
    const readLessBtn = document.getElementById('read-less-btn');
    const shortDesc = document.getElementById('short-desc');
    const fullDesc = document.getElementById('full-desc');

    if (readMoreBtn) {
        readMoreBtn.addEventListener('click', function () {
            if (shortDesc) shortDesc.classList.add('hidden');
            if (fullDesc) fullDesc.classList.remove('hidden');
        });
    }

    if (readLessBtn) {
        readLessBtn.addEventListener('click', function () {
            if (fullDesc) fullDesc.classList.add('hidden');
            if (shortDesc) shortDesc.classList.remove('hidden');
        });
    }
}); 