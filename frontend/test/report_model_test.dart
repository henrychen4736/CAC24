import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:tennis_analyze/features/results/models/report.dart';

/// The sample is real backend output (see its `sample_source` field), so these
/// tests check parsing against the raw JSON instead of hard-coding its values —
/// they keep passing when the sample is regenerated.
Map<String, dynamic> loadRaw() =>
    jsonDecode(File('assets/sample_report.json').readAsStringSync()) as Map<String, dynamic>;

double _d(Object? v) => (v as num).toDouble();

void main() {
  group('AnalysisReport.fromJson (sample report)', () {
    final raw = loadRaw();
    final report = AnalysisReport.fromJson(raw);
    final rawStrokes = raw['strokes'] as List;

    test('parses top-level sections', () {
      final video = raw['video'] as Map;
      expect(report.version, raw['version']);
      expect(report.video.fps, _d(video['fps']));
      expect(report.video.aspectRatio, closeTo(_d(video['width']) / _d(video['height']), 1e-9));
      expect(report.player.handedness, raw['player']['handedness']);
      expect(report.player.view, raw['player']['view']);
      expect(report.quality.warnings, hasLength((raw['quality']['warnings'] as List).length));
      expect(report.models.classifier, raw['models']['classifier']);
      expect(report.summary.overallScore, raw['summary']['overall_score']);
      expect(report.summary.strokeCounts, (raw['summary']['stroke_counts'] as Map).cast<String, int>());

      final p0 = (raw['summary']['priorities'] as List).first as Map;
      final first = report.summary.priorities.first;
      expect(first.metricId, p0['metric_id']);
      expect(first.title, p0['title']);
      expect(first.severity, Rating.parse(p0['severity'] as String));
      expect(first.strokeIndices, (p0['stroke_indices'] as List).cast<int>());
    });

    test('is real output: learned classifier, calibrated ranges, credited source', () {
      expect(report.models.classifier, startsWith('learned:'));
      expect(report.models.reference, 'calibrated');
      expect(raw['sample_source'], contains('CC BY-SA'));
    });

    test('parses strokes, phases, and metrics', () {
      expect(report.strokes.map((s) => s.type), rawStrokes.map((s) => s['type']));
      final fh = report.strokes.first;
      final r0 = rawStrokes.first as Map;
      expect(fh.family, StrokeFamily.forehand);
      expect(fh.contactS, _d(r0['contact_s']));
      expect(fh.keyFrames['backswing_end'], _d(r0['key_frames']['backswing_end']));
      expect(fh.phases.map((p) => p.name), ['preparation', 'forward_swing', 'follow_through']);
      expect(fh.metrics, hasLength((r0['metrics'] as List).length));

      // "Contact point in front" is one-sided: at least X, no upper bound.
      final contact = fh.metrics.firstWhere((m) => m.id == 'contact_in_front');
      expect(contact.reference, isNotNull);
      expect(contact.reference!.good!.$1, isNotNull);
      expect(contact.reference!.good!.$2, isNull);
      expect(contact.joints, contains('r_wrist'));

      final speed = fh.metrics.firstWhere((m) => m.id == 'swing_speed');
      expect(speed.rating, Rating.info);
      expect(speed.score, isNull);
      expect(speed.reference, isNull);
    });

    test('momentFor uses key frames, then phase ends, then contact', () {
      final fh = report.strokes.first;
      Metric byPhase(String phase) => fh.metrics.firstWhere((m) => m.phase == phase);
      final prepEnd = fh.phases.firstWhere((p) => p.name == 'preparation').endS;
      expect(fh.momentFor(byPhase('contact')), fh.keyFrames['contact']); // key frame "contact"
      expect(fh.momentFor(byPhase('preparation')), prepEnd); // end of preparation
      expect(fh.momentFor(byPhase('follow_through')), fh.keyFrames['finish']); // "finish"
    });

    test('metricsByPhase follows the stroke phase order', () {
      final groups = report.strokes.first.metricsByPhase();
      expect(groups.map((g) => g.$1), ['preparation', 'forward_swing', 'follow_through', 'contact']);
      final total = groups.fold<int>(0, (n, g) => n + g.$2.length);
      expect(total, report.strokes.first.metrics.length);
    });

    test('pose track frames', () {
      final track = report.poseTrack!;
      expect(track.joints, hasLength(17));
      expect(track.frames, hasLength((raw['pose_track']['frames'] as List).length));
      expect(track.frameAt(0), hasLength(34));
      expect(track.frameAt(-1), isNull);
      expect(track.frameAt(1e6), isNull);
      expect(track.edges, contains((1, 2)));
    });

    test('toJsonWithoutPoseTrack drops only the pose track', () {
      final json = report.toJsonWithoutPoseTrack();
      expect(json.containsKey('pose_track'), isFalse);
      expect(json['strokes'], isList);
      expect(report.toJson().containsKey('pose_track'), isTrue);
    });

    test('primary stroke type and families', () {
      expect(report.primaryStrokeType, 'forehand');
      expect(report.families, {StrokeFamily.forehand});
    });
  });

  test('pose track dropouts (null frames) read as missing', () {
    final track = PoseTrack.fromJson({
      'fps': 30,
      'joints': ['a', 'b'],
      'edges': [
        [0, 1],
      ],
      'frames': [
        [0.1, 0.2, 0.3, 0.4],
        null,
        [0.1, 0.2, 0.3, 0.4],
      ],
    });
    expect(track.frameAt(0), hasLength(4));
    expect(track.frameAt(1 / 30), isNull);
    expect(track.frameAt(2 / 30), hasLength(4));
  });

  group('tolerant parsing', () {
    test('an empty object yields defaults', () {
      final r = AnalysisReport.fromJson({});
      expect(r.strokes, isEmpty);
      expect(r.poseTrack, isNull);
      expect(r.summary.overallScore, isNull);
      expect(r.video.aspectRatio, closeTo(16 / 9, 1e-9));
      expect(r.primaryStrokeType, isNull);
    });

    test('unknown fields and values are ignored', () {
      final r = AnalysisReport.fromJson({
        'future_field': {'x': 1},
        'strokes': [
          {
            'index': 0,
            'type': 'tweener',
            'family': 'trick',
            'metrics': [
              {'id': 'm', 'value': 'n/a', 'rating': 'excellent', 'confidence': 'weird', 'reference': 5},
              'not a map',
            ],
          },
        ],
      });
      final s = r.strokes.single;
      expect(s.family, StrokeFamily.unknown);
      final m = s.metrics.single;
      expect(m.value, isNull);
      expect(m.rating, Rating.info);
      expect(m.confidence, Confidence.high);
      expect(m.reference, isNull);
      expect(m.label, 'm');
    });

    test('integers are accepted where doubles are expected', () {
      final r = AnalysisReport.fromJson({
        'video': {'duration_s': 8, 'fps': 60, 'width': 1080, 'height': 1920},
      });
      expect(r.video.fps, 60.0);
      expect(r.video.aspectRatio, closeTo(1080 / 1920, 1e-9));
    });
  });
}
