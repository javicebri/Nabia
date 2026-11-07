// Nabia must not change package:timezone's global state when the app
// initialized it first (own database and local location). Each test
// file runs in its own isolate, so Nabia loads its zones here first.

import 'package:nabia/src/core/time_zones.dart';
import 'package:test/test.dart';
import 'package:timezone/data/latest_10y.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

void main() {
  test('the app database and local location are kept', () {
    tzdata.initializeTimeZones();
    final lisbon = tz.getLocation('Europe/Lisbon');
    tz.setLocalLocation(lisbon);
    final before = Map.of(tz.timeZoneDatabase.locations);

    // First use loads Nabia's full database (history back to 1940).
    final monrovia = zoneNamed('Africa/Monrovia')!;
    final offset1960 = monrovia.timeZone(
      DateTime.utc(1960).millisecondsSinceEpoch,
    );
    expect(offset1960.offset, const Duration(minutes: -44, seconds: -30));

    expect(tz.timeZoneDatabase.locations, before);
    expect(tz.local, same(lisbon));
  });
}
