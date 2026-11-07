// Nabia must not initialize package:timezone's global database for an
// app that never did. Each test file runs in its own isolate.

import 'package:nabia/src/core/time_zones.dart';
import 'package:test/test.dart';
import 'package:timezone/timezone.dart' as tz;

void main() {
  test('the global database stays empty', () {
    expect(tz.timeZoneDatabase.isInitialized, isFalse);
    expect(zoneNamed('Europe/Madrid'), isNotNull);
    expect(zoneNamed('UTC'), isNotNull);
    expect(zoneNamed('GMT'), isNotNull);
    expect(tz.timeZoneDatabase.isInitialized, isFalse);
  });
}
