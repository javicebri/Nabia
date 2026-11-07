/// HTTP layer shared by every provider client.
///
/// Same policy as the Python reference: HTTPS only, redirects never
/// followed, retries with backoff for transient failures (network
/// errors, HTTP 429 and 5xx) honouring `Retry-After`, HTTP failures
/// mapped to typed exceptions, and credentials redacted from every
/// message. TLS is verified by the platform.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:http/http.dart' as http;

import '../version.dart';
import 'errors.dart';
import 'redaction.dart';

/// Network settings shared by every provider client.
final class HttpOptions {
  /// Creates the settings; the defaults match the Python reference.
  const HttpOptions({
    this.timeout = const Duration(seconds: 30),
    this.maxRetries = 3,
    this.userAgent = 'nabia/$packageVersion',
  });

  /// Time limit for each attempt (0 < timeout <= 10 minutes).
  final Duration timeout;

  /// Retries for transient failures, from 0 to 10.
  final int maxRetries;

  /// `User-Agent` header sent to every provider.
  final String userAgent;
}

/// HTTP statuses retried as transient failures.
const retryableStatuses = {429, 500, 502, 503, 504};

const _backoffBase = Duration(milliseconds: 500);
const _waitCap = Duration(seconds: 30);
const _maxDetailChars = 300;

/// Extracts the provider's reason from a failed response, if any.
typedef ErrorParser = String? Function(http.Response response);

/// Waits before a retry; replaceable in tests.
typedef Sleep = Future<void> Function(Duration duration);

/// Sends GET requests to one provider.
final class ProviderHttp {
  /// Creates the HTTP layer for [provider].
  ///
  /// When [client] is given its owner keeps closing it; otherwise one
  /// is created and [close] releases it. [secretParams] lists extra
  /// query parameter names holding credentials.
  ///
  /// Throws an [ArgumentError] for invalid [options].
  ProviderHttp({
    required this.provider,
    this.options = const HttpOptions(),
    http.Client? client,
    Iterable<String> secretParams = const [],
    ErrorParser? errorParser,
    Sleep? sleep,
    Random? random,
  }) : _client = client ?? http.Client(),
       _ownsClient = client == null,
       _redactor = Redactor(secretParams),
       _errorParser = errorParser,
       _sleep = sleep ?? Future<void>.delayed,
       _random = random ?? Random() {
    if (options.maxRetries < 0 || options.maxRetries > 10) {
      throw RangeError.range(options.maxRetries, 0, 10, 'maxRetries');
    }
    if (options.timeout <= Duration.zero ||
        options.timeout > const Duration(minutes: 10)) {
      throw ArgumentError.value(
        options.timeout,
        'timeout',
        'must be positive and at most 10 minutes',
      );
    }
    if (options.userAgent.isEmpty) {
      throw ArgumentError.value(options.userAgent, 'userAgent', 'is empty');
    }
  }

  /// Provider identifier used in errors.
  final String provider;

  /// Network settings.
  final HttpOptions options;

  final http.Client _client;
  final bool _ownsClient;
  final Redactor _redactor;
  final ErrorParser? _errorParser;
  final Sleep _sleep;
  final Random _random;

  /// Sends a GET request and decodes the JSON body.
  ///
  /// Throws an [ArgumentError] for non-HTTPS URLs, a
  /// [ProviderConnectionException] when the network fails after every
  /// retry, a [ProviderHttpException] (or subclass) for unexpected
  /// statuses and a [ProviderContractException] for invalid JSON.
  Future<Object?> getJson(Uri url) async {
    final response = await _send(url);
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException catch (error) {
      throw ProviderContractException(
        '$provider: response is not valid JSON: ${error.message}',
        provider: provider,
        url: _redactor.url(url),
      );
    }
  }

  /// Releases the client if this object created it.
  void close() {
    if (_ownsClient) _client.close();
  }

  Future<http.Response> _send(Uri url) async {
    if (!url.isScheme('https')) {
      throw ArgumentError.value(_redactor.url(url), 'url', 'must use HTTPS');
    }
    final safeUrl = _redactor.url(url);
    for (var attempt = 0; ; attempt++) {
      final last = attempt >= options.maxRetries;
      final http.Response response;
      try {
        response = await _request(url);
      } on Exception catch (error) {
        if (last) {
          throw ProviderConnectionException(
            '$provider: connection failed after ${attempt + 1} '
            'attempt(s): ${_redactor.text(error.toString())}',
            provider: provider,
            url: safeUrl,
          );
        }
        await _sleep(_backoff(attempt));
        continue;
      }
      if (retryableStatuses.contains(response.statusCode) && !last) {
        final requested = retryAfter(response);
        // Never sleep longer than the cap: a long wait is the caller's
        // decision, made from the exception thrown at the end.
        await _sleep(
          requested == null
              ? _backoff(attempt)
              : (requested < _waitCap ? requested : _waitCap),
        );
        continue;
      }
      _throwForStatus(response, safeUrl);
      return response;
    }
  }

  Future<http.Response> _request(Uri url) async {
    final request = http.Request('GET', url)
      ..followRedirects = false
      ..headers['User-Agent'] = options.userAgent;
    final streamed = await _client.send(request).timeout(options.timeout);
    return http.Response.fromStream(streamed).timeout(options.timeout);
  }

  Duration _backoff(int attempt) {
    final base = min(
      _waitCap.inMicroseconds,
      _backoffBase.inMicroseconds * pow(2, attempt),
    );
    final jitter = _random.nextDouble() * _backoffBase.inMicroseconds;
    return Duration(microseconds: (base + jitter).round());
  }

  void _throwForStatus(http.Response response, String safeUrl) {
    final status = response.statusCode;
    if (status >= 200 && status < 300) return;
    final message = '$provider: HTTP $status - ${_detail(response)}';
    if (status == 401 || status == 403) {
      throw AuthenticationException(
        message,
        provider: provider,
        statusCode: status,
        url: safeUrl,
      );
    }
    if (status == 429) {
      throw RateLimitException(
        message,
        provider: provider,
        url: safeUrl,
        retryAfter: retryAfter(response),
      );
    }
    if (status >= 500) {
      throw ProviderServerException(
        message,
        provider: provider,
        statusCode: status,
        url: safeUrl,
      );
    }
    throw ProviderHttpException(
      message,
      provider: provider,
      statusCode: status,
      url: safeUrl,
    );
  }

  String _detail(http.Response response) {
    String? detail;
    final parser = _errorParser;
    if (parser != null) {
      try {
        detail = parser(response);
      } on Exception {
        detail = null; // a broken parser must not hide the error
      }
    }
    if (detail == null || detail.isEmpty) {
      detail = response.reasonPhrase ?? '';
    }
    if (detail.isEmpty) detail = 'unknown error';
    final redacted = _redactor.text(detail);
    return redacted.length > _maxDetailChars
        ? redacted.substring(0, _maxDetailChars)
        : redacted;
  }
}

/// Wait the provider asked for in `Retry-After`, uncapped.
///
/// Returns `null` when the header is absent or uses the HTTP-date form
/// (rare for APIs; backoff applies instead).
Duration? retryAfter(http.Response response) {
  // Header names are case-insensitive; injected clients may keep the
  // server's casing instead of lower-casing them as dart:io does.
  final value = response.headers.entries
      .where((header) => header.key.toLowerCase() == 'retry-after')
      .map((header) => header.value)
      .firstOrNull;
  if (value == null) return null;
  final seconds = double.tryParse(value.trim());
  if (seconds == null || !seconds.isFinite) return null;
  return Duration(microseconds: (max(0.0, seconds) * 1e6).round());
}
