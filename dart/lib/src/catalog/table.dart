import '../core/errors.dart';
import '../generated/catalog.g.dart';
import 'conversion.dart';

/// How a provider names and measures one canonical variable.
final class NativeVariable {
  /// Creates the entry.
  const NativeVariable({
    required this.name,
    required this.unit,
    this.notes = '',
  });

  /// Identifier used by the provider API.
  final String name;

  /// Unit the provider reports for [name].
  final Unit unit;

  /// Caveats on the provider definition, if any.
  final String notes;
}

/// Equivalence table between canonical variables and one provider
/// dataset.
///
/// Tables are generated from the shared contract. Besides translating
/// names, [extract] protects callers from upstream drift: a missing
/// column, a changed unit or an entirely empty column throws instead of
/// returning wrong data.
final class VariableTable {
  /// Creates a table.
  const VariableTable({
    required this.provider,
    required this.dataset,
    required this.referenceUrl,
    required this.verifiedOn,
    this.hourly = const {},
    this.daily = const {},
  });

  /// Provider identifier (e.g. `open_meteo`).
  final String provider;

  /// Dataset or endpoint within the provider.
  final String dataset;

  /// Documentation the table was built from.
  final String referenceUrl;

  /// Last date the table was checked against the live API (ISO 8601).
  final String verifiedOn;

  /// Canonical to native mapping for hourly series.
  final Map<Variable, NativeVariable> hourly;

  /// Canonical to native mapping for daily series.
  final Map<Variable, NativeVariable> daily;

  /// The mapping for [resolution].
  Map<Variable, NativeVariable> entries(Resolution resolution) =>
      switch (resolution) {
        Resolution.hourly => hourly,
        Resolution.daily => daily,
      };

  /// The canonical variables offered at [resolution].
  Set<Variable> supported(Resolution resolution) =>
      Set.unmodifiable(entries(resolution).keys);

  /// Translates [variables] into native names.
  ///
  /// Throws an [UnsupportedVariableError] if one is not in the table.
  List<String> nativeNames(Resolution resolution, List<Variable> variables) {
    final mapping = entries(resolution);
    final missing = [
      for (final variable in variables)
        if (!mapping.containsKey(variable)) variable.key,
    ];
    if (missing.isNotEmpty) {
      final available = (mapping.keys.map((v) => v.key).toList()..sort()).join(
        ', ',
      );
      throw UnsupportedVariableError(
        '$provider/$dataset does not provide ${missing.join(', ')} at '
        '${resolution.key} resolution. Available: $available',
      );
    }
    return [for (final variable in variables) mapping[variable]!.name];
  }

  /// Picks, verifies and converts native columns to canonical values.
  ///
  /// [columns] maps native names to raw values as returned upstream;
  /// [reportedUnits] maps native names to the unit the provider
  /// reports, or is `null` when the provider reports none. [source] is
  /// the selected model or product, used in messages.
  ///
  /// Throws a [ProviderContractException] when a requested column is
  /// missing, a [UnitMismatchException] when a reported unit differs
  /// from the table, and a [NoDataException] when a non-empty column
  /// holds no value at all.
  Map<Variable, List<double?>> extract(
    Resolution resolution,
    List<Variable> variables,
    Map<String, List<double?>> columns,
    Map<String, String>? reportedUnits, {
    String? source,
  }) {
    final names = nativeNames(resolution, variables);
    final mapping = entries(resolution);
    final result = <Variable, List<double?>>{};
    for (final (index, variable) in variables.indexed) {
      final native = mapping[variable]!;
      final column = columns[names[index]];
      if (column == null) {
        throw ProviderContractException(
          "$provider/$dataset: column '${native.name}' missing from "
          'response (canonical: ${variable.key})',
          provider: provider,
        );
      }
      if (reportedUnits != null) {
        final reported = reportedUnits[native.name];
        if (reported != native.unit.symbol) {
          throw UnitMismatchException(
            "$provider/$dataset: '${native.name}' reported in "
            "${reported == null ? 'no unit' : "'$reported'"}, table expects "
            "'${native.unit.symbol}'. Review the table.",
            provider: provider,
          );
        }
      }
      if (column.isNotEmpty && column.every((value) => value == null)) {
        final origin = source == null ? '' : " with source '$source'";
        throw NoDataException(
          '$provider/$dataset$origin returned no values for '
          "${variable.key} ('${native.name}'): the source may not provide "
          'it, or the period is not available yet.',
          provider: provider,
        );
      }
      result[variable] = convertValues(column, native.unit, variable.unit);
    }
    return result;
  }
}
