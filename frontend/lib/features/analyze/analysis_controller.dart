import 'package:dio/dio.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api/api_client.dart';
import '../../core/api/api_exception.dart';
import '../../core/config/settings.dart';
import '../../core/providers.dart';
import '../history/history_repository.dart';
import '../results/result_args.dart';

class AnalysisRequest {
  const AnalysisRequest({
    required this.videoPath,
    required this.strokeHint,
    required this.handedness,
  });

  final String videoPath;

  /// `auto` | `forehand` | `backhand` | `serve`.
  final String strokeHint;
  final Handedness handedness;
}

sealed class AnalysisFlowState {
  const AnalysisFlowState();
}

class FlowIdle extends AnalysisFlowState {
  const FlowIdle();
}

class FlowUploading extends AnalysisFlowState {
  const FlowUploading(this.progress);
  final double progress;
}

class FlowProcessing extends AnalysisFlowState {
  const FlowProcessing(this.stage, this.progress);

  /// Server stage: `queued` | `decoding` | `pose` | `analysis` | `done`.
  final String stage;
  final double progress;
}

class FlowSaving extends AnalysisFlowState {
  const FlowSaving();
}

class FlowDone extends AnalysisFlowState {
  const FlowDone(this.args);
  final ResultArgs args;
}

class FlowFailed extends AnalysisFlowState {
  const FlowFailed(this.message, {this.code});
  final String message;
  final String? code;
}

/// Upload → poll → save, as a small state machine the processing screen watches.
class AnalysisFlowController extends Notifier<AnalysisFlowState> {
  CancelToken? _cancel;
  String? _jobId;
  AnalysisRequest? _last;

  @override
  AnalysisFlowState build() {
    ref.onDispose(() => _cancel?.cancel());
    return const FlowIdle();
  }

  void _set(AnalysisFlowState s) {
    if (ref.mounted) state = s;
  }

  Future<void> start(AnalysisRequest request) async {
    _last = request;
    _cancel?.cancel();
    final cancel = _cancel = CancelToken();
    _jobId = null;
    final api = ref.read(apiClientProvider);
    final repo = ref.read(historyRepositoryProvider);
    _set(const FlowUploading(0));

    try {
      var job = await api.createAnalysis(
        filePath: request.videoPath,
        strokeHint: request.strokeHint,
        handedness: request.handedness.wire,
        cancelToken: cancel,
        onUploadProgress: (p) {
          if (!cancel.isCancelled) _set(FlowUploading(p));
        },
      );
      _jobId = job.id;
      _set(FlowProcessing(job.stage, job.progress));

      if (!job.status.isTerminal) {
        await for (final update in api.watchAnalysis(job.id, cancelToken: cancel)) {
          job = update;
          if (!job.status.isTerminal) _set(FlowProcessing(job.stage, job.progress));
        }
      }
      if (cancel.isCancelled) return;

      if (job.status == JobStatus.failed) {
        final err = job.error ?? const ApiException('internal');
        _set(FlowFailed(err.message, code: err.code));
        return;
      }
      final report = job.result;
      if (report == null) {
        _set(const FlowFailed('The server finished without a report. Please try again.'));
        return;
      }

      _set(const FlowSaving());
      String? savedVideo;
      String? saveError;
      if (repo != null) {
        try {
          savedVideo = await repo.save(id: job.id, report: report, videoPath: request.videoPath);
        } on FirebaseException catch (e) {
          saveError = e.message ?? e.code;
        } catch (e) {
          saveError = '$e';
        }
      }
      _set(FlowDone(ResultArgs(
        report: report,
        videoPath: savedVideo ?? request.videoPath,
        analysisId: job.id,
        createdAt: DateTime.now(),
        saveError: saveError,
      )));
    } on ApiException catch (e) {
      if (e.code == 'cancelled') return;
      _set(FlowFailed(e.message, code: e.code));
    }
  }

  Future<void> retry() async {
    final last = _last;
    if (last != null) await start(last);
  }

  /// Stops uploading/polling and asks the server to drop the job.
  Future<void> cancel() async {
    _cancel?.cancel();
    final id = _jobId;
    final api = ref.read(apiClientProvider);
    _set(const FlowIdle());
    if (id != null) {
      try {
        await api.deleteAnalysis(id);
      } on ApiException {
        // Best effort; the server expires jobs on its own.
      }
    }
  }
}

final analysisFlowProvider =
    NotifierProvider.autoDispose<AnalysisFlowController, AnalysisFlowState>(
  AnalysisFlowController.new,
);
