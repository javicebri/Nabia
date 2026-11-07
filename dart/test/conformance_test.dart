// Replays the conformance cases shared with the Python reference
// (contract/conformance/*.json): same call and provider answer, same
// request sent and same series or error. See contract/README.md.

import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nabia/nabia.dart';
import 'package:test/test.dart';

/// Builds the client of each provider with retries disabled.
final _clients = <String, OpenMeteoClient Function(http.Client)>{
  'open_meteo': (client) => OpenMeteoClient(
    httpClient: client,
    options: const HttpOptions(maxRetries: 0),
  ),
};

void main() {
  final files =
      Directory('../contract/conformance')
          .listSync()
          .whereType<File>()
          .where((file) => file.path.endsWith('.json'))
          .toList()
        ..sort((a, b) => a.path.compareTo(b.path));
  test('there are conformance cases', () => expect(files, isNotEmpty));
  for (final file in files) {
    final document =
        jsonDecode(file.readAsStringSync()) as Map<String, Object?>;
    final provider = document['provider']! as String;
    group(provider, () {
      for (final item in document['cases']! as List<Object?>) {
        final testCase = item! as Map<String, Object?>;
        test(testCase['name']! as String, () => _replay(provider, testCase));
      }
    });
  }
}

Future<void> _replay(String provider, Map<String, Object?> testCase) async {
  final factory = _clients[provider];
  if (factory == null) fail('No Dart client for provider $provider');
  final response = testCase['response'] as Map<String, Object?>?;
  final requests = <http.BaseRequest>[];
  final mock = MockClient((request) async {
    requests.add(request);
    if (response == null) throw StateError('No request may be sent');
    if (response['failure'] == 'connection') {
      throw http.ClientException('simulated failure', request.url);
    }
    final headers = (response['headers']! as Map<String, Object?>).map(
      (name, value) => MapEntry(name, value! as String),
    );
    return http.Response.bytes(
      utf8.encode(jsonEncode(response['body'])),
      response['status']! as int,
      headers: {...headers, 'content-type': 'application/json'},
      request: request,
    );
  });
  final client = factory(mock);
  Object outcome;
  try {
    outcome = await _invoke(client, testCase['call']! as Map<String, Object?>);
  } on NabiaException catch (exception) {
    outcome = exception;
    // The cases specify argument errors too: they are part of the
    // contract, so this harness has to observe them.
    // ignore: avoid_catching_errors
  } on ArgumentError catch (error) {
    outcome = error;
  } finally {
    client.close();
  }

  final expectedRequest = testCase['request'] as Map<String, Object?>?;
  if (expectedRequest == null) {
    expect(requests, isEmpty, reason: 'no request may be sent');
  } else {
    expect(requests, hasLength(1), reason: 'exactly one request');
    final url = requests.single.url;
    final base = Uri(
      scheme: url.scheme,
      host: url.host,
      port: url.hasPort ? url.port : null,
      path: url.path,
    );
    expect(base.toString(), expectedRequest['url']);
    final sent = url.queryParametersAll;
    final wanted = expectedRequest['params']! as Map<String, Object?>;
    expect(sent.keys.toSet(), wanted.keys.toSet());
    for (final MapEntry(:key, :value) in wanted.entries) {
      expect(sent[key], hasLength(1), reason: 'repeated parameter $key');
      expect(
        sameParam(value! as String, sent[key]!.single),
        isTrue,
        reason: '$key: sent ${sent[key]!.single}, expected $value',
      );
    }
  }

  final expected = testCase['expected']! as Map<String, Object?>;
  if (expected.containsKey('series')) {
    expect(outcome, isA<TimeSeries<Object>>(), reason: '$outcome');
    final series = outcome as TimeSeries<Object>;
    expect(jsonDecode(jsonEncode(series.toJson())), equals(expected['series']));
    final loaded = TimeSeries.fromJson(
      expected['series']! as Map<String, Object?>,
    );
    expect(loaded, equals(series), reason: 'JSON round trip');
  } else {
    expect(errorKind(outcome), expected['error'], reason: '$outcome');
    final status = outcome is ProviderHttpException ? outcome.statusCode : null;
    expect(status, expected['status_code']);
    final wait = outcome is RateLimitException ? outcome.retryAfter : null;
    expect(
      wait == null
          ? null
          : wait.inMicroseconds / Duration.microsecondsPerSecond,
      expected['retry_after'],
    );
    final text = expected['message_contains'] as String?;
    if (text != null) expect('$outcome', contains(text));
  }
}

/// Calls the operation named in [call] with its options mapped to Dart
/// arguments (`past_days` becomes `pastDays`, dates become
/// [CalendarDate]s, surfaces become [Surface]s).
Future<TimeSeries<Object>> _invoke(
  OpenMeteoClient client,
  Map<String, Object?> call,
) {
  final location = call['location']! as Map<String, Object?>;
  final point = GeoPoint(
    latitude: (location['latitude']! as num).toDouble(),
    longitude: (location['longitude']! as num).toDouble(),
  );
  final variables = [
    for (final key in call['variables']! as List<Object?>)
      Variable.fromKey(key! as String),
  ];
  final options = call['options']! as Map<String, Object?>;
  final named = {
    for (final MapEntry(:key, :value) in options.entries)
      Symbol(_camel(key)): _argument(key, value),
  };
  final Function method = switch (call['operation']) {
    'forecast_hourly' => client.forecastHourly,
    'forecast_daily' => client.forecastDaily,
    'historical_hourly' => client.historicalHourly,
    'historical_daily' => client.historicalDaily,
    final other => throw StateError('Unknown operation $other'),
  };
  return Function.apply(method, [point, variables], named)
      as Future<TimeSeries<Object>>;
}

Object? _argument(String name, Object? value) => switch (name) {
  'start' || 'end' => CalendarDate.parse(value! as String),
  'surface' => _surface(value! as Map<String, Object?>),
  'elevation' => (value! as num).toDouble(),
  'days' || 'past_days' => value! as int,
  'timezone' || 'model' => value! as String,
  _ => throw StateError('Unknown option $name'),
};

Surface _surface(Map<String, Object?> json) => Surface(
  tilt: (json['tilt']! as num).toDouble(),
  aspect: (json['aspect']! as num).toDouble(),
);

String _camel(String snake) {
  final parts = snake.split('_');
  return parts.first +
      parts.skip(1).map((p) => p[0].toUpperCase() + p.substring(1)).join();
}

/// Neutral error kind of [outcome] (see contract/README.md).
String errorKind(Object outcome) => switch (outcome) {
  UnsupportedVariableError() => 'unsupported_variable',
  ArgumentError() => 'invalid_argument',
  UnitMismatchException() => 'unit_mismatch',
  ProviderContractException() => 'provider_contract',
  NoDataException() => 'no_data',
  AuthenticationException() => 'authentication',
  RateLimitException() => 'rate_limit',
  ProviderServerException() => 'provider_server',
  ProviderHttpException() => 'provider_http',
  ProviderConnectionException() => 'provider_connection',
  _ => 'unexpected ${outcome.runtimeType}',
};

/// Compares query values; numbers by value (`30` equals `30.0`).
bool sameParam(String expected, String actual) {
  if (expected == actual) return true;
  final a = double.tryParse(expected);
  final b = double.tryParse(actual);
  return a != null && b != null && a == b;
}
