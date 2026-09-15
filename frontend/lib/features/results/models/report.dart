// Typed models for the analysis report returned by the backend.
// Contract: docs/ARCHITECTURE.md §6. Parsing is tolerant: unknown fields are
// ignored and optional fields fall back to sensible defaults, so the backend
// can add fields without breaking older app builds.

typedef Json = Map<String, dynamic>;

double? _toDouble(Object? v) => v is num ? v.toDouble() : null;
int? _toInt(Object? v) => v is num ? v.round() : null;
String? _toStr(Object? v) => v is String ? v : null;
Json _toMap(Object? v) => v is Map ? v.cast<String, dynamic>() : const {};
List<Object?> _toList(Object? v) => v is List ? v : const [];

enum Rating {
  good,
  fair,
  needsWork,
  info;

  static Rating parse(String? v) => switch (v) {
        'good' => Rating.good,
        'fair' => Rating.fair,
        'needs_work' => Rating.needsWork,
        _ => Rating.info,
      };

  String get wire => switch (this) {
        Rating.good => 'good',
        Rating.fair => 'fair',
        Rating.needsWork => 'needs_work',
        Rating.info => 'info',
      };
}

enum Confidence {
  high,
  medium,
  low;

  static Confidence parse(String? v) => switch (v) {
        'low' => Confidence.low,
        'medium' => Confidence.medium,
        _ => Confidence.high,
      };
}

/// Stroke families used for grouping and filtering.
enum StrokeFamily {
  forehand,
  backhand,
  overhead,
  unknown;

  static StrokeFamily parse(String? v) => switch (v) {
        'forehand' => StrokeFamily.forehand,
        'backhand' => StrokeFamily.backhand,
        'overhead' => StrokeFamily.overhead,
        _ => StrokeFamily.unknown,
      };
}

class AnalysisReport {
  const AnalysisReport({
    required this.version,
    required this.video,
    required this.player,
    required this.quality,
    required this.models,
    required this.summary,
    required this.strokes,
    required this.poseTrack,
    required this.raw,
  });

  final String version;
  final VideoInfo video;
  final PlayerInfo player;
  final QualityInfo quality;
  final ModelsInfo models;
  final ReportSummary summary;
  final List<Stroke> strokes;
  final PoseTrack? poseTrack;

  /// The original JSON, kept so the report round-trips without losing fields
  /// this app version doesn't know about.
  final Json raw;

  factory AnalysisReport.fromJson(Json json) => AnalysisReport(
        version: _toStr(json['version']) ?? '2.0',
        video: VideoInfo.fromJson(_toMap(json['video'])),
        player: PlayerInfo.fromJson(_toMap(json['player'])),
        quality: QualityInfo.fromJson(_toMap(json['quality'])),
        models: ModelsInfo.fromJson(_toMap(json['models'])),
        summary: ReportSummary.fromJson(_toMap(json['summary'])),
        strokes: [
          for (final s in _toList(json['strokes']))
            if (s is Map) Stroke.fromJson(s.cast<String, dynamic>()),
        ],
        poseTrack: json['pose_track'] is Map
            ? PoseTrack.fromJson(_toMap(json['pose_track']))
            : null,
        raw: json,
      );

  Json toJson() => raw;

  /// JSON without the (large) pose track — what gets stored in Firestore.
  Json toJsonWithoutPoseTrack() => Map.of(raw)..remove('pose_track');

  AnalysisReport withPoseTrack(PoseTrack? track) => AnalysisReport(
        version: version,
        video: video,
        player: player,
        quality: quality,
        models: models,
        summary: summary,
        strokes: strokes,
        poseTrack: track,
        raw: raw,
      );

  /// The most frequent stroke type, used as the headline of a history entry.
  String? get primaryStrokeType {
    if (summary.strokeCounts.isNotEmpty) {
      final sorted = summary.strokeCounts.entries.toList()
        ..sort((a, b) => b.value.compareTo(a.value));
      return sorted.first.key;
    }
    return strokes.isEmpty ? null : strokes.first.type;
  }

  Set<StrokeFamily> get families => {for (final s in strokes) s.family};
}

class VideoInfo {
  const VideoInfo({
    required this.durationS,
    required this.fps,
    required this.width,
    required this.height,
    required this.framesAnalyzed,
  });

  final double durationS;
  final double fps;
  final int width;
  final int height;
  final int framesAnalyzed;

  double get aspectRatio => (width > 0 && height > 0) ? width / height : 16 / 9;

  factory VideoInfo.fromJson(Json json) => VideoInfo(
        durationS: _toDouble(json['duration_s']) ?? 0,
        fps: _toDouble(json['fps']) ?? 30,
        width: _toInt(json['width']) ?? 0,
        height: _toInt(json['height']) ?? 0,
        framesAnalyzed: _toInt(json['frames_analyzed']) ?? 0,
      );
}

class PlayerInfo {
  const PlayerInfo({
    required this.handedness,
    required this.handednessSource,
    required this.view,
    required this.viewConfidence,
  });

  final String handedness;
  final String handednessSource;
  final String view;
  final double? viewConfidence;

  factory PlayerInfo.fromJson(Json json) => PlayerInfo(
        handedness: _toStr(json['handedness']) ?? 'right',
        handednessSource: _toStr(json['handedness_source']) ?? 'detected',
        view: _toStr(json['view']) ?? 'unknown',
        viewConfidence: _toDouble(json['view_confidence']),
      );
}

class QualityWarning {
  const QualityWarning({required this.code, required this.message});

  final String code;
  final String message;

  factory QualityWarning.fromJson(Json json) => QualityWarning(
        code: _toStr(json['code']) ?? 'warning',
        message: _toStr(json['message']) ?? '',
      );
}

class QualityInfo {
  const QualityInfo({required this.score, required this.warnings});

  final double? score;
  final List<QualityWarning> warnings;

  factory QualityInfo.fromJson(Json json) => QualityInfo(
        score: _toDouble(json['score']),
        warnings: [
          for (final w in _toList(json['warnings']))
            if (w is Map) QualityWarning.fromJson(w.cast<String, dynamic>()),
        ],
      );
}

class ModelsInfo {
  const ModelsInfo({this.pose, this.classifier, this.reference});

  final String? pose;
  final String? classifier;
  final String? reference;

  factory ModelsInfo.fromJson(Json json) => ModelsInfo(
        pose: _toStr(json['pose']),
        classifier: _toStr(json['classifier']),
        reference: _toStr(json['reference']),
      );
}

class Priority {
  const Priority({
    required this.metricId,
    required this.title,
    required this.cue,
    required this.strokeType,
    required this.strokeIndices,
    required this.severity,
  });

  final String metricId;
  final String title;
  final String cue;
  final String? strokeType;
  final List<int> strokeIndices;
  final Rating severity;

  factory Priority.fromJson(Json json) => Priority(
        metricId: _toStr(json['metric_id']) ?? '',
        title: _toStr(json['title']) ?? '',
        cue: _toStr(json['cue']) ?? '',
        strokeType: _toStr(json['stroke_type']),
        strokeIndices: [
          for (final i in _toList(json['stroke_indices']))
            if (i is num) i.toInt(),
        ],
        severity: Rating.parse(_toStr(json['severity'])),
      );
}

class ReportSummary {
  const ReportSummary({
    required this.overallScore,
    required this.strokeCounts,
    required this.headline,
    required this.priorities,
  });

  final int? overallScore;
  final Map<String, int> strokeCounts;
  final String headline;
  final List<Priority> priorities;

  factory ReportSummary.fromJson(Json json) => ReportSummary(
        overallScore: _toInt(json['overall_score']),
        strokeCounts: {
          for (final e in _toMap(json['stroke_counts']).entries)
            if (e.value is num) e.key: (e.value as num).toInt(),
        },
        headline: _toStr(json['headline']) ?? '',
        priorities: [
          for (final p in _toList(json['priorities']))
            if (p is Map) Priority.fromJson(p.cast<String, dynamic>()),
        ],
      );
}

class Phase {
  const Phase({required this.name, required this.startS, required this.endS});

  final String name;
  final double startS;
  final double endS;

  factory Phase.fromJson(Json json) => Phase(
        name: _toStr(json['name']) ?? '',
        startS: _toDouble(json['start_s']) ?? 0,
        endS: _toDouble(json['end_s']) ?? 0,
      );
}

class ReferenceRange {
  const ReferenceRange({required this.good, required this.ok, required this.source});

  /// Inclusive [low, high] band rated "good". A null bound is open-ended:
  /// `(0.25, null)` means "at least 0.25" — most metrics are only coached on
  /// one side (e.g. contact can't be "too far in front").
  final (double?, double?)? good;

  /// Inclusive [low, high] band rated at least "fair" (same null convention).
  final (double?, double?)? ok;
  final String source;

  static (double?, double?)? _pair(Object? v) {
    if (v is! List || v.length != 2) return null;
    double? bound(Object? b) => b is num ? b.toDouble() : null;
    final lo = bound(v[0]), hi = bound(v[1]);
    if (lo == null && hi == null) return null;
    return (lo, hi);
  }

  static ReferenceRange? fromJson(Object? json) {
    if (json is! Map) return null;
    final m = json.cast<String, dynamic>();
    final good = _pair(m['good']);
    final ok = _pair(m['ok']);
    if (good == null && ok == null) return null;
    return ReferenceRange(good: good, ok: ok, source: _toStr(m['source']) ?? 'default');
  }
}

class Metric {
  const Metric({
    required this.id,
    required this.label,
    required this.value,
    required this.unit,
    required this.phase,
    required this.rating,
    required this.score,
    required this.confidence,
    required this.reference,
    required this.explanation,
    required this.cue,
    required this.joints,
  });

  final String id;
  final String label;
  final double? value;
  final String unit;
  final String phase;
  final Rating rating;
  final int? score;
  final Confidence confidence;
  final ReferenceRange? reference;
  final String explanation;
  final String? cue;
  final List<String> joints;

  factory Metric.fromJson(Json json) => Metric(
        id: _toStr(json['id']) ?? '',
        label: _toStr(json['label']) ?? _toStr(json['id']) ?? 'Metric',
        value: _toDouble(json['value']),
        unit: _toStr(json['unit']) ?? '',
        phase: _toStr(json['phase']) ?? '',
        rating: Rating.parse(_toStr(json['rating'])),
        score: _toInt(json['score']),
        confidence: Confidence.parse(_toStr(json['confidence'])),
        reference: ReferenceRange.fromJson(json['reference']),
        explanation: _toStr(json['explanation']) ?? '',
        cue: _toStr(json['cue']),
        joints: [
          for (final j in _toList(json['joints']))
            if (j is String) j,
        ],
      );
}

class Stroke {
  const Stroke({
    required this.index,
    required this.type,
    required this.family,
    required this.typeConfidence,
    required this.typeSource,
    required this.startS,
    required this.contactS,
    required this.endS,
    required this.keyFrames,
    required this.phases,
    required this.score,
    required this.skillScore,
    required this.metrics,
  });

  final int index;
  final String type;
  final StrokeFamily family;
  final double? typeConfidence;
  final String typeSource;
  final double startS;
  final double contactS;
  final double endS;
  final Map<String, double> keyFrames;
  final List<Phase> phases;
  final int? score;
  final double? skillScore;
  final List<Metric> metrics;

  factory Stroke.fromJson(Json json) => Stroke(
        index: _toInt(json['index']) ?? 0,
        type: _toStr(json['type']) ?? 'unknown',
        family: StrokeFamily.parse(_toStr(json['family'])),
        typeConfidence: _toDouble(json['type_confidence']),
        typeSource: _toStr(json['type_source']) ?? 'heuristic',
        startS: _toDouble(json['start_s']) ?? 0,
        contactS: _toDouble(json['contact_s']) ?? 0,
        endS: _toDouble(json['end_s']) ?? 0,
        keyFrames: {
          for (final e in _toMap(json['key_frames']).entries)
            if (e.value is num) e.key: (e.value as num).toDouble(),
        },
        phases: [
          for (final p in _toList(json['phases']))
            if (p is Map) Phase.fromJson(p.cast<String, dynamic>()),
        ],
        score: _toInt(json['score']),
        skillScore: _toDouble(json['skill_score']),
        metrics: [
          for (final m in _toList(json['metrics']))
            if (m is Map) Metric.fromJson(m.cast<String, dynamic>()),
        ],
      );

  /// The moment in the video that best illustrates [metric]: its key frame if
  /// the stroke has one with the same name, else the end of the matching
  /// phase, else contact.
  double momentFor(Metric metric) {
    final key = keyFrames[metric.phase];
    if (key != null) return key;
    for (final p in phases) {
      if (p.name == metric.phase) {
        return p.name == 'follow_through' ? (keyFrames['finish'] ?? p.endS) : p.endS;
      }
    }
    return contactS;
  }

  /// Metrics grouped by phase, in the order phases occur in the stroke.
  List<(String phase, List<Metric> metrics)> metricsByPhase() {
    final order = <String>[];
    for (final p in phases) {
      order.add(p.name);
    }
    for (final k in keyFrames.keys) {
      if (!order.contains(k)) order.add(k);
    }
    final groups = <String, List<Metric>>{};
    for (final m in metrics) {
      groups.putIfAbsent(m.phase, () => []).add(m);
    }
    final keys = groups.keys.toList()
      ..sort((a, b) {
        final ia = order.indexOf(a), ib = order.indexOf(b);
        return (ia < 0 ? 1 << 20 : ia).compareTo(ib < 0 ? 1 << 20 : ib);
      });
    return [for (final k in keys) (k, groups[k]!)];
  }
}

/// Per-frame 2D keypoints for the skeleton overlay.
class PoseTrack {
  const PoseTrack({
    required this.fps,
    required this.joints,
    required this.edges,
    required this.frames,
  });

  final double fps;
  final List<String> joints;
  final List<(int, int)> edges;

  /// One entry per analyzed frame; each is `[x0, y0, x1, y1, ...]` normalized
  /// to the displayed video frame, or null when no player was detected.
  final List<List<double>?> frames;

  int indexOf(String joint) => joints.indexOf(joint);

  /// Frame for time [t] seconds, or null if out of range / not detected.
  List<double>? frameAt(double t) {
    if (frames.isEmpty || fps <= 0 || t < 0) return null;
    final i = (t * fps).round();
    if (i >= frames.length) return null;
    final f = frames[i];
    return (f != null && f.length >= joints.length * 2) ? f : null;
  }

  factory PoseTrack.fromJson(Json json) => PoseTrack(
        fps: _toDouble(json['fps']) ?? 30,
        joints: [
          for (final j in _toList(json['joints']))
            if (j is String) j,
        ],
        edges: [
          for (final e in _toList(json['edges']))
            if (e is List && e.length == 2 && e[0] is num && e[1] is num)
              ((e[0] as num).toInt(), (e[1] as num).toInt()),
        ],
        frames: [
          for (final f in _toList(json['frames']))
            f is List ? [for (final v in f) v is num ? v.toDouble() : double.nan] : null,
        ],
      );

  Json toJson() => {
        'fps': fps,
        'joints': joints,
        'edges': [
          for (final (a, b) in edges) [a, b],
        ],
        'frames': frames,
      };
}
