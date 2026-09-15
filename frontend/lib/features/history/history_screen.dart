import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme.dart';
import '../../core/format.dart';
import '../../core/widgets/common.dart';
import '../results/models/report.dart';
import 'history_repository.dart';

class HistoryScreen extends ConsumerStatefulWidget {
  const HistoryScreen({super.key});

  @override
  ConsumerState<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends ConsumerState<HistoryScreen> {
  StrokeFamily? _filter;

  static const _filters = [null, StrokeFamily.forehand, StrokeFamily.backhand, StrokeFamily.overhead];

  @override
  Widget build(BuildContext context) {
    final history = ref.watch(historyProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('History')),
      body: history.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => EmptyState(
          icon: Icons.cloud_off_rounded,
          title: "Couldn't load your history",
          message: '$e',
          action: OutlinedButton(
            onPressed: () => ref.invalidate(historyProvider),
            child: const Text('Try again'),
          ),
        ),
        data: (records) {
          if (records.isEmpty) {
            return EmptyState(
              icon: Icons.history_rounded,
              title: 'No analyses yet',
              message: 'Your analyzed swings show up here so you can track progress over time.',
              action: FilledButton.icon(
                onPressed: () => context.go('/analyze'),
                icon: const Icon(Icons.add_rounded),
                label: const Text('Analyze a swing'),
              ),
            );
          }
          final filtered = _filter == null
              ? records
              : records.where((r) => r.families.contains(_filter)).toList();
          return ListView(
            padding: const EdgeInsets.fromLTRB(Insets.lg, 0, Insets.lg, Insets.xxl),
            children: [
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(vertical: Insets.sm),
                child: Row(
                  children: [
                    for (final f in _filters)
                      Padding(
                        padding: const EdgeInsets.only(right: Insets.sm),
                        child: ChoiceChip(
                          label: Text(f == null ? 'All' : familyLabel(f)),
                          selected: _filter == f,
                          onSelected: (_) => setState(() => _filter = f),
                        ),
                      ),
                  ],
                ),
              ),
              if (filtered.isEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: Insets.xxl),
                  child: Text(
                    'No ${familyLabel(_filter!).toLowerCase()} analyses yet.',
                    textAlign: TextAlign.center,
                  ),
                ),
              for (final r in filtered) ...[
                AnalysisRecordTile(
                  record: r,
                  onTap: () => context.push('/history/${r.id}'),
                  onDelete: () => deleteAnalysis(context, ref, r),
                ),
                const SizedBox(height: Insets.sm),
              ],
            ],
          );
        },
      ),
    );
  }
}

Future<void> deleteAnalysis(BuildContext context, WidgetRef ref, AnalysisRecord record) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Delete analysis?'),
      content: const Text('This removes the analysis from your history on all devices.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
      ],
    ),
  );
  if (ok != true) return;
  try {
    await ref.read(historyRepositoryProvider)?.delete(record.id);
  } catch (e) {
    if (context.mounted) showMessage(context, "Couldn't delete: $e", error: true);
  }
}

class AnalysisRecordTile extends StatelessWidget {
  const AnalysisRecordTile({super.key, required this.record, this.onTap, this.onDelete});

  final AnalysisRecord record;
  final VoidCallback? onTap;
  final VoidCallback? onDelete;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final title = record.primaryType == null ? 'No strokes detected' : strokeTypeLabel(record.primaryType!);
    final extra = record.strokeCounts.length > 1 ? ' + ${record.strokeCounts.length - 1} more' : '';
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(Insets.lg, Insets.md, Insets.xs, Insets.md),
          child: Row(
            children: [
              ScoreRing(score: record.overallScore, size: 52, strokeWidth: 5),
              const SizedBox(width: Insets.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('$title$extra', style: theme.textTheme.titleSmall),
                    const SizedBox(height: 2),
                    Text(
                      [
                        if (record.createdAt != null) formatShortDate(record.createdAt!),
                        strokeCountsLabel(record.strokeCounts),
                      ].join(' · '),
                      style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              if (onDelete != null)
                PopupMenuButton<String>(
                  tooltip: 'More',
                  onSelected: (_) => onDelete!(),
                  itemBuilder: (context) => const [
                    PopupMenuItem(value: 'delete', child: Text('Delete')),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }
}
