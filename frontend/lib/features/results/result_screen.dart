import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart' show Ticker;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:video_player/video_player.dart';

import '../../app/theme.dart';
import '../../core/format.dart';
import '../../core/widgets/common.dart';
import '../analyze/filming_tips.dart';
import 'models/report.dart';
import 'result_args.dart';
import 'widgets/metric_widgets.dart';
import 'widgets/playback.dart';
import 'widgets/pose_player.dart';

/// Loads a result by id (`sample` or a saved analysis) and shows it.
class ResultLoaderScreen extends ConsumerWidget {
  const ResultLoaderScreen({super.key, required this.id});

  final String id;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final args = ref.watch(resultArgsProvider(id));
    return args.when(
      data: (a) => ResultScreen(args: a),
      loading: () => Scaffold(
        appBar: AppBar(),
        body: const Center(child: CircularProgressIndicator()),
      ),
      error: (e, _) => Scaffold(
        appBar: AppBar(),
        body: EmptyState(
          icon: Icons.error_outline_rounded,
          title: "Couldn't open this analysis",
          message: e is StateError ? e.message : '$e',
        ),
      ),
    );
  }
}

class ResultScreen extends StatefulWidget {
  const ResultScreen({super.key, required this.args});

  final ResultArgs args;

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> with SingleTickerProviderStateMixin {
  VideoPlayerController? _video;
  Playback? _playback;
  late final Ticker _ticker;

  bool _showOverlay = true;
  int? _strokeIndex;
  String? _metricId;
  final _dismissed = <String>{};
  final _metricKeys = <String, GlobalKey>{};

  AnalysisReport get _report => widget.args.report;

  Stroke? get _stroke {
    final i = _strokeIndex;
    if (i == null) return null;
    for (final s in _report.strokes) {
      if (s.index == i) return s;
    }
    return null;
  }

  Metric? get _metric {
    final s = _stroke;
    if (s == null || _metricId == null) return null;
    for (final m in s.metrics) {
      if (m.id == _metricId) return m;
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    _ticker = createTicker((elapsed) => _playback?.tick(elapsed));
    if (_report.strokes.isNotEmpty) _strokeIndex = _report.strokes.first.index;
    _initPlayback();
  }

  Future<void> _initPlayback() async {
    VideoPlayerController? video;
    final path = widget.args.videoPath;
    if (path != null && File(path).existsSync()) {
      final controller = VideoPlayerController.file(File(path));
      try {
        await controller.initialize();
        await controller.setLooping(true);
        await controller.setVolume(0);
        video = controller;
      } catch (_) {
        // Unplayable or missing codec: fall back to the skeleton-only replay.
        await controller.dispose();
      }
    }
    _video = video;
    final Playback playback = video != null ? VideoPlayback(video) : _synthetic();
    if (!mounted) {
      playback.dispose();
      await _video?.dispose();
      return;
    }
    setState(() => _playback = playback);
    _ticker.start();
    final s = _stroke;
    if (s != null) await playback.seekSeconds(s.startS);
  }

  SyntheticPlayback _synthetic() {
    final track = _report.poseTrack;
    var seconds = _report.video.durationS;
    if (track != null && track.fps > 0) {
      final trackSeconds = track.frames.length / track.fps;
      if (seconds <= 0 || trackSeconds < seconds) seconds = trackSeconds;
    }
    return SyntheticPlayback(Duration(milliseconds: (seconds * 1000).round()));
  }

  @override
  void dispose() {
    _ticker.dispose();
    _playback?.dispose();
    _video?.dispose();
    super.dispose();
  }

  void _selectStroke(Stroke stroke) {
    setState(() {
      _strokeIndex = stroke.index;
      _metricId = null;
    });
    _playback?.pause();
    _playback?.seekSeconds(stroke.contactS);
  }

  void _selectMetric(Stroke stroke, Metric metric, {bool scroll = false}) {
    final deselect = _strokeIndex == stroke.index && _metricId == metric.id && !scroll;
    setState(() {
      _strokeIndex = stroke.index;
      _metricId = deselect ? null : metric.id;
    });
    if (deselect) return;
    _playback?.pause();
    _playback?.seekSeconds(stroke.momentFor(metric));
    if (scroll) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final ctx = _metricKeys[metric.id]?.currentContext;
        if (ctx != null) {
          Scrollable.ensureVisible(ctx, duration: const Duration(milliseconds: 350), alignment: 0.1);
        }
      });
    }
  }

  void _openPriority(Priority p) {
    Stroke? stroke;
    for (final s in _report.strokes) {
      if (p.strokeIndices.contains(s.index) || (p.strokeIndices.isEmpty && s.type == p.strokeType)) {
        stroke = s;
        break;
      }
    }
    if (stroke == null) return;
    for (final m in stroke.metrics) {
      if (m.id == p.metricId) {
        _selectMetric(stroke, m, scroll: true);
        return;
      }
    }
    _selectStroke(stroke);
  }

  @override
  Widget build(BuildContext context) {
    final args = widget.args;
    final playback = _playback;
    final height = MediaQuery.sizeOf(context).height;
    return Scaffold(
      appBar: AppBar(
        title: Text(args.isSample ? 'Sample analysis' : 'Your analysis'),
        bottom: args.createdAt == null
            ? null
            : PreferredSize(
                preferredSize: const Size.fromHeight(20),
                child: Padding(
                  padding: const EdgeInsets.only(left: Insets.lg, bottom: Insets.xs),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      formatDate(args.createdAt!),
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ),
              ),
      ),
      body: Column(
        children: [
          if (playback == null)
            SizedBox(
              height: MediaQuery.sizeOf(context).width / _report.video.aspectRatio,
              child: const ColoredBox(
                color: Colors.black,
                child: Center(child: CircularProgressIndicator()),
              ),
            )
          else
            PosePlayer(
              playback: playback,
              report: _report,
              videoController: _video,
              showOverlay: _showOverlay,
              onToggleOverlay: () => setState(() => _showOverlay = !_showOverlay),
              highlightJoints: _metric?.joints.toSet() ?? const {},
              selectedStroke: _strokeIndex,
              onStrokeMarkerTap: _selectStroke,
              maxHeight: height * 0.42,
            ),
          const Divider(height: 1),
          Expanded(child: _details(context)),
        ],
      ),
    );
  }

  Widget _details(BuildContext context) {
    final theme = Theme.of(context);
    final palette = context.scores;
    final report = _report;
    final args = widget.args;
    final stroke = _stroke;
    final warnings = report.quality.warnings.where((w) => !_dismissed.contains(w.code)).toList();

    return ListView(
      padding: const EdgeInsets.fromLTRB(Insets.lg, Insets.lg, Insets.lg, Insets.xxl),
      children: [
        if (args.saveError != null) ...[
          InfoBanner(
            icon: Icons.cloud_off_rounded,
            color: palette.needsWork,
            child: Text("Couldn't save to your history: ${args.saveError}"),
          ),
          const SizedBox(height: Insets.sm),
        ],
        if (args.isSample) ...[
          InfoBanner(
            icon: Icons.auto_awesome_rounded,
            color: theme.colorScheme.primary,
            child: const Text(
              'This is a sample analysis. Record your own swing to get personal feedback.',
            ),
          ),
          const SizedBox(height: Insets.sm),
        ],
        for (final w in warnings) ...[
          InfoBanner(
            icon: Icons.warning_amber_rounded,
            color: palette.fair,
            onClose: () => setState(() => _dismissed.add(w.code)),
            child: Text(w.message.isEmpty ? humanize(w.code) : w.message),
          ),
          const SizedBox(height: Insets.sm),
        ],
        _SummaryCard(report: report),
        if (report.strokes.isEmpty)
          EmptyState(
            icon: Icons.sports_tennis_rounded,
            title: 'No swings detected',
            message: 'We found you in the video but no swings. Make sure the whole stroke is in '
                'the clip and the camera is steady.',
            action: OutlinedButton.icon(
              onPressed: () => showFilmingTips(context),
              icon: const Icon(Icons.videocam_outlined),
              label: const Text('How to film'),
            ),
          )
        else ...[
          if (report.summary.priorities.isNotEmpty) ...[
            const SectionHeader('Top priorities'),
            for (final (i, p) in report.summary.priorities.indexed) ...[
              PriorityCard(rank: i + 1, priority: p, onTap: () => _openPriority(p)),
              const SizedBox(height: Insets.sm),
            ],
          ],
          const SectionHeader('Strokes'),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final s in report.strokes)
                  Padding(
                    padding: const EdgeInsets.only(right: Insets.sm),
                    child: ChoiceChip(
                      avatar: CircleAvatar(
                        backgroundColor: palette.forScore(s.score),
                        child: Text(
                          s.score?.toString() ?? '–',
                          style: const TextStyle(fontSize: 10, color: Colors.white, fontWeight: FontWeight.w700),
                        ),
                      ),
                      label: Text('${s.index + 1} · ${strokeTypeShortLabel(s.type)}'),
                      selected: s.index == _strokeIndex,
                      showCheckmark: false,
                      onSelected: (_) => _selectStroke(s),
                    ),
                  ),
              ],
            ),
          ),
          if (stroke != null) ..._strokeDetails(context, stroke),
        ],
        const SizedBox(height: Insets.xl),
        Text(
          [
            if (report.models.pose != null) 'Pose: ${report.models.pose}',
            if (report.models.classifier != null) 'Stroke type: ${report.models.classifier}',
            if (report.models.reference != null)
              'Targets: ${report.models.reference == 'default' ? 'coaching defaults' : report.models.reference}',
          ].join(' · '),
          style: theme.textTheme.labelSmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
      ],
    );
  }

  List<Widget> _strokeDetails(BuildContext context, Stroke stroke) {
    final theme = Theme.of(context);
    final confidence = stroke.typeConfidence;
    final subtitle = [
      'Contact at ${formatTimestamp(stroke.contactS)}',
      if (stroke.typeSource == 'user')
        'type set by you'
      else if (confidence != null)
        '${(confidence * 100).round()}% sure of type',
    ].join(' · ');

    return [
      const SizedBox(height: Insets.md),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(Insets.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(strokeTypeLabel(stroke.type), style: theme.textTheme.titleLarge),
                        const SizedBox(height: 2),
                        Text(
                          subtitle,
                          style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                        ),
                      ],
                    ),
                  ),
                  ScoreRing(score: stroke.score, size: 56, strokeWidth: 6),
                ],
              ),
              if (stroke.skillScore case final skill?) ...[
                const SizedBox(height: Insets.md),
                Row(
                  children: [
                    Text('Expert-likeness', style: theme.textTheme.labelMedium),
                    const SizedBox(width: Insets.md),
                    Expanded(
                      child: LinearProgressIndicator(
                        value: skill.clamp(0.0, 1.0),
                        minHeight: 6,
                        borderRadius: BorderRadius.circular(3),
                      ),
                    ),
                    const SizedBox(width: Insets.sm),
                    Text('${(skill * 100).round()}%', style: theme.textTheme.labelMedium),
                  ],
                ),
              ],
              const SizedBox(height: Insets.sm),
              Text(
                'Tap a metric to jump to that moment and highlight the joints involved.',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ],
          ),
        ),
      ),
      for (final (phase, metrics) in stroke.metricsByPhase()) ...[
        SectionHeader(humanize(phase)),
        for (final m in metrics) ...[
          MetricTile(
            key: _metricKeys.putIfAbsent(m.id, GlobalKey.new),
            metric: m,
            selected: m.id == _metricId,
            onTap: () => _selectMetric(stroke, m),
          ),
          const SizedBox(height: Insets.sm),
        ],
      ],
    ];
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.report});

  final AnalysisReport report;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final palette = context.scores;
    final summary = report.summary;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(Insets.lg),
        child: Row(
          children: [
            ScoreRing(score: summary.overallScore, caption: 'overall'),
            const SizedBox(width: Insets.lg),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    summary.headline.isEmpty ? 'Analysis complete' : summary.headline,
                    style: theme.textTheme.titleMedium,
                  ),
                  const SizedBox(height: Insets.sm),
                  Wrap(
                    spacing: Insets.xs,
                    runSpacing: Insets.xs,
                    children: [
                      Pill(label: strokeCountsLabel(summary.strokeCounts), color: theme.colorScheme.primary),
                      Pill(
                        label: viewLabel(report.player.view),
                        color: palette.info,
                        icon: Icons.videocam_outlined,
                      ),
                      Pill(
                        label: '${humanize(report.player.handedness)}-handed',
                        color: palette.info,
                        icon: Icons.back_hand_outlined,
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
