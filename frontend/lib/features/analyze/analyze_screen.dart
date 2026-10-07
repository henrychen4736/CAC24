import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:video_player/video_player.dart';

import '../../app/theme.dart';
import '../../core/config/settings.dart';
import '../../core/format.dart';
import '../../core/widgets/common.dart';
import 'analysis_controller.dart';
import 'filming_tips.dart';

/// The strokes the user can say they filmed, grouped by family. The server
/// analyzes every swing in the clip as the chosen stroke.
const _strokeGroups = [
  ('Forehand', ['forehand', 'forehand_slice', 'forehand_volley']),
  ('Backhand', ['backhand_1h', 'backhand_2h', 'backhand_slice', 'backhand_volley']),
  ('Overhead', ['serve', 'smash']),
];

class AnalyzeScreen extends ConsumerStatefulWidget {
  const AnalyzeScreen({super.key});

  @override
  ConsumerState<AnalyzeScreen> createState() => _AnalyzeScreenState();
}

class _AnalyzeScreenState extends ConsumerState<AnalyzeScreen> {
  final _picker = ImagePicker();
  XFile? _file;
  VideoPlayerController? _preview;
  String? _strokeType;
  Handedness? _handedness;
  bool _picking = false;

  @override
  void dispose() {
    _preview?.dispose();
    super.dispose();
  }

  Future<void> _pick(ImageSource source) async {
    setState(() => _picking = true);
    try {
      final file = await _picker.pickVideo(source: source, maxDuration: const Duration(seconds: 60));
      if (file == null || !mounted) return;
      final old = _preview;
      final controller = VideoPlayerController.file(File(file.path));
      setState(() {
        _file = file;
        _preview = controller;
      });
      await old?.dispose();
      await controller.initialize();
      await controller.setLooping(true);
      await controller.setVolume(0);
      await controller.play();
      if (mounted) setState(() {});
    } on PlatformException catch (e) {
      if (mounted) {
        showMessage(
          context,
          e.code.contains('denied')
              ? 'Permission denied. Allow camera / photo access in Settings.'
              : "Couldn't open the video: ${e.message ?? e.code}",
          error: true,
        );
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  void _clear() {
    _preview?.dispose();
    setState(() {
      _preview = null;
      _file = null;
    });
  }

  void _setHandedness(Handedness h) {
    setState(() => _handedness = h);
    // remember it for next time if the profile doesn't have one yet
    if (ref.read(settingsProvider).handedness == null) {
      ref.read(settingsProvider.notifier).setHandedness(h);
    }
  }

  void _analyze() {
    final file = _file;
    final strokeType = _strokeType;
    final handedness = _handedness ?? ref.read(settingsProvider).handedness;
    if (file == null || strokeType == null || handedness == null) return;
    _preview?.pause();
    context.push(
      '/processing',
      extra: AnalysisRequest(videoPath: file.path, strokeType: strokeType, handedness: handedness),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('New analysis'),
        actions: [
          IconButton(
            tooltip: 'How to film',
            icon: const Icon(Icons.help_outline_rounded),
            onPressed: () => showFilmingTips(context),
          ),
        ],
      ),
      body: _file == null ? _pickPrompt(context) : _options(context),
    );
  }

  Widget _pickPrompt(BuildContext context) {
    final theme = Theme.of(context);
    return ListView(
      padding: const EdgeInsets.all(Insets.xl),
      children: [
        Container(
          padding: const EdgeInsets.all(Insets.xl),
          decoration: BoxDecoration(
            color: theme.colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(Radii.lg),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.sports_tennis_rounded, size: 40, color: theme.colorScheme.onPrimaryContainer),
              const SizedBox(height: Insets.lg),
              Text(
                'Film a few swings',
                style: theme.textTheme.headlineSmall?.copyWith(color: theme.colorScheme.onPrimaryContainer),
              ),
              const SizedBox(height: Insets.sm),
              Text(
                'Film one kind of stroke per clip: forehands, backhands, or serves. We find each '
                'swing, measure your technique, and tell you what to work on first.',
                style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onPrimaryContainer),
              ),
            ],
          ),
        ),
        const SizedBox(height: Insets.xl),
        FilledButton.icon(
          onPressed: _picking ? null : () => _pick(ImageSource.camera),
          icon: const Icon(Icons.videocam_rounded),
          label: const Text('Record a video'),
        ),
        const SizedBox(height: Insets.md),
        OutlinedButton.icon(
          onPressed: _picking ? null : () => _pick(ImageSource.gallery),
          icon: const Icon(Icons.video_library_rounded),
          label: const Text('Choose from library'),
        ),
        const SizedBox(height: Insets.xl),
        Card(
          child: ListTile(
            leading: const Icon(Icons.tips_and_updates_outlined),
            title: const Text('How to film for the best feedback'),
            subtitle: const Text('Full body in frame · side or behind · steady'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: () => showFilmingTips(context),
          ),
        ),
      ],
    );
  }

  Widget _options(BuildContext context) {
    final theme = Theme.of(context);
    final preview = _preview;
    final handedness = _handedness ?? ref.watch(settingsProvider).handedness;
    return ListView(
      padding: const EdgeInsets.all(Insets.lg),
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(Radii.md),
          child: ColoredBox(
            color: Colors.black,
            child: AspectRatio(
              aspectRatio: 16 / 10,
              child: preview != null && preview.value.isInitialized
                  ? GestureDetector(
                      onTap: () => preview.value.isPlaying ? preview.pause() : preview.play(),
                      child: Center(
                        child: AspectRatio(
                          aspectRatio: preview.value.aspectRatio,
                          child: VideoPlayer(preview),
                        ),
                      ),
                    )
                  : const Center(child: CircularProgressIndicator()),
            ),
          ),
        ),
        const SizedBox(height: Insets.sm),
        Row(
          children: [
            Expanded(
              child: Text(
                preview != null && preview.value.isInitialized
                    ? '${preview.value.duration.inSeconds} s clip'
                    : 'Loading preview…',
                style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
            ),
            TextButton.icon(
              onPressed: _clear,
              icon: const Icon(Icons.swap_horiz_rounded),
              label: const Text('Change video'),
            ),
          ],
        ),
        const SectionHeader('Which stroke did you film?'),
        for (final (group, types) in _strokeGroups) ...[
          Padding(
            padding: const EdgeInsets.only(top: Insets.sm, bottom: Insets.xs),
            child: Text(group, style: theme.textTheme.labelLarge),
          ),
          Wrap(
            spacing: Insets.sm,
            runSpacing: Insets.sm,
            children: [
              for (final type in types)
                ChoiceChip(
                  label: Text(strokeTypeLabel(type)),
                  selected: _strokeType == type,
                  onSelected: (_) => setState(() => _strokeType = type),
                ),
            ],
          ),
        ],
        const SizedBox(height: Insets.sm),
        Text(
          _strokeType == null
              ? 'Every swing in the clip is analyzed as this stroke, so film one kind per clip.'
              : 'Every swing in the clip is analyzed as a ${strokeTypeLabel(_strokeType!).toLowerCase()}.',
          style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
        const SectionHeader('Your hitting hand'),
        SegmentedButton<Handedness>(
          segments: const [
            ButtonSegment(value: Handedness.right, label: Text('Right')),
            ButtonSegment(value: Handedness.left, label: Text('Left')),
          ],
          emptySelectionAllowed: handedness == null,
          selected: {?handedness},
          onSelectionChanged: (s) => _setHandedness(s.first),
        ),
        const SizedBox(height: Insets.xxl),
        FilledButton.icon(
          onPressed: _strokeType != null && handedness != null ? _analyze : null,
          icon: const Icon(Icons.auto_awesome_rounded),
          label: const Text('Analyze swing'),
        ),
        if (_strokeType == null || handedness == null) ...[
          const SizedBox(height: Insets.sm),
          Text(
            _strokeType == null && handedness == null
                ? 'Choose the stroke and your hitting hand to continue.'
                : _strokeType == null
                    ? 'Choose the stroke you filmed to continue.'
                    : 'Choose your hitting hand to continue.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
      ],
    );
  }
}
