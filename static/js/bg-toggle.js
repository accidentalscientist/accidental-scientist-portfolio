document.addEventListener('DOMContentLoaded', function () {
    const bgToggle = document.getElementById('bg-toggle');
    const body = document.body;

    // Set initial state from localStorage
    const initBg = localStorage.getItem('bgStyle');
    if (initBg === 'grey') {
        body.classList.add('bg-grey');
    }

    bgToggle.addEventListener('click', () => {
        const isGrey = body.classList.toggle('bg-grey');
        localStorage.setItem('bgStyle', isGrey ? 'grey' : 'gradient');
    });
});
