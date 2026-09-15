import 'package:intl/intl.dart';

import '../features/results/models/report.dart';

/// "forward_swing" -> "Forward swing".
String humanize(String snake) {
  if (snake.isEmpty) return snake;
  final words = snake.replaceAll('_', ' ').trim();
  return words[0].toUpperCase() + words.substring(1);
}

String strokeTypeLabel(String type) => switch (type) {
      'forehand' => 'Forehand',
      'forehand_slice' => 'Forehand slice',
      'forehand_volley' => 'Forehand volley',
      'backhand_1h' => 'One-handed backhand',
      'backhand_2h' => 'Two-handed backhand',
      'backhand_slice' => 'Backhand slice',
      'backhand_volley' => 'Backhand volley',
      'serve' => 'Serve',
      'smash' => 'Smash',
      _ => humanize(type),
    };

/// Short label that fits in chips.
String strokeTypeShortLabel(String type) => switch (type) {
      'backhand_1h' => '1H backhand',
      'backhand_2h' => '2H backhand',
      _ => strokeTypeLabel(type),
    };

String familyLabel(StrokeFamily family) => switch (family) {
      StrokeFamily.forehand => 'Forehand',
      StrokeFamily.backhand => 'Backhand',
      StrokeFamily.overhead => 'Serve',
      StrokeFamily.unknown => 'Other',
    };

String viewLabel(String view) => switch (view) {
      'back' => 'Back view',
      'front' => 'Front view',
      'side' => 'Side view',
      'oblique' => 'Angled view',
      _ => 'Unknown view',
    };

String unitLabel(String unit) => switch (unit) {
      'deg' => '°',
      'torso' => 'torso lengths',
      'torso/s' => 'torso lengths/s',
      's' => 's',
      _ => unit,
    };

/// Formats a metric value with its unit, e.g. `71°`, `0.08 torso`, `0.42 s`.
String formatMetricValue(double? value, String unit) {
  if (value == null || value.isNaN) return '—';
  return switch (unit) {
    'deg' => '${value.round()}°',
    'torso' => '${value.toStringAsFixed(2)} torso',
    'torso/s' => '${value.toStringAsFixed(1)} torso/s',
    's' => '${value.toStringAsFixed(2)} s',
    '' => _trim(value),
    _ => '${_trim(value)} $unit',
  };
}

/// Formats a bound of a reference range (no unit suffix except degrees).
String formatBound(double value, String unit) =>
    unit == 'deg' ? '${value.round()}°' : _trim(value);

String _trim(double v) {
  if (v == v.roundToDouble()) return v.toStringAsFixed(0);
  return v.abs() >= 10 ? v.toStringAsFixed(1) : v.toStringAsFixed(2);
}

String formatTimestamp(double seconds) {
  final s = seconds.clamp(0, 24 * 3600);
  final m = s ~/ 60;
  final rest = s - m * 60;
  return '$m:${rest.toStringAsFixed(1).padLeft(4, '0')}';
}

String formatDate(DateTime date) => DateFormat('MMM d, y · h:mm a').format(date.toLocal());

String formatShortDate(DateTime date) {
  final local = date.toLocal();
  final now = DateTime.now();
  final today = DateTime(now.year, now.month, now.day);
  final day = DateTime(local.year, local.month, local.day);
  final diff = today.difference(day).inDays;
  if (diff == 0) return 'Today · ${DateFormat.jm().format(local)}';
  if (diff == 1) return 'Yesterday · ${DateFormat.jm().format(local)}';
  if (diff < 7) return DateFormat('EEEE · h:mm a').format(local);
  return DateFormat('MMM d, y').format(local);
}

String pluralize(int count, String singular, [String? plural]) =>
    '$count ${count == 1 ? singular : (plural ?? '${singular}s')}';

/// "3 forehands · 1 serve" from a stroke-count map.
String strokeCountsLabel(Map<String, int> counts) {
  if (counts.isEmpty) return 'No strokes';
  final entries = counts.entries.toList()..sort((a, b) => b.value.compareTo(a.value));
  return entries
      .map((e) => '${e.value} ${strokeTypeShortLabel(e.key).toLowerCase()}${e.value == 1 ? '' : 's'}')
      .join(' · ');
}
