/// Open-Meteo client: weather forecast and historical weather.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../catalog/table.dart';
import '../../core/http.dart';
import '../../core/models.dart';
import '../../generated/catalog.g.dart';
import '../../generated/providers/open_meteo.g.dart';
import '../capabilities.dart';
import 'mapping.dart';
import 'parser.dart';
import 'schemas.dart';

/// Endpoints of the Open-Meteo APIs.
///
/// Override them to use a self-hosted Open-Meteo instance; they must
/// use HTTPS.
final class OpenMeteoEndpoints {
  /// Creates the endpoints; the defaults are the public APIs.
  const OpenMeteoEndpoints({
    this.forecastUrl = OpenMeteoContract.forecastUrl,
    this.archiveUrl = OpenMeteoContract.archiveUrl,
  });

  /// Weather forecast endpoint.
  final String forecastUrl;

  /// Historical weather (reanalysis) endpoint.
  final String archiveUrl;
}

/// Client for the Open-Meteo forecast and historical weather APIs.
///
/// The public endpoints need no API key for non-commercial use. Show
/// [attribution] (also in every series) wherever the data are
/// displayed: the CC BY 4.0 licence requires it.
///
/// ```dart
/// final client = OpenMeteoClient();
/// try {
///   final series = await client.forecastDaily(
///     GeoPoint(latitude: 40.42, longitude: -3.70),
///     [Variable.precipitation, Variable.rain],
///   );
/// } finally {
///   client.close();
/// }
/// ```
final class OpenMeteoClient
    implements
        ForecastHourlyProvider,
        ForecastDailyProvider,
        HistoricalHourlyProvider,
        HistoricalDailyProvider {
  /// Creates a client.
  ///
  /// Pass [httpClient] to share connections or to plug in the app's own
  /// client; its owner keeps closing it. Throws an [ArgumentError] for
  /// non-HTTPS [endpoints] or invalid [options].
  OpenMeteoClient({
    OpenMeteoEndpoints endpoints = const OpenMeteoEndpoints(),
    HttpOptions options = const HttpOptions(),
    http.Client? httpClient,
  }) : _forecastUrl = _httpsUri(endpoints.forecastUrl, 'forecastUrl'),
       _archiveUrl = _httpsUri(endpoints.archiveUrl, 'archiveUrl'),
       _http = ProviderHttp(
         provider: provider,
         options: options,
         client: httpClient,
         errorParser: _parseError,
       );

  /// Provider identifier used in output and errors.
  static const provider = OpenMeteoContract.provider;

  /// Credit line the data licence (CC BY 4.0) requires apps to show.
  static const attribution = OpenMeteoContract.attribution;

  /// Variables offered by the forecast endpoint, per resolution.
  static const VariableTable forecastTable = OpenMeteoContract.forecast;

  /// Variables offered by the historical endpoint, per resolution.
  static const VariableTable archiveTable = OpenMeteoContract.archive;

  /// First day covered by the historical archive.
  static final archiveStart = CalendarDate(1940, 1, 1);

  static final _model = RegExp(r'^[a-z0-9_]+$');

  final Uri _forecastUrl;
  final Uri _archiveUrl;
  final ProviderHttp _http;

  /// An hourly forecast.
  ///
  /// [days] is the horizon including today (1-16) and [pastDays] the
  /// days before today to include (0-92). [timezone] is an IANA name,
  /// or `auto` for the zone of [location]. [model] picks a forecast
  /// model (e.g. `icon_eu`); by default Open-Meteo combines the best
  /// ones without reporting which. [elevation] (metres) replaces the
  /// terrain altitude Open-Meteo would use. [surface] is required for
  /// [Variable.shortwaveRadiationTilted] and ignored otherwise.
  @override
  Future<HourlySeries> forecastHourly(
    GeoPoint location,
    List<Variable> variables, {
    int days = 7,
    int pastDays = 0,
    String timezone = 'auto',
    String? model,
    double? elevation,
    Surface? surface,
  }) async {
    final query = _Query.checked(
      location,
      variables,
      timezone,
      model,
      elevation,
      surface,
    );
    return _hourly(
      forecastTable,
      _forecastUrl,
      query,
      _forecastRange(days, pastDays),
    );
  }

  /// Daily variant of [forecastHourly].
  @override
  Future<DailySeries> forecastDaily(
    GeoPoint location,
    List<Variable> variables, {
    int days = 7,
    int pastDays = 0,
    String timezone = 'auto',
    String? model,
    double? elevation,
  }) async {
    final query = _Query.checked(
      location,
      variables,
      timezone,
      model,
      elevation,
      null,
    );
    return _daily(
      forecastTable,
      _forecastUrl,
      query,
      _forecastRange(days, pastDays),
    );
  }

  /// Hourly historical data (reanalysis and analyses).
  ///
  /// [start] and [end] are inclusive; data start on [archiveStart] and
  /// recent days may be unavailable for a few days after real time.
  /// [model] picks an archive source, e.g. `era5` for a homogeneous
  /// series since 1940; by default Open-Meteo picks one per date without
  /// reporting it, so long series may mix sources. Other arguments as in
  /// [forecastHourly].
  @override
  Future<HourlySeries> historicalHourly(
    GeoPoint location,
    List<Variable> variables, {
    required CalendarDate start,
    required CalendarDate end,
    String timezone = 'auto',
    String? model,
    double? elevation,
    Surface? surface,
  }) async {
    final query = _Query.checked(
      location,
      variables,
      timezone,
      model,
      elevation,
      surface,
    );
    return _hourly(archiveTable, _archiveUrl, query, _dateRange(start, end));
  }

  /// Daily variant of [historicalHourly].
  @override
  Future<DailySeries> historicalDaily(
    GeoPoint location,
    List<Variable> variables, {
    required CalendarDate start,
    required CalendarDate end,
    String timezone = 'auto',
    String? model,
    double? elevation,
  }) async {
    final query = _Query.checked(
      location,
      variables,
      timezone,
      model,
      elevation,
      null,
    );
    return _daily(archiveTable, _archiveUrl, query, _dateRange(start, end));
  }

  /// Releases network resources (unless the HTTP client was given).
  void close() => _http.close();

  Future<HourlySeries> _hourly(
    VariableTable table,
    Uri url,
    _Query query,
    Map<String, String> extra,
  ) async {
    final names = table.nativeNames(Resolution.hourly, query.variables);
    final surface = query.tiltedSurface();
    final params = {
      ...query.baseParams(),
      ...extra,
      'hourly': names.join(','),
      'timeformat': 'unixtime',
      if (surface != null) ...{
        'tilt': _number(surface.tilt),
        'azimuth': _number(toAzimuth(surface.aspect)),
      },
    };
    final json = await _http.getJson(url.replace(queryParameters: params));
    return parseHourly(
      json,
      table,
      query.variables,
      provenanceOf(table, query.model),
      surface: surface,
    );
  }

  Future<DailySeries> _daily(
    VariableTable table,
    Uri url,
    _Query query,
    Map<String, String> extra,
  ) async {
    final names = table.nativeNames(Resolution.daily, query.variables);
    final params = {
      ...query.baseParams(),
      ...extra,
      'daily': names.join(','),
      'timeformat': 'iso8601',
    };
    final json = await _http.getJson(url.replace(queryParameters: params));
    return parseDaily(
      json,
      table,
      query.variables,
      provenanceOf(table, query.model),
    );
  }

  static Map<String, String> _forecastRange(int days, int pastDays) {
    if (days < 1 || days > 16) {
      throw RangeError.range(days, 1, 16, 'days');
    }
    if (pastDays < 0 || pastDays > 92) {
      throw RangeError.range(pastDays, 0, 92, 'pastDays');
    }
    return {'forecast_days': '$days', 'past_days': '$pastDays'};
  }

  static Map<String, String> _dateRange(CalendarDate start, CalendarDate end) {
    if (end.isBefore(start)) {
      throw ArgumentError('end ($end) must not be before start ($start)');
    }
    if (start.isBefore(archiveStart)) {
      throw ArgumentError('start must be on or after $archiveStart');
    }
    return {'start_date': '$start', 'end_date': '$end'};
  }

  static Uri _httpsUri(String url, String name) {
    final uri = Uri.tryParse(url);
    if (uri == null || !uri.isScheme('https') || uri.host.isEmpty) {
      throw ArgumentError.value(url, name, 'must be an absolute HTTPS URL');
    }
    return uri;
  }

  static String? _parseError(http.Response response) {
    try {
      return errorReason(_decode(response));
    } on FormatException {
      return null;
    }
  }
}

/// Options shared by every request, validated before sending anything.
final class _Query {
  _Query._(
    this.location,
    this.variables,
    this.timezone,
    this.model,
    this.elevation,
    this.surface,
  );

  factory _Query.checked(
    GeoPoint location,
    List<Variable> variables,
    String timezone,
    String? model,
    double? elevation,
    Surface? surface,
  ) {
    if (variables.isEmpty) {
      throw ArgumentError.value(variables, 'variables', 'must not be empty');
    }
    if (timezone.isEmpty) {
      throw ArgumentError.value(timezone, 'timezone', 'must not be empty');
    }
    // One model only: a list would rename the response columns.
    if (model != null &&
        (model.length > 64 || !OpenMeteoClient._model.hasMatch(model))) {
      throw ArgumentError.value(
        model,
        'model',
        'must be one model id ([a-z0-9_], at most 64 characters)',
      );
    }
    if (elevation != null && !(elevation >= -500 && elevation <= 9000)) {
      throw ArgumentError.value(
        elevation,
        'elevation',
        'must be between -500 and 9000 metres',
      );
    }
    // Preserve request order while dropping duplicates.
    return _Query._(
      location,
      List.unmodifiable(variables.toSet()),
      timezone,
      model,
      elevation,
      surface,
    );
  }

  final GeoPoint location;
  final List<Variable> variables;
  final String timezone;
  final String? model;
  final double? elevation;
  final Surface? surface;

  /// The surface, when a tilted variable needs it.
  Surface? tiltedSurface() {
    if (!variables.contains(Variable.shortwaveRadiationTilted)) return null;
    return surface ??
        (throw ArgumentError(
          '${Variable.shortwaveRadiationTilted.key} requires '
          'surface: Surface(tilt: ..., aspect: ...)',
        ));
  }

  Map<String, String> baseParams() => {
    'latitude': _number(location.latitude),
    'longitude': _number(location.longitude),
    'timezone': timezone,
    ...OpenMeteoContract.unitParams,
    'models': ?model,
    if (elevation != null) 'elevation': _number(elevation!),
  };
}

/// Decimal form of a number, as the Python reference sends it.
String _number(double value) => value.toString();

/// Decodes a UTF-8 JSON body; throws a [FormatException] if invalid.
Object? _decode(http.Response response) =>
    jsonDecode(utf8.decode(response.bodyBytes));
