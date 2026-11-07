import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:nabia/nabia.dart';
import 'package:nabia/src/core/http.dart';
import 'package:test/test.dart';

final _url = Uri.parse('https://api.test/data?lat=1');

http.Response _json(int status, Object? body, [Map<String, String>? headers]) =>
    http.Response.bytes(
      utf8.encode(jsonEncode(body)),
      status,
      headers: {'content-type': 'application/json', ...?headers},
    );

/// Answers with [responses] in order and records requests and sleeps.
final class _Server {
  _Server(List<Object> responses) : _responses = List.of(responses);

  final List<Object> _responses;
  final requests = <http.BaseRequest>[];
  final sleeps = <Duration>[];

  ProviderHttp http_({
    HttpOptions options = const HttpOptions(maxRetries: 2),
    Iterable<String> secretParams = const [],
  }) => ProviderHttp(
    provider: 'test',
    options: options,
    client: MockClient((request) async {
      requests.add(request);
      final next = _responses.removeAt(0);
      if (next is Exception) throw next;
      return next as http.Response;
    }),
    secretParams: secretParams,
    sleep: (duration) async => sleeps.add(duration),
  );
}

void main() {
  test('decodes JSON and sends the user agent without redirects', () async {
    final server = _Server([
      _json(200, {'value': 1}),
    ]);
    expect(await server.http_().getJson(_url), {'value': 1});
    final request = server.requests.single as http.Request;
    expect(request.followRedirects, isFalse);
    expect(request.headers['User-Agent'], 'nabia/$packageVersion');
  });

  test('retries transient failures, then succeeds', () async {
    final server = _Server([
      http.ClientException('reset'),
      _json(503, null),
      _json(200, {'ok': true}),
    ]);
    expect(await server.http_().getJson(_url), {'ok': true});
    expect(server.requests, hasLength(3));
    expect(server.sleeps, hasLength(2));
    // First backoff step (0.5 s) plus up to 0.5 s of jitter.
    expect(server.sleeps.first.inMilliseconds, inInclusiveRange(500, 1000));
  });

  test('Retry-After caps the sleep but not the reported wait', () async {
    final server = _Server([
      _json(429, null, {'Retry-After': '120'}),
      _json(429, null, {'retry-after': '120'}),
    ]);
    final error = await server
        .http_(options: const HttpOptions(maxRetries: 1))
        .getJson(_url)
        .then<Object?>((_) => null, onError: (Object e) => e);
    expect(server.sleeps, [const Duration(seconds: 30)]);
    expect(error, isA<RateLimitException>());
    expect(
      (error! as RateLimitException).retryAfter,
      const Duration(minutes: 2),
    );
  });

  test('Retry-After 0 retries at once; a date falls back to backoff', () async {
    final server = _Server([
      _json(429, null, {'Retry-After': '0'}),
      _json(429, null, {'Retry-After': 'Wed, 21 Oct 2026 07:28:00 GMT'}),
      _json(200, 1),
    ]);
    await server.http_().getJson(_url);
    expect(server.sleeps.first, Duration.zero);
    expect(
      server.sleeps.last,
      greaterThanOrEqualTo(const Duration(seconds: 1)),
    );
  });

  test('maps statuses to typed exceptions', () async {
    Future<Object> errorFor(int status) async {
      final server = _Server([_json(status, null)]);
      try {
        await server
            .http_(options: const HttpOptions(maxRetries: 0))
            .getJson(_url);
      } on NabiaException catch (error) {
        return error;
      }
      fail('no exception for $status');
    }

    expect(await errorFor(401), isA<AuthenticationException>());
    expect(await errorFor(403), isA<AuthenticationException>());
    expect(await errorFor(500), isA<ProviderServerException>());
    final redirect = await errorFor(301);
    expect(redirect, isA<ProviderHttpException>());
    expect((redirect as ProviderHttpException).statusCode, 301);
  });

  test('redacts secrets from URLs and messages', () async {
    final server = _Server([
      http.ClientException('failed for ?token=abc&mysecret=xyz'),
    ]);
    // Fake credentials: this test checks they are masked.
    final url = Uri.parse(
      'https://user:pw@api.test/data?apikey=K&lat=1&mysecret=S', // pragma: allowlist secret
    );
    final error = await server
        .http_(
          options: const HttpOptions(maxRetries: 0),
          secretParams: ['MySecret'],
        )
        .getJson(url)
        .then<Object?>((_) => null, onError: (Object e) => e);
    final exception = error! as ProviderConnectionException;
    expect(
      exception.url,
      'https://***@api.test/data?apikey=***&lat=1&mysecret=***',
    );
    expect(exception.message, contains('token=***'));
    expect(exception.message, contains('mysecret=***'));
    for (final secret in ['abc', 'xyz', 'pw', '=K', '=S']) {
      expect('${exception.url} ${exception.message}', isNot(contains(secret)));
    }
  });

  test('timeouts are connection failures', () async {
    final layer = ProviderHttp(
      provider: 'test',
      options: const HttpOptions(
        maxRetries: 0,
        timeout: Duration(milliseconds: 10),
      ),
      client: MockClient((_) => Completer<http.Response>().future),
    );
    await expectLater(
      layer.getJson(_url),
      throwsA(isA<ProviderConnectionException>()),
    );
  });

  test('invalid JSON is a contract error', () async {
    final server = _Server([http.Response('<html>', 200)]);
    await expectLater(
      server.http_().getJson(_url),
      throwsA(isA<ProviderContractException>()),
    );
  });

  test('rejects plain HTTP and invalid options', () async {
    final server = _Server([]);
    await expectLater(
      server.http_().getJson(Uri.parse('http://api.test/data')),
      throwsArgumentError,
    );
    expect(server.requests, isEmpty);
    expect(
      () => ProviderHttp(
        provider: 'p',
        options: const HttpOptions(maxRetries: 11),
      ),
      throwsRangeError,
    );
    expect(
      () => ProviderHttp(
        provider: 'p',
        options: const HttpOptions(timeout: Duration.zero),
      ),
      throwsArgumentError,
    );
    expect(
      () => ProviderHttp(
        provider: 'p',
        options: const HttpOptions(userAgent: ''),
      ),
      throwsArgumentError,
    );
    expect(
      () => OpenMeteoClient(
        endpoints: const OpenMeteoEndpoints(forecastUrl: 'http://x.test/v1'),
      ),
      throwsArgumentError,
    );
  });

  test('a broken error parser does not hide the error', () async {
    final layer = ProviderHttp(
      provider: 'test',
      options: const HttpOptions(maxRetries: 0),
      client: MockClient(
        (_) async => http.Response('', 400, reasonPhrase: 'Bad Request'),
      ),
      errorParser: (_) => throw const FormatException('broken'),
    );
    await expectLater(
      layer.getJson(_url),
      throwsA(
        isA<ProviderHttpException>().having(
          (e) => e.message,
          'message',
          'test: HTTP 400 - Bad Request',
        ),
      ),
    );
  });

  test('long error details are truncated', () async {
    final layer = ProviderHttp(
      provider: 'test',
      options: const HttpOptions(maxRetries: 0),
      client: MockClient((_) async => http.Response('', 418)),
      errorParser: (_) => 'x' * 1000,
    );
    await expectLater(
      layer.getJson(_url),
      throwsA(
        isA<ProviderHttpException>().having(
          (e) => e.message.length,
          'length',
          'test: HTTP 418 - '.length + 300,
        ),
      ),
    );
  });

  test('closing the client it created', () {
    ProviderHttp(provider: 'p').close();
    OpenMeteoClient().close();
  });

  test('closes only the client it created', () {
    var closed = false;
    final injected = _ClosingClient(() => closed = true);
    ProviderHttp(provider: 'p', client: injected).close();
    expect(closed, isFalse);
  });
}

final class _ClosingClient extends http.BaseClient {
  _ClosingClient(this._onClose);

  final void Function() _onClose;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) =>
      throw UnimplementedError();

  @override
  void close() => _onClose();
}
