/// Errors and exceptions thrown by Nabia.
///
/// Following Dart conventions, invalid arguments are programming
/// errors: they throw an [ArgumentError] (or its subclass
/// [UnsupportedVariableError]) before any request is sent. Failures
/// that a correct program must still handle are [NabiaException]s, a
/// sealed hierarchy that `switch` can match exhaustively.
library;

/// A variable is not offered for a provider dataset and resolution.
///
/// Check the table (e.g. `OpenMeteoClient.forecastTable.supported`)
/// before asking, or let the user choose only supported variables.
final class UnsupportedVariableError extends ArgumentError {
  /// Creates the error; [message] lists the available variables.
  UnsupportedVariableError(String super.message);
}

/// Base of every exception thrown by Nabia.
sealed class NabiaException implements Exception {
  NabiaException(this.message);

  /// Human-readable description, free of secrets.
  final String message;

  @override
  String toString() => message;
}

/// Failure while talking to a remote provider.
sealed class ProviderException extends NabiaException {
  ProviderException(super.message, {required this.provider, this.url});

  /// Provider identifier (e.g. `open_meteo`).
  final String provider;

  /// Request URL with credentials redacted, when known.
  final String? url;
}

/// Network failure or timeout persisting after every retry.
final class ProviderConnectionException extends ProviderException {
  /// Creates the exception.
  ProviderConnectionException(
    super.message, {
    required super.provider,
    super.url,
  });
}

/// The provider answered with an unexpected HTTP status.
///
/// Subclasses cover statuses that callers usually handle differently:
/// [AuthenticationException], [RateLimitException] and
/// [ProviderServerException].
final class ProviderHttpException extends ProviderException {
  /// Creates the exception.
  ProviderHttpException(
    super.message, {
    required super.provider,
    required this.statusCode,
    super.url,
  });

  /// HTTP status code of the response.
  final int statusCode;
}

/// The provider rejected the credentials (HTTP 401 or 403).
final class AuthenticationException extends ProviderHttpException {
  /// Creates the exception.
  AuthenticationException(
    super.message, {
    required super.provider,
    required super.statusCode,
    super.url,
  });
}

/// The provider throttled the client (HTTP 429).
final class RateLimitException extends ProviderHttpException {
  /// Creates the exception.
  RateLimitException(
    super.message, {
    required super.provider,
    super.statusCode = 429,
    super.url,
    this.retryAfter,
  });

  /// Wait the provider asked for (`Retry-After`), when it gave one.
  final Duration? retryAfter;
}

/// The provider failed on its side (HTTP 5xx).
final class ProviderServerException extends ProviderHttpException {
  /// Creates the exception.
  ProviderServerException(
    super.message, {
    required super.provider,
    required super.statusCode,
    super.url,
  });
}

/// The response does not match what Nabia expects.
///
/// It usually means the upstream API changed. It is thrown on purpose:
/// returning silently wrong data is worse than failing.
final class ProviderContractException extends ProviderException {
  /// Creates the exception.
  ProviderContractException(
    super.message, {
    required super.provider,
    super.url,
  });
}

/// The provider reported a different unit than the mapping table.
final class UnitMismatchException extends ProviderContractException {
  /// Creates the exception.
  UnitMismatchException(super.message, {required super.provider, super.url});
}

/// A requested variable came back with no value at all.
///
/// The selected source may not provide the variable, or the period may
/// not be available yet. Partially missing values are returned as
/// `null` instead.
final class NoDataException extends ProviderException {
  /// Creates the exception.
  NoDataException(super.message, {required super.provider, super.url});
}
