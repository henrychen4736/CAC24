import 'dart:math' as math;

import 'package:flutter/rendering.dart';

import '../models/report.dart';

/// Draws the player's skeleton for the current playback time on top of the
/// video. Keypoints are normalized to the displayed video frame, so they are
/// mapped into the letterboxed rectangle the video occupies inside the canvas.
class PoseOverlayPainter extends CustomPainter {
  PoseOverlayPainter({
    required this.track,
    required this.timeSeconds,
    required this.videoAspectRatio,
    required this.boneColor,
    required this.jointColor,
    required this.highlightColor,
    this.highlightJoints = const {},
    super.repaint,
  });

  final PoseTrack track;
  final double Function() timeSeconds;
  final double videoAspectRatio;
  final Color boneColor;
  final Color jointColor;
  final Color highlightColor;
  final Set<String> highlightJoints;

  /// The rectangle a video with [aspectRatio] (width / height) occupies when
  /// fitted ("contain") into [canvas] and centered.
  static Rect videoRect(Size canvas, double aspectRatio) {
    if (canvas.isEmpty || aspectRatio <= 0) return Offset.zero & canvas;
    final canvasAspect = canvas.width / canvas.height;
    if (canvasAspect > aspectRatio) {
      final w = canvas.height * aspectRatio;
      return Rect.fromLTWH((canvas.width - w) / 2, 0, w, canvas.height);
    }
    final h = canvas.width / aspectRatio;
    return Rect.fromLTWH(0, (canvas.height - h) / 2, canvas.width, h);
  }

  /// Canvas position of joint [j] in [frame], or null if it is missing.
  static Offset? mapPoint(List<double> frame, int j, Rect rect) {
    if (j < 0 || 2 * j + 1 >= frame.length) return null;
    final x = frame[2 * j], y = frame[2 * j + 1];
    if (x.isNaN || y.isNaN) return null;
    return Offset(rect.left + x * rect.width, rect.top + y * rect.height);
  }

  @override
  void paint(Canvas canvas, Size size) {
    final frame = track.frameAt(timeSeconds());
    if (frame == null) return;
    final rect = videoRect(size, videoAspectRatio);
    final points = [
      for (var j = 0; j < track.joints.length; j++) mapPoint(frame, j, rect),
    ];
    final highlighted = <int>{
      for (final name in highlightJoints)
        if (track.indexOf(name) >= 0) track.indexOf(name),
    };

    final unit = rect.height;
    final boneWidth = (unit * 0.008).clamp(2.0, 5.0);
    final shadow = Paint()
      ..color = const Color(0x66000000)
      ..strokeWidth = boneWidth + 2
      ..strokeCap = StrokeCap.round;
    final bone = Paint()
      ..strokeWidth = boneWidth
      ..strokeCap = StrokeCap.round;

    for (final (a, b) in track.edges) {
      if (a >= points.length || b >= points.length) continue;
      final pa = points[a], pb = points[b];
      if (pa == null || pb == null) continue;
      final hot = highlighted.contains(a) && highlighted.contains(b);
      canvas.drawLine(pa, pb, shadow);
      canvas.drawLine(
        pa,
        pb,
        bone
          ..color = hot ? highlightColor : boneColor
          ..strokeWidth = hot ? boneWidth * 1.6 : boneWidth,
      );
    }

    final r = math.max(2.5, boneWidth * 0.9);
    final fill = Paint();
    for (var j = 0; j < points.length; j++) {
      final p = points[j];
      if (p == null) continue;
      if (highlighted.contains(j)) {
        canvas.drawCircle(p, r * 3, fill..color = highlightColor.withValues(alpha: 0.3));
        canvas.drawCircle(p, r * 1.6, fill..color = highlightColor);
      } else {
        canvas.drawCircle(p, r + 1, fill..color = const Color(0x66000000));
        canvas.drawCircle(p, r, fill..color = jointColor);
      }
    }
  }

  @override
  bool shouldRepaint(PoseOverlayPainter old) =>
      old.track != track ||
      old.videoAspectRatio != videoAspectRatio ||
      old.boneColor != boneColor ||
      old.highlightColor != highlightColor ||
      !_sameSet(old.highlightJoints, highlightJoints);
}

bool _sameSet<T>(Set<T> a, Set<T> b) => a.length == b.length && a.containsAll(b);
