import 'package:flutter_test/flutter_test.dart';
import 'package:tennis_analyze/core/config/settings.dart';

void main() {
  test('Handedness.parse: right/left, and unset for anything else (incl. the old "auto")', () {
    expect(Handedness.parse('right'), Handedness.right);
    expect(Handedness.parse('left'), Handedness.left);
    expect(Handedness.parse('auto'), isNull);
    expect(Handedness.parse(null), isNull);
  });

  test('handedness starts unset so the user has to choose', () {
    expect(const AppSettings().handedness, isNull);
  });
}
