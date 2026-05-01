# Mobile Setup — Capacitor → iOS + Android

This is the runbook for turning the live web app into App Store / Play Store apps.

## Prerequisites

- macOS (required for iOS builds — Xcode only runs on Mac)
- Node 18+ + npm
- Xcode 15+ (App Store: install from Mac App Store)
- Android Studio (Play Store: download from developer.android.com)
- Apple Developer Program membership ($99/yr) — sign up at developer.apple.com
- Google Play Console account ($25 one-time) — sign up at play.google.com/console

## Step 1 — Install Capacitor

```bash
npm install
npx cap add ios
npx cap add android
```

This creates `ios/` and `android/` directories — these are the native Xcode and Android Studio projects.

## Step 2 — Configure the production URL

Edit [capacitor.config.json](capacitor.config.json):

```json
"server": {
  "url": "https://YOUR-PRODUCTION-DOMAIN"
}
```

This is the URL the WebView loads. Use your Railway domain initially, then swap when you have a custom domain.

## Step 3 — App icons + splash screen

You need a single 1024x1024 PNG of your logo. Then:

```bash
npm install -g @capacitor/assets
npx capacitor-assets generate --iconBackgroundColor "#0A0A0A" --splashBackgroundColor "#0A0A0A"
```

This generates all required icon and splash sizes for both platforms.

## Step 4 — Build & run

```bash
# iOS (opens Xcode)
npx cap sync ios && npx cap open ios

# Android (opens Android Studio)
npx cap sync android && npx cap open android
```

In Xcode: select a simulator, hit Run. In Android Studio: select an emulator, hit Run.

## Step 5 — Push notifications setup

### iOS (Apple Push Notification service)

1. In Xcode → project settings → Signing & Capabilities → add "Push Notifications" capability.
2. Create an APNs key in Apple Developer portal → Keys → "+" → enable APNs.
3. Save the .p8 file securely.

### Android (Firebase Cloud Messaging)

1. Create a Firebase project at console.firebase.google.com.
2. Add an Android app with package name `com.onepercentmensclub.app`.
3. Download `google-services.json` and put in `android/app/`.
4. Get the FCM server key from Firebase project settings.

### Server-side

Add APNs key + FCM key to Railway env vars:

```
APNS_KEY_ID=ABCDEFG123
APNS_TEAM_ID=AAAAAAAAAA
APNS_BUNDLE_ID=com.onepercentmensclub.app
APNS_PRIVATE_KEY=<contents of .p8>
FCM_SERVER_KEY=AAAA...
```

(Server-side push send is not yet implemented — this is a TODO for after Capacitor wrappers ship.)

## Step 6 — App Store submission (iOS)

1. In Xcode: Product → Archive.
2. Window → Organizer → Distribute App → App Store Connect.
3. In App Store Connect (appstoreconnect.apple.com): create app record, fill in metadata, screenshots (6.7", 6.5", 5.5"), privacy questionnaire.
4. Submit for review.

**Reviewer test account**: provide credentials to a member who has lifetime access. Apple reviewers will use this to verify the app works.

**Justification for WebView**: include in the review notes — "App provides native value via push notifications, biometric login, camera/photo upload, and native share. Web functionality is enhanced, not duplicated."

Apple often rejects on first submission of WebView-heavy apps. Be prepared to respond.

## Step 7 — Play Store submission (Android)

1. In Android Studio: Build → Generate Signed Bundle → AAB.
2. In Play Console: create app, internal testing track first, upload AAB.
3. Once internal works, promote to production.

## What's already wired in the web app

- `is_native_app` Jinja flag — true when request comes from Capacitor shell.
- CSS rule `html.native-app a[href*="/pricing"] { display: none }` — hides paywall CTAs in the iOS app per Apple "reader" rule.
- `/api/devices/register` endpoint for storing push tokens.
- `static/js/capacitor-bridge.js` — auto-loads in native shell, requests push permission, registers token, tags fetches with `X-Native-App: 1`.

## What you'll need to do server-side after wrapping

1. **Wire up push send**: when a notification is created server-side, also fan out to APNs/FCM via the device tokens. (Library suggestions: `aioapns` for APNs, `pyfcm` for FCM.)
2. **Generate icons**: I scaffolded the manifest with a placeholder. Replace `static/manifest.json` icon entries with real 192x192 and 512x512 PNGs.
3. **Update bundle ID** if you want something other than `com.onepercentmensclub.app`.
