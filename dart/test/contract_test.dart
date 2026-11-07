// Generated code and package metadata stay consistent with the shared
// contract and with the Python reference.

import 'dart:convert';
import 'dart:io';

import 'package:nabia/nabia.dart';
import 'package:nabia/src/catalog/conversion.dart' show convertValues;
import 'package:test/test.dart';

import '../tool/generate.dart' as generator;

void main() {
  test('generated sources match the contract', () async {
    final sources = await generator.generateSources(Directory('../contract'));
    expect(
      generator.staleFiles(Directory(generator.generatedDir), sources),
      isEmpty,
      reason: 'Run: dart run tool/generate.dart',
    );
  });

  test('package version matches pubspec and the Python package', () {
    String version(String path, RegExp pattern) =>
        pattern.firstMatch(File(path).readAsStringSync())!.group(1)!;
    final pubspec = version(
      'pubspec.yaml',
      RegExp(r'^version: (\S+)$', multiLine: true),
    );
    final python = version(
      '../pyproject.toml',
      RegExp(r'^version = "([^"]+)"$', multiLine: true),
    );
    expect(packageVersion, pubspec);
    expect(pubspec, python, reason: 'one shared tag per release');
  });

  test('conversions reproduce the contract exactly', () {
    final catalog =
        jsonDecode(File('../contract/catalog.json').readAsStringSync())
            as Map<String, Object?>;
    final units = (catalog['units']! as Map<String, Object?>).map(
      (key, symbol) => MapEntry(key, Unit.fromSymbol(symbol! as String)),
    );
    for (final item in catalog['conversions']! as List<Object?>) {
      final entry = item! as Map<String, Object?>;
      final conversion = conversionBetween(
        units[entry['from']]!,
        units[entry['to']]!,
      )!;
      for (final value in [-40.5, 0.0, 1.0, 273.15, 101325.0, 86400.0]) {
        final offset = (entry['offset']! as num).toDouble();
        final divisor = (entry['divisor']! as num).toDouble();
        expect(conversion.apply(value), (value - offset) / divisor);
      }
    }
  });

  for (final table in [
    OpenMeteoClient.forecastTable,
    OpenMeteoClient.archiveTable,
  ]) {
    test('table ${table.provider}/${table.dataset} fits the catalog', () {
      for (final resolution in Resolution.values) {
        for (final MapEntry(key: variable, value: native)
            in table.entries(resolution).entries) {
          expect(variable.resolutions, contains(resolution));
          expect(canConvert(native.unit, variable.unit), isTrue);
        }
      }
    });
  }

  test('enum keys round-trip', () {
    for (final variable in Variable.values) {
      expect(Variable.fromKey(variable.key), variable);
    }
    for (final unit in Unit.values) {
      expect(Unit.fromSymbol(unit.symbol), unit);
    }
    for (final resolution in Resolution.values) {
      expect(Resolution.fromKey(resolution.key), resolution);
    }
    for (final aggregation in Aggregation.values) {
      expect(Aggregation.fromKey(aggregation.key), aggregation);
    }
    for (final kind in SourceKind.values) {
      expect(SourceKind.fromKey(kind.key), kind);
    }
    expect(() => Variable.fromKey('snowfall_on_mars'), throwsArgumentError);
    expect(() => Unit.fromSymbol('furlong'), throwsArgumentError);
    expect(() => Resolution.fromKey('weekly'), throwsArgumentError);
    expect(() => Aggregation.fromKey('median'), throwsArgumentError);
    expect(() => SourceKind.fromKey('guess'), throwsArgumentError);
  });

  test('undefined conversions are rejected', () {
    expect(canConvert(Unit.celsius, Unit.percent), isFalse);
    expect(conversionBetween(Unit.celsius, Unit.kelvin), isNull);
    expect(
      () => convertValues([1.0], Unit.celsius, Unit.percent),
      throwsArgumentError,
    );
    expect(convertValues([1.0, null], Unit.hour, Unit.hour), [1.0, null]);
  });

  test('supported variables follow the table order', () {
    final hourly = OpenMeteoClient.forecastTable.supported(Resolution.hourly);
    expect(hourly.first, Variable.airTemperature);
    expect(hourly, contains(Variable.precipitationProbability));
    expect(
      OpenMeteoClient.archiveTable.supported(Resolution.hourly),
      isNot(contains(Variable.precipitationProbability)),
    );
  });
}
