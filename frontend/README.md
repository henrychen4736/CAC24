# Henry Tennis — mobile app

Flutter app (iOS + Android). You film a swing, the app uploads it to the
analysis service (`../backend`), and it shows the coaching report: scores,
top priorities, a metric-by-metric breakdown, and a skeleton overlay on your
video. The API contract lives in [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) §6.

## Requirements

- **Flutter 3.47.3 or newer (Dart 3.13).** The code uses recent Dart language features and
  current Firebase / Riverpod 3 / go_router packages. If your global SDK is
  older, run `flutter upgrade` before anything else.
- Android Studio (Android SDK + JDK 17) for Android, and Xcode 16+ plus CocoaPods
  on a Mac for iOS.
- The analysis server running somewhere the phone can reach (see `../backend/README.md`).

## Run

```bash
flutter pub get
flutter run                                   # uses the default server URL below
flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000   # custom server
```

Default server URL when `API_BASE_URL` isn't set:

| Where the app runs | Default | Notes |
|---|---|---|
| Android emulator | `http://10.0.2.2:8000` | 10.0.2.2 is the emulator's alias for your computer |
| iOS simulator | `http://localhost:8000` | |
| Physical phone | set it | Use your computer's LAN IP, via `--dart-define` or **Profile → Analysis server** in the app (saved on the device) |

**Profile → Test connection** calls `GET /v1/health` and shows which pose model,
stroke classifier, and reference ranges the server is using.

### Plain HTTP during development

- **Android:** debug builds allow HTTP to any host (`android/app/src/debug/res/xml/network_security_config.xml`)
  so a LAN server works. Release/profile builds allow HTTPS only, except `10.0.2.2` and
  `localhost` (`android/app/src/main/res/xml/network_security_config.xml`).
- **iOS:** `NSAllowsLocalNetworking` permits HTTP to local-network hosts; iOS also asks
  for Local Network permission the first time.

Deploy the server behind HTTPS for real users.

## Firebase setup

The app uses the Firebase project `henry-tennis-q8mkn` (`lib/firebase_options.dart`, `.firebaserc`).
In the [Firebase console](https://console.firebase.google.com/):

1. **Authentication → Sign-in method:** enable **Email/Password**.
2. **Firestore Database:** create a database if there isn't one yet.
3. Deploy the security rules (each user can only read and write `users/{uid}/…`):
   ```bash
   npm install -g firebase-tools
   firebase login
   firebase deploy --only firestore:rules      # run from this folder
   ```

If you change bundle IDs or add platforms, re-run `flutterfire configure`.

### What is stored where

- **Firestore** `users/{uid}/analyses/{jobId}`: summary fields (score, stroke counts,
  families, headline) plus the full report as JSON, *without* the per-frame pose track.
- **On the device** (`<app documents>/analyses/<jobId>/`): a copy of the video and the
  pose track, so a result can be replayed with the skeleton overlay. On another device,
  history still shows the full report; the overlay plays over a plain background.

## iOS

```bash
cd ios && pod install && cd ..
flutter run -d <iphone>
```

The deployment target is iOS 15 (required by current Firebase SDKs). On the first
iOS build the Flutter tool may migrate the Xcode project for newer Flutter versions;
commit those changes.

## Project layout

```
lib/
  main.dart            Firebase + SharedPreferences bootstrap, ProviderScope
  app/                 router (go_router, auth/onboarding redirects), theme (Material 3 tokens)
  core/                API client + errors, settings, providers, formatting, shared widgets
  features/
    onboarding/        first-run intro
    auth/              sign in / sign up / reset password
    home/              dashboard: new analysis, averages, recent results, tips
    analyze/           pick/record → options → upload & processing
    results/           report models, result screen, skeleton overlay, playback clock
    history/           Firestore repository, local file store, history list
    profile/           name, hitting hand, server URL, theme, sign out, delete account
assets/sample_report.json   example report (opened via "View sample analysis")
```

State is managed with Riverpod (no code generation). The report models are
parsed by hand and ignore unknown fields, so the server can add fields without
breaking older app builds.

## Tests

```bash
flutter analyze
flutter test
```

Tests cover report parsing (using `assets/sample_report.json`), API error mapping,
the overlay's coordinate mapping, the playback clock, router redirects, and the result
screen. None of them need Firebase.

`assets/sample_report.json` is real backend output. It comes from a forehand drill
clip on Wikimedia Commons (credited in its `sample_source` field). Regenerate it
with `tennis-ai analyze <clip> --out report.json` when the report format changes.

### Screenshots without a device

```bash
flutter test test_screenshots/result_screen_screenshot_test.dart
```

This renders the Result screen with real fonts to `build/screenshots/*.png`. You
don't need an emulator or a Firebase sign-in. Point `SAMPLE_REPORT` at any report
JSON to preview it. It lives outside `test/` on purpose, because pixel output
differs between machines, so it isn't part of `flutter test`.

## Regenerating the app icon

```bash
dart run flutter_launcher_icons
```

Uses `Images/logo.png` (see `flutter_launcher_icons` in `pubspec.yaml`).
