function toggleUserMenu() {
    const dropdown = document.getElementById('user-dropdown');
    if (dropdown) {
        dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
    }
}

// Close dropdown when clicking outside
window.addEventListener('click', function(e) {
    const dropdown = document.getElementById('user-dropdown');
    const burger = document.querySelector('.burger-btn');
    if (dropdown && dropdown.style.display === 'block') {
        if (!dropdown.contains(e.target) && !burger.contains(e.target)) {
            dropdown.style.display = 'none';
        }
    }
});

// Global Loading & Transition Logic
document.addEventListener('DOMContentLoaded', function() {
    // Inject Loading Overlay
    const loaderHTML = `
        <div id="loading-overlay">
            <div class="spinner-container">
                <div class="spinner-ring"></div>
                <div class="spinner-ring"></div>
            </div>
            <div class="loading-text">Attendeez Loading...</div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', loaderHTML);

    const loader = document.getElementById('loading-overlay');

    // Show loader on page change (navigation)
    window.addEventListener('beforeunload', () => {
        loader.style.display = 'flex';
    });

    // Show loader on form submissions
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', (e) => {
            // Only show if the form is valid (if using browser validation)
            if (form.checkValidity()) {
                loader.style.display = 'flex';
            }
        });
    });

    // Add click feedback to all buttons and nav items
    const interactiveElements = document.querySelectorAll('.btn, .nav-item, .class-card, .subject-card');
    interactiveElements.forEach(el => {
        el.addEventListener('click', function(e) {
            // If it's a link, the beforeunload will handle the loader
            // This just provides immediate visual feedback
            this.style.transform = 'scale(0.96)';
            setTimeout(() => {
                this.style.transform = '';
            }, 100);
        });
    });
});
