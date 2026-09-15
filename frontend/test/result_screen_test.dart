import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tennis_analyze/app/theme.dart';
import 'package:tennis_analyze/core/format.dart';
import 'package:tennis_analyze/features/results/models/report.dart';
import 'package:tennis_analyze/features/results/result_args.dart';
import 'package:tennis_analyze/features/results/result_screen.dart';

void main() {
  final report = AnalysisReport.fromJson(
    jsonDecode(File('assets/sample_report.json').readAsStringSync()) as Map<String, dynamic>,
  );

  Future<void> pumpResult(WidgetTester tester, ResultArgs args) async {
    // Tall surface so the lazily built list renders every metric group.
    tester.view.physicalSize = const Size(1080, 8000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(theme: AppTheme.light(), home: ResultScreen(args: args)));
    // The playback ticker never settles, so pump fixed frames instead of pumpAndSettle.
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
  }

  Future<void> unmount(WidgetTester tester) async {
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 1));
  }

  testWidgets('renders summary, priorities, and metrics of the sample report', (tester) async {
    await pumpResult(tester, ResultArgs(report: report, isSample: true));

    expect(find.text('Sample analysis'), findsOneWidget);
    expect(find.text(report.summary.headline), findsOneWidget);
    expect(find.text('Top priorities'), findsOneWidget);
    for (final p in report.summary.priorities) {
      expect(find.text(p.cue), findsWidgets);
    }
    // First stroke is selected: its metric labels (sent by the server) are shown.
    expect(find.text('Contact point in front'), findsWidgets);
    expect(find.text('Hitting-arm extension'), findsOneWidget);
    // one chip per detected stroke
    for (final s in report.strokes) {
      expect(find.text('${s.index + 1} · ${strokeTypeShortLabel(s.type)}'), findsOneWidget);
    }

    await unmount(tester);
  });

  testWidgets('selecting another stroke shows that stroke', (tester) async {
    await pumpResult(tester, ResultArgs(report: report, isSample: true));
    final third = report.strokes[2];
    String contactLine(Stroke s) => 'Contact at ${formatTimestamp(s.contactS)}';
    expect(find.textContaining(contactLine(report.strokes.first)), findsOneWidget);

    await tester.tap(find.text('3 · ${strokeTypeShortLabel(third.type)}'));
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(find.textContaining(contactLine(third)), findsOneWidget);
    expect(find.textContaining(contactLine(report.strokes.first)), findsNothing);

    await unmount(tester);
  });

  testWidgets('shows an empty state when no strokes were detected', (tester) async {
    final empty = AnalysisReport.fromJson({
      'summary': {'overall_score': null, 'headline': 'No swings found.'},
      'quality': {
        'warnings': [
          {'code': 'no_strokes', 'message': 'We found you but no swings.'},
        ],
      },
      'strokes': [],
    });
    await pumpResult(tester, ResultArgs(report: empty));

    expect(find.text('No swings detected'), findsOneWidget);
    expect(find.text('We found you but no swings.'), findsOneWidget);
    expect(find.text('Top priorities'), findsNothing);

    await unmount(tester);
  });
}
