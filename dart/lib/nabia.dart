/// Typed, normalized access to public weather, climate, agricultural
/// and forestry data APIs.
///
/// Dart port of the Nabia Python library. Every provider is mapped onto
/// one canonical vocabulary (variable names, units, timestamps with
/// their UTC offset), so app code does not change when an upstream API
/// evolves or when you switch providers. Behaviour is checked against
/// the conformance cases shared with the Python reference.
library;

export 'src/catalog/conversion.dart' show Conversion, canConvert;
export 'src/catalog/table.dart' show NativeVariable, VariableTable;
export 'src/core/errors.dart';
export 'src/core/http.dart' show HttpOptions;
export 'src/core/models.dart'
    show CalendarDate, DailySeries, GeoPoint, HourlySeries, Surface, TimeSeries;
export 'src/generated/catalog.g.dart'
    show Aggregation, Resolution, SourceKind, Unit, Variable, conversionBetween;
export 'src/providers/capabilities.dart';
export 'src/providers/open_meteo/client.dart'
    show OpenMeteoClient, OpenMeteoEndpoints;
export 'src/version.dart';
