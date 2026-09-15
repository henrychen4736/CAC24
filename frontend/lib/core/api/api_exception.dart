import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';

/// An error from the analysis service, normalized to the contract's error
/// codes (docs/ARCHITECTURE.md §6) plus a few client-side ones
/// (`network`, `timeout`, `cancelled`, `unknown`).
class ApiException implements Exception {
  const ApiException(this.code, {this.serverMessage, this.statusCode});

  final String code;

  /// User-facing message written by the server, when it sent one.
  final String? serverMessage;
  final int? statusCode;

  /// What to show the user: the server's message if present, else our copy.
  String get message {
    final m = serverMessage?.trim();
    return (m != null && m.isNotEmpty) ? m : friendlyMessageFor(code);
  }

  static String friendlyMessageFor(String code) => switch (code) {
        'video_unreadable' =>
          "We couldn't read that video. Try exporting it again as an MP4 or MOV file.",
        'video_too_long' =>
          'That video is too long. Trim it to the strokes you want analyzed (under a minute).',
        'video_too_large' =>
          'That file is too large to upload. Trim it or record at a lower resolution.',
        'unsupported_format' => "That file type isn't supported. Use an MP4 or MOV video.",
        'no_player_detected' =>
          "We couldn't find a player in the video. Make sure your whole body is in frame "
              'and well lit.',
        'internal' => 'Something went wrong on the analysis server. Please try again.',
        'unauthorized' => 'Your session has expired. Please sign in again.',
        'not_found' => 'That analysis is no longer available on the server.',
        'invalid_request' => 'The server rejected the request. Please update the app and try again.',
        'network' =>
          "Can't reach the analysis server. Check your connection and the server URL in Profile.",
        'timeout' => 'The analysis server is taking too long to respond. Please try again.',
        'cancelled' => 'Analysis cancelled.',
        _ => 'Something went wrong. Please try again.',
      };

  static String codeForStatus(int? status) {
    if (status == null) return 'unknown';
    return switch (status) {
      401 || 403 => 'unauthorized',
      404 => 'not_found',
      413 => 'video_too_large',
      415 => 'unsupported_format',
      422 || 400 => 'invalid_request',
      >= 500 => 'internal',
      _ => 'unknown',
    };
  }

  /// Builds an exception from an error body `{"error": {"code", "message"}}`
  /// (also tolerating FastAPI's default `{"detail": ...}`).
  factory ApiException.fromResponse(int? statusCode, Object? data) {
    Object? body = data;
    if (body is String && body.isNotEmpty) {
      try {
        body = jsonDecode(body);
      } on FormatException {
        body = null;
      }
    }
    String? code;
    String? message;
    if (body is Map) {
      final err = body['error'];
      if (err is Map) {
        code = err['code'] is String ? err['code'] as String : null;
        message = err['message'] is String ? err['message'] as String : null;
      } else if (body['detail'] is String) {
        message = body['detail'] as String;
      }
    }
    return ApiException(
      code ?? codeForStatus(statusCode),
      serverMessage: message,
      statusCode: statusCode,
    );
  }

  factory ApiException.fromDio(DioException e) => switch (e.type) {
        DioExceptionType.badResponse =>
          ApiException.fromResponse(e.response?.statusCode, e.response?.data),
        DioExceptionType.connectionError || DioExceptionType.badCertificate =>
          const ApiException('network'),
        DioExceptionType.cancel => const ApiException('cancelled'),
        DioExceptionType.connectionTimeout ||
        DioExceptionType.sendTimeout ||
        DioExceptionType.receiveTimeout =>
          const ApiException('timeout'),
        // `unknown`, plus any type added by future dio versions (e.g. transformTimeout).
        _ when e.error is SocketException || e.error is HttpException => const ApiException('network'),
        _ when e.type.name.toLowerCase().contains('timeout') => const ApiException('timeout'),
        _ => const ApiException('unknown'),
      };

  @override
  String toString() => 'ApiException($code, $statusCode): $message';
}
