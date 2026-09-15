import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../../../app/theme.dart';
import '../../../core/format.dart';
import '../models/report.dart';
import 'playback.dart';
import 'pose_overlay_painter.dart';

/// Video (or a plain backdrop when there is no video) with the skeleton
/// overlay, plus transport controls and a timeline with stroke markers.
class PosePlayer extends StatelessWidget {
  const PosePlayer({
    super.key,
    required this.playback,
    required this.report,
    required this.showOverlay,
    required this.onToggleOverlay,
    this.videoController,
    this.highlightJoints = const {},
    this.selectedStroke,
    this.onStrokeMarkerTap,
    this.maxHeight,
  });

  final Playback playback;
  final AnalysisReport report;
  final VideoPlayerController? videoController;
  final bool showOverlay;
  final VoidCallback onToggleOverlay;
  final Set<String> highlightJoints;
  final int? selectedStroke;
  final ValueChanged<Stroke>? onStrokeMarkerTap;
  final double? maxHeight;

  double get _aspect {
    final c = videoController;
    if (c != null && c.value.isInitialized && c.value.aspectRatio > 0) return c.value.aspectRatio;
    return report.video.aspectRatio;
  }

  @override
  Widget build(BuildContext context) {
    final palette = context.scores;
    final track = report.poseTrack;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth;
            var height = width / _aspect;
            if (maxHeight != null && height > maxHeight!) height = maxHeight!;
            return GestureDetector(
              onTap: playback.togglePlay,
              child: Container(
                width: width,
                height: height,
                color: Colors.black,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    if (videoController != null && videoController!.value.isInitialized)
                      Center(
                        child: AspectRatio(
                          aspectRatio: _aspect,
                          child: VideoPlayer(videoController!),
                        ),
                      )
                    else
                      _NoVideoBackdrop(aspectRatio: _aspect),
                    if (showOverlay && track != null)
                      CustomPaint(
                        painter: PoseOverlayPainter(
                          track: track,
                          timeSeconds: () => playback.positionSeconds,
                          videoAspectRatio: _aspect,
                          boneColor: palette.bone,
                          jointColor: palette.joint,
                          highlightColor: palette.highlight,
                          highlightJoints: highlightJoints,
                          repaint: playback,
                        ),
                      ),
                    Positioned(
                      right: Insets.sm,
                      top: Insets.sm,
                      child: _OverlayButton(
                        icon: showOverlay ? Icons.accessibility_new : Icons.accessibility_new_outlined,
                        tooltip: showOverlay ? 'Hide skeleton' : 'Show skeleton',
                        active: showOverlay,
                        onTap: onToggleOverlay,
                      ),
                    ),
                    ListenableBuilder(
                      listenable: playback,
                      builder: (context, _) => AnimatedOpacity(
                        opacity: playback.isPlaying ? 0 : 1,
                        duration: const Duration(milliseconds: 200),
                        child: IgnorePointer(
                          child: Center(
                            child: Container(
                              padding: const EdgeInsets.all(Insets.md),
                              decoration: const BoxDecoration(
                                color: Color(0x88000000),
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(Icons.play_arrow_rounded, color: Colors.white, size: 36),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
        _Controls(
          playback: playback,
          strokes: report.strokes,
          selectedStroke: selectedStroke,
          onStrokeMarkerTap: onStrokeMarkerTap,
        ),
      ],
    );
  }
}

class _NoVideoBackdrop extends StatelessWidget {
  const _NoVideoBackdrop({required this.aspectRatio});

  final double aspectRatio;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: AspectRatio(
        aspectRatio: aspectRatio,
        child: DecoratedBox(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFF12321F), Color(0xFF1B5E3B)],
            ),
          ),
          child: Align(
            alignment: Alignment.bottomLeft,
            child: Padding(
              padding: const EdgeInsets.all(Insets.sm),
              child: Text(
                'Skeleton replay — video not on this device',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(color: Colors.white70),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _OverlayButton extends StatelessWidget {
  const _OverlayButton({
    required this.icon,
    required this.tooltip,
    required this.active,
    required this.onTap,
  });

  final IconData icon;
  final String tooltip;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Material(
        color: active ? context.scores.highlight : const Color(0x88000000),
        shape: const CircleBorder(),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(Insets.sm),
            child: Icon(icon, size: 20, color: active ? Colors.black : Colors.white),
          ),
        ),
      ),
    );
  }
}

class _Controls extends StatelessWidget {
  const _Controls({
    required this.playback,
    required this.strokes,
    required this.selectedStroke,
    required this.onStrokeMarkerTap,
  });

  final Playback playback;
  final List<Stroke> strokes;
  final int? selectedStroke;
  final ValueChanged<Stroke>? onStrokeMarkerTap;

  static const _speeds = [1.0, 0.5, 0.25];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ListenableBuilder(
      listenable: playback,
      builder: (context, _) {
        final durationS = playback.duration.inMicroseconds / 1e6;
        return Padding(
          padding: const EdgeInsets.fromLTRB(Insets.xs, Insets.xs, Insets.sm, 0),
          child: Row(
            children: [
              IconButton(
                tooltip: playback.isPlaying ? 'Pause' : 'Play',
                icon: Icon(playback.isPlaying ? Icons.pause_rounded : Icons.play_arrow_rounded),
                onPressed: playback.togglePlay,
              ),
              Expanded(
                child: Timeline(
                  position: playback.positionSeconds,
                  duration: durationS,
                  strokes: strokes,
                  selectedStroke: selectedStroke,
                  onSeek: playback.seekSeconds,
                  onStrokeTap: onStrokeMarkerTap,
                ),
              ),
              const SizedBox(width: Insets.sm),
              Text(
                formatTimestamp(playback.positionSeconds),
                style: theme.textTheme.labelMedium?.copyWith(
                  fontFeatures: const [FontFeature.tabularFigures()],
                ),
              ),
              TextButton(
                style: TextButton.styleFrom(
                  minimumSize: const Size(48, 36),
                  padding: const EdgeInsets.symmetric(horizontal: Insets.sm),
                ),
                onPressed: () {
                  final i = _speeds.indexOf(playback.speed);
                  playback.setSpeed(_speeds[(i + 1) % _speeds.length]);
                },
                child: Text('${_fmtSpeed(playback.speed)}×'),
              ),
            ],
          ),
        );
      },
    );
  }

  static String _fmtSpeed(double s) => s == s.roundToDouble() ? s.toStringAsFixed(0) : '$s';
}

/// Scrubbable timeline with a marker at each stroke's contact moment.
class Timeline extends StatelessWidget {
  const Timeline({
    super.key,
    required this.position,
    required this.duration,
    required this.strokes,
    required this.onSeek,
    this.selectedStroke,
    this.onStrokeTap,
  });

  final double position;
  final double duration;
  final List<Stroke> strokes;
  final int? selectedStroke;
  final ValueChanged<double> onSeek;
  final ValueChanged<Stroke>? onStrokeTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final palette = context.scores;
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        double toSeconds(double dx) => duration <= 0 ? 0 : (dx / width).clamp(0.0, 1.0) * duration;

        void onTapAt(double dx) {
          // Snap to a stroke marker when the tap lands close to one.
          if (onStrokeTap != null && duration > 0) {
            for (final s in strokes) {
              if ((s.contactS / duration * width - dx).abs() < 12) {
                onStrokeTap!(s);
                return;
              }
            }
          }
          onSeek(toSeconds(dx));
        }

        return GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTapDown: (d) => onTapAt(d.localPosition.dx),
          onHorizontalDragUpdate: (d) => onSeek(toSeconds(d.localPosition.dx)),
          child: SizedBox(
            height: 36,
            child: CustomPaint(
              painter: _TimelinePainter(
                progress: duration <= 0 ? 0 : (position / duration).clamp(0.0, 1.0),
                markers: [
                  for (final s in strokes)
                    (
                      duration <= 0 ? 0.0 : (s.contactS / duration).clamp(0.0, 1.0),
                      palette.forScore(s.score),
                      s.index == selectedStroke,
                    ),
                ],
                track: scheme.surfaceContainerHighest,
                played: scheme.primary,
                thumb: scheme.primary,
                selectedRing: scheme.onSurface,
              ),
            ),
          ),
        );
      },
    );
  }
}

class _TimelinePainter extends CustomPainter {
  _TimelinePainter({
    required this.progress,
    required this.markers,
    required this.track,
    required this.played,
    required this.thumb,
    required this.selectedRing,
  });

  final double progress;
  final List<(double, Color, bool)> markers;
  final Color track;
  final Color played;
  final Color thumb;
  final Color selectedRing;

  @override
  void paint(Canvas canvas, Size size) {
    final cy = size.height / 2;
    final p = Paint()
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(0, cy), Offset(size.width, cy), p..color = track);
    canvas.drawLine(Offset(0, cy), Offset(size.width * progress, cy), p..color = played);
    for (final (x, color, selected) in markers) {
      final c = Offset(size.width * x, cy);
      if (selected) {
        canvas.drawCircle(
          c,
          8,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2
            ..color = selectedRing,
        );
      }
      canvas.drawCircle(c, 5, Paint()..color = color);
    }
    canvas.drawCircle(Offset(size.width * progress, cy), 7, Paint()..color = thumb);
  }

  @override
  bool shouldRepaint(_TimelinePainter old) =>
      old.progress != progress || old.markers.length != markers.length || old.track != track ||
      !_sameMarkers(old.markers, markers);

  static bool _sameMarkers(List<(double, Color, bool)> a, List<(double, Color, bool)> b) {
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }
}
