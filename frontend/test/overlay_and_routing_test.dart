import 'dart:ui';

import 'package:flutter_test/flutter_test.dart';
import 'package:tennis_analyze/app/router.dart';
import 'package:tennis_analyze/features/results/widgets/playback.dart';
import 'package:tennis_analyze/features/results/widgets/pose_overlay_painter.dart';

void main() {
  group('PoseOverlayPainter.videoRect', () {
    test('pillarboxes a portrait video in a landscape canvas', () {
      final r = PoseOverlayPainter.videoRect(const Size(400, 300), 9 / 16);
      expect(r.height, 300);
      expect(r.width, closeTo(300 * 9 / 16, 1e-9));
      expect(r.left, closeTo((400 - r.width) / 2, 1e-9));
      expect(r.top, 0);
    });

    test('letterboxes a landscape video in a portrait canvas', () {
      final r = PoseOverlayPainter.videoRect(const Size(300, 600), 16 / 9);
      expect(r.width, 300);
      expect(r.height, closeTo(300 * 9 / 16, 1e-9));
      expect(r.top, closeTo((600 - r.height) / 2, 1e-9));
      expect(r.left, 0);
    });

    test('fills the canvas when aspect ratios match', () {
      final r = PoseOverlayPainter.videoRect(const Size(320, 180), 16 / 9);
      expect(r, const Rect.fromLTWH(0, 0, 320, 180));
    });
  });

  group('PoseOverlayPainter.mapPoint', () {
    const rect = Rect.fromLTWH(50, 0, 200, 100);
    final frame = [0.0, 0.0, 0.5, 0.5, 1.0, 1.0, double.nan, 0.2];

    test('maps normalized coordinates into the video rectangle', () {
      expect(PoseOverlayPainter.mapPoint(frame, 0, rect), const Offset(50, 0));
      expect(PoseOverlayPainter.mapPoint(frame, 1, rect), const Offset(150, 50));
      expect(PoseOverlayPainter.mapPoint(frame, 2, rect), const Offset(250, 100));
    });

    test('returns null for missing or out-of-range joints', () {
      expect(PoseOverlayPainter.mapPoint(frame, 3, rect), isNull);
      expect(PoseOverlayPainter.mapPoint(frame, 4, rect), isNull);
      expect(PoseOverlayPainter.mapPoint(frame, -1, rect), isNull);
    });
  });

  group('SyntheticPlayback', () {
    test('advances with ticks only while playing, and loops', () async {
      final p = SyntheticPlayback(const Duration(seconds: 2));
      p.tick(Duration.zero);
      p.tick(const Duration(milliseconds: 500));
      expect(p.position, Duration.zero);

      await p.play();
      p.tick(const Duration(milliseconds: 600));
      p.tick(const Duration(milliseconds: 1100));
      expect(p.position, const Duration(milliseconds: 500));

      await p.setSpeed(0.5);
      p.tick(const Duration(milliseconds: 1500));
      expect(p.position, const Duration(milliseconds: 700));

      p.tick(const Duration(milliseconds: 5000));
      expect(p.position, Duration.zero); // looped

      await p.seekSeconds(9);
      expect(p.position, const Duration(seconds: 2));
      p.dispose();
    });
  });

  group('appRedirect', () {
    String? go(String loc, {bool onboarded = true, bool loading = false, bool signedIn = true}) =>
        appRedirect(location: loc, onboardingDone: onboarded, authLoading: loading, signedIn: signedIn);

    test('onboarding comes first', () {
      expect(go('/home', onboarded: false), '/welcome');
      expect(go('/welcome', onboarded: false), isNull);
    });

    test('waits for auth, then requires sign-in', () {
      expect(go('/home', loading: true), '/splash');
      expect(go('/home', signedIn: false), '/auth');
      expect(go('/auth', signedIn: false), isNull);
    });

    test('signed-in users leave the gate screens', () {
      expect(go('/auth'), '/home');
      expect(go('/welcome'), '/home');
      expect(go('/splash'), '/home');
      expect(go('/history'), isNull);
      expect(go('/analysis/abc'), isNull);
    });
  });
}
