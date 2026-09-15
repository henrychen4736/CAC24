import 'package:flutter/foundation.dart' show defaultTargetPlatform, kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Base URL baked in at build time with `--dart-define=API_BASE_URL=...`.
const _envApiBaseUrl = String.fromEnvironment('API_BASE_URL');

/// Default analysis server URL: the dart-define if given, otherwise the host
/// machine as seen from the Android emulator / iOS simulator.
String defaultApiBaseUrl() {
  if (_envApiBaseUrl.isNotEmpty) return _envApiBaseUrl;
  if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
    return 'http://10.0.2.2:8000';
  }
  return 'http://localhost:8000';
}

enum Handedness {
  auto('auto', 'Auto-detect'),
  right('right', 'Right-handed'),
  left('left', 'Left-handed');

  const Handedness(this.wire, this.label);
  final String wire;
  final String label;

  static Handedness parse(String? v) =>
      Handedness.values.firstWhere((h) => h.wire == v, orElse: () => Handedness.auto);
}

@immutable
class AppSettings {
  const AppSettings({
    this.themeMode = ThemeMode.system,
    this.handedness = Handedness.auto,
    this.apiBaseUrlOverride,
    this.onboardingDone = false,
  });

  final ThemeMode themeMode;
  final Handedness handedness;
  final String? apiBaseUrlOverride;
  final bool onboardingDone;

  String get apiBaseUrl => apiBaseUrlOverride ?? defaultApiBaseUrl();

  AppSettings copyWith({
    ThemeMode? themeMode,
    Handedness? handedness,
    String? Function()? apiBaseUrlOverride,
    bool? onboardingDone,
  }) =>
      AppSettings(
        themeMode: themeMode ?? this.themeMode,
        handedness: handedness ?? this.handedness,
        apiBaseUrlOverride:
            apiBaseUrlOverride != null ? apiBaseUrlOverride() : this.apiBaseUrlOverride,
        onboardingDone: onboardingDone ?? this.onboardingDone,
      );
}

/// Overridden in `main()` with the loaded instance (and in tests with a mock).
final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) => throw UnimplementedError('sharedPreferencesProvider must be overridden'),
);

class SettingsController extends Notifier<AppSettings> {
  static const _kTheme = 'settings.themeMode';
  static const _kHandedness = 'settings.handedness';
  static const _kApiUrl = 'settings.apiBaseUrl';
  static const _kOnboarding = 'settings.onboardingDone';

  SharedPreferences get _prefs => ref.read(sharedPreferencesProvider);

  @override
  AppSettings build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return AppSettings(
      themeMode: ThemeMode.values.firstWhere(
        (m) => m.name == prefs.getString(_kTheme),
        orElse: () => ThemeMode.system,
      ),
      handedness: Handedness.parse(prefs.getString(_kHandedness)),
      apiBaseUrlOverride: prefs.getString(_kApiUrl),
      onboardingDone: prefs.getBool(_kOnboarding) ?? false,
    );
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    state = state.copyWith(themeMode: mode);
    await _prefs.setString(_kTheme, mode.name);
  }

  Future<void> setHandedness(Handedness h) async {
    state = state.copyWith(handedness: h);
    await _prefs.setString(_kHandedness, h.wire);
  }

  /// Pass null or an empty string to go back to the default URL.
  Future<void> setApiBaseUrl(String? url) async {
    final cleaned = url?.trim().replaceAll(RegExp(r'/+$'), '');
    if (cleaned == null || cleaned.isEmpty) {
      state = state.copyWith(apiBaseUrlOverride: () => null);
      await _prefs.remove(_kApiUrl);
    } else {
      state = state.copyWith(apiBaseUrlOverride: () => cleaned);
      await _prefs.setString(_kApiUrl, cleaned);
    }
  }

  Future<void> completeOnboarding() async {
    state = state.copyWith(onboardingDone: true);
    await _prefs.setBool(_kOnboarding, true);
  }
}

final settingsProvider =
    NotifierProvider<SettingsController, AppSettings>(SettingsController.new);
