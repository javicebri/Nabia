# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/).

While the version is `0.x`, minor releases may contain breaking changes;
they are always listed under **Changed** or **Removed**.

## [Unreleased]

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
