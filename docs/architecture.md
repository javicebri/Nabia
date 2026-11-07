# Architecture

## Goal

Nabia is an intermediary between consumer projects and public data
APIs. Upstream APIs change; consumer code should not. All adaptation
happens inside Nabia, which is versioned and installed from Git tags.

### Scope rules

- Only free data sources; a free registration for an API key is
  acceptable, paid or subscription plans are not.
- No geocoding or place search.
- Nabia returns what the provider delivers: it normalizes names,
  units, time zones and request parameters (e.g. orientation
  conventions) but never computes, estimates or derives data.

## Layers

```text
consumer project
      |  canonical Variable / Unit, HourlySeries / DailySeries
      v
providers/<name>/client.py    public methods, argument validation
providers/<name>/mapping.py   VariableTable: canonical <-> native names
providers/<name>/parser.py    raw schemas -> output models
providers/<name>/schemas.py   pydantic mirror of the upstream JSON
      |
core/http.py                  retries, errors, cache, redaction, TLS
      v
upstream API
```

`catalog/` (vocabulary and equivalence tables) and `core/` never
import from `providers/`. Providers never import each other.

## Two model layers

1. **Raw schemas** (`schemas.py`) mirror the upstream payload. When an
   API changes, this is usually the only file to touch. Unknown fields
   are ignored; missing or retyped fields raise
   `ProviderContractError`.
2. **Output models** (`core/models.py`) are the stable contract:
   canonical variables, canonical units, timezone-aware timestamps,
   immutable, JSON round-trippable.

## Equivalence tables and drift detection

`catalog/variables.py` defines each canonical variable once: unit,
aggregation (instant, mean, sum, ...) and allowed resolutions. Each
provider declares a `VariableTable` that maps canonical variables to
its native name and the unit it reports.

Definitions drift over time, so tables are checked at three moments:

| When         | Check                                                  |
|--------------|--------------------------------------------------------|
| Import time  | Resolution allowed, unit convertible to canonical unit |
| Every call   | Native column present, reported unit equals the table  |
| Offline      | Every name/value the client sends is in the spec snapshot |
| `-m live`    | Every mapped variable requested from the real API      |
| `-m live`    | Published spec compared with the snapshot (early warning) |

`verified_on` records the last successful live check. A mismatch
raises; Nabia never returns data it cannot vouch for.

### Upstream specifications

When a provider publishes a machine-readable description (OpenAPI,
OGC API Processes, parameter metadata), its test folder can hold a
small JSON snapshot of the parts Nabia relies on (`spec_snapshot.json`,
built by `spec.py`), never the full document. Snapshots are local
maintenance baselines: git-ignored, never published, and the tests
that need one are skipped until it is created. Specifications can lag
the real API, so the live API stays the source of truth: values that
work live but are not documented yet are listed in `KNOWN_SPEC_GAPS`,
and a test fails as soon as upstream documents them. Specifications
are used as a checker, not to generate code.

## Language-neutral contract

Python is the reference implementation. Apps written in other
languages (Flutter) cannot use it, so Nabia will also be ported to
Dart, in this repository, as idiomatic Dart rather than a line-by-line
clone. What both implementations must share is exported to
`contract/` by `python -m tools.contract`: the catalog (units,
conversions, variables), each provider's endpoints and mapping
tables, the JSON Schema of the output models and golden conformance
cases. Ports generate their code from it at development time and
replay the cases in their tests: same call and provider response, same
request sent and same series or error. An offline test fails while the
committed files are stale. Unit conversions are declared as data (`(value - offset) /
divisor`) so ports reproduce Python's results bit for bit.

## Errors

`NabiaError` is the single root. Provider errors carry the provider id
and a redacted URL. HTTP failures map to typed subclasses; schema or
unit surprises map to `ProviderContractError`. A requested variable
with no value at all raises `NoDataError` (checked in
`VariableTable.extract`, so every provider inherits it); partially
missing values are returned as `None`.

## Provenance

Every series states what is known for certain about its origin:

- `source`: model, product or station; `None` when the provider
  chooses the source itself without reporting it.
- `source_kind`: `forecast`, `analysis`, `reanalysis`,
  `observation` or `satellite`; only `observation` is a measurement.
  `None` when it cannot be stated for the whole series.
- `attribution`: the credit line the data licence requires.

Nabia never guesses provenance: it is filled only from explicit
requests or from what the provider reports.

## Security model

- Secrets: env/`.env` only, `SecretStr`, no defaults in code.
- Redaction: URLs in errors/logs, a filter on the `httpx` and
  `httpcore` loggers, and cache keys computed without secrets.
- Transport: HTTPS enforced in settings, redirects disabled, TLS
  verified against the OS store (`truststore`) or `certifi` on
  platforms where the OS store is unreadable (Android).
- Repository: `.gitignore` for credential files, `detect-secrets` and
  `detect-private-key` in pre-commit.
- Privacy: the response cache is opt-in and stores only bodies.

## Decision log

| Date       | Decision |
|------------|----------|
| 2026-11-07 | Rewrite as a library; old simulator kept at tag `legacy-simulator`. |
| 2026-11-07 | Python >= 3.12, synchronous httpx client, pydantic v2. |
| 2026-11-07 | Distribution via `pip install git+...@vX.Y.Z` (SemVer tags). |
| 2026-11-07 | Tooling: uv, ruff (PEP 8, 79 cols), strict mypy, pytest, pre-commit. |
| 2026-11-07 | Canonical vocabulary only in output; native names stay in mapping tables. |
| 2026-11-07 | Extras: pandas export; opt-in SQLite response cache. |
| 2026-11-07 | TLS via OS trust store by default; certifi fallback (Android). |
| 2026-11-07 | First providers: Open-Meteo (reference), then AEMET, NASA POWER, Copernicus CDS/ADS/CLMS. |
| 2026-11-07 | Published API specs watched as drift early warning; not used for code generation. |
| 2026-11-07 | Provenance fields (`source`, `source_kind`, `attribution`) on every series; `analysis` kind added for operational analyses such as ECMWF IFS. |
| 2026-11-07 | An entirely empty variable raises `NoDataError` instead of returning `None` values. |
| 2026-11-07 | Open-Meteo: optional `model=` (default `best_match`, unchanged) and `elevation=`. |
| 2026-11-07 | Scope rules: free sources only, no geocoding, no computed or derived data. |
| 2026-11-07 | Precipitation probability (forecast) and tilted irradiance added; surfaces use a compass aspect (0 = north) translated per provider. |
| 2026-11-07 | Spec snapshots stay local (git-ignored): development happens on one machine, nothing derived from upstream specs is published. |
| 2026-11-07 | Python stays the reference; an idiomatic Dart port will live in this repository (monorepo) and build from the generated `contract/`. Credentials stay agnostic: the consuming app supplies them. |
| 2026-11-07 | Unit conversions declared as affine data instead of code, so ports reproduce results exactly. |
