// Sovereign Society — Service Worker
// Handles: install/activate lifecycle, offline-friendly page fallback,
// push notifications, and notification clicks.
//
// Bump CACHE_VERSION whenever you ship breaking SW changes so old clients
// upgrade cleanly on next visit.

const CACHE_VERSION = 'sovereign-v4';
const OFFLINE_URL = '/offline';
const PRECACHE_ASSETS = [
  '/static/css/style.css',
  '/static/css/phase3.css',
  '/static/img/sovereign-logo.png',
  '/static/img/icons/icon-192.png',
  '/static/img/icons/icon-512.png',
];

// ---------- Install ----------
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(PRECACHE_ASSETS))
      .catch(() => null)  // don't block install if a precache asset fails
  );
  self.skipWaiting();
});

// ---------- Activate ----------
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ---------- Fetch ----------
// Strategy: network-first for navigations (fall back to a cached offline page
// only when the network truly fails). Static assets are cached opportunistically.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Never intercept auth / API / push endpoints — they must hit the network
  // so login state, CSRF, and push subscription updates are always live.
  const PASSTHROUGH = ['/login', '/logout', '/signup', '/api/', '/push/', '/checkout', '/billing', '/stripe'];
  if (PASSTHROUGH.some((p) => url.pathname.startsWith(p))) return;

  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() =>
        caches.match(OFFLINE_URL).then((r) => r || new Response('Offline', { status: 503 }))
      )
    );
    return;
  }

  // Static assets: cache-first with background revalidate
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.open(CACHE_VERSION).then((cache) =>
        cache.match(req).then((cached) => {
          const fresh = fetch(req).then((res) => {
            if (res.ok) cache.put(req, res.clone());
            return res;
          }).catch(() => cached);
          return cached || fresh;
        })
      )
    );
  }
});

// ---------- Push ----------
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (e) {
    data = { title: 'Sovereign', body: event.data ? event.data.text() : '' };
  }

  const title = data.title || 'Sovereign Society';
  const options = {
    body: data.body || '',
    icon: data.icon || '/static/img/icons/icon-192.png',
    badge: data.badge || '/static/img/icons/icon-192.png',
    tag: data.tag || undefined,
    data: { url: data.url || '/feed' },
    vibrate: [120, 60, 120],
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// ---------- Notification click ----------
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/feed';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // Focus an existing tab if one is on our origin
      for (const client of clientList) {
        try {
          const u = new URL(client.url);
          if (u.origin === self.location.origin && 'focus' in client) {
            client.navigate(target);
            return client.focus();
          }
        } catch (e) { /* skip */ }
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
    })
  );
});
