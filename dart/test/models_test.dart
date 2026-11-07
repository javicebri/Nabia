import 'dart:convert';

import 'package:nabia/nabia.dart';
import 'package:nabia/src/core/models.dart' show formatOffsetDateTime;
import 'package:nabia/src/core/time_zones.dart';
import 'package:test/test.dart';
import 'package:timezone/timezone.dart' as tz;

final _madrid = GeoPoint(latitude: 40.42, longitude: -3.7);

DailySeries _daily({
  List<CalendarDate>? time,
  Map<Variable, List<double?>>? values,
}) => DailySeries(
  provider: 'p',
  dataset: 'd',
  location: _madrid,
  timezone: 'Europe/Madrid',
  time: time ?? [CalendarDate(2024, 3, 30), CalendarDate(2024, 3, 31)],
  values:
      values ??
      {
        Variable.precipitation: [1.5, null],
      },
);

void main() {
  group('CalendarDate', () {
    test('parses and prints ISO 8601', () {
      final date = CalendarDate.parse('2024-02-29');
      expect(date, CalendarDate(2024, 2, 29));
      expect('$date', '2024-02-29');
      expect('${CalendarDate(987, 1, 2)}', '0987-01-02');
    });

    test('rejects dates that do not exist or other formats', () {
      expect(() => CalendarDate(2023, 2, 29), throwsArgumentError);
      expect(() => CalendarDate(0, 1, 1), throwsArgumentError);
      for (final text in ['2023-02-29', '2024-3-1', '2024-03-01T00:00']) {
        expect(() => CalendarDate.parse(text), throwsFormatException);
      }
    });

    test('orders chronologically', () {
      final dates = [
        CalendarDate(2024, 3, 1),
        CalendarDate(2023, 12, 31),
        CalendarDate(2024, 2, 29),
      ]..sort();
      expect(dates.map((d) => '$d'), [
        '2023-12-31',
        '2024-02-29',
        '2024-03-01',
      ]);
      expect(dates.first.isBefore(dates.last), isTrue);
      expect(dates.last.isAfter(dates.first), isTrue);
    });
  });

  group('GeoPoint and Surface', () {
    test('reject values out of range, NaN included', () {
      expect(() => GeoPoint(latitude: 91, longitude: 0), throwsArgumentError);
      expect(
        () => GeoPoint(latitude: 0, longitude: double.nan),
        throwsArgumentError,
      );
      expect(() => Surface(tilt: -1, aspect: 0), throwsArgumentError);
      expect(() => Surface(tilt: 0, aspect: 360), throwsArgumentError);
      expect(Surface(tilt: 90, aspect: 359.9).tilt, 90);
    });

    test('compare by value', () {
      expect(_madrid, GeoPoint(latitude: 40.42, longitude: -3.7));
      expect(
        Surface(tilt: 30, aspect: 180).hashCode,
        Surface(tilt: 30, aspect: 180).hashCode,
      );
    });
  });

  group('series', () {
    test('derive units from the catalog and are unmodifiable', () {
      final series = _daily();
      expect(series.units, {Variable.precipitation: Unit.millimetre});
      expect(series.variables, [Variable.precipitation]);
      expect(
        () => series.time.add(CalendarDate(2024, 4, 1)),
        throwsUnsupportedError,
      );
      expect(
        () => series.values[Variable.precipitation]![0] = 3,
        throwsUnsupportedError,
      );
    });

    test('reject inconsistent data', () {
      expect(
        () => _daily(
          values: {
            Variable.precipitation: [1.0],
          },
        ),
        throwsA(
          isA<ArgumentError>().having(
            (e) => '$e',
            'message',
            contains('aligned'),
          ),
        ),
      );
      expect(
        () => _daily(
          time: [CalendarDate(2024, 3, 31), CalendarDate(2024, 3, 30)],
        ),
        throwsA(
          isA<ArgumentError>().having(
            (e) => '$e',
            'message',
            contains('increasing'),
          ),
        ),
      );
      expect(
        () => _daily(
          values: {
            Variable.shortwaveRadiationTilted: [1.0, 2.0],
          },
        ),
        throwsA(
          isA<ArgumentError>().having(
            (e) => '$e',
            'message',
            contains('surface'),
          ),
        ),
      );
    });

    test('JSON round trip keeps everything', () {
      final series = _daily();
      final json =
          jsonDecode(jsonEncode(series.toJson())) as Map<String, Object?>;
      expect(json['units'], {'precipitation': 'mm'});
      expect(json['resolution'], 'daily');
      expect(TimeSeries.fromJson(json), series);
    });

    test('fromJson rejects unknown fields, wrong units and bad offsets', () {
      final json = _daily().toJson();
      expect(
        () => TimeSeries.fromJson({...json, 'extra': 1}),
        throwsFormatException,
      );
      expect(
        () => TimeSeries.fromJson({
          ...json,
          'units': {'precipitation': 'in'},
        }),
        throwsFormatException,
      );
      expect(
        () => TimeSeries.fromJson({...json, 'resolution': 'weekly'}),
        throwsFormatException,
      );
      final hourly = {
        ...json,
        'resolution': 'hourly',
        // Madrid is +02:00 in summer: +01:00 contradicts the zone.
        'time': ['2024-07-01T00:00:00+01:00', '2024-07-01T01:00:00+01:00'],
      };
      expect(() => TimeSeries.fromJson(hourly), throwsFormatException);
    });
  });

  group('timestamps', () {
    test('format like Python isoformat, offset seconds included', () {
      final madrid = zoneNamed('Europe/Madrid')!;
      final summer = tz.TZDateTime.utc(2024, 7, 1, 10);
      expect(
        formatOffsetDateTime(tz.TZDateTime.from(summer, madrid)),
        '2024-07-01T12:00:00+02:00',
      );
      expect(
        formatOffsetDateTime(tz.TZDateTime.from(summer, zoneNamed('UTC')!)),
        '2024-07-01T10:00:00+00:00',
      );
      // Liberia kept local mean time (-00:44:30) until 1972.
      final monrovia = zoneNamed('Africa/Monrovia')!;
      expect(
        formatOffsetDateTime(
          tz.TZDateTime.from(tz.TZDateTime.utc(1960, 1, 1, 12), monrovia),
        ),
        '1960-01-01T11:15:30-00:44:30',
      );
    });

    test('unknown zones fall back to a fixed offset', () {
      expect(zoneNamed('Unknown/Zone'), isNull);
      final zone = zoneOrFixedOffset('Unknown/Zone', const Duration(hours: 1));
      final summer = tz.TZDateTime.from(tz.TZDateTime.utc(2024, 7, 1), zone);
      expect(summer.timeZoneOffset, const Duration(hours: 1));
    });
  });
}
