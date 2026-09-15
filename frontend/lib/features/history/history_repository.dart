import 'dart:convert';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/providers.dart';
import '../results/models/report.dart';
import '../results/result_args.dart';
import 'local_store.dart';

/// A saved analysis as listed in history (`users/{uid}/analyses/{id}`).
class AnalysisRecord {
  const AnalysisRecord({
    required this.id,
    required this.createdAt,
    required this.primaryType,
    required this.families,
    required this.overallScore,
    required this.strokeCounts,
    required this.familyScores,
    required this.headline,
    required this.reportJson,
  });

  final String id;
  final DateTime? createdAt;
  final String? primaryType;
  final Set<StrokeFamily> families;
  final int? overallScore;
  final Map<String, int> strokeCounts;

  /// Average stroke score per family in this analysis (e.g. `forehand: 74`).
  final Map<StrokeFamily, double> familyScores;
  final String headline;

  /// The full report minus the pose track, stored as a JSON string so
  /// Firestore's nested-array restrictions never apply.
  final String? reportJson;

  int get strokeCount => strokeCounts.values.fold(0, (a, b) => a + b);

  AnalysisReport? get report {
    final json = reportJson;
    if (json == null) return null;
    try {
      return AnalysisReport.fromJson(jsonDecode(json) as Map<String, dynamic>);
    } on FormatException {
      return null;
    }
  }

  factory AnalysisRecord.fromMap(String id, Map<String, dynamic> data) {
    DateTime? time(Object? v) => v is Timestamp ? v.toDate() : null;
    return AnalysisRecord(
      id: id,
      createdAt: time(data['createdAt']) ?? time(data['clientCreatedAt']),
      primaryType: data['primaryType'] as String?,
      families: {
        for (final f in (data['families'] as List? ?? const []))
          if (f is String) StrokeFamily.parse(f),
      },
      overallScore: (data['overallScore'] as num?)?.round(),
      strokeCounts: {
        for (final e in ((data['strokeCounts'] as Map?) ?? const {}).entries)
          if (e.key is String && e.value is num) e.key as String: (e.value as num).toInt(),
      },
      familyScores: {
        for (final e in ((data['familyScores'] as Map?) ?? const {}).entries)
          if (e.key is String && e.value is num) StrokeFamily.parse(e.key as String): (e.value as num).toDouble(),
      },
      headline: data['headline'] as String? ?? '',
      reportJson: data['reportJson'] as String?,
    );
  }

  static Map<String, dynamic> toMap(AnalysisReport report) {
    final familyScores = <String, List<int>>{};
    for (final s in report.strokes) {
      final score = s.score;
      if (score != null) familyScores.putIfAbsent(s.family.name, () => []).add(score);
    }
    return {
      'createdAt': FieldValue.serverTimestamp(),
      'clientCreatedAt': Timestamp.now(),
      'primaryType': report.primaryStrokeType,
      'families': [for (final f in report.families) f.name],
      'overallScore': report.summary.overallScore,
      'strokeCounts': report.summary.strokeCounts,
      'familyScores': {
        for (final e in familyScores.entries)
          e.key: e.value.reduce((a, b) => a + b) / e.value.length,
      },
      'headline': report.summary.headline,
      'reportVersion': report.version,
      'reportJson': jsonEncode(report.toJsonWithoutPoseTrack()),
    };
  }
}

class HistoryRepository {
  HistoryRepository({
    required FirebaseFirestore db,
    required this.uid,
    required LocalAnalysisStore local,
  })  : _db = db, // ignore: prefer_initializing_formals
        _local = local; // ignore: prefer_initializing_formals

  final FirebaseFirestore _db;
  final String uid;
  final LocalAnalysisStore _local;

  DocumentReference<Map<String, dynamic>> get _user => _db.collection('users').doc(uid);
  CollectionReference<Map<String, dynamic>> get _col => _user.collection('analyses');

  Stream<List<AnalysisRecord>> watchAll({int limit = 200}) => _col
      .orderBy('clientCreatedAt', descending: true)
      .limit(limit)
      .snapshots()
      .map((snap) => [for (final d in snap.docs) AnalysisRecord.fromMap(d.id, d.data())]);

  /// Saves the report to Firestore and the pose track + video on the device.
  /// Returns the local video path (or null if there was no video). Local file
  /// errors are swallowed; Firestore errors propagate to the caller.
  Future<String?> save({
    required String id,
    required AnalysisReport report,
    String? videoPath,
  }) async {
    String? localVideo;
    try {
      if (report.poseTrack != null) await _local.savePoseTrack(id, report.poseTrack!);
      if (videoPath != null) localVideo = await _local.saveVideo(id, videoPath);
    } catch (_) {
      localVideo = null;
    }
    await _col.doc(id).set(AnalysisRecord.toMap(report));
    return localVideo;
  }

  Future<ResultArgs?> load(String id) async {
    final doc = await _col.doc(id).get();
    final data = doc.data();
    if (data == null) return null;
    final record = AnalysisRecord.fromMap(doc.id, data);
    final report = record.report;
    if (report == null) return null;
    return ResultArgs(
      report: report.withPoseTrack(await _local.loadPoseTrack(id)),
      videoPath: await _local.findVideo(id),
      analysisId: id,
      createdAt: record.createdAt,
    );
  }

  Future<void> delete(String id) async {
    await _col.doc(id).delete();
    await _local.delete(id);
  }

  /// Deletes every analysis and the user document (used before account deletion).
  Future<void> deleteAll() async {
    while (true) {
      final snap = await _col.limit(300).get();
      if (snap.docs.isEmpty) break;
      final batch = _db.batch();
      for (final d in snap.docs) {
        batch.delete(d.reference);
      }
      await batch.commit();
    }
    await _user.delete();
    await _local.deleteAll();
  }
}

final localStoreProvider = Provider<LocalAnalysisStore>((ref) => LocalAnalysisStore());

final historyRepositoryProvider = Provider<HistoryRepository?>((ref) {
  final uid = ref.watch(authStateProvider.select((a) => a.value?.uid));
  if (uid == null) return null;
  return HistoryRepository(
    db: ref.watch(firestoreProvider),
    uid: uid,
    local: ref.watch(localStoreProvider),
  );
});

final historyProvider = StreamProvider<List<AnalysisRecord>>((ref) {
  final repo = ref.watch(historyRepositoryProvider);
  if (repo == null) return Stream.value(const []);
  return repo.watchAll();
});
