/// Capability interfaces for provider-agnostic code.
///
/// Type against a capability instead of a concrete client, so switching
/// providers is a one-line change:
///
/// ```dart
/// Future<DailySeries> rainfall(HistoricalDailyProvider source) =>
///     source.historicalDaily(point, [Variable.precipitation],
///         start: start, end: end);
/// ```
library;

import '../core/models.dart';
import '../generated/catalog.g.dart';

/// Provides hourly forecasts.
abstract interface class ForecastHourlyProvider {
  /// An hourly forecast for the next [days] days.
  Future<HourlySeries> forecastHourly(
    GeoPoint location,
    List<Variable> variables, {
    int days,
  });
}

/// Provides daily forecasts.
abstract interface class ForecastDailyProvider {
  /// A daily forecast for the next [days] days.
  Future<DailySeries> forecastDaily(
    GeoPoint location,
    List<Variable> variables, {
    int days,
  });
}

/// Provides hourly historical data.
abstract interface class HistoricalHourlyProvider {
  /// Hourly data from [start] to [end], inclusive.
  Future<HourlySeries> historicalHourly(
    GeoPoint location,
    List<Variable> variables, {
    required CalendarDate start,
    required CalendarDate end,
  });
}

/// Provides daily historical data.
abstract interface class HistoricalDailyProvider {
  /// Daily data from [start] to [end], inclusive.
  Future<DailySeries> historicalDaily(
    GeoPoint location,
    List<Variable> variables, {
    required CalendarDate start,
    required CalendarDate end,
  });
}
