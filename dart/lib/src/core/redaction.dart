/// Masks credentials in URLs and free text before they reach an error.
library;

/// Replacement for every secret value.
const redactedValue = '***';

/// Query parameter names always treated as secrets (case-insensitive).
const defaultSecretParams = {
  'access_token',
  'api_key',
  'apikey',
  'key',
  'password',
  'secret',
  'token',
};

/// Redacts secret query values and URL user info.
final class Redactor {
  /// Creates a redactor for [defaultSecretParams] plus [extraParams].
  Redactor([Iterable<String> extraParams = const []])
    : _pattern = _secretPattern({
        ...defaultSecretParams,
        for (final name in extraParams) name.toLowerCase(),
      });

  final RegExp _pattern;

  static final _userInfo = RegExp(r'(://)[^/@\s]+@');

  static RegExp _secretPattern(Set<String> names) {
    final alternatives = (names.toList()..sort()).map(RegExp.escape).join('|');
    return RegExp(
      '([?&;\\s]|^)($alternatives)=([^&\\s"\']+)',
      caseSensitive: false,
    );
  }

  /// Masks `name=value` pairs for secret names inside [text].
  String text(String text) => text.replaceAllMapped(
    _pattern,
    (match) => '${match[1]}${match[2]}=$redactedValue',
  );

  /// Returns [url] with secret query values and user info masked.
  String url(Uri url) => text(
    url.toString().replaceFirstMapped(
      _userInfo,
      (match) => '${match[1]}$redactedValue@',
    ),
  );
}
