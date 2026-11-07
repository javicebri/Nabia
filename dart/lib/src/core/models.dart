/// Normalized, provider-independent output models.
///
/// These models are the stable contract shared with the Python
/// reference: canonical variable names, canonical units and timestamps
/// that keep their UTC offset. [TimeSeries.toJson] produces exactly the
/// JSON the Python models serialize to, and [TimeSeries.fromJson] reads
/// it back.
library;

import 'dart:convert';

import 'package:timezone/timezone.dart' as tz;

import '../generated/catalog.g.dart';
import 'time_zones.dart';

/// WGS84 coordinates in decimal degrees.
final class GeoPoint {
  /// Creates a point; throws an [ArgumentError] when out of range.
  GeoPoint({required this.latitude, required this.longitude}) {
    _throwIfProblem(_problem(latitude, longitude));
  }

  /// Reads the JSON form produced by [toJson].
  ///
  /// Throws a [FormatException] for invalid data.
  factory GeoPoint.fromJson(Map<String, Object?> json) {
    final reader = _JsonReader(json, 'location');
    final latitude = reader.number('latitude');
    final longitude = reader.number('longitude');
    reader.done();
    _formatIfProblem(_problem(latitude, longitude));
    return GeoPoint(latitude: latitude, longitude: longitude);
  }

  /// Latitude, from -90 to 90.
  final double latitude;

  /// Longitude, from -180 to 180.
  final double longitude;

  static String? _problem(double latitude, double longitude) =>
      _intervalProblem(latitude, 'latitude', -90, 90) ??
      _intervalProblem(longitude, 'longitude', -180, 180);

  /// JSON form, as serialized by the Python reference.
  Map<String, Object?> toJson() => {
    'latitude': latitude,
    'longitude': longitude,
  };

  @override
  bool operator ==(Object other) =>
      other is GeoPoint &&
      other.latitude == latitude &&
      other.longitude == longitude;

  @override
  int get hashCode => Object.hash(latitude, longitude);

  @override
  String toString() => 'GeoPoint($latitude, $longitude)';
}

/// Inclined surface, e.g. a slope, for plane-of-array variables.
final class Surface {
  /// Creates a surface; throws an [ArgumentError] when out of range.
  ///
  /// [tilt] is the inclination from the horizontal in degrees (0 =
  /// flat, 90 = vertical). [aspect] is the compass direction the
  /// surface faces, in degrees clockwise from north (0 = north, 90 =
  /// east, 180 = south, 270 = west); providers' own conventions are
  /// translated.
  Surface({required this.tilt, required this.aspect}) {
    _throwIfProblem(_problem(tilt, aspect));
  }

  /// Reads the JSON form produced by [toJson].
  ///
  /// Throws a [FormatException] for invalid data.
  factory Surface.fromJson(Map<String, Object?> json) {
    final reader = _JsonReader(json, 'surface');
    final tilt = reader.number('tilt');
    final aspect = reader.number('aspect');
    reader.done();
    _formatIfProblem(_problem(tilt, aspect));
    return Surface(tilt: tilt, aspect: aspect);
  }

  /// Inclination from the horizontal in degrees, from 0 to 90.
  final double tilt;

  /// Compass direction faced, in degrees: 0 <= aspect < 360.
  final double aspect;

  static String? _problem(double tilt, double aspect) =>
      _intervalProblem(tilt, 'tilt', 0, 90) ??
      _intervalProblem(aspect, 'aspect', 0, 360, maxInclusive: false);

  /// JSON form, as serialized by the Python reference.
  Map<String, Object?> toJson() => {'tilt': tilt, 'aspect': aspect};

  @override
  bool operator ==(Object other) =>
      other is Surface && other.tilt == tilt && other.aspect == aspect;

  @override
  int get hashCode => Object.hash(tilt, aspect);

  @override
  String toString() => 'Surface(tilt: $tilt, aspect: $aspect)';
}

/// A day in the calendar, without time or time zone.
///
/// Dart has no date type; [DateTime] always carries a time and a zone,
/// which invites off-by-one-day errors for daily data.
final class CalendarDate implements Comparable<CalendarDate> {
  /// Creates a date; throws an [ArgumentError] if it does not exist.
  factory CalendarDate(int year, int month, int day) {
    _throwIfProblem(_problem(year, month, day));
    return CalendarDate._(year, month, day);
  }

  const CalendarDate._(this.year, this.month, this.day);

  /// Parses an ISO 8601 date (`YYYY-MM-DD`).
  ///
  /// Throws a [FormatException] for any other text.
  static CalendarDate parse(String text) {
    final match = _isoDate.firstMatch(text);
    if (match == null) {
      throw FormatException('Not an ISO 8601 date (YYYY-MM-DD)', text);
    }
    final year = int.parse(match[1]!);
    final month = int.parse(match[2]!);
    final day = int.parse(match[3]!);
    final problem = _problem(year, month, day);
    if (problem != null) throw FormatException(problem, text);
    return CalendarDate._(year, month, day);
  }

  static final _isoDate = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$');

  /// Year, from 1 to 9999.
  final int year;

  /// Month, from 1 to 12.
  final int month;

  /// Day of the month, from 1.
  final int day;

  static String? _problem(int year, int month, int day) {
    if (year < 1 || year > 9999) return 'Year $year out of range 1-9999';
    final date = DateTime.utc(year, month, day);
    if (date.year != year || date.month != month || date.day != day) {
      return 'Date $year-$month-$day does not exist';
    }
    return null;
  }

  /// Whether this date comes before [other].
  bool isBefore(CalendarDate other) => compareTo(other) < 0;

  /// Whether this date comes after [other].
  bool isAfter(CalendarDate other) => compareTo(other) > 0;

  @override
  int compareTo(CalendarDate other) {
    if (year != other.year) return year.compareTo(other.year);
    if (month != other.month) return month.compareTo(other.month);
    return day.compareTo(other.day);
  }

  @override
  bool operator ==(Object other) =>
      other is CalendarDate &&
      other.year == year &&
      other.month == month &&
      other.day == day;

  @override
  int get hashCode => Object.hash(year, month, day);

  /// ISO 8601 form (`YYYY-MM-DD`).
  @override
  String toString() => '${_pad(year, 4)}-${_pad(month, 2)}-${_pad(day, 2)}';
}

/// Column-oriented series of canonical variables at one location.
///
/// [HourlySeries] and [DailySeries] are the only kinds. Every column in
/// [values] is aligned with [time]; `null` marks a missing value.
sealed class TimeSeries<T extends Object> {
  TimeSeries._({
    required this.provider,
    required this.dataset,
    required this.location,
    required this.timezone,
    required List<T> time,
    required Map<Variable, List<double?>> values,
    this.elevation,
    this.source,
    this.sourceKind,
    this.attribution,
    this.surface,
  }) : time = List.unmodifiable(time),
       values = Map.unmodifiable({
         for (final MapEntry(:key, :value) in values.entries)
           key: List<double?>.unmodifiable(value),
       }) {
    _throwIfProblem(seriesProblem(this.time, this.values, surface, _compare));
  }

  /// Reads the JSON form produced by [toJson] (or by the Python
  /// reference), dispatching on its `resolution`.
  ///
  /// Throws a [FormatException] for invalid data.
  static TimeSeries<Object> fromJson(Map<String, Object?> json) =>
      switch (json['resolution']) {
        'hourly' => HourlySeries.fromJson(json),
        'daily' => DailySeries.fromJson(json),
        final other => throw FormatException('Unknown resolution: $other'),
      };

  /// Provider identifier (e.g. `open_meteo`).
  final String provider;

  /// Dataset or endpoint within the provider.
  final String dataset;

  /// Coordinates the data refer to (grid cell or station); they may
  /// differ from the requested point.
  final GeoPoint location;

  /// Altitude in metres the provider associates with the data, if
  /// known. Its meaning depends on the provider (see its README).
  final double? elevation;

  /// Time zone name used for timestamps and daily bounds, as the
  /// provider reported it.
  final String timezone;

  /// Strictly increasing time axis.
  final List<T> time;

  /// Canonical variable to values aligned with [time], in request
  /// order; `null` marks a missing value.
  final Map<Variable, List<double?>> values;

  /// Model, product or station that produced the data, when known for
  /// certain.
  final String? source;

  /// Nature of the data, when it holds for the whole series.
  final SourceKind? sourceKind;

  /// Credit line the provider's licence requires applications to
  /// display, if any.
  final String? attribution;

  /// Inclined surface that tilted variables refer to.
  final Surface? surface;

  /// Temporal resolution of the series.
  Resolution get resolution;

  /// Variables present in the series, in request order.
  List<Variable> get variables => List.unmodifiable(values.keys);

  /// Canonical unit of each variable.
  Map<Variable, Unit> get units => Map.unmodifiable({
    for (final variable in values.keys) variable: variable.unit,
  });

  int _compare(T a, T b);

  Object _encodeTime(T time);

  /// JSON form, identical to the Python reference's serialization.
  Map<String, Object?> toJson() => {
    'provider': provider,
    'dataset': dataset,
    'location': location.toJson(),
    'elevation': elevation,
    'timezone': timezone,
    'time': [for (final t in time) _encodeTime(t)],
    'values': {
      for (final MapEntry(:key, :value) in values.entries) key.key: value,
    },
    'units': {
      for (final variable in values.keys) variable.key: variable.unit.symbol,
    },
    'source': source,
    'source_kind': sourceKind?.key,
    'attribution': attribution,
    'surface': surface?.toJson(),
    'resolution': resolution.key,
  };

  @override
  bool operator ==(Object other) =>
      other is TimeSeries &&
      other.resolution == resolution &&
      jsonEncode(other.toJson()) == jsonEncode(toJson());

  @override
  int get hashCode => jsonEncode(toJson()).hashCode;
}

/// Hourly series; timestamps keep the zone and UTC offset of
/// [TimeSeries.timezone].
final class HourlySeries extends TimeSeries<tz.TZDateTime> {
  /// Creates a series; throws an [ArgumentError] if it is inconsistent
  /// (see [seriesProblem]).
  HourlySeries({
    required super.provider,
    required super.dataset,
    required super.location,
    required super.timezone,
    required super.time,
    required super.values,
    super.elevation,
    super.source,
    super.sourceKind,
    super.attribution,
    super.surface,
  }) : super._();

  /// Reads the JSON form produced by [toJson].
  ///
  /// Throws a [FormatException] for invalid data.
  factory HourlySeries.fromJson(Map<String, Object?> json) {
    final fields = _SeriesFields.read(json, Resolution.hourly);
    final stamps = [
      for (final item in fields.rawTime) _parseOffsetDateTime(_timeText(item)),
    ];
    final zone = zoneOrFixedOffset(
      fields.timezone,
      stamps.isEmpty ? Duration.zero : stamps.first.offset,
    );
    final time = <tz.TZDateTime>[];
    for (final stamp in stamps) {
      final local = tz.TZDateTime.fromMicrosecondsSinceEpoch(
        zone,
        stamp.instant.microsecondsSinceEpoch,
      );
      if (local.timeZoneOffset != stamp.offset) {
        throw FormatException(
          'time: offset does not match zone ${fields.timezone}',
          stamp.text,
        );
      }
      time.add(local);
    }
    _formatIfProblem(
      seriesProblem(time, fields.values, fields.surface, _compareInstants),
    );
    return HourlySeries(
      provider: fields.provider,
      dataset: fields.dataset,
      location: fields.location,
      timezone: fields.timezone,
      time: time,
      values: fields.values,
      elevation: fields.elevation,
      source: fields.source,
      sourceKind: fields.sourceKind,
      attribution: fields.attribution,
      surface: fields.surface,
    );
  }

  @override
  Resolution get resolution => Resolution.hourly;

  @override
  int _compare(tz.TZDateTime a, tz.TZDateTime b) => _compareInstants(a, b);

  @override
  Object _encodeTime(tz.TZDateTime time) => formatOffsetDateTime(time);
}

/// Daily series; each date is a calendar day in
/// [TimeSeries.timezone].
final class DailySeries extends TimeSeries<CalendarDate> {
  /// Creates a series; throws an [ArgumentError] if it is inconsistent
  /// (see [seriesProblem]).
  DailySeries({
    required super.provider,
    required super.dataset,
    required super.location,
    required super.timezone,
    required super.time,
    required super.values,
    super.elevation,
    super.source,
    super.sourceKind,
    super.attribution,
    super.surface,
  }) : super._();

  /// Reads the JSON form produced by [toJson].
  ///
  /// Throws a [FormatException] for invalid data.
  factory DailySeries.fromJson(Map<String, Object?> json) {
    final fields = _SeriesFields.read(json, Resolution.daily);
    final time = [
      for (final item in fields.rawTime) CalendarDate.parse(_timeText(item)),
    ];
    _formatIfProblem(
      seriesProblem(time, fields.values, fields.surface, _compareDates),
    );
    return DailySeries(
      provider: fields.provider,
      dataset: fields.dataset,
      location: fields.location,
      timezone: fields.timezone,
      time: time,
      values: fields.values,
      elevation: fields.elevation,
      source: fields.source,
      sourceKind: fields.sourceKind,
      attribution: fields.attribution,
      surface: fields.surface,
    );
  }

  @override
  Resolution get resolution => Resolution.daily;

  @override
  int _compare(CalendarDate a, CalendarDate b) => _compareDates(a, b);

  @override
  Object _encodeTime(CalendarDate time) => time.toString();
}

/// Why a series would be inconsistent, or `null` if it is valid.
///
/// Rules shared with the Python reference: a tilted variable needs the
/// [surface], every column has the length of [time], and [time] is
/// strictly increasing according to [compare].
String? seriesProblem<T>(
  List<T> time,
  Map<Variable, List<double?>> values,
  Surface? surface,
  int Function(T a, T b) compare,
) {
  if (values.containsKey(Variable.shortwaveRadiationTilted) &&
      surface == null) {
    return 'Tilted variables require the surface';
  }
  final size = time.length;
  final misaligned = [
    for (final MapEntry(:key, :value) in values.entries)
      if (value.length != size) key.key,
  ];
  if (misaligned.isNotEmpty) {
    return 'Columns not aligned with the time axis ($size): '
        '${misaligned.join(', ')}';
  }
  for (var i = 1; i < size; i++) {
    if (compare(time[i - 1], time[i]) >= 0) {
      return 'Time axis must be strictly increasing';
    }
  }
  return null;
}

/// ISO 8601 form with UTC offset, as Python's `isoformat()` writes it:
/// `2024-03-31T03:00:00+02:00` (fraction and offset seconds only when
/// not zero).
String formatOffsetDateTime(tz.TZDateTime time) {
  final buffer = StringBuffer()
    ..write('${_pad(time.year, 4)}-${_pad(time.month, 2)}-')
    ..write('${_pad(time.day, 2)}T${_pad(time.hour, 2)}:')
    ..write('${_pad(time.minute, 2)}:${_pad(time.second, 2)}');
  final micros = time.millisecond * 1000 + time.microsecond;
  if (micros != 0) buffer.write('.${_pad(micros, 6)}');
  final offset = time.timeZoneOffset;
  final seconds = offset.inSeconds.abs();
  buffer
    ..write(offset.isNegative ? '-' : '+')
    ..write('${_pad(seconds ~/ 3600, 2)}:${_pad(seconds % 3600 ~/ 60, 2)}');
  if (seconds % 60 != 0) buffer.write(':${_pad(seconds % 60, 2)}');
  return buffer.toString();
}

// -- private helpers ------------------------------------------------------

int _compareInstants(tz.TZDateTime a, tz.TZDateTime b) => a.compareTo(b);

int _compareDates(CalendarDate a, CalendarDate b) => a.compareTo(b);

String _pad(int value, int width) => value.toString().padLeft(width, '0');

String? _intervalProblem(
  double value,
  String name,
  double min,
  double max, {
  bool maxInclusive = true,
}) {
  final inside = value >= min && (maxInclusive ? value <= max : value < max);
  if (inside) return null;
  final upper = maxInclusive ? '<= $max' : '< $max';
  return '$name must be >= $min and $upper, got $value';
}

void _throwIfProblem(String? problem) {
  if (problem != null) throw ArgumentError(problem);
}

void _formatIfProblem(String? problem) {
  if (problem != null) throw FormatException(problem);
}

String _timeText(Object? item) {
  if (item is String) return item;
  throw FormatException('time: expected strings, got $item');
}

final _offsetDateTime = RegExp(
  r'^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?'
  r'([+-])(\d{2}):(\d{2})(?::(\d{2}))?$',
);

typedef _Stamp = ({DateTime instant, Duration offset, String text});

_Stamp _parseOffsetDateTime(String text) {
  final match = _offsetDateTime.firstMatch(text);
  if (match == null) {
    throw FormatException('time: not an ISO 8601 time with offset', text);
  }
  int part(int group) => int.parse(match[group] ?? '0');
  final fraction = (match[7] ?? '').padRight(6, '0');
  final wall = DateTime.utc(
    part(1),
    part(2),
    part(3),
    part(4),
    part(5),
    part(6),
    0,
    int.parse(fraction.isEmpty ? '0' : fraction),
  );
  if (wall.year != part(1) ||
      wall.month != part(2) ||
      wall.day != part(3) ||
      wall.hour != part(4) ||
      wall.minute != part(5) ||
      wall.second != part(6)) {
    throw FormatException('time: invalid date or time', text);
  }
  final magnitude = Duration(
    hours: part(9),
    minutes: part(10),
    seconds: part(11),
  );
  final offset = match[8] == '-' ? -magnitude : magnitude;
  return (instant: wall.subtract(offset), offset: offset, text: text);
}

/// Fields shared by both series kinds, read and checked from JSON.
final class _SeriesFields {
  _SeriesFields._(this._reader);

  factory _SeriesFields.read(Map<String, Object?> json, Resolution expected) {
    final fields = _SeriesFields._(_JsonReader(json, 'series'));
    final reader = fields._reader;
    final resolution = reader.optionalString('resolution');
    if (resolution != null && resolution != expected.key) {
      throw FormatException(
        'series: resolution $resolution, expected '
        '${expected.key}',
      );
    }
    fields
      ..provider = reader.string('provider')
      ..dataset = reader.string('dataset')
      ..location = GeoPoint.fromJson(reader.object('location'))
      ..elevation = reader.optionalNumber('elevation')
      ..timezone = reader.string('timezone')
      ..rawTime = reader.list('time')
      ..values = _readValues(reader.object('values'))
      ..source = reader.optionalString('source')
      ..attribution = reader.optionalString('attribution');
    final kind = reader.optionalString('source_kind');
    fields.sourceKind = kind == null ? null : _sourceKind(kind);
    final surface = reader.optionalObject('surface');
    fields.surface = surface == null ? null : Surface.fromJson(surface);
    final units = reader.optionalObject('units');
    if (units != null) _checkUnits(units, fields.values);
    reader.done();
    return fields;
  }

  final _JsonReader _reader;
  late final String provider;
  late final String dataset;
  late final GeoPoint location;
  late final double? elevation;
  late final String timezone;
  late final List<Object?> rawTime;
  late final Map<Variable, List<double?>> values;
  late final String? source;
  late final SourceKind? sourceKind;
  late final String? attribution;
  late final Surface? surface;

  static Map<Variable, List<double?>> _readValues(Map<String, Object?> json) {
    final values = <Variable, List<double?>>{};
    for (final MapEntry(:key, :value) in json.entries) {
      final variable = _variable(key);
      if (value is! List<Object?>) {
        throw FormatException('values.$key: expected a list');
      }
      values[variable] = [
        for (final item in value)
          switch (item) {
            null => null,
            num() => item.toDouble(),
            _ => throw FormatException('values.$key: expected numbers'),
          },
      ];
    }
    return values;
  }

  static void _checkUnits(
    Map<String, Object?> units,
    Map<Variable, List<double?>> values,
  ) {
    final expected = {
      for (final variable in values.keys) variable.key: variable.unit.symbol,
    };
    final same =
        units.length == expected.length &&
        expected.entries.every((e) => units[e.key] == e.value);
    if (!same) {
      throw FormatException(
        'units must match the canonical catalog: expected $expected, '
        'got $units',
      );
    }
  }

  static Variable _variable(String key) {
    for (final variable in Variable.values) {
      if (variable.key == key) return variable;
    }
    throw FormatException('Unknown variable: $key');
  }

  static SourceKind _sourceKind(String key) {
    for (final kind in SourceKind.values) {
      if (kind.key == key) return kind;
    }
    throw FormatException('Unknown source kind: $key');
  }
}

/// Typed access to a decoded JSON object, rejecting unknown fields.
final class _JsonReader {
  _JsonReader(this._json, this._context);

  final Map<String, Object?> _json;
  final String _context;
  final _seen = <String>{};

  Object? _optional(String key) {
    _seen.add(key);
    return _json[key];
  }

  Object _required(String key) =>
      _optional(key) ??
      (throw FormatException('$_context: missing or null "$key"'));

  FormatException _wrong(String key, String expected) =>
      FormatException('$_context: "$key" must be $expected');

  String string(String key) => switch (_required(key)) {
    final String value => value,
    _ => throw _wrong(key, 'a string'),
  };

  String? optionalString(String key) => switch (_optional(key)) {
    null => null,
    final String value => value,
    _ => throw _wrong(key, 'a string or null'),
  };

  double number(String key) => switch (_required(key)) {
    final num value => value.toDouble(),
    _ => throw _wrong(key, 'a number'),
  };

  double? optionalNumber(String key) => switch (_optional(key)) {
    null => null,
    final num value => value.toDouble(),
    _ => throw _wrong(key, 'a number or null'),
  };

  Map<String, Object?> object(String key) => switch (_required(key)) {
    final Map<String, Object?> value => value,
    _ => throw _wrong(key, 'an object'),
  };

  Map<String, Object?>? optionalObject(String key) => switch (_optional(key)) {
    null => null,
    final Map<String, Object?> value => value,
    _ => throw _wrong(key, 'an object or null'),
  };

  List<Object?> list(String key) => switch (_required(key)) {
    final List<Object?> value => value,
    _ => throw _wrong(key, 'a list'),
  };

  void done() {
    final unknown = _json.keys.where((key) => !_seen.contains(key)).toList();
    if (unknown.isNotEmpty) {
      throw FormatException('$_context: unknown fields ${unknown.join(', ')}');
    }
  }
}
