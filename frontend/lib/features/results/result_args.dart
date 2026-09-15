import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../history/history_repository.dart';
import 'models/report.dart';

/// Everything the result screen needs to render an analysis.
class ResultArgs {
  const ResultArgs({
    required this.report,
    this.videoPath,
    this.analysisId,
    this.createdAt,
    this.isSample = false,
    this.saveError,
  });

  final AnalysisReport report;

  /// Local video file to play under the overlay; null shows a skeleton-only replay.
  final String? videoPath;
  final String? analysisId;
  final DateTime? createdAt;
  final bool isSample;

  /// Set when the analysis finished but could not be saved to history.
  final String? saveError;
}

const sampleReportAsset = 'assets/sample_report.json';

Future<AnalysisReport> loadSampleReport([AssetBundle? bundle]) async {
  final text = await (bundle ?? rootBundle).loadString(sampleReportAsset);
  return AnalysisReport.fromJson(jsonDecode(text) as Map<String, dynamic>);
}

/// Loads a result by id: `sample` for the bundled example, otherwise a saved
/// analysis from history.
final resultArgsProvider = FutureProvider.autoDispose.family<ResultArgs, String>((ref, id) async {
  if (id == 'sample') {
    return ResultArgs(report: await loadSampleReport(), isSample: true);
  }
  final repo = ref.watch(historyRepositoryProvider);
  if (repo == null) throw StateError('Sign in to view saved analyses.');
  final args = await repo.load(id);
  if (args == null) throw StateError('This analysis no longer exists.');
  return args;
});
