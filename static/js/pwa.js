// Sovereign Society — PWA bootstrap
// Handles: service worker registration, "Add to Home Screen" prompts
// (Android programmatic + iOS instructional), and push subscription.
//
// Reads config from <body data-*> set by base.html:
//   data-pwa-vapid-public-key  — base64url VAPID public key (empty if push disabled)
//   data-pwa-authed            — "1" when current_user.is_authenticated
//   data-pwa-csrf              — CSRF token for fetch() POSTs

(function () {
  'use strict';

  if (!('serviceWorker' in navigator)) return;

  const body = document.body;
  const VAPID_PUBLIC_KEY = (body && body.dataset.pwaVapidPublicKey) || '';
  const IS_AUTHED = (body && body.dataset.pwaAuthed) === '1';
  const CSRF = (body && body.dataset.pwaCsrf) || '';

  const isStandalone = () =>
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  const isIOS = () =>
    /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;

  // ---------- Service worker registration ----------
  let swRegistration = null;
  window.addEventListener('load', async () => {
    try {
      swRegistration = await navigator.serviceWorker.register('/service-worker.js', { scope: '/' });
      // If user is already authed and previously granted permission, refresh their subscription
      if (IS_AUTHED && VAPID_PUBLIC_KEY && Notification.permission === 'granted') {
        ensurePushSubscription().catch(() => {});
      }
    } catch (e) {
      console.warn('[PWA] SW registration failed:', e);
    }
  });

  // ---------- Install banner (Android programmatic) ----------
  let deferredPrompt = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    // Install promotion is post-signup only — pre-signup installs lead to dead
    // home-screen icons that hit the login wall. Browser-level install (URL bar
    // icon, OS share menu) still works for anyone who really wants it.
    if (!IS_AUTHED) return;
    if (dismissedRecently('pwa_install_dismissed', 14)) return;
    showInstallBanner('android');
  });

  // ---------- Install banner (iOS instructional) ----------
  // iOS doesn't expose programmatic install — surface a one-time hint
  window.addEventListener('load', () => {
    if (!isIOS() || isStandalone()) return;
    if (!IS_AUTHED) return; // Only nudge logged-in users
    if (dismissedRecently('pwa_install_dismissed', 14)) return;
    // Slight delay so it doesn't fight the page load
    setTimeout(() => showInstallBanner('ios'), 4000);
  });

  function dismissedRecently(key, days) {
    try {
      const ts = parseInt(localStorage.getItem(key) || '0', 10);
      return ts && (Date.now() - ts) < days * 86400 * 1000;
    } catch (e) { return false; }
  }

  function markDismissed(key) {
    try { localStorage.setItem(key, String(Date.now())); } catch (e) {}
  }

  function showInstallBanner(mode) {
    if (document.getElementById('pwaInstallBanner')) return;

    const banner = document.createElement('div');
    banner.id = 'pwaInstallBanner';
    banner.className = 'pwa-install-banner';
    banner.innerHTML = `
      <img src="/static/img/icons/icon-192.png" alt="" class="pwa-banner-icon">
      <div class="pwa-banner-text">
        <strong>Install Sovereign</strong>
        <span>${mode === 'ios' ? 'Add to your home screen for the full experience.' : 'Install the app for push notifications and faster access.'}</span>
      </div>
      <button class="pwa-banner-cta" type="button">${mode === 'ios' ? 'How' : 'Install'}</button>
      <button class="pwa-banner-close" type="button" aria-label="Dismiss">&times;</button>
    `;
    document.body.appendChild(banner);
    requestAnimationFrame(() => banner.classList.add('open'));

    banner.querySelector('.pwa-banner-close').addEventListener('click', () => {
      markDismissed('pwa_install_dismissed');
      banner.classList.remove('open');
      setTimeout(() => banner.remove(), 300);
    });

    banner.querySelector('.pwa-banner-cta').addEventListener('click', async () => {
      if (mode === 'android' && deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'dismissed') markDismissed('pwa_install_dismissed');
        deferredPrompt = null;
        banner.remove();
      } else {
        showIOSInstructions();
      }
    });
  }

  function showIOSInstructions() {
    if (document.getElementById('pwaIosModal')) return;
    const modal = document.createElement('div');
    modal.id = 'pwaIosModal';
    modal.className = 'pwa-ios-modal';
    modal.innerHTML = `
      <div class="pwa-ios-card">
        <button class="pwa-ios-close" type="button" aria-label="Close">&times;</button>
        <h2>Install Sovereign</h2>
        <p class="pwa-ios-subtitle">Add to your home screen for fullscreen mode and push notifications.</p>
        <ol class="pwa-ios-steps">
          <li>Tap the <strong>Share</strong> button <span class="pwa-ios-icon">&#x2191;</span> in Safari's toolbar.</li>
          <li>Scroll down and tap <strong>Add to Home Screen</strong>.</li>
          <li>Tap <strong>Add</strong> in the top right.</li>
        </ol>
        <button class="btn btn-gold pwa-ios-done" type="button">Got it</button>
      </div>
    `;
    document.body.appendChild(modal);
    requestAnimationFrame(() => modal.classList.add('open'));
    const close = () => {
      modal.classList.remove('open');
      setTimeout(() => modal.remove(), 250);
    };
    modal.querySelector('.pwa-ios-close').addEventListener('click', close);
    modal.querySelector('.pwa-ios-done').addEventListener('click', close);
    modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  }

  // ---------- Push subscription ----------
  // Exposed on window so /notifications page can call it from a button.
  window.SovereignPush = {
    enable: enablePush,
    disable: disablePush,
    status: pushStatus,
  };

  async function pushStatus() {
    if (!('PushManager' in window) || !('Notification' in window)) return 'unsupported';
    if (!swRegistration) {
      try { swRegistration = await navigator.serviceWorker.ready; } catch (e) { return 'unsupported'; }
    }
    if (Notification.permission === 'denied') return 'denied';
    const sub = await swRegistration.pushManager.getSubscription();
    return sub ? 'enabled' : 'disabled';
  }

  async function enablePush() {
    if (!IS_AUTHED) throw new Error('Sign in first.');
    if (!VAPID_PUBLIC_KEY) throw new Error('Push not configured on server.');
    if (!('PushManager' in window)) throw new Error('Push not supported on this browser.');
    if (!swRegistration) swRegistration = await navigator.serviceWorker.ready;

    const permission = await Notification.requestPermission();
    if (permission !== 'granted') throw new Error('Notification permission was not granted.');

    return ensurePushSubscription();
  }

  async function ensurePushSubscription() {
    if (!swRegistration) swRegistration = await navigator.serviceWorker.ready;
    let sub = await swRegistration.pushManager.getSubscription();
    if (!sub) {
      sub = await swRegistration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      });
    }
    await postJSON('/push/subscribe', sub.toJSON());
    return sub;
  }

  async function disablePush() {
    if (!swRegistration) swRegistration = await navigator.serviceWorker.ready;
    const sub = await swRegistration.pushManager.getSubscription();
    if (sub) {
      const endpoint = sub.endpoint;
      await sub.unsubscribe();
      await postJSON('/push/unsubscribe', { endpoint });
    }
  }

  async function postJSON(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Server rejected push subscription (' + res.status + ').');
    return res.json().catch(() => ({}));
  }

  // VAPID public keys are sent as urlsafe-base64; PushManager wants Uint8Array
  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = window.atob(base64);
    const out = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; ++i) out[i] = raw.charCodeAt(i);
    return out;
  }
})();
