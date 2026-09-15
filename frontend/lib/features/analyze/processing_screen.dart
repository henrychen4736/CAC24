import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme.dart';
import '../../core/widgets/common.dart';
import 'analysis_controller.dart';

class ProcessingScreen extends ConsumerStatefulWidget {
  const ProcessingScreen({super.key, required this.request});

  final AnalysisRequest request;

  @override
  ConsumerState<ProcessingScreen> createState() => _ProcessingScreenState();
}

class _ProcessingScreenState extends ConsumerState<ProcessingScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(analysisFlowProvider.notifier).start(widget.request);
    });
  }

  Future<void> _confirmCancel() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel analysis?'),
        content: const Text('Your video will stop uploading and the analysis will be discarded.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Keep going')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Cancel it')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    await ref.read(analysisFlowProvider.notifier).cancel();
    if (mounted) context.pop();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(analysisFlowProvider);
    ref.listen(analysisFlowProvider, (_, next) {
      if (next is FlowDone) context.pushReplacement('/result', extra: next.args);
    });

    final running = state is! FlowFailed && state is! FlowDone;
    return PopScope(
      canPop: !running,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _confirmCancel();
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Analyzing'),
          leading: IconButton(
            icon: const Icon(Icons.close_rounded),
            tooltip: 'Cancel',
            onPressed: running ? _confirmCancel : () => context.pop(),
          ),
        ),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(Insets.xl),
            child: state is FlowFailed ? _failed(context, state) : _progress(context, state),
          ),
        ),
      ),
    );
  }

  Widget _failed(BuildContext context, FlowFailed state) {
    return EmptyState(
      icon: Icons.error_outline_rounded,
      title: 'Analysis failed',
      message: state.message,
      action: Column(
        children: [
          FilledButton.icon(
            onPressed: () => ref.read(analysisFlowProvider.notifier).retry(),
            icon: const Icon(Icons.refresh_rounded),
            label: const Text('Try again'),
          ),
          const SizedBox(height: Insets.sm),
          TextButton(onPressed: () => context.pop(), child: const Text('Choose another video')),
        ],
      ),
    );
  }

  Widget _progress(BuildContext context, AnalysisFlowState state) {
    final theme = Theme.of(context);
    final (step, progress) = switch (state) {
      FlowUploading(:final progress) => (0, progress),
      FlowProcessing(stage: 'analysis' || 'done', :final progress) => (2, progress),
      FlowProcessing(:final progress) => (1, progress),
      FlowSaving() || FlowDone() => (3, null),
      _ => (0, null),
    };
    const steps = [
      ('Uploading video', Icons.cloud_upload_outlined),
      ('Tracking your movement', Icons.accessibility_new_rounded),
      ('Measuring your technique', Icons.straighten_rounded),
      ('Saving to history', Icons.bookmark_outline_rounded),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: Insets.xl),
        Center(
          child: SizedBox.square(
            dimension: 96,
            child: CircularProgressIndicator(
              value: progress,
              strokeWidth: 6,
              strokeCap: StrokeCap.round,
            ),
          ),
        ),
        const SizedBox(height: Insets.xl),
        Text(
          steps[step].$1,
          style: theme.textTheme.headlineSmall,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: Insets.sm),
        Text(
          progress == null ? 'Just a moment…' : '${(progress * 100).round()}%',
          style: theme.textTheme.bodyLarge?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: Insets.xxl),
        for (final (i, (label, icon)) in steps.indexed)
          ListTile(
            leading: i < step
                ? Icon(Icons.check_circle_rounded, color: context.scores.good)
                : Icon(icon, color: i == step ? theme.colorScheme.primary : theme.colorScheme.outline),
            title: Text(
              label,
              style: TextStyle(
                color: i <= step ? theme.colorScheme.onSurface : theme.colorScheme.outline,
                fontWeight: i == step ? FontWeight.w600 : null,
              ),
            ),
          ),
        const Spacer(),
        Text(
          'Analysis usually takes under a minute. You can keep this screen open.',
          style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
          textAlign: TextAlign.center,
        ),
      ],
    );
  }
}
