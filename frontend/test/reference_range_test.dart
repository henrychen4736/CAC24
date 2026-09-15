// The backend sends open-ended reference bounds as null (e.g. "contact point in
// front" is only coached when it's too small: good = [0.25, null]). Most metrics
// are one-sided, so dropping those ranges would hide most range bars.
import 'package:flutter_test/flutter_test.dart';
import 'package:tennis_analyze/features/results/models/report.dart';
import 'package:tennis_analyze/features/results/widgets/metric_widgets.dart';

void main() {
  test('open-ended reference bounds parse as null', () {
    final lower = ReferenceRange.fromJson({
      'good': [0.25, null],
      'ok': [0.1, null],
      'source': 'default',
    })!;
    expect(lower.good, (0.25, null));
    expect(lower.ok, (0.1, null));

    final upper = ReferenceRange.fromJson({
      'good': [null, 20],
      'ok': [null, 32],
    })!;
    expect(upper.good, (null, 20.0));
    expect(ReferenceRange.fromJson({'good': [null, null]}), isNull);
  });

  test('a metric with a one-sided range keeps its reference', () {
    final m = Metric.fromJson({
      'id': 'contact_in_front',
      'value': 0.08,
      'unit': 'torso',
      'rating': 'needs_work',
      'reference': {
        'good': [0.25, null],
        'ok': [0.1, null],
        'source': 'calibrated',
      },
    });
    expect(m.reference, isNotNull);
    expect(m.reference!.source, 'calibrated');
  });

  test('range bar domain covers the value and finite bounds, with room on open sides', () {
    final r = ReferenceRange.fromJson({
      'good': [0.25, null],
      'ok': [0.1, null],
    })!;
    final (lo, hi) = RangeBar.domain(r, 0.5);
    expect(lo, lessThan(0.1));
    expect(hi, greaterThan(0.5));
    // the open (high) side gets more room than the closed side
    expect(hi - 0.5, greaterThan(0.1 - lo));

    final (lo2, _) = RangeBar.domain(r, -0.3);
    expect(lo2, lessThan(-0.3));
  });

  test('target label reads naturally for one- and two-sided ranges', () {
    expect(targetLabel((60, null), 'deg'), 'Target ≥ 60°');
    expect(targetLabel((null, 20), 'deg'), 'Target ≤ 20°');
    expect(targetLabel((0.8, 2.2), 'torso'), 'Target 0.80 – 2.20 torso lengths');
  });
}
