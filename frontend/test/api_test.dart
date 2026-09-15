import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tennis_analyze/core/api/api_client.dart';
import 'package:tennis_analyze/core/api/api_exception.dart';

void main() {
  group('ApiException.fromResponse', () {
    test('uses the contract error body and shows the server message', () {
      final e = ApiException.fromResponse(413, {
        'error': {'code': 'video_too_large', 'message': 'Videos must be under 300 MB.'},
      });
      expect(e.code, 'video_too_large');
      expect(e.statusCode, 413);
      expect(e.message, 'Videos must be under 300 MB.');
    });

    test('falls back to our copy when the server sends no message', () {
      final e = ApiException.fromResponse(415, {
        'error': {'code': 'unsupported_format'},
      });
      expect(e.message, ApiException.friendlyMessageFor('unsupported_format'));
    });

    test('maps HTTP status to a code when the body has none', () {
      expect(ApiException.fromResponse(401, null).code, 'unauthorized');
      expect(ApiException.fromResponse(404, '').code, 'not_found');
      expect(ApiException.fromResponse(413, 'Request Entity Too Large').code, 'video_too_large');
      expect(ApiException.fromResponse(415, null).code, 'unsupported_format');
      expect(ApiException.fromResponse(422, null).code, 'invalid_request');
      expect(ApiException.fromResponse(503, null).code, 'internal');
      expect(ApiException.fromResponse(418, null).code, 'unknown');
    });

    test('decodes JSON error bodies delivered as strings', () {
      final e = ApiException.fromResponse(404, '{"error":{"code":"not_found","message":"Gone."}}');
      expect(e.code, 'not_found');
      expect(e.message, 'Gone.');
    });

    test("tolerates FastAPI's default {detail} body", () {
      final e = ApiException.fromResponse(422, {'detail': 'file is required'});
      expect(e.code, 'invalid_request');
      expect(e.message, 'file is required');
    });

    test('every contract code has friendly copy', () {
      const codes = [
        'video_unreadable',
        'video_too_long',
        'video_too_large',
        'unsupported_format',
        'no_player_detected',
        'internal',
        'unauthorized',
        'not_found',
        'invalid_request',
      ];
      final generic = ApiException.friendlyMessageFor('something_else');
      for (final c in codes) {
        expect(ApiException.friendlyMessageFor(c), isNot(generic), reason: c);
      }
    });
  });

  group('ApiException.fromDio', () {
    final req = RequestOptions(path: '/v1/analyses');

    test('network and timeout failures', () {
      expect(
        ApiException.fromDio(DioException.connectionError(requestOptions: req, reason: 'x')).code,
        'network',
      );
      expect(
        ApiException.fromDio(DioException(requestOptions: req, type: DioExceptionType.receiveTimeout))
            .code,
        'timeout',
      );
      expect(
        ApiException.fromDio(DioException(requestOptions: req, type: DioExceptionType.cancel)).code,
        'cancelled',
      );
    });

    test('bad responses use the body', () {
      final e = ApiException.fromDio(
        DioException(
          requestOptions: req,
          type: DioExceptionType.badResponse,
          response: Response(
            requestOptions: req,
            statusCode: 401,
            data: {
              'error': {'code': 'unauthorized', 'message': 'Sign in again.'},
            },
          ),
        ),
      );
      expect(e.code, 'unauthorized');
      expect(e.message, 'Sign in again.');
    });
  });

  group('AnalysisJob.fromJson', () {
    test('failed job carries the error', () {
      final job = AnalysisJob.fromJson({
        'id': 'abc',
        'status': 'failed',
        'stage': 'pose',
        'progress': 0.4,
        'created_at': '2026-09-10T18:30:00Z',
        'error': {'code': 'no_player_detected', 'message': 'No player found.'},
        'result': null,
      });
      expect(job.status, JobStatus.failed);
      expect(job.status.isTerminal, isTrue);
      expect(job.error!.code, 'no_player_detected');
      expect(job.error!.message, 'No player found.');
      expect(job.createdAt, DateTime.utc(2026, 9, 10, 18, 30));
      expect(job.result, isNull);
    });

    test('processing job clamps progress', () {
      final job = AnalysisJob.fromJson({'id': 'x', 'status': 'processing', 'progress': 1.7});
      expect(job.status.isTerminal, isFalse);
      expect(job.progress, 1.0);
    });

    test('done job parses the report', () {
      final job = AnalysisJob.fromJson({
        'id': 'x',
        'status': 'done',
        'result': {
          'strokes': [],
          'summary': {'overall_score': null},
        },
      });
      expect(job.result, isNotNull);
      expect(job.result!.strokes, isEmpty);
    });
  });

  test('HealthInfo parses the health contract', () {
    final h = HealthInfo.fromJson({
      'status': 'ok',
      'version': '2.0.0',
      'pose_model': 'mediapipe-pose-landmarker-heavy',
      'classifier': 'heuristic',
      'reference': 'default',
      'auth_required': true,
    });
    expect(h.isOk, isTrue);
    expect(h.poseModel, 'mediapipe-pose-landmarker-heavy');
    expect(h.authRequired, isTrue);
  });

  test('videoMimeType', () {
    expect(videoMimeType('clip.MP4'), 'video/mp4');
    expect(videoMimeType('IMG_0001.MOV'), 'video/quicktime');
    expect(videoMimeType('noext'), 'application/octet-stream');
  });
}
