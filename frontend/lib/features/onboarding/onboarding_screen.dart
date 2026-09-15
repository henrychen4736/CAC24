import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme.dart';
import '../../core/config/settings.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _controller = PageController();
  int _page = 0;

  static const _pages = [
    (
      icon: Icons.sports_tennis_rounded,
      title: 'Your pocket tennis coach',
      body: 'Film a few swings and get specific feedback on your forehand, backhand, and serve.',
    ),
    (
      icon: Icons.accessibility_new_rounded,
      title: 'We measure what coaches look at',
      body: 'Shoulder turn, knee bend, contact point, extension, and follow-through — '
          'each with a clear target and a tip to fix it.',
    ),
    (
      icon: Icons.videocam_rounded,
      title: 'Film it right',
      body: 'Whole body in frame, camera steady beside or behind you, landscape, 60 fps if you can.',
    ),
  ];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _next() {
    if (_page == _pages.length - 1) {
      ref.read(settingsProvider.notifier).completeOnboarding();
    } else {
      _controller.nextPage(duration: const Duration(milliseconds: 300), curve: Curves.easeOutCubic);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final last = _page == _pages.length - 1;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: () => ref.read(settingsProvider.notifier).completeOnboarding(),
                child: const Text('Skip'),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _controller,
                itemCount: _pages.length,
                onPageChanged: (i) => setState(() => _page = i),
                itemBuilder: (context, i) {
                  final p = _pages[i];
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: Insets.xxl),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(Insets.xxl),
                          decoration: BoxDecoration(
                            color: theme.colorScheme.primaryContainer,
                            shape: BoxShape.circle,
                          ),
                          child: Icon(p.icon, size: 72, color: theme.colorScheme.onPrimaryContainer),
                        ),
                        const SizedBox(height: Insets.xxl),
                        Text(p.title, style: theme.textTheme.headlineSmall, textAlign: TextAlign.center),
                        const SizedBox(height: Insets.md),
                        Text(
                          p.body,
                          style: theme.textTheme.bodyLarge?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                for (var i = 0; i < _pages.length; i++)
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    margin: const EdgeInsets.symmetric(horizontal: 3),
                    height: 8,
                    width: i == _page ? 24 : 8,
                    decoration: BoxDecoration(
                      color: i == _page ? theme.colorScheme.primary : theme.colorScheme.outlineVariant,
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
              ],
            ),
            Padding(
              padding: const EdgeInsets.all(Insets.xl),
              child: FilledButton(onPressed: _next, child: Text(last ? 'Get started' : 'Next')),
            ),
          ],
        ),
      ),
    );
  }
}
