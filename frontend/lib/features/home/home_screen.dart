import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/theme.dart';
import '../../core/format.dart';
import '../../core/providers.dart';
import '../../core/widgets/common.dart';
import '../analyze/filming_tips.dart';
import '../history/history_repository.dart';
import '../history/history_screen.dart';
import '../results/models/report.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final user = ref.watch(authStateProvider).value;
    final name = user?.displayName?.trim().split(' ').first;
    final history = ref.watch(historyProvider);
    final records = history.value ?? const <AnalysisRecord>[];

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(Insets.lg, Insets.xl, Insets.lg, Insets.xxl),
          children: [
            Text(
              (name == null || name.isEmpty) ? 'Welcome back' : 'Hi, $name',
              style: theme.textTheme.headlineMedium,
            ),
            const SizedBox(height: Insets.xs),
            Text(
              'Ready to work on your game?',
              style: theme.textTheme.bodyLarge?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: Insets.xl),
            _NewAnalysisCard(onTap: () => context.go('/analyze')),
            if (records.isNotEmpty) ...[
              const SectionHeader('Your averages'),
              _Averages(records: records),
            ],
            SectionHeader(
              'Recent analyses',
              trailing: records.isEmpty
                  ? null
                  : TextButton(onPressed: () => context.go('/history'), child: const Text('See all')),
            ),
            if (history.isLoading && records.isEmpty)
              const Padding(
                padding: EdgeInsets.all(Insets.xl),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (records.isEmpty)
              _EmptyRecent(onSample: () => context.push('/sample'))
            else
              for (final r in records.take(3)) ...[
                AnalysisRecordTile(record: r, onTap: () => context.push('/analysis/${r.id}')),
                const SizedBox(height: Insets.sm),
              ],
            SectionHeader(
              'Filming tips',
              trailing: TextButton(
                onPressed: () => showFilmingTips(context),
                child: const Text('All tips'),
              ),
            ),
            SizedBox(
              height: 132,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: 4,
                separatorBuilder: (_, _) => const SizedBox(width: Insets.sm),
                itemBuilder: (context, i) => _TipCard(tip: filmingTips[i]),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NewAnalysisCard extends StatelessWidget {
  const _NewAnalysisCard({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final text = Theme.of(context).textTheme;
    return Material(
      color: scheme.primary,
      borderRadius: BorderRadius.circular(Radii.lg),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(Insets.xl),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Analyze a swing', style: text.titleLarge?.copyWith(color: scheme.onPrimary)),
                    const SizedBox(height: Insets.xs),
                    Text(
                      'Record or upload a clip and get coaching feedback in about a minute.',
                      style: text.bodyMedium?.copyWith(color: scheme.onPrimary.withValues(alpha: 0.85)),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: Insets.lg),
              CircleAvatar(
                radius: 28,
                backgroundColor: scheme.tertiary,
                foregroundColor: scheme.onTertiary,
                child: const Icon(Icons.videocam_rounded, size: 28),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Averages extends StatelessWidget {
  const _Averages({required this.records});

  final List<AnalysisRecord> records;

  @override
  Widget build(BuildContext context) {
    final sums = <StrokeFamily, (double, int)>{};
    for (final r in records) {
      for (final e in r.familyScores.entries) {
        final (s, n) = sums[e.key] ?? (0.0, 0);
        sums[e.key] = (s + e.value, n + 1);
      }
    }
    return Row(
      children: [
        for (final f in const [StrokeFamily.forehand, StrokeFamily.backhand, StrokeFamily.overhead])
          Expanded(
            child: Card(
              margin: const EdgeInsets.symmetric(horizontal: Insets.xs),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: Insets.lg),
                child: Column(
                  children: [
                    ScoreRing(
                      score: sums[f] == null ? null : (sums[f]!.$1 / sums[f]!.$2).round(),
                      size: 56,
                      strokeWidth: 6,
                    ),
                    const SizedBox(height: Insets.sm),
                    Text(familyLabel(f), style: Theme.of(context).textTheme.labelLarge),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _EmptyRecent extends StatelessWidget {
  const _EmptyRecent({required this.onSample});

  final VoidCallback onSample;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(Insets.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('No analyses yet', style: theme.textTheme.titleSmall),
            const SizedBox(height: Insets.xs),
            Text(
              'See what you get: open a sample analysis with scores, priorities, and the '
              'skeleton overlay.',
              style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: Insets.md),
            OutlinedButton.icon(
              onPressed: onSample,
              icon: const Icon(Icons.play_circle_outline_rounded),
              label: const Text('View sample analysis'),
            ),
          ],
        ),
      ),
    );
  }
}

class _TipCard extends StatelessWidget {
  const _TipCard({required this.tip});

  final FilmingTip tip;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      width: 220,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(Insets.lg),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(tip.icon, color: theme.colorScheme.primary),
              const SizedBox(height: Insets.sm),
              Text(tip.title, style: theme.textTheme.titleSmall),
              const SizedBox(height: 2),
              Expanded(
                child: Text(
                  tip.body,
                  style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.onSurfaceVariant),
                  overflow: TextOverflow.fade,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
