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

## Layout

- `src/nabia/core/`: config, http (retries, cache, redaction), tls,
  errors, models (output contract)
- `src/nabia/catalog/`: canonical `Variable`/`Unit` vocabulary and
  `VariableTable` (equivalences and drift checks)
- `src/nabia/providers/<name>/`: one self-contained provider (README,
  config, mapping, schemas, parser, client)
- `tests/` mirrors `src/`; `tests/live/` hits the real APIs

## Token-efficient workflow

- For provider work, read only `providers/<name>/`, its tests and
  `docs/adding-a-provider.md`. Do not open other providers.
- Never read fixtures or `uv.lock` whole; grep them.
- Provider facts (endpoints, quirks, limits) live in the provider
  README; update it instead of re-researching.

## Rules

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
