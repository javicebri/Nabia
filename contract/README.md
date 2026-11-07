# Nabia contract

Language-neutral description of what Nabia guarantees, exported from
the Python reference implementation. Ports to other languages (the Dart
package) generate their code from these files and replay the
conformance cases, so the vocabulary, the unit conversions, the
provider tables and the expected behaviour live in one place.

The JSON files are generated: do not edit them by hand. After changing
the catalog, the output models, a provider or its conformance cases,
run

```sh
uv run python -m tools.contract          # regenerate
uv run python -m tools.contract --check  # exit 1 if stale
```

and commit the result. The `contract` pre-commit hook and
`tests/test_contract.py` fail while the files are stale. Review changes
to these files like code: a diff in a conformance case is a change of
behaviour.

## Files

| File | Content |
|------|---------|
| `catalog.json` | Units, conversions, resolutions, aggregations, source kinds and canonical variables. |
| `providers/<name>.json` | One provider: `endpoints` (default URLs, keyed by settings field), `constants` (every public constant of its `mapping.py`, lower-cased) and `datasets` (native name and unit per variable and resolution). |
| `conformance/<name>.json` | Golden cases: a call, the provider's answer and what must happen (request sent, series or error returned). |
| `models.schema.json` | JSON Schema of serialized `HourlySeries` and `DailySeries`. Every field is required: Python always emits them all. |

Functions in a provider's `mapping.py` (e.g. Open-Meteo's
`to_azimuth`) are logic, not data: the conformance cases cover them.

## Using it from a port

- Generate code at development time (constants, enums, tables) and
  commit it. Do not read these files at runtime: an installed package
  or a mobile app cannot reach them.
- `contract_version` changes only when the structure of a file changes
  in a way an existing generator cannot read.
- Order is significant: units, variables and table entries are listed
  in declaration order.

## Conventions

- Units are referenced by a stable key (`"celsius"`); `units` maps each
  key to the symbol used in output (`"°C"`).
- Every conversion is `(value - offset) / divisor`. Evaluate exactly
  that expression in IEEE 754 doubles, in that order, to reproduce
  Python's results bit for bit. Missing values (`null`) stay missing.
- Dates are ISO 8601 (`verified_on`).
- In a provider file, `unit` is the unit the provider reports. If the
  response reports a different unit, or a requested column is missing,
  it is a contract error: never coerce.

## Conformance cases

Cases are defined in `tests/providers/<name>/conformance.py`, each with
its declared outcome, and recorded by running the Python client against
a mocked transport; recording fails if the outcome differs. Python
replays the committed cases in `tests/test_conformance.py`, and every
port replays them the same way, with retries disabled:

1. Mock HTTP so that any request gets `response`: either an HTTP
   answer (`status`, `headers`, JSON `body`) or
   `{"failure": "connection"}`, a network failure.
2. Call `call.operation` with `call.location`, `call.variables` and
   `call.options`. Option names are Python keyword names
   (`past_days`); map them to the port's own style (`pastDays`).
   Dates are ISO strings, `surface` is `{tilt, aspect}`.
3. Check the request:
   - `request: null`: no request may be sent at all (invalid
     arguments and unsupported variables fail first).
   - Otherwise exactly one GET to `request.url` with exactly
     `request.params`. Numeric parameters may be compared by value
     (`"30.0"` and `"30"` are equivalent); every other value is
     compared as a string.
4. Check the outcome:
   - `expected.series`: the serialized series must be equal, numbers
     bit for bit and timestamps including their UTC offset.
   - `expected.error`: the port raises its equivalent of that error
     kind. `status_code` and `retry_after` must match when present
     (and be absent otherwise); the message must contain
     `message_contains` when present.

Error kinds, with the Python class each one maps to. Nested kinds are
special cases of their parent: keep that hierarchy (e.g. a sealed class
hierarchy in Dart) so callers can handle a whole family at once.

| Error kind | Python | Meaning |
|------------|--------|---------|
| `invalid_argument` | `ValueError` / `ValidationError` | Argument out of range or inconsistent; nothing is sent. |
| `unsupported_variable` | `UnsupportedVariableError` | Variable not offered for that dataset and resolution; nothing is sent. |
| `provider_connection` | `ProviderConnectionError` | The provider cannot be reached. |
| `provider_http` | `ProviderHTTPError` | Unexpected HTTP status; the provider's reason is kept when it gives one. |
| - `authentication` | `AuthenticationError` | HTTP 401/403: credentials rejected. |
| - `rate_limit` | `RateLimitError` | HTTP 429; `retry_after` is the wait the provider asked for, in seconds. |
| - `provider_server` | `ProviderServerError` | HTTP 5xx: failure on the provider's side. |
| `provider_contract` | `ProviderContractError` | Response does not match the expected structure or cannot form a valid series. |
| - `unit_mismatch` | `UnitMismatchError` | Reported unit differs from the table. |
| `no_data` | `NoDataError` | A requested variable has no value at all. |

`no_data` is a provider error but not a contract error: the provider
answered correctly and simply has no value for that source or period.

## Retries

Cases run without retries, so they do not cover this policy; ports
should follow it. Python retries network errors and HTTP 429, 500,
502, 503 and 504, up to `max_retries` times (3 by default). It waits
for the `Retry-After` the provider sent, capped at 30 s, or else an
exponential backoff (0.5 s doubling per attempt, capped at 30 s, plus
up to 0.5 s of jitter). When retries run out, the error reports the
provider's requested wait uncapped, so the caller decides.

## Rules the schema does not express

Serialized series must also satisfy:

1. `units` holds exactly the variables in `values`, each with its
   canonical unit from `catalog.json`.
2. Every column in `values` has the length of `time`; `null` marks a
   missing value.
3. `time` is strictly increasing. Hourly timestamps carry their UTC
   offset; daily entries are calendar dates in `timezone`.
4. `timezone` is the zone name the provider reported. When the time
   zone database lacks it, timestamps use the fixed UTC offset the
   provider reported.
5. A series holding `shortwave_radiation_tilted` has a `surface`.
   `aspect` is a compass direction (0 = north, clockwise); each
   provider translates its own convention.
6. A requested variable with no value at all is an error (`no_data`),
   not a column of `null`.
