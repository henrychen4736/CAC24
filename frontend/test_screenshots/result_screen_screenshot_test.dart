// Renders the Result screen to PNGs with real fonts, for eyeballing the UI
// without a device or a Firebase sign-in. Not part of the normal test suite
// (it lives outside test/). Run:
//
//   flutter test test_screenshots/result_screen_screenshot_test.dart
//
// Environment variables:
//   FLUTTER_ROOT     SDK root (fonts come from bin/cache/artifacts/material_fonts)
//   SAMPLE_REPORT    report JSON to render (default: assets/sample_report.json)
//   SCREENSHOT_DIR   output directory (default: build/screenshots)
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tennis_analyze/app/theme.dart';
import 'package:tennis_analyze/features/results/models/report.dart';
import 'package:tennis_analyze/features/results/result_args.dart';
import 'package:tennis_analyze/features/results/result_screen.dart';

const _phone = Size(412, 915);

Future<void> _loadFont(String family, List<String> paths) async {
  final loader = FontLoader(family);
  for (final p in paths) {
    loader.addFont(Future.value(ByteData.sublistView(File(p).readAsBytesSync())));
  }
  await loader.load();
}

Future<void> _loadFonts() async {
  final root = Platform.environment['FLUTTER_ROOT'] ?? 'C:/Users/Henry/flutter-sdks/stable';
  final dir = '$root/bin/cache/artifacts/material_fonts';
  await _loadFont('Roboto', [
    for (final w in ['regular', 'medium', 'bold']) '$dir/roboto-$w.ttf',
  ]);
  await _loadFont('MaterialIcons', ['$dir/materialicons-regular.otf']);
}

ThemeData _theme() {
  final base = AppTheme.light();
  return base.copyWith(
    textTheme: base.textTheme.apply(fontFamily: 'Roboto'),
    primaryTextTheme: base.primaryTextTheme.apply(fontFamily: 'Roboto'),
  );
}

Future<void> _capture(WidgetTester tester, GlobalKey key, String name) async {
  final outDir = Directory(Platform.environment['SCREENSHOT_DIR'] ?? 'build/screenshots')
    ..createSync(recursive: true);
  await tester.runAsync(() async {
    final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
    final ui.Image image = await boundary.toImage(pixelRatio: 1.5);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    File('${outDir.path}/$name.png').writeAsBytesSync(bytes!.buffer.asUint8List());
  });
  // ignore: avoid_print
  print('wrote ${outDir.path}/$name.png');
}

Future<void> _pumpFrames(WidgetTester tester, [int n = 12]) async {
  // the skeleton replay ticker never settles, so step fixed frames
  for (var i = 0; i < n; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

void main() {
  final path = Platform.environment['SAMPLE_REPORT'] ?? 'assets/sample_report.json';
  final report = AnalysisReport.fromJson(
    jsonDecode(File(path).readAsStringSync()) as Map<String, dynamic>,
  );

  testWidgets('result screen screenshots', (tester) async {
    await tester.runAsync(_loadFonts);
    final key = GlobalKey();

    Future<void> render(Size size, String name) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      await tester.pumpWidget(RepaintBoundary(
        key: key,
        child: MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: _theme(),
          home: ResultScreen(args: ResultArgs(report: report, isSample: true)),
        ),
      ));
      await _pumpFrames(tester);
      await _capture(tester, key, name);
    }

    await render(_phone, 'result_top');
    await render(Size(_phone.width, 4200), 'result_full');

    tester.view.reset();
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 1));
  });
}
