# Nabia

Typed, normalized access to public weather, climate, agricultural and
forestry data APIs.

Nabia sits between your projects and upstream APIs. Every provider is
mapped onto one canonical vocabulary (variable names, units,
timezone-aware timestamps), so consumer code does not change when an
API evolves or when you switch providers: only Nabia is updated.

## Providers

| Provider       | Data                                   | Key      | Status      |
|----------------|----------------------------------------|----------|-------------|
| Open-Meteo     | Forecast and historical weather        | No       | Available   |
| AEMET OpenData | Spanish observations and forecasts     | Yes      | Planned     |
| NASA POWER     | Agro-climatology, solar radiation      | No       | Planned     |
| Copernicus CDS | ERA5 reanalysis, climate projections   | Yes      | Planned     |
| Copernicus ADS | Air quality, atmospheric composition   | Yes      | Planned     |
| Copernicus CLMS| Land cover, vegetation, forests        | Yes      | Planned     |

Each provider has a README with endpoints, terms of use and quirks,
e.g. [`providers/open_meteo/README.md`](src/nabia/providers/open_meteo/README.md).

## Installation

Install a tagged version from Git, so each project controls when it
upgrades:

```bash
pip install "nabia[pandas] @ git+https://github.com/javicebri/Nabia@v0.4.0"
# or, with uv
uv add git+https://github.com/javicebri/Nabia --tag v0.4.0 --extra pandas
```

The `pandas` extra is optional and only needed for `to_dataframe()`.

### Dart and Flutter

A Dart port lives in [`dart/`](dart/README.md), released with the same
tags. Its tables are generated from the shared
[contract](contract/README.md) and it passes the same conformance
cases as Python:

```yaml
dependencies:
  nabia:
    git:
      url: https://github.com/javicebri/Nabia.git
      path: dart
      ref: v0.4.0
```

## Quick start

```python
from datetime import date

from nabia import GeoPoint, Variable
from nabia.providers.open_meteo import OpenMeteoClient

madrid = GeoPoint(latitude=40.42, longitude=-3.70)

with OpenMeteoClient() as client:
    daily = client.historical_daily(
        madrid,
        [Variable.PRECIPITATION, Variable.REFERENCE_EVAPOTRANSPIRATION],
        start=date(2024, 3, 1),
        end=date(2024, 3, 31),
    )

daily.values[Variable.PRECIPITATION]  # tuple[float | None, ...] in mm
daily.units  # {Variable.PRECIPITATION: Unit.MILLIMETRE, ...}
daily.to_dataframe()  # pandas, index = date
daily.model_dump_json()  # serializable, loadable again
daily.source, daily.source_kind  # provenance, when known for certain
daily.attribution  # credit line the data licence requires
```

Type against capabilities to stay provider-agnostic:

```python
from nabia import DailySeries
from nabia.providers.protocols import HistoricalDailyProvider


def rainfall(source: HistoricalDailyProvider) -> DailySeries: ...
```

## Variables

All output uses the canonical catalog in `nabia.catalog`. Print the
cross-provider equivalence table with:

```bash
python -m nabia.catalog          # in a project where Nabia is installed
uv run python -m nabia.catalog   # inside this repository
```

Use the Python of the environment where Nabia is installed (>= 3.12);
a system interpreter without Nabia fails with
`ModuleNotFoundError: No module named 'nabia'`.

Requesting a variable a provider does not offer raises
`UnsupportedVariableError` before any network call.

Radiation on an inclined surface needs the surface, given as tilt
and compass aspect (0 = north, 90 = east, 180 = south, 270 = west);
Nabia translates it to each provider's convention:

```python
from nabia import Surface

client.forecast_hourly(
    point,
    [Variable.SHORTWAVE_RADIATION_TILTED],
    surface=Surface(tilt=30, aspect=0),  # 30 degree slope facing north
)
```

## Configuration

Settings come from environment variables or a `.env` file in the
working directory of the consuming project (see `.env.example`).
Credentials are never stored in code.

| Variable                  | Default    | Meaning                               |
|---------------------------|------------|---------------------------------------|
| `NABIA_TIMEOUT_SECONDS`   | `30`       | Per-request timeout                   |
| `NABIA_MAX_RETRIES`       | `3`        | Retries on network errors, 429, 5xx   |
| `NABIA_SSL_TRUST`         | `system`   | `system` (OS store) or `certifi`      |
| `NABIA_CACHE_ENABLED`     | `false`    | Cache successful responses on disk    |
| `NABIA_CACHE_PATH`        | user cache | SQLite file for the cache             |
| `NABIA_CACHE_TTL_SECONDS` | `3600`     | Lifetime of cached responses          |
| `NABIA_USER_AGENT`        | `nabia/x`  | `User-Agent` header                   |

Provider-specific variables use the prefix `NABIA_<PROVIDER>_`.

## Errors

Every error derives from `nabia.NabiaError`:

- `ConfigurationError`: missing key or invalid settings.
- `UnsupportedVariableError`: variable not mapped for that provider.
- `ProviderConnectionError`: network failure after retries.
- `ProviderHTTPError` (`AuthenticationError`, `RateLimitError`,
  `ProviderServerError`): unexpected HTTP status.
- `NoDataError`: a requested variable came back entirely empty (the
  chosen source may not provide it, or the period is not available).
- `ProviderContractError` (`UnitMismatchError`): the upstream response
  changed shape or units. Nabia fails instead of returning wrong data.

## Security and privacy

- API keys are read from the environment only, held as `SecretStr` and
  redacted from logs (including httpx's), errors and cache keys.
- HTTPS only; redirects are never followed.
- The cache is off by default because it records which places and
  dates were queried.
- TLS is verified against the OS trust store (works behind antivirus
  HTTPS scanning or corporate proxies). On Android, Nabia falls back
  to the `certifi` bundle.

## Data licensing

Every series carries the provider's required credit line in
`series.attribution`; show it wherever the data are displayed.
Each provider has its own terms (attribution, commercial use, rate
limits); see the provider README. Applications displaying the data
must honour them.

## Development

```bash
uv sync --all-extras
uv run python -m pre_commit install       # secret scan, lint, types
uv run python -m pytest                   # offline tests
uv run python -m pytest -m live           # contract tests (real APIs)
uv run python -m mypy
```

Run tools with `python -m ...` rather than the `.exe` launchers in
`.venv/Scripts`, which some antivirus products sandbox.

Contributor docs: [`docs/architecture.md`](docs/architecture.md) and
[`docs/adding-a-provider.md`](docs/adding-a-provider.md).

## Versioning

Semantic Versioning, documented in [`CHANGELOG.md`](CHANGELOG.md).
Breaking changes to the output models or public functions require a
new major version (minor while in `0.x`).
