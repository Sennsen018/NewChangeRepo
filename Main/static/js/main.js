function toggleUserMenu() {
    const dropdown = document.getElementById('user-dropdown');
    if (dropdown) {
        dropdown.classList.toggle('active');
    }
}

function toggleAccordion(button) {
    const accordion = button.closest('.nav-accordion');
    if (accordion) {
        accordion.classList.toggle('open');
    }
}

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    if (sidebar) {
        sidebar.classList.toggle('open');
        if (overlay) {
            overlay.classList.toggle('active');
        }
    }
}

// Close dropdown or sidebar when clicking outside
window.addEventListener('click', function(e) {
    const dropdown = document.getElementById('user-dropdown');
    const burger = document.querySelector('.burger-btn');
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const overlay = document.querySelector('.sidebar-overlay');

    // Handle User Dropdown
    if (dropdown && dropdown.classList.contains('active')) {
        if (!dropdown.contains(e.target) && (!burger || !burger.contains(e.target))) {
            dropdown.classList.remove('active');
        }
    }

    // Handle Sidebar Overlay click
    if (overlay && overlay.contains(e.target)) {
        if (sidebar) sidebar.classList.remove('open');
        overlay.classList.remove('active');
    }
});

// Global Loading & Transition Logic
document.addEventListener('DOMContentLoaded', function() {
    // Inject UI elements (Guard against multiple injections if script is loaded twice)
    if (!document.getElementById('loading-overlay')) {
        const extraUI = `
            <div id="loading-overlay">
                <div class="spinner-container">
                    <div class="spinner-ring"></div>
                    <div class="spinner-ring"></div>
                </div>
                <div class="loading-text">Attendeez Loading...</div>
            </div>
            <div class="sidebar-overlay"></div>
        `;
        document.body.insertAdjacentHTML('beforeend', extraUI);
    }

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

    // --- DELETION PIN SECURITY UI ---
    const pinModalsHTML = `
        <div id="pinVerifyModal" class="modal-overlay" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 9999; justify-content: center; align-items: center; backdrop-filter: blur(4px);">
            <div class="glass-panel" style="width: 400px; padding: 2rem; border: 1px solid var(--danger);">
                <h3 style="color: var(--danger); margin-bottom: 1rem;"><i class="fas fa-shield-alt"></i> Security Verification</h3>
                <p style="font-size: 0.85rem; margin-bottom: 1.5rem;">This action is permanent. Please enter your 6-digit security PIN to confirm deletion.</p>
                <div class="form-group mb-4">
                    <input type="password" id="security_pin_input" class="form-control" placeholder="Enter PIN" maxlength="6" style="text-align: center; font-size: 1.5rem; letter-spacing: 0.5rem;" inputmode="numeric" pattern="[0-9]*" autofocus>
                    <div id="pin_error_msg" style="color: var(--danger); font-size: 0.75rem; margin-top: 0.5rem; display: none;">Incorrect PIN. Please try again.</div>
                </div>
                <div class="flex gap-2">
                    <button class="btn btn-secondary w-full" onclick="closePinModal()">Cancel</button>
                    <button class="btn btn-danger w-full" id="confirm_pin_btn">Verify & Delete</button>
                </div>
            </div>
        </div>

        <div id="pinChangeModal" class="modal-overlay" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); z-index: 9999; justify-content: center; align-items: center; backdrop-filter: blur(4px);">
            <div class="glass-panel" style="width: 400px; padding: 2rem;">
                <h3 style="margin-bottom: 1rem;">Setup/Change Deletion PIN</h3>
                
                <div id="pin_step_1">
                    <p style="font-size: 0.85rem; margin-bottom: 1.5rem;">To change your security PIN, we need to verify your identity. An OTP will be sent to your admin email.</p>
                    <button class="btn btn-primary w-full" onclick="requestPinOTP()">Send Verification Code</button>
                </div>

                <div id="pin_step_2" style="display: none;">
                    <p style="font-size: 0.85rem; margin-bottom: 1.5rem;" id="pin_otp_status"></p>
                    <div class="form-group mb-3">
                        <label class="form-label">Enter 4-Digit OTP</label>
                        <input type="text" id="pin_otp_input" class="form-control" maxlength="4" placeholder="0000">
                    </div>
                    <div class="form-group mb-4">
                        <label class="form-label">Enter New Numerical PIN (6-Digits)</label>
                        <input type="password" id="new_pin_input" class="form-control" maxlength="6" inputmode="numeric" pattern="[0-9]*" placeholder="6-digit PIN only">
                    </div>
                    <button class="btn btn-primary w-full" onclick="verifyAndSetPin()">Update Security PIN</button>
                </div>
                
                <button class="btn btn-secondary w-full mt-3" onclick="document.getElementById('pinChangeModal').classList.remove('active')">Cancel</button>
            </div>
        </div>
    `;
    // --- LOGOUT CONFIRMATION MODAL ---
    const logoutModalHTML = `
        <div id="logout-modal-overlay" class="modal-overlay">
            <div class="confirm-modal">
                <div class="modal-icon">
                    <i class="fas fa-sign-out-alt"></i>
                </div>
                <h3 class="modal-title">Confirm Logout</h3>
                <p class="modal-text">Are you sure you want to log out? Your current session will be ended.</p>
                <div class="modal-actions">
                    <button type="button" class="btn-cancel" onclick="closeLogoutModal()">Cancel</button>
                    <a href="/logout" class="btn-confirm-logout">Log Out</a>
                </div>
            </div>
        </div>
    `;

    if (!document.getElementById('logout-modal-overlay')) {
        document.body.insertAdjacentHTML('beforeend', logoutModalHTML);
    }

    window.closeLogoutModal = function() {
        document.getElementById('logout-modal-overlay').classList.remove('active');
    };

    window.showLogoutModal = function(e) {
        if (e) e.preventDefault();
        document.getElementById('logout-modal-overlay').classList.add('active');
    };

    // Intercept all logout links EXCEPT the one in the modal
    const logoutLinks = document.querySelectorAll('a[href="/logout"]:not(.btn-confirm-logout)');
    logoutLinks.forEach(link => {
        link.addEventListener('click', showLogoutModal);
    });

    if (!document.getElementById('pinVerifyModal')) {
        document.body.insertAdjacentHTML('beforeend', pinModalsHTML);
    }
});

let pendingDeleteUrl = null;

/**
 * Global function to intercept deletion links with PIN verification
 */
window.confirmWithPin = function(deleteUrl) {
    pendingDeleteUrl = deleteUrl;
    const modal = document.getElementById('pinVerifyModal');
    const input = document.getElementById('security_pin_input');
    const error = document.getElementById('pin_error_msg');
    
    input.value = '';
    error.style.display = 'none';
    modal.classList.add('active');
    input.focus();
    
    // Setup confirm button handler once
    document.getElementById('confirm_pin_btn').onclick = async function() {
        const pin = input.value;
        if (!pin) return;

        const formData = new FormData();
        formData.append('pin', pin);
        formData.append('csrf_token', document.querySelector('input[name="csrf_token"]')?.value || '');

        try {
            const response = await fetch('/admin/verify_pin', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (data.success) {
                window.location.href = pendingDeleteUrl;
            } else {
                error.style.display = 'block';
                input.value = '';
                input.focus();
            }
        } catch (err) {
            alert('Verification service unavailable.');
        }
    };
};

window.closePinModal = function() {
    document.getElementById('pinVerifyModal').classList.remove('active');
    pendingDeleteUrl = null;
};

/**
 * PIN Management Logicc
 */
window.openChangePinModal = function() {
    document.getElementById('pinChangeModal').classList.add('active');
    document.getElementById('pin_step_1').style.display = 'block';
    document.getElementById('pin_step_2').style.display = 'none';
};

window.requestPinOTP = async function() {
    const formData = new FormData();
    formData.append('csrf_token', document.querySelector('input[name="csrf_token"]')?.value || '');
    
    try {
        const response = await fetch('/admin/request_pin_otp', { method: 'POST', body: formData });
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('pin_step_1').style.display = 'none';
            document.getElementById('pin_step_2').style.display = 'block';
            document.getElementById('pin_otp_status').innerText = data.message;
        } else {
            alert(data.message);
        }
    } catch (err) {
        alert('Failed to send OTP.');
    }
};

window.verifyAndSetPin = async function() {
    const otp = document.getElementById('pin_otp_input').value;
    const newPin = document.getElementById('new_pin_input').value;
    
    if (!otp || !newPin) {
        alert('Please fill in both OTP and New PIN.');
        return;
    }

    const formData = new FormData();
    formData.append('otp', otp);
    formData.append('new_pin', newPin);
    formData.append('csrf_token', document.querySelector('input[name="csrf_token"]')?.value || '');

    try {
        const response = await fetch('/admin/change_deletion_pin', { method: 'POST', body: formData });
        const data = await response.json();
        
        if (data.success) {
            alert('Security PIN updated successfully!');
            document.getElementById('pinChangeModal').classList.remove('active');
        } else {
            alert(data.message);
        }
    } catch (err) {
        alert('Failed to update PIN.');
    }
};
