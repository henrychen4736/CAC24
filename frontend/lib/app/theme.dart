import 'package:flutter/material.dart';

import '../features/results/models/report.dart';

/// Spacing tokens. Use these instead of ad-hoc numbers.
abstract final class Insets {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
  static const double xxl = 32;
}

/// Corner radius tokens.
abstract final class Radii {
  static const double sm = 10;
  static const double md = 16;
  static const double lg = 24;
}

const _courtGreen = Color(0xFF1B5E3B);
const _opticYellow = Color(0xFFD7F03A);
const _onOpticYellow = Color(0xFF1F2600);

/// Semantic colors for ratings, scores, and the skeleton overlay.
@immutable
class ScorePalette extends ThemeExtension<ScorePalette> {
  const ScorePalette({
    required this.good,
    required this.fair,
    required this.needsWork,
    required this.info,
    required this.bone,
    required this.joint,
    required this.highlight,
  });

  final Color good;
  final Color fair;
  final Color needsWork;
  final Color info;

  /// Skeleton overlay colors (drawn on top of video, so they don't follow the
  /// light/dark theme).
  final Color bone;
  final Color joint;
  final Color highlight;

  static const light = ScorePalette(
    good: Color(0xFF2E7D32),
    fair: Color(0xFFB26A00),
    needsWork: Color(0xFFC62828),
    info: Color(0xFF546E7A),
    bone: Color(0xE6FFFFFF),
    joint: Color(0xFFFFFFFF),
    highlight: _opticYellow,
  );

  static const dark = ScorePalette(
    good: Color(0xFF81C784),
    fair: Color(0xFFFFB74D),
    needsWork: Color(0xFFEF9A9A),
    info: Color(0xFF90A4AE),
    bone: Color(0xE6FFFFFF),
    joint: Color(0xFFFFFFFF),
    highlight: _opticYellow,
  );

  Color forRating(Rating rating) => switch (rating) {
        Rating.good => good,
        Rating.fair => fair,
        Rating.needsWork => needsWork,
        Rating.info => info,
      };

  Color forScore(num? score) {
    if (score == null) return info;
    if (score >= 80) return good;
    if (score >= 60) return fair;
    return needsWork;
  }

  @override
  ScorePalette copyWith({
    Color? good,
    Color? fair,
    Color? needsWork,
    Color? info,
    Color? bone,
    Color? joint,
    Color? highlight,
  }) =>
      ScorePalette(
        good: good ?? this.good,
        fair: fair ?? this.fair,
        needsWork: needsWork ?? this.needsWork,
        info: info ?? this.info,
        bone: bone ?? this.bone,
        joint: joint ?? this.joint,
        highlight: highlight ?? this.highlight,
      );

  @override
  ScorePalette lerp(ScorePalette? other, double t) {
    if (other == null) return this;
    return ScorePalette(
      good: Color.lerp(good, other.good, t)!,
      fair: Color.lerp(fair, other.fair, t)!,
      needsWork: Color.lerp(needsWork, other.needsWork, t)!,
      info: Color.lerp(info, other.info, t)!,
      bone: Color.lerp(bone, other.bone, t)!,
      joint: Color.lerp(joint, other.joint, t)!,
      highlight: Color.lerp(highlight, other.highlight, t)!,
    );
  }
}

extension ScorePaletteX on BuildContext {
  ScorePalette get scores => Theme.of(this).extension<ScorePalette>()!;
}

abstract final class AppTheme {
  static ThemeData light() => _build(Brightness.light);
  static ThemeData dark() => _build(Brightness.dark);

  static ThemeData _build(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: _courtGreen,
      brightness: brightness,
    ).copyWith(tertiary: _opticYellow, onTertiary: _onOpticYellow);

    final base = ThemeData(colorScheme: scheme, brightness: brightness);
    final text = base.textTheme.copyWith(
      displaySmall: base.textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700),
      headlineMedium: base.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700),
      headlineSmall: base.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700),
      titleLarge: base.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600),
      titleMedium: base.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
    );
    final rounded = RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.md));

    return base.copyWith(
      textTheme: text,
      scaffoldBackgroundColor: scheme.surface,
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        surfaceTintColor: Colors.transparent,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: text.titleLarge?.copyWith(color: scheme.onSurface),
      ),
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        color: scheme.surfaceContainerLow,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Radii.md),
          side: BorderSide(color: scheme.outlineVariant.withValues(alpha: 0.6)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          shape: rounded,
          textStyle: text.titleMedium,
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          shape: rounded,
          textStyle: text.titleMedium,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Radii.sm),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Radii.sm),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(Radii.sm),
          borderSide: BorderSide(color: scheme.primary, width: 2),
        ),
      ),
      chipTheme: base.chipTheme.copyWith(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.sm)),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: scheme.surfaceContainer,
        indicatorColor: scheme.secondaryContainer,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      ),
      snackBarTheme: const SnackBarThemeData(behavior: SnackBarBehavior.floating),
      bottomSheetTheme: const BottomSheetThemeData(showDragHandle: true),
      extensions: [
        brightness == Brightness.light ? ScorePalette.light : ScorePalette.dark,
      ],
    );
  }
}
