import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../app/theme.dart';
import '../../../core/format.dart';
import '../../../core/widgets/common.dart';
import '../models/report.dart';

String ratingLabel(Rating r) => switch (r) {
      Rating.good => 'Good',
      Rating.fair => 'Fair',
      Rating.needsWork => 'Needs work',
      Rating.info => 'Info',
    };

IconData ratingIcon(Rating r) => switch (r) {
      Rating.good => Icons.check_circle_rounded,
      Rating.fair => Icons.adjust_rounded,
      Rating.needsWork => Icons.error_rounded,
      Rating.info => Icons.info_rounded,
    };

/// "Target 60° – 110°", or "Target ≥ 60°" / "Target ≤ 20°" for one-sided ranges.
String targetLabel((double?, double?) good, String unit) {
  final suffix = unit == 'deg' ? '' : ' ${unitLabel(unit)}';
  return switch (good) {
    (final lo?, final hi?) => 'Target ${formatBound(lo, unit)} – ${formatBound(hi, unit)}$suffix',
    (final lo?, null) => 'Target ≥ ${formatBound(lo, unit)}$suffix',
    (null, final hi?) => 'Target ≤ ${formatBound(hi, unit)}$suffix',
    _ => '',
  };
}

/// A metric's value shown against its reference range: the "ok" band, the
/// "good" band inside it, and a marker for the measured value. Open-ended
/// bounds run to the edge of the bar.
class RangeBar extends StatelessWidget {
  const RangeBar({
    super.key,
    required this.reference,
    required this.value,
    required this.unit,
    required this.valueColor,
  });

  final ReferenceRange reference;
  final double value;
  final String unit;
  final Color valueColor;

  /// Visible domain: every finite bound plus the value, padded 15 %. Open-ended
  /// sides get extra room so the band visibly continues past the last number.
  static (double, double) domain(ReferenceRange r, double value) {
    final bounds = <double>[value];
    var openLow = false, openHigh = false;
    for (final band in [?r.ok, ?r.good]) {
      if (band.$1 case final lo?) {
        bounds.add(lo);
      } else {
        openLow = true;
      }
      if (band.$2 case final hi?) {
        bounds.add(hi);
      } else {
        openHigh = true;
      }
    }
    final lo = bounds.reduce(math.min), hi = bounds.reduce(math.max);
    final span = hi - lo;
    final pad = span == 0 ? math.max(value.abs() * 0.25, 1.0) : span * 0.15;
    return (lo - pad * (openLow ? 2.5 : 1), hi + pad * (openHigh ? 2.5 : 1));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final palette = context.scores;
    final good = reference.good;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SizedBox(
          height: 18,
          child: CustomPaint(
            painter: _RangePainter(
              domain: domain(reference, value),
              ok: reference.ok,
              good: good,
              value: value,
              track: theme.colorScheme.surfaceContainerHighest,
              okColor: palette.fair.withValues(alpha: 0.30),
              goodColor: palette.good.withValues(alpha: 0.55),
              valueColor: valueColor,
              outline: theme.colorScheme.surface,
            ),
          ),
        ),
        if (good != null)
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              targetLabel(good, unit),
              style: theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
          ),
      ],
    );
  }
}

class _RangePainter extends CustomPainter {
  _RangePainter({
    required this.domain,
    required this.ok,
    required this.good,
    required this.value,
    required this.track,
    required this.okColor,
    required this.goodColor,
    required this.valueColor,
    required this.outline,
  });

  final (double, double) domain;
  final (double?, double?)? ok;
  final (double?, double?)? good;
  final double value;
  final Color track, okColor, goodColor, valueColor, outline;

  @override
  void paint(Canvas canvas, Size size) {
    final (lo, hi) = domain;
    double x(double v) => ((v - lo) / (hi - lo)).clamp(0.0, 1.0) * size.width;
    final cy = size.height / 2;
    const h = 8.0;
    RRect band(double a, double b) => RRect.fromRectAndRadius(
          Rect.fromLTRB(x(a), cy - h / 2, x(b), cy + h / 2),
          const Radius.circular(h / 2),
        );
    canvas.drawRRect(band(lo, hi), Paint()..color = track);
    // open-ended bounds (null) run to the edge of the bar
    if (ok case (final a, final b)) canvas.drawRRect(band(a ?? lo, b ?? hi), Paint()..color = okColor);
    if (good case (final a, final b)) {
      canvas.drawRRect(band(a ?? lo, b ?? hi), Paint()..color = goodColor);
    }
    final c = Offset(x(value), cy);
    canvas.drawCircle(c, 8, Paint()..color = outline);
    canvas.drawCircle(c, 6, Paint()..color = valueColor);
  }

  @override
  bool shouldRepaint(_RangePainter old) =>
      old.value != value || old.domain != domain || old.valueColor != valueColor;
}

class MetricTile extends StatelessWidget {
  const MetricTile({super.key, required this.metric, this.selected = false, this.onTap});

  final Metric metric;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final palette = context.scores;
    final color = palette.forRating(metric.rating);
    final lowConfidence = metric.confidence == Confidence.low;
    final value = metric.value;

    return Opacity(
      opacity: lowConfidence ? 0.65 : 1,
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(Radii.md),
          side: BorderSide(
            color: selected ? palette.highlight : theme.colorScheme.outlineVariant.withValues(alpha: 0.6),
            width: selected ? 2 : 1,
          ),
        ),
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(Insets.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: Text(metric.label, style: theme.textTheme.titleSmall)),
                    const SizedBox(width: Insets.sm),
                    Text(
                      formatMetricValue(value, metric.unit),
                      style: theme.textTheme.titleMedium?.copyWith(color: color),
                    ),
                  ],
                ),
                const SizedBox(height: Insets.xs),
                Wrap(
                  spacing: Insets.xs,
                  runSpacing: Insets.xs,
                  children: [
                    Pill(label: ratingLabel(metric.rating), color: color, icon: ratingIcon(metric.rating)),
                    if (metric.confidence != Confidence.high)
                      Pill(
                        label: metric.confidence == Confidence.low
                            ? 'Low confidence from this angle'
                            : 'Medium confidence',
                        color: palette.info,
                        icon: Icons.videocam_outlined,
                      ),
                  ],
                ),
                if (metric.reference != null && value != null && !value.isNaN) ...[
                  const SizedBox(height: Insets.md),
                  RangeBar(reference: metric.reference!, value: value, unit: metric.unit, valueColor: color),
                ],
                if (metric.explanation.isNotEmpty) ...[
                  const SizedBox(height: Insets.sm),
                  Text(
                    metric.explanation,
                    style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                  ),
                ],
                if (metric.cue case final cue? when cue.isNotEmpty) ...[
                  const SizedBox(height: Insets.sm),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.lightbulb_outline_rounded, size: 18, color: theme.colorScheme.primary),
                      const SizedBox(width: Insets.sm),
                      Expanded(child: Text(cue, style: theme.textTheme.bodyMedium)),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class PriorityCard extends StatelessWidget {
  const PriorityCard({super.key, required this.rank, required this.priority, this.onTap});

  final int rank;
  final Priority priority;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = context.scores.forRating(priority.severity);
    final count = priority.strokeIndices.length;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(Insets.lg),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              CircleAvatar(
                radius: 14,
                backgroundColor: color.withValues(alpha: 0.15),
                child: Text('$rank', style: theme.textTheme.labelLarge?.copyWith(color: color)),
              ),
              const SizedBox(width: Insets.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(priority.title, style: theme.textTheme.titleSmall),
                    const SizedBox(height: Insets.xs),
                    Text(priority.cue, style: theme.textTheme.bodyMedium),
                    if (priority.strokeType != null) ...[
                      const SizedBox(height: Insets.sm),
                      Text(
                        count > 1
                            ? '${strokeTypeLabel(priority.strokeType!)} · seen in $count strokes'
                            : strokeTypeLabel(priority.strokeType!),
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (onTap != null)
                Icon(Icons.chevron_right_rounded, color: theme.colorScheme.onSurfaceVariant),
            ],
          ),
        ),
      ),
    );
  }
}
