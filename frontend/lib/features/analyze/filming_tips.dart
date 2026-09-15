import 'package:flutter/material.dart';

import '../../app/theme.dart';

typedef FilmingTip = ({IconData icon, String title, String body});

const List<FilmingTip> filmingTips = [
  (
    icon: Icons.accessibility_new_rounded,
    title: 'Whole body in frame',
    body: 'Keep head to feet visible for the entire swing, with a little space around you.',
  ),
  (
    icon: Icons.videocam_rounded,
    title: 'Film from the side or behind',
    body: 'Place the phone beside the court or behind the baseline, at about hip height.',
  ),
  (
    icon: Icons.stay_current_landscape_rounded,
    title: 'Landscape and steady',
    body: 'Turn the phone sideways and prop it up. Avoid panning or zooming while recording.',
  ),
  (
    icon: Icons.speed_rounded,
    title: '60 fps if you can',
    body: 'Higher frame rates capture the moment of contact more precisely.',
  ),
  (
    icon: Icons.person_rounded,
    title: 'One player in view',
    body: 'Keep other people out of the shot so we track the right person.',
  ),
  (
    icon: Icons.timer_outlined,
    title: 'Short clips',
    body: 'A few strokes in 10–30 seconds works best. Trim long rallies first.',
  ),
];

Future<void> showFilmingTips(BuildContext context) => showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) => const FilmingTipsSheet(),
    );

class FilmingTipsSheet extends StatelessWidget {
  const FilmingTipsSheet({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(Insets.xl, 0, Insets.xl, Insets.xl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('How to film your swing', style: theme.textTheme.titleLarge),
            const SizedBox(height: Insets.xs),
            Text(
              'Good footage makes the feedback far more accurate.',
              style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: Insets.lg),
            for (final tip in filmingTips)
              Padding(
                padding: const EdgeInsets.only(bottom: Insets.lg),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    CircleAvatar(
                      backgroundColor: theme.colorScheme.primaryContainer,
                      foregroundColor: theme.colorScheme.onPrimaryContainer,
                      child: Icon(tip.icon, size: 20),
                    ),
                    const SizedBox(width: Insets.lg),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(tip.title, style: theme.textTheme.titleSmall),
                          const SizedBox(height: 2),
                          Text(tip.body, style: theme.textTheme.bodyMedium),
                        ],
                      ),
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
