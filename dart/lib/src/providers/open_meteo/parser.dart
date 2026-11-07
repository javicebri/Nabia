/// Converts raw Open-Meteo responses into normalized series.
library;

import 'package:timezone/timezone.dart' as tz;

import '../../catalog/table.dart';
import '../../core/errors.dart';
import '../../core/models.dart';
import '../../core/time_zones.dart';
import '../../generated/catalog.g.dart';
import '../../generated/providers/open_meteo.g.dart';
import 'mapping.dart';
import 'schemas.dart';

const _provider = OpenMeteoContract.provider;

/// Builds an [HourlySeries] from a `timeformat=unixtime` response.
///
/// Unix timestamps are unambiguous UTC instants; they are expressed in
/// the response zone so local wall-clock time is preserved, including
/// daylight saving transitions. A zone name missing from the database
/// falls back to the fixed offset the response reports.
HourlySeries parseHourly(
  Object? json,
  VariableTable table,
  List<Variable> variables,
  Provenance provenance, {
  Surface? surface,
}) {
  final raw = OpenMeteoResponse.parse(json);
  final block = raw.hourly ?? (throw _missingBlock('hourly'));
  final values = table.extract(
    Resolution.hourly,
    variables,
    block.columns,
    raw.hourlyUnits,
    source: provenance.source,
  );
  final zone = zoneOrFixedOffset(
    raw.timezone,
    Duration(seconds: raw.utcOffsetSeconds),
  );
  final time = [
    for (final seconds in block.time)
      tz.TZDateTime.fromMillisecondsSinceEpoch(zone, seconds * 1000),
  ];
  _checkSeries(seriesProblem(time, values, surface, (a, b) => a.compareTo(b)));
  return HourlySeries(
    provider: _provider,
    dataset: table.dataset,
    location: _location(raw),
    elevation: raw.elevation,
    timezone: raw.timezone,
    time: time,
    values: values,
    source: provenance.source,
    sourceKind: provenance.sourceKind,
    attribution: OpenMeteoContract.attribution,
    surface: surface,
  );
}

/// Builds a [DailySeries] from a `timeformat=iso8601` response.
DailySeries parseDaily(
  Object? json,
  VariableTable table,
  List<Variable> variables,
  Provenance provenance,
) {
  final raw = OpenMeteoResponse.parse(json);
  final block = raw.daily ?? (throw _missingBlock('daily'));
  final values = table.extract(
    Resolution.daily,
    variables,
    block.columns,
    raw.dailyUnits,
    source: provenance.source,
  );
  _checkSeries(
    seriesProblem(block.time, values, null, (a, b) => a.compareTo(b)),
  );
  return DailySeries(
    provider: _provider,
    dataset: table.dataset,
    location: _location(raw),
    elevation: raw.elevation,
    timezone: raw.timezone,
    time: block.time,
    values: values,
    source: provenance.source,
    sourceKind: provenance.sourceKind,
    attribution: OpenMeteoContract.attribution,
  );
}

GeoPoint _location(OpenMeteoResponse raw) {
  if (raw.latitude.abs() > 90 || raw.longitude.abs() > 180) {
    throw ProviderContractException(
      '$_provider: response coordinates out of range',
      provider: _provider,
    );
  }
  return GeoPoint(latitude: raw.latitude, longitude: raw.longitude);
}

void _checkSeries(String? problem) {
  if (problem != null) {
    throw ProviderContractException(
      '$_provider: response cannot form a valid series: $problem',
      provider: _provider,
    );
  }
}

ProviderContractException _missingBlock(String name) =>
    ProviderContractException(
      "$_provider: response has no '$name' block",
      provider: _provider,
    );
