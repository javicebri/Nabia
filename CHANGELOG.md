# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/).

While the version is `0.x`, minor releases may contain breaking changes;
they are always listed under **Changed** or **Removed**.

## [Unreleased]

### Added

- `Conversion` and `CONVERSIONS` in `nabia.catalog`: unit conversions
  are declared as data, `(value - offset) / divisor`. Results are
  unchanged, bit for bit.
- `contract/`: language-neutral export of the catalog, the provider
  tables and endpoints, the output model schema and golden
  conformance cases (call, response, expected request and result),
  for ports to other languages. Regenerated with
  `python -m tools.contract`, checked with `--check` and a pre-commit
  hook (not shipped in the wheel).

### Changed

- The serialization JSON Schema of output models
  (`model_json_schema(mode="serialization")`) lists every field as
  required, since serialization always emits them all.
- A `Retry-After: 0` header now retries immediately instead of
  falling back to exponential backoff.

### Fixed

- `RateLimitError.retry_after` reports the wait the provider asked for.
  It was capped at 30 s, the limit Nabia applies to its own waits
  between retries, so callers could retry too early.

### Removed

- `nabia.catalog.units.Converter`, an undocumented type alias for the
  former conversion lambdas.

## [0.3.0] - 2026-11-07

### Added

- Variables `precipitation_probability` (hourly) and
  `precipitation_probability_max` (daily), forecast only, with the
  new `probability` aggregation.
- Variable `shortwave_radiation_tilted` (hourly) and the `Surface`
  model (tilt and compass aspect). Series holding it record the
  surface. Open-Meteo's south-based azimuth is translated.

## [0.2.0] - 2026-11-07

### Added

- Provenance on every series: `source`, `source_kind` (new
  `SourceKind` enum) and `attribution`. Optional fields, so series
  serialized with 0.1.0 still load.
- `NoDataError` when a requested variable has no values at all.
- Open-Meteo: optional `model=` to choose the source (default
  `best_match`, unchanged) and `elevation=` to set the altitude of
  the point; the spec watcher also tracks the archive source list.
- Upstream specification watcher: Open-Meteo's published OpenAPI files
  are reduced to a local, git-ignored JSON snapshot; offline tests
  check every value the client sends, live tests report upstream
  additions and removals.
- `NOTICE` crediting the Open-Meteo data (CC BY 4.0) in test fixtures.

### Changed

- A variable returned entirely empty now raises `NoDataError`
  instead of yielding a column of `None`.

### Fixed

- `elevation` documentation: for Open-Meteo it is the terrain
  altitude of the requested point (90 m terrain model), not the
  altitude of the grid cell.
- README: clarify that `python -m nabia.catalog` needs the interpreter
  where Nabia is installed (`uv run` inside this repository).

## [0.1.0] - 2026-11-07

### Added

- Project rewritten as a library. The previous Lotka-Volterra
  simulator is preserved under the git tag `legacy-simulator`.
- Core: settings from environment/`.env`, shared HTTP client with
  retries, error mapping, optional SQLite response cache, secret
  redaction in logs and errors, TLS through the OS trust store.
- Canonical variable/unit catalog and per-provider equivalence tables
  with unit-drift detection.
- Output models `HourlySeries` and `DailySeries` with pandas export
  (`nabia[pandas]`).
- Open-Meteo provider: forecast and historical (archive), hourly and
  daily.
