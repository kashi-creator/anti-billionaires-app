/* ============================================
   ABMC - Main Application JavaScript
   ============================================ */

// ===== NOTIFICATION POLLING =====
let notifPollInterval = null;

function startNotifPolling() {
    pollNotifications();
    notifPollInterval = setInterval(pollNotifications, 30000);
}

function pollNotifications() {
    fetch('/api/notifications/unread-count')
        .then(r => r.json())
        .then(data => {
            const badge = document.getElementById('notifBadge');
            if (badge) {
                if (data.count > 0) {
                    badge.textContent = data.count;
                    badge.style.display = 'flex';
                } else {
                    badge.style.display = 'none';
                }
            }
        })
        .catch(() => {});
}

// ===== NOTIFICATION DROPDOWN =====
function toggleNotifDropdown(e) {
    e.stopPropagation();
    const dropdown = document.getElementById('notifDropdown');
    const avatarDd = document.getElementById('avatarDropdown');
    if (avatarDd) avatarDd.classList.remove('open');

    dropdown.classList.toggle('open');
    if (dropdown.classList.contains('open')) {
        loadNotifDropdown();
    }
}

function loadNotifDropdown() {
    fetch('/api/notifications/recent')
        .then(r => r.json())
        .then(data => {
            const list = document.getElementById('notifDropdownList');
            if (!data.notifications || data.notifications.length === 0) {
                list.innerHTML = '<div class="notif-dropdown-empty">No notifications yet</div>';
                return;
            }
            let html = '';
            data.notifications.forEach(n => {
                html += `<a href="${n.link || '#'}" class="notif-dd-item ${n.is_read ? '' : 'unread'}">
                    <div class="notif-dd-msg">${n.message}</div>
                    <div class="notif-dd-time">${n.time_ago}</div>
                </a>`;
            });
            list.innerHTML = html;
        })
        .catch(() => {});
}

function markAllReadFromDropdown() {
    fetch('/notifications/mark-read', { method: 'POST' })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const badge = document.getElementById('notifBadge');
                if (badge) badge.style.display = 'none';
                document.querySelectorAll('.notif-dd-item.unread').forEach(el => {
                    el.classList.remove('unread');
                });
            }
        });
}

// ===== AVATAR DROPDOWN =====
function toggleAvatarDropdown(e) {
    e.stopPropagation();
    const dropdown = document.getElementById('avatarDropdown');
    const notifDd = document.getElementById('notifDropdown');
    if (notifDd) notifDd.classList.remove('open');

    dropdown.classList.toggle('open');
}

// Close dropdowns when clicking outside
document.addEventListener('click', function(e) {
    const notifContainer = document.getElementById('notifContainer');
    const avatarContainer = document.getElementById('avatarContainer');
    const notifDd = document.getElementById('notifDropdown');
    const avatarDd = document.getElementById('avatarDropdown');

    if (notifDd && notifContainer && !notifContainer.contains(e.target)) {
        notifDd.classList.remove('open');
    }
    if (avatarDd && avatarContainer && !avatarContainer.contains(e.target)) {
        avatarDd.classList.remove('open');
    }
});

// ===== CONFETTI =====
function launchConfetti() {
    const canvas = document.getElementById('confettiCanvas');
    if (!canvas) return;
    canvas.style.display = 'block';
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const colors = ['#D4AF37', '#E8C547', '#B8941F', '#F5D060', '#FFFFFF', '#FFD700'];
    const particles = [];
    const count = 120;

    for (let i = 0; i < count; i++) {
        particles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height - canvas.height,
            w: Math.random() * 8 + 4,
            h: Math.random() * 6 + 3,
            color: colors[Math.floor(Math.random() * colors.length)],
            vx: (Math.random() - 0.5) * 4,
            vy: Math.random() * 3 + 2,
            rot: Math.random() * 360,
            rotSpeed: (Math.random() - 0.5) * 10,
            opacity: 1,
        });
    }

    let frame = 0;
    const maxFrames = 180;

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        frame++;

        particles.forEach(p => {
            p.x += p.vx;
            p.y += p.vy;
            p.vy += 0.05;
            p.rot += p.rotSpeed;
            if (frame > maxFrames - 40) {
                p.opacity = Math.max(0, p.opacity - 0.025);
            }

            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate((p.rot * Math.PI) / 180);
            ctx.globalAlpha = p.opacity;
            ctx.fillStyle = p.color;
            ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
            ctx.restore();
        });

        if (frame < maxFrames) {
            requestAnimationFrame(animate);
        } else {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            canvas.style.display = 'none';
        }
    }

    animate();
}

// ===== LESSON COMPLETION =====
function completeLessonWithCountdown(formId) {
    const form = document.getElementById(formId);
    const btn = form.querySelector('button');
    const originalText = btn.textContent;

    let count = 3;
    btn.disabled = true;
    btn.textContent = count;

    const interval = setInterval(() => {
        count--;
        if (count > 0) {
            btn.textContent = count;
        } else {
            clearInterval(interval);
            btn.textContent = 'Done!';
            launchConfetti();
            setTimeout(() => form.submit(), 500);
        }
    }, 1000);
}

// ===== MESSAGE BADGE POLLING =====
function pollMessageBadge() {
    fetch('/api/messages/unread-count')
        .then(r => r.json())
        .then(data => {
            const badge = document.getElementById('msgBadge');
            if (badge) {
                if (data.count > 0) {
                    badge.textContent = data.count;
                    badge.style.display = 'flex';
                } else {
                    badge.style.display = 'none';
                }
            }
        })
        .catch(() => {});
}

// ===== INIT =====
document.addEventListener('DOMContentLoaded', function() {
    // Start notification polling if user is logged in (nav exists)
    if (document.querySelector('.navbar')) {
        startNotifPolling();
        pollMessageBadge();
        setInterval(pollMessageBadge, 15000);
    }

    // Auto-dismiss flash messages
    setTimeout(() => {
        document.querySelectorAll('.flash').forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(-10px)';
            setTimeout(() => el.remove(), 300);
        });
    }, 4000);

    // Check if checklist is fully complete - show confetti
    const checklistComplete = document.querySelector('[data-checklist-complete="true"]');
    if (checklistComplete) {
        setTimeout(launchConfetti, 500);
    }
});
