import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/config/settings.dart';
import '../core/providers.dart';
import '../features/analyze/analysis_controller.dart';
import '../features/analyze/analyze_screen.dart';
import '../features/analyze/processing_screen.dart';
import '../features/auth/auth_screen.dart';
import '../features/history/history_screen.dart';
import '../features/home/home_screen.dart';
import '../features/onboarding/onboarding_screen.dart';
import '../features/profile/profile_screen.dart';
import '../features/results/result_args.dart';
import '../features/results/result_screen.dart';

/// Where the app should be given onboarding and auth state, or null to stay.
@visibleForTesting
String? appRedirect({
  required String location,
  required bool onboardingDone,
  required bool authLoading,
  required bool signedIn,
}) {
  const gates = {'/welcome', '/auth', '/splash'};
  if (!onboardingDone) return location == '/welcome' ? null : '/welcome';
  if (authLoading) return location == '/splash' ? null : '/splash';
  if (!signedIn) return location == '/auth' ? null : '/auth';
  if (gates.contains(location)) return '/home';
  return null;
}

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.listen(authStateProvider, (_, _) => refresh.value++);
  ref.listen(settingsProvider.select((s) => s.onboardingDone), (_, _) => refresh.value++);

  final router = GoRouter(
    initialLocation: '/home',
    refreshListenable: refresh,
    redirect: (context, state) {
      final auth = ref.read(authStateProvider);
      return appRedirect(
        location: state.matchedLocation,
        onboardingDone: ref.read(settingsProvider).onboardingDone,
        authLoading: auth.isLoading && !auth.hasValue,
        signedIn: auth.value != null,
      );
    },
    routes: [
      GoRoute(path: '/splash', builder: (_, _) => const _Splash()),
      GoRoute(path: '/welcome', builder: (_, _) => const OnboardingScreen()),
      GoRoute(path: '/auth', builder: (_, _) => const AuthScreen()),
      StatefulShellRoute.indexedStack(
        builder: (context, state, shell) => _AppShell(shell: shell),
        branches: [
          StatefulShellBranch(routes: [GoRoute(path: '/home', builder: (_, _) => const HomeScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/analyze', builder: (_, _) => const AnalyzeScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/history', builder: (_, _) => const HistoryScreen())]),
          StatefulShellBranch(routes: [GoRoute(path: '/profile', builder: (_, _) => const ProfileScreen())]),
        ],
      ),
      GoRoute(
        path: '/processing',
        redirect: (_, state) => state.extra is AnalysisRequest ? null : '/analyze',
        builder: (_, state) => ProcessingScreen(request: state.extra! as AnalysisRequest),
      ),
      GoRoute(
        path: '/result',
        redirect: (_, state) => state.extra is ResultArgs ? null : '/home',
        builder: (_, state) => ResultScreen(args: state.extra! as ResultArgs),
      ),
      GoRoute(path: '/sample', builder: (_, _) => const ResultLoaderScreen(id: 'sample')),
      GoRoute(
        path: '/analysis/:id',
        builder: (_, state) => ResultLoaderScreen(id: state.pathParameters['id']!),
      ),
    ],
  );
  ref.onDispose(() {
    router.dispose();
    refresh.dispose();
  });
  return router;
});

class _AppShell extends StatelessWidget {
  const _AppShell({required this.shell});

  final StatefulNavigationShell shell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: shell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: shell.currentIndex,
        onDestinationSelected: (i) => shell.goBranch(i, initialLocation: i == shell.currentIndex),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home_rounded),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.add_circle_outline_rounded),
            selectedIcon: Icon(Icons.add_circle_rounded),
            label: 'Analyze',
          ),
          NavigationDestination(
            icon: Icon(Icons.history_rounded),
            selectedIcon: Icon(Icons.history_toggle_off_rounded),
            label: 'History',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline_rounded),
            selectedIcon: Icon(Icons.person_rounded),
            label: 'Profile',
          ),
        ],
      ),
    );
  }
}

class _Splash extends StatelessWidget {
  const _Splash();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: scheme.primary,
      body: Center(child: Icon(Icons.sports_tennis_rounded, size: 72, color: scheme.tertiary)),
    );
  }
}
