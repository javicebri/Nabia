# Adding a provider

Use `providers/open_meteo/` as the reference implementation.

## Checklist

1. **Confirm scope with the user**: endpoints, datasets, variables,
   terms of use, whether a key is needed. Do not guess semantics.
2. **Create `providers/<name>/`**:
   - `README.md`: endpoints, docs links, terms/licence, rate limits,
     quirks, verification date.
   - `config.py`: `EnvSettings` subclass with
     `env_prefix="NABIA_<NAME>_"`. Keys as `SecretStr | None`, read
     with `require_secret(...)` at call time. URLs typed `HttpsUrl`.
   - `mapping.py`: one `VariableTable` per dataset/endpoint, with
     `reference_url` and `verified_on`. Pin units through request
     parameters when the API allows it.
   - `schemas.py`: pydantic models mirroring the raw JSON; declare
     only what is used.
   - `parser.py`: raw schema -> `HourlySeries`/`DailySeries`, using
     `VariableTable.extract` (it checks columns, units and empty
     columns). Fill `source`, `source_kind` and `attribution` only
     with facts the request or the response guarantee.
   - `client.py`: subclass `BaseClient`, set `PROVIDER`, validate
     arguments with `@validate_call`, pass `secret_params` for
     credentials sent as query parameters.
3. **New canonical variables** go in `catalog/variables.py` (with a
   precise definition) before they are mapped. Ask the user when the
   provider definition differs (height, aggregation, interval).
4. **New units** go in `catalog/units.py` with their conversion
   (`Conversion(offset=..., divisor=...)`) and a test.
5. **Register** the tables in `providers/registry.py`, add an export
   function for the provider to `tools/contract.py` and its
   conformance cases to `tools/conformance.py` (copy the Open-Meteo
   ones), and regenerate the contract with
   `uv run python -m tools.contract`.
6. **Tests**:
   - `tests/providers/<name>/` with trimmed real responses in
     `fixtures/` (scrub any credential or personal data).
   - `tests/live/test_<name>_live.py` requesting every mapped variable,
     marked `live`. Keys come from the environment; skip when absent.
   - If the provider publishes a specification: `tests/providers/<name>/
     spec.py` (sources, `extract`, `used`, `KNOWN_SPEC_GAPS`), an
     offline `test_spec.py` and a live spec test. Copy the Open-Meteo
     ones and reuse the helpers in `tests/specs.py`. The snapshot is
     generated locally and git-ignored; never commit it.
7. **Docs**: provider row in `README.md`, variables in `.env.example`,
   entry in `CHANGELOG.md`.

## When an upstream API changes (drift runbook)

1. Reproduce: `uv run python -m pytest -m live -k <name>`.
2. Read the error: `ProviderContractError` names the missing column or
   field; `UnitMismatchError` shows reported vs expected unit; a spec
   test lists values added or removed in the published specification.
3. Check the provider changelog/docs and update, in this order:
   `schemas.py` (structure), `mapping.py` (names/units),
   `parser.py` (logic). Ask the user if a definition changed meaning.
4. Refresh affected fixtures with a trimmed real response, and the
   spec snapshot with `uv run python -m tests.providers.<name>.spec`.
5. Run the full suite, bump `verified_on`, note it in the provider
   README and `CHANGELOG.md`, and tag a patch release.
