# Nabia for Dart

Dart port of [Nabia](../README.md): typed, normalized access to public
weather, climate, agricultural and forestry data APIs, for Flutter apps
and any other Dart code. It is a pure Dart package (no Flutter
dependency).

The Python package is the reference implementation. This port is not a
line-by-line copy: its vocabulary and provider tables are generated
from the shared [contract](../contract/README.md), and its behaviour is
checked by replaying the same conformance cases Python passes (same
call and provider response, same request sent and same series or
error).

## Installation

Python and Dart share one Git tag per release. In the app's
`pubspec.yaml`:

```yaml
dependencies:
  nabia:
    git:
      url: https://github.com/javicebri/Nabia.git
      path: dart
      ref: v0.4.0 # the release to use
```

## Quick start

```dart
import 'package:nabia/nabia.dart';

Future<void> main() async {
  final client = OpenMeteoClient();
  try {
    final daily = await client.historicalDaily(
      GeoPoint(latitude: 40.42, longitude: -3.70),
      [Variable.precipitation, Variable.referenceEvapotranspiration],
      start: CalendarDate(2024, 3, 1),
      end: CalendarDate(2024, 3, 31),
    );
    daily.values[Variable.precipitation]; // List<double?> in mm
    daily.units; // {Variable.precipitation: Unit.millimetre, ...}
    daily.attribution; // credit line the data licence requires
    daily.toJson(); // same JSON as the Python package
  } on NoDataException catch (e) {
    // The source has no value for a variable in that period.
  } on ProviderException catch (e) {
    // Network, HTTP or upstream contract failure: e.message, e.provider.
  } finally {
    client.close();
  }
}
```

Type against capabilities to stay provider-agnostic:
`ForecastHourlyProvider`, `ForecastDailyProvider`,
`HistoricalHourlyProvider` and `HistoricalDailyProvider`.

## Design

| Topic | Dart | Python reference |
|-------|------|------------------|
| Calls | `Future`s; errors arrive through the future | synchronous |
| Invalid arguments | `ArgumentError` (`RangeError`, `UnsupportedVariableError`), before any request | `ValueError` / `ValidationError`, `UnsupportedVariableError` |
| Run-time failures | sealed `NabiaException` hierarchy (see below) | `NabiaError` hierarchy |
| Hourly timestamps | `TZDateTime` (package:timezone) in the zone the provider reported, offset preserved | timezone-aware `datetime` |
| Daily dates | `CalendarDate` (Dart has no date type) | `date` |
| Settings | constructor arguments (`HttpOptions`, `OpenMeteoEndpoints`) | environment / `.env` |
| HTTP | `package:http`; inject your own `http.Client` if you want | httpx |
| TLS | the platform's trust store | OS trust store via truststore |

Exceptions, matching the contract's error kinds:

```text
NabiaException (sealed)
└─ ProviderException (sealed): provider, url (redacted)
   ├─ ProviderConnectionException      provider_connection
   ├─ ProviderHttpException            provider_http (statusCode)
   │  ├─ AuthenticationException       authentication (401/403)
   │  ├─ RateLimitException            rate_limit (retryAfter)
   │  └─ ProviderServerException       provider_server (5xx)
   ├─ ProviderContractException        provider_contract
   │  └─ UnitMismatchException         unit_mismatch
   └─ NoDataException                  no_data
```

### Credentials

Nabia never stores credentials. Providers that need a key will take it
as a constructor argument: the app decides where it lives (for
example, secure storage filled from a settings screen) and Nabia only
uses it for requests and masks it in every message. A key compiled
into an app can be extracted, so prefer keys the user supplies.

### Time zones

Hourly data are expressed in the zone the provider reports, using the
full IANA database (history back to 1940). Nabia loads its own copy on
first use and leaves `package:timezone`'s global database and local
location exactly as the app had them. A zone name the database lacks
falls back to the fixed UTC offset the provider reported.

### Not included

- Response cache: cache serialized series (`toJson`/`fromJson`) in the
  app if needed.
- pandas export and environment-based settings, which are Python-only.
- On the web, browsers follow redirects themselves; elsewhere Nabia
  never follows them, as in Python.

## Development

From this folder:

```sh
dart pub get
dart run tool/generate.dart        # after the contract changes
dart format .
dart analyze --fatal-infos
dart test
```

Or, from the repository root, every check at once (also the `dart`
pre-commit hook): `uv run python -m tools.dart`. Line coverage of
`lib/` (kept at 100%, like Python's):
`uv run python -m tools.dart coverage`.

Live tests against the real APIs are skipped by default:
`dart test --run-skipped -t live`.

- `lib/src/generated/` comes from `../contract` (never edit it);
  `test/contract_test.dart` fails while it is stale.
- `test/conformance_test.dart` replays `../contract/conformance/*.json`.
  A new provider in the contract fails there until its Dart client is
  registered in that test.
- `pubspec.yaml`, `lib/src/version.dart` and the Python
  `pyproject.toml` hold the same version; tests in both languages
  check it.
