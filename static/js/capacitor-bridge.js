/**
 * Capacitor bridge — runs only inside the native iOS/Android shell.
 * On the web, Capacitor.isNativePlatform() returns false and this file is a no-op.
 *
 * Loaded conditionally from base.html when {{ is_native_app }} is True.
 */
(function () {
  if (typeof Capacitor === 'undefined' || !Capacitor.isNativePlatform || !Capacitor.isNativePlatform()) {
    return;
  }

  const { PushNotifications } = Capacitor.Plugins.PushNotifications || {};
  const { Preferences } = Capacitor.Plugins.Preferences || {};
  const { StatusBar } = Capacitor.Plugins.StatusBar || {};

  // Status bar styling
  if (StatusBar && StatusBar.setBackgroundColor) {
    try { StatusBar.setBackgroundColor({ color: '#0A0A0A' }); } catch (e) {}
  }

  // Hide checkout/upgrade CTAs (Apple "reader" rule)
  document.documentElement.classList.add('native-app');

  // Push notifications: request permission and register
  async function setupPush() {
    if (!PushNotifications) return;
    try {
      const perm = await PushNotifications.requestPermissions();
      if (perm.receive !== 'granted') return;
      await PushNotifications.register();

      PushNotifications.addListener('registration', async (token) => {
        const platform = Capacitor.getPlatform(); // 'ios' or 'android'
        try {
          await fetch('/api/devices/register', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-Native-App': '1' },
            body: JSON.stringify({ token: token.value, platform }),
          });
        } catch (e) { console.warn('register failed', e); }
      });

      PushNotifications.addListener('registrationError', (err) => {
        console.warn('Push registration error:', err);
      });

      PushNotifications.addListener('pushNotificationActionPerformed', (notif) => {
        const link = (notif.notification && notif.notification.data && notif.notification.data.link) || '/';
        window.location.href = link;
      });
    } catch (e) {
      console.warn('Push setup failed', e);
    }
  }

  // Tag every fetch from the native shell with X-Native-App header
  const origFetch = window.fetch;
  window.fetch = function (input, init) {
    init = init || {};
    init.headers = new Headers(init.headers || {});
    if (!init.headers.has('X-Native-App')) init.headers.set('X-Native-App', '1');
    return origFetch.call(this, input, init);
  };

  document.addEventListener('DOMContentLoaded', setupPush);
})();
