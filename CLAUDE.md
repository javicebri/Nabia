# Nabia: guide for Claude

Typed Python (>=3.12) library giving normalized access to public
weather, climate, agricultural and forestry APIs. Other projects
(including Android apps) install it from Git tags, so output models
are a stable contract. Design: `docs/architecture.md`.

## Commands

Always run tools through `python -m`: Avast CyberCapture on this
machine sandboxes the `.exe` launchers in `.venv/Scripts`.

- Offline tests: `uv run python -m pytest`
- Contract tests against real APIs: `uv run python -m pytest -m live`
- Types: `uv run python -m mypy`
- Lint/format: `uv run ruff check --fix . ; uv run ruff format .`
- All hooks: `uv run python -m pre_commit run --all-files`
- Equivalence table: `uv run python -m nabia.catalog`
- Regenerate the language-neutral contract (commit it) after changing
  the catalog, output models, a provider or its conformance cases:
  `uv run python -m tools.contract` (`--check` only verifies)
- Dart port, inside `dart/`: `dart run tool/generate.dart` (after the
  contract changes), `dart format .`, `dart analyze --fatal-infos`,
  `dart test`; all at once from the root: `uv run python -m tools.dart`
- Create/refresh a spec snapshot (local only, git-ignored; never
  commit it): `uv run python -m tests.providers.<name>.spec`

## Layout

- `src/nabia/core/`: config, http (retries, cache, redaction), tls,
  errors, models (output contract)
- `src/nabia/catalog/`: canonical `Variable`/`Unit` vocabulary and
  `VariableTable` (equivalences and drift checks)
- `src/nabia/providers/<name>/`: one self-contained provider (README,
  config, mapping, schemas, parser, client)
- `tests/` mirrors `src/`; `tests/live/` hits the real APIs;
  `tests/providers/<name>/conformance.py` defines the behaviour shared
  with ports (replayed by `tests/test_conformance.py`)
- `contract/`: generated JSON (catalog, provider tables, model schema,
  conformance cases) that ports to other languages build from and
  test against; see its README. Large: grep it, never read it whole
- `tools/`: repository maintenance scripts (contract export,
  conformance recording, Dart checks), not shipped; never
  provider-specific
- `dart/`: idiomatic Dart port (pure Dart, for Flutter). Python is the
  reference: change behaviour there first, regenerate the contract,
  then make Dart pass it. `lib/src/generated/` is generated; never edit
  it. See `dart/README.md`

## Token-efficient workflow

- For provider work, read only `providers/<name>/`, its tests and
  `docs/adding-a-provider.md`. Do not open other providers.
- Never read fixtures or `uv.lock` whole; grep them.
- Provider facts (endpoints, quirks, limits) live in the provider
  README; update it instead of re-researching.

## Rules

- **Scope (agreed with the user)**:
  - Free data only: no paid or subscription services (a free
    registration to obtain an API key is fine).
  - No geocoding or place search.
  - Raw provider data only: normalize names, units, time zones and
    request parameters, but never compute, estimate or derive data
    (no models, balances or derived variables).
- **Ask before inferring**: unclear API semantics, units, new
  dependencies or public API changes are the user's decision.
- PEP 8 (79 cols, docstrings 72), Google docstrings, English comments,
  strict mypy, pydantic models.
- Output uses canonical names and units only. Native names live
  exclusively in `providers/<name>/mapping.py`.
- Raw schemas mirror upstream. Unexpected data raises
  `ProviderContractError`; never guess or silently coerce.
- Security: credentials only from env/.env as `SecretStr`; never log,
  print, cache, commit or hardcode them; never read `.env`. HTTPS
  only, no redirects. Offline tests mock HTTP with respx.
- Public API changes: update `CHANGELOG.md` and follow SemVer.
