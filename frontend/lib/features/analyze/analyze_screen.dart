import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:video_player/video_player.dart';

import '../../app/theme.dart';
import '../../core/config/settings.dart';
import '../../core/widgets/common.dart';
import 'analysis_controller.dart';
import 'filming_tips.dart';

const _strokeHints = [
  ('auto', 'Auto-detect'),
  ('forehand', 'Forehand'),
  ('backhand', 'Backhand'),
  ('serve', 'Serve'),
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
  String _hint = 'auto';
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

  void _analyze() {
    final file = _file;
    if (file == null) return;
    _preview?.pause();
    context.push(
      '/processing',
      extra: AnalysisRequest(
        videoPath: file.path,
        strokeHint: _hint,
        handedness: _handedness ?? ref.read(settingsProvider).handedness,
      ),
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
                'Forehands, backhands, or serves — we find each stroke, measure your technique, '
                'and tell you what to work on first.',
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
        const SectionHeader('Which stroke?'),
        Wrap(
          spacing: Insets.sm,
          runSpacing: Insets.sm,
          children: [
            for (final (value, label) in _strokeHints)
              ChoiceChip(
                label: Text(label),
                selected: _hint == value,
                onSelected: (_) => setState(() => _hint = value),
              ),
          ],
        ),
        const SizedBox(height: Insets.xs),
        Text(
          _hint == 'auto'
              ? 'We detect every stroke in the clip automatically.'
              : 'We only analyze ${_hint}s in this clip.',
          style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
        ),
        const SectionHeader('Your hitting hand'),
        SegmentedButton<Handedness>(
          segments: const [
            ButtonSegment(value: Handedness.auto, label: Text('Auto')),
            ButtonSegment(value: Handedness.right, label: Text('Right')),
            ButtonSegment(value: Handedness.left, label: Text('Left')),
          ],
          selected: {handedness},
          onSelectionChanged: (s) => setState(() => _handedness = s.first),
        ),
        const SizedBox(height: Insets.xxl),
        FilledButton.icon(
          onPressed: _analyze,
          icon: const Icon(Icons.auto_awesome_rounded),
          label: const Text('Analyze swing'),
        ),
      ],
    );
  }
}
