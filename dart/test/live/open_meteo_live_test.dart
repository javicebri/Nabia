// Contract tests against the real Open-Meteo API, mirroring the
// Python live tests: every mapped variable is requested, so a renamed
// variable, a changed unit or a new response structure fails here.
// Run with: dart test --run-skipped -t live
@Tags(['live'])
library;

import 'package:nabia/nabia.dart';
import 'package:test/test.dart';

final _madrid = GeoPoint(latitude: 40.42, longitude: -3.7);
final _start = CalendarDate(2024, 3, 30);
final _end = CalendarDate(2024, 3, 31);
final _slope = Surface(tilt: 30, aspect: 180);

void main() {
  late OpenMeteoClient client;
  setUp(() => client = OpenMeteoClient());
  tearDown(() => client.close());

  final forecast = OpenMeteoClient.forecastTable;
  final archive = OpenMeteoClient.archiveTable;

  test('forecast hourly', () async {
    final variables = forecast.supported(Resolution.hourly).toList();
    final series = await client.forecastHourly(
      _madrid,
      variables,
      days: 1,
      surface: _slope,
    );
    expect(series.time, hasLength(24));
    expect(series.variables, variables);
    expect(series.sourceKind, SourceKind.forecast);
  });

  test('forecast daily', () async {
    final variables = forecast.supported(Resolution.daily).toList();
    final series = await client.forecastDaily(_madrid, variables, days: 2);
    expect(series.time, hasLength(2));
    expect(series.variables, variables);
  });

  test('archive hourly across the DST change', () async {
    final variables = archive.supported(Resolution.hourly).toList();
    final series = await client.historicalHourly(
      _madrid,
      variables,
      start: _start,
      end: _end,
      surface: _slope,
    );
    expect(series.time, hasLength(48)); // as the Python live test
    expect(series.variables, variables);
    expect(series.time.first.timeZoneOffset, const Duration(hours: 1));
    expect(series.time.last.timeZoneOffset, const Duration(hours: 2));
  });

  test('archive daily with an explicit model', () async {
    final variables = archive.supported(Resolution.daily).toList();
    final series = await client.historicalDaily(
      _madrid,
      variables,
      start: _start,
      end: _end,
      model: 'era5',
    );
    expect(series.time, [_start, _end]);
    expect(series.variables, variables);
    expect(series.sourceKind, SourceKind.reanalysis);
  });
}
