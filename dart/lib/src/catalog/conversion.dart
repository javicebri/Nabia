import '../generated/catalog.g.dart';

/// Affine unit conversion: `(value - offset) / divisor`.
///
/// Conversions are data in the shared contract, so every
/// implementation evaluates the same expression and gets the same
/// results, bit for bit.
final class Conversion {
  /// Creates a conversion; the defaults leave values unchanged.
  const Conversion({this.offset = 0.0, this.divisor = 1.0});

  /// Subtracted from the value first.
  final double offset;

  /// The difference is then divided by it.
  final double divisor;

  /// Converts one value.
  double apply(double value) => (value - offset) / divisor;
}

/// Whether values in [source] can be converted to [target].
bool canConvert(Unit source, Unit target) =>
    source == target || conversionBetween(source, target) != null;

/// Converts [values] from [source] to [target], keeping missing values.
///
/// Throws an [ArgumentError] when no conversion is defined.
List<double?> convertValues(
  Iterable<double?> values,
  Unit source,
  Unit target,
) {
  if (source == target) return List.unmodifiable(values);
  final conversion = conversionBetween(source, target);
  if (conversion == null) {
    throw ArgumentError(
      'No conversion defined from ${source.symbol} to ${target.symbol}',
    );
  }
  return List.unmodifiable([
    for (final value in values) value == null ? null : conversion.apply(value),
  ]);
}
