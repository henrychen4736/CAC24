import 'dart:async';
import 'dart:math' as math;

import 'package:dio/dio.dart';

import '../../features/results/models/report.dart';
import 'api_exception.dart';

typedef TokenProvider = Future<String?> Function();

/// `GET /v1/health`.
class HealthInfo {
  const HealthInfo({
    required this.status,
    this.version,
    this.poseModel,
    this.classifier,
    this.reference,
    this.authRequired = false,
  });

  final String status;
  final String? version;
  final String? poseModel;
  final String? classifier;
  final String? reference;
  final bool authRequired;

  bool get isOk => status == 'ok';

  factory HealthInfo.fromJson(Map<String, dynamic> json) => HealthInfo(
        status: json['status'] as String? ?? 'unknown',
        version: json['version'] as String?,
        poseModel: json['pose_model'] as String?,
        classifier: json['classifier'] as String?,
        reference: json['reference'] as String?,
        authRequired: json['auth_required'] as bool? ?? false,
      );
}

enum JobStatus {
  queued,
  processing,
  done,
  failed;

  static JobStatus parse(String? v) =>
      JobStatus.values.firstWhere((s) => s.name == v, orElse: () => JobStatus.queued);

  bool get isTerminal => this == JobStatus.done || this == JobStatus.failed;
}

class AnalysisJob {
  const AnalysisJob({
    required this.id,
    required this.status,
    required this.stage,
    required this.progress,
    this.createdAt,
    this.error,
    this.result,
  });

  final String id;
  final JobStatus status;
  final String stage;
  final double progress;
  final DateTime? createdAt;
  final ApiException? error;
  final AnalysisReport? result;

  factory AnalysisJob.fromJson(Map<String, dynamic> json) {
    final err = json['error'];
    final result = json['result'];
    return AnalysisJob(
      id: json['id'] as String? ?? '',
      status: JobStatus.parse(json['status'] as String?),
      stage: json['stage'] as String? ?? 'queued',
      progress: (json['progress'] as num?)?.toDouble().clamp(0.0, 1.0) ?? 0,
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? ''),
      error: err is Map
          ? ApiException(
              err['code'] as String? ?? 'internal',
              serverMessage: err['message'] as String?,
            )
          : null,
      result: result is Map ? AnalysisReport.fromJson(result.cast<String, dynamic>()) : null,
    );
  }
}

/// Typed client for the analysis service (docs/ARCHITECTURE.md §6).
/// Every method throws [ApiException] on failure.
class TennisApi {
  TennisApi({required String baseUrl, TokenProvider? tokenProvider, Dio? dio})
      : _dio = dio ?? Dio() {
    _dio.options
      ..baseUrl = baseUrl
      ..connectTimeout = const Duration(seconds: 10)
      ..receiveTimeout = const Duration(seconds: 60)
      ..sendTimeout = null; // uploads can be slow on mobile networks
    if (tokenProvider != null) {
      _dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) async {
            try {
              final token = await tokenProvider();
              if (token != null) options.headers['Authorization'] = 'Bearer $token';
            } catch (_) {
              // Proceed without a token; the server answers 401 if it needs one.
            }
            handler.next(options);
          },
        ),
      );
    }
  }

  final Dio _dio;

  String get baseUrl => _dio.options.baseUrl;

  Future<T> _guard<T>(Future<T> Function() call) async {
    try {
      return await call();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<HealthInfo> health() => _guard(() async {
        final res = await _dio.get<Map<String, dynamic>>(
          '/v1/health',
          options: Options(receiveTimeout: const Duration(seconds: 10)),
        );
        return HealthInfo.fromJson(res.data ?? const {});
      });

  /// Uploads a video and starts an analysis job. [onUploadProgress] receives
  /// values in 0..1.
  Future<AnalysisJob> createAnalysis({
    required String filePath,
    String strokeHint = 'auto',
    String handedness = 'auto',
    void Function(double progress)? onUploadProgress,
    CancelToken? cancelToken,
  }) =>
      _guard(() async {
        final fileName = filePath.split(RegExp(r'[\\/]')).last;
        final form = FormData.fromMap({
          'file': await MultipartFile.fromFile(
            filePath,
            filename: fileName,
            contentType: DioMediaType.parse(videoMimeType(fileName)),
          ),
          'stroke_hint': strokeHint,
          'handedness': handedness,
        });
        final res = await _dio.post<Map<String, dynamic>>(
          '/v1/analyses',
          data: form,
          cancelToken: cancelToken,
          onSendProgress: (sent, total) {
            if (total > 0) onUploadProgress?.call(sent / total);
          },
        );
        return AnalysisJob.fromJson(res.data ?? const {});
      });

  Future<AnalysisJob> getAnalysis(String id, {CancelToken? cancelToken}) => _guard(() async {
        final res = await _dio.get<Map<String, dynamic>>(
          '/v1/analyses/$id',
          cancelToken: cancelToken,
        );
        return AnalysisJob.fromJson(res.data ?? const {});
      });

  Future<void> deleteAnalysis(String id) => _guard(() async {
        await _dio.delete<void>('/v1/analyses/$id');
      });

  /// Polls a job until it is done or failed, emitting every update. Backs off
  /// from 1 s to 4 s between polls; transient network errors are retried a
  /// few times before giving up.
  Stream<AnalysisJob> watchAnalysis(
    String id, {
    Duration timeout = const Duration(minutes: 10),
    CancelToken? cancelToken,
  }) async* {
    final deadline = DateTime.now().add(timeout);
    var delay = const Duration(seconds: 1);
    var transientFailures = 0;
    while (true) {
      if (cancelToken?.isCancelled ?? false) throw const ApiException('cancelled');
      try {
        final job = await getAnalysis(id, cancelToken: cancelToken);
        transientFailures = 0;
        yield job;
        if (job.status.isTerminal) return;
      } on ApiException catch (e) {
        final transient = e.code == 'network' || e.code == 'timeout';
        if (!transient || ++transientFailures > 3) rethrow;
      }
      if (DateTime.now().isAfter(deadline)) throw const ApiException('timeout');
      await Future<void>.delayed(delay);
      delay = Duration(milliseconds: math.min(4000, (delay.inMilliseconds * 1.5).round()));
    }
  }
}

String videoMimeType(String fileName) {
  final ext = fileName.contains('.') ? fileName.split('.').last.toLowerCase() : '';
  return switch (ext) {
    'mp4' => 'video/mp4',
    'mov' || 'qt' => 'video/quicktime',
    'm4v' => 'video/x-m4v',
    '3gp' => 'video/3gpp',
    'webm' => 'video/webm',
    'mkv' => 'video/x-matroska',
    'avi' => 'video/x-msvideo',
    _ => 'application/octet-stream',
  };
}
