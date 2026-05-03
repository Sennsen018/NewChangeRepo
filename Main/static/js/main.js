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
        if (!dropdown.contains(e.target) && (!burger || !burger.contains(e.target))) {
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
    let loaderTimeout = null;

    function showLoader() {
        loader.style.display = 'flex';
        // Safety fallback: auto-hide after 8 seconds in case navigation stalls
        if (loaderTimeout) clearTimeout(loaderTimeout);
        loaderTimeout = setTimeout(() => {
            loader.style.display = 'none';
            loaderTimeout = null;
        }, 8000);
    }

    function hideLoader() {
        loader.style.display = 'none';
        if (loaderTimeout) { clearTimeout(loaderTimeout); loaderTimeout = null; }
    }

    // Show loader ONLY on full-page navigation (leaving the page)
    window.addEventListener('beforeunload', () => {
        showLoader();
    });

    // Do NOT attach loader to form submits here — individual pages handle their own forms.
    // This prevents the overlay from blocking buttons on multi-form pages.

    // Add click feedback to all buttons and nav items (subtle scale only)
    const interactiveElements = document.querySelectorAll('.btn, .nav-item, .class-card, .subject-card');
    interactiveElements.forEach(el => {
        el.addEventListener('click', function() {
            this.style.transform = 'scale(0.97)';
            setTimeout(() => {
                this.style.transform = '';
            }, 120);
        });
    });

    // Sidebar scroll support: ensure scrollbar shows when nav overflows
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebar.style.overflowY = 'auto';
        sidebar.style.scrollbarWidth = 'thin';
    }
});
