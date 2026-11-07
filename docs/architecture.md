# Architecture

## Goal

Nabia is an intermediary between consumer projects and public data
APIs. Upstream APIs change; consumer code should not. All adaptation
happens inside Nabia, which is versioned and installed from Git tags.

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
| `-m live`    | Every mapped variable requested from the real API      |

`verified_on` records the last successful live check. A mismatch
raises; Nabia never returns data it cannot vouch for.

## Errors

`NabiaError` is the single root. Provider errors carry the provider id
and a redacted URL. HTTP failures map to typed subclasses; schema or
unit surprises map to `ProviderContractError`.

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
