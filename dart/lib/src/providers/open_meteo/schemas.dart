/// Raw Open-Meteo response, mirroring the upstream JSON.
///
/// Only the fields Nabia relies on are read. Unknown top-level fields
/// are ignored, so additive upstream changes do not break parsing,
/// while missing or retyped fields throw a contract exception.
library;

import '../../core/errors.dart';
import '../../core/models.dart';

const _provider = 'open_meteo';

/// Time axis plus one column per requested variable.
final class Block<T> {
  Block._(this.time, this.columns);

  /// Time axis.
  final List<T> time;

  /// Variable columns keyed by native name.
  final Map<String, List<double?>> columns;
}

/// Successful forecast or archive response.
final class OpenMeteoResponse {
  OpenMeteoResponse._({
    required this.latitude,
    required this.longitude,
    required this.elevation,
    required this.timezone,
    required this.utcOffsetSeconds,
    required this.hourlyUnits,
    required this.hourly,
    required this.dailyUnits,
    required this.daily,
  });

  /// Validates a decoded JSON body.
  ///
  /// Throws a [ProviderContractException] when the structure differs.
  factory OpenMeteoResponse.parse(Object? json) {
    final root = _object(json, '<root>');
    return OpenMeteoResponse._(
      latitude: _number(root, 'latitude'),
      longitude: _number(root, 'longitude'),
      elevation: _optionalNumber(root, 'elevation'),
      timezone: _string(root, 'timezone'),
      utcOffsetSeconds: _int(root, 'utc_offset_seconds', 'utc_offset_seconds'),
      hourlyUnits: _units(root, 'hourly_units'),
      hourly: _block(root, 'hourly', (item, path) => _int(item, null, path)),
      dailyUnits: _units(root, 'daily_units'),
      daily: _block(root, 'daily', _date),
    );
  }

  /// Latitude of the grid cell.
  final double latitude;

  /// Longitude of the grid cell.
  final double longitude;

  /// Terrain altitude Open-Meteo used, in metres.
  final double? elevation;

  /// Zone name of the timestamps.
  final String timezone;

  /// UTC offset of the zone at the start of the data.
  final int utcOffsetSeconds;

  /// Unit of each hourly column.
  final Map<String, String>? hourlyUnits;

  /// Hourly block, requested with `timeformat=unixtime`.
  final Block<int>? hourly;

  /// Unit of each daily column.
  final Map<String, String>? dailyUnits;

  /// Daily block, requested with `timeformat=iso8601`.
  final Block<CalendarDate>? daily;
}

/// Reason of an Open-Meteo error payload (`{"error": true, "reason"}`).
String? errorReason(Object? json) {
  if (json is Map<String, Object?> && json['error'] is bool) {
    final reason = json['reason'];
    if (reason is String) return reason;
  }
  return null;
}

ProviderContractException _invalid(String path, String expected) =>
    ProviderContractException(
      '$_provider: unexpected response structure: $path must be $expected',
      provider: _provider,
    );

Map<String, Object?> _object(Object? value, String path) =>
    value is Map<String, Object?> ? value : throw _invalid(path, 'an object');

String _string(Map<String, Object?> json, String key) => switch (json[key]) {
  final String value => value,
  _ => throw _invalid(key, 'a string'),
};

double _number(Map<String, Object?> json, String key) => switch (json[key]) {
  final num value => value.toDouble(),
  _ => throw _invalid(key, 'a number'),
};

double? _optionalNumber(Map<String, Object?> json, String key) =>
    switch (json[key]) {
      null => null,
      final num value => value.toDouble(),
      _ => throw _invalid(key, 'a number or null'),
    };

int _int(Object? source, String? key, String path) {
  final value = key == null ? source : _object(source, '<root>')[key];
  if (value is int) return value;
  if (value is double && value == value.truncateToDouble()) {
    return value.toInt();
  }
  throw _invalid(path, 'an integer');
}

CalendarDate _date(Object? value, String path) {
  if (value is String) {
    try {
      return CalendarDate.parse(value);
    } on FormatException {
      // Reported below with the path of the offending item.
    }
  }
  throw _invalid(path, 'an ISO 8601 date');
}

Map<String, String>? _units(Map<String, Object?> json, String key) {
  final value = json[key];
  if (value == null) return null;
  final units = _object(value, key);
  return {
    for (final MapEntry(key: name, :value) in units.entries)
      name: value is String ? value : throw _invalid('$key.$name', 'a string'),
  };
}

Block<T>? _block<T>(
  Map<String, Object?> json,
  String key,
  T Function(Object? item, String path) parseTime,
) {
  final value = json[key];
  if (value == null) return null;
  final block = _object(value, key);
  final rawTime = block['time'];
  if (rawTime is! List<Object?>) throw _invalid('$key.time', 'a list');
  final time = [
    for (final (index, item) in rawTime.indexed)
      parseTime(item, '$key.time.$index'),
  ];
  final columns = <String, List<double?>>{};
  for (final MapEntry(key: name, value: column) in block.entries) {
    if (name == 'time') continue;
    if (column is! List<Object?>) {
      throw _invalid('$key.$name', 'a list of numbers or null');
    }
    columns[name] = [
      for (final (index, item) in column.indexed)
        switch (item) {
          null => null,
          final num number => number.toDouble(),
          _ => throw _invalid('$key.$name.$index', 'a number or null'),
        },
    ];
  }
  return Block._(time, columns);
}
