/// IANA time zones for Nabia, isolated from the app's global state.
///
/// `package:timezone` keeps one global database, and initializing it
/// also resets its local location. A library must not change either,
/// so Nabia loads the full database once (historical data go back to
/// 1940), keeps its own copy and restores the global state exactly as
/// it found it.
library;

import 'package:timezone/data/latest_all.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

/// Nabia's copy of the full IANA database, loaded on first use.
final Map<String, tz.Location> _zones = _loadZones();

Map<String, tz.Location> _loadZones() {
  final database = tz.timeZoneDatabase;
  final previous = Map.of(database.locations);
  // Initializing the database is what sets the local location, so it
  // can only be read when the app initialized the database before.
  final previousLocal = previous.isEmpty ? null : tz.local;
  tzdata.initializeTimeZones();
  final zones = Map<String, tz.Location>.unmodifiable(database.locations);
  database.clear();
  previous.values.forEach(database.add);
  if (previousLocal != null) tz.setLocalLocation(previousLocal);
  return zones;
}

/// The IANA zone named [name], or `null` if the database lacks it.
tz.Location? zoneNamed(String name) => _zones[name];

/// A zone named [name] with the constant UTC [offset] (no DST).
tz.Location fixedOffsetZone(String name, Duration offset) => tz.Location(
  name,
  [tz.minTime],
  [0],
  [tz.TimeZone(offset, isDst: false, abbreviation: name)],
);

/// The zone named [name], or a fixed-[offset] zone when the database
/// lacks that name.
tz.Location zoneOrFixedOffset(String name, Duration offset) =>
    zoneNamed(name) ?? fixedOffsetZone(name, offset);
