/// Open-Meteo logic that is not data. Tables and constants are
/// generated from the contract (`OpenMeteoContract`).
library;

import '../../catalog/table.dart';
import '../../generated/catalog.g.dart';
import '../../generated/providers/open_meteo.g.dart';

/// Translates a compass aspect into Open-Meteo's `azimuth`.
///
/// Open-Meteo measures from the south: 0 = south, -90 = east, 90 =
/// west, +-180 = north (verified against the live API; see the provider
/// README in the Python package).
double toAzimuth(double aspect) => aspect - 180.0;

/// What is known for certain about where a response's data come from.
typedef Provenance = ({String? source, SourceKind? sourceKind});

/// Provenance of a request to [table] with [model].
///
/// The default model hides which source answered, so nothing is
/// claimed about it beyond what holds for the whole dataset.
Provenance provenanceOf(VariableTable table, String? model) {
  final source = model == null || model == OpenMeteoContract.defaultModel
      ? null
      : model;
  if (table.dataset == OpenMeteoContract.forecast.dataset) {
    return (source: source, sourceKind: SourceKind.forecast);
  }
  final kind = source == null ? null : OpenMeteoContract.archiveSources[source];
  return (
    source: source,
    sourceKind: kind == null ? null : SourceKind.fromKey(kind),
  );
}
