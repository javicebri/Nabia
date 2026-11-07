# Nabia contract

Language-neutral description of what Nabia guarantees, exported from
the Python reference implementation. Ports to other languages (the Dart
package) generate their code from these files, so the vocabulary, the
unit conversions and the provider tables live in one place.

The JSON files are generated: do not edit them by hand. After changing
the catalog, the output models or a provider mapping, run

```sh
uv run python -m tools.contract
```

and commit the result. `tests/test_contract.py` fails while they are
stale.

## Files

| File | Content |
|------|---------|
| `catalog.json` | Units, conversions, resolutions, aggregations, source kinds and canonical variables. |
| `providers/<name>.json` | One provider: default endpoints, native names and units per dataset and resolution, request parameters that pin units, attribution and other constants of its `mapping.py`. |
| `conformance/<name>.json` | Golden cases: a call, the provider response and what must happen (request sent, series or error returned). |
| `models.schema.json` | JSON Schema of serialized `HourlySeries` and `DailySeries`. |

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

Each case is recorded by running the Python client against a mocked
transport, so it states what the reference implementation does. A port
replays every case in its own tests:

1. Mock HTTP so that any request receives `response` (`status` and
   JSON `body`).
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
     kind; when present, `status_code` must match and the message must
     contain `message_contains`.

| Error kind | Python | Meaning |
|------------|--------|---------|
| `invalid_argument` | `ValueError` / `ValidationError` | Argument out of range or inconsistent; nothing is sent. |
| `unsupported_variable` | `UnsupportedVariableError` | Variable not offered for that dataset and resolution. |
| `provider_http` | `ProviderHTTPError` | Unexpected HTTP status; the provider's reason is kept. |
| `provider_contract` | `ProviderContractError` | Response does not match the expected structure. |
| `unit_mismatch` | `UnitMismatchError` | Reported unit differs from the table (a contract error). |
| `no_data` | `NoDataError` | A requested variable has no value at all. |

## Rules the schema does not express

Serialized series must also satisfy:

1. `units` holds exactly the variables in `values`, each with its
   canonical unit from `catalog.json`.
2. Every column in `values` has the length of `time`; `null` marks a
   missing value.
3. `time` is strictly increasing. Hourly timestamps carry their UTC
   offset; daily entries are calendar dates in `timezone` (IANA name).
4. A series holding `shortwave_radiation_tilted` has a `surface`.
   `aspect` is a compass direction (0 = north, clockwise); each
   provider translates its own convention (see its README).
5. A requested variable with no value at all is an error (`NoDataError`
   in Python), not a column of `null`.
6. Python emits every field, including those left at their default
   (`units`, `resolution`, `null` provenance fields).
