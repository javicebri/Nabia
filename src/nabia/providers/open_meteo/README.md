# Open-Meteo

Global weather forecast and historical reanalysis. No API key for
non-commercial use.

| Dataset    | Endpoint                                         | Docs |
|------------|--------------------------------------------------|------|
| `forecast` | `https://api.open-meteo.com/v1/forecast`         | <https://open-meteo.com/en/docs> |
| `archive`  | `https://archive-api.open-meteo.com/v1/archive`  | <https://open-meteo.com/en/docs/historical-weather-api> |

Equivalence tables: `mapping.py` (last verified: see `VERIFIED_ON`).

Published specification: one OpenAPI file per API in
<https://github.com/open-meteo/open-meteo/tree/main/openapi>
(`forecast.yml`, `historical-weather.yml`), watched by
`tests/providers/open_meteo/spec.py`. It lags the live API: the daily
forecast variables `temperature_2m_mean` and
`relative_humidity_2m_mean` work but are undocumented there
(`KNOWN_SPEC_GAPS`, checked 2026-11-07).

## Terms of use

- Free tier is for **non-commercial use** only; commercial use needs a
  paid plan with an API key (not implemented yet).
- Data is licensed **CC BY 4.0**: applications that show it must credit
  Open-Meteo. Check <https://open-meteo.com/en/terms> for the current
  terms and rate limits before relying on them.

## Request conventions used by Nabia

- Units are pinned with `temperature_unit=celsius`,
  `wind_speed_unit=ms` and `precipitation_unit=mm` (`UNIT_PARAMS`).
- Hourly requests use `timeformat=unixtime`: timestamps are UTC
  instants converted to the response time zone.
- Daily requests use `timeformat=iso8601`: plain calendar dates.
- `model=` sends Open-Meteo's `models` parameter (one model only).
  Without it Open-Meteo uses `best_match` and the series reports
  `source=None`; archive kinds come from `ARCHIVE_SOURCES`.
- `elevation=` overrides the terrain altitude Open-Meteo would use.
- `series.attribution` holds the CC BY 4.0 credit line.

## Where the data come from

Open-Meteo measures nothing itself: it serves model output.

- **Forecast**: numerical weather prediction models from national
  services and ECMWF (51 options in the published specification),
  combined per location by `best_match`.
- **Archive**: reanalyses (ERA5, ERA5-Land, CERRA) and ECMWF IFS
  analyses. A reanalysis re-runs a weather model over the past while
  assimilating observations (stations, satellites, radiosondes,
  aircraft, buoys). Precipitation is produced by the model, not taken
  from rain gauges, so it is a grid-cell estimate, not a measurement.
- Some variables are computed by Open-Meteo, e.g. ET0 (FAO-56) from
  model temperature, humidity, wind and radiation.

## Quirks (verified 2026-11-07)

- **Fixed UTC offset per response.** Open-Meteo applies the offset of
  the start of the range to the whole response, even across a DST
  change: a 2-day request starting in CET returns 48 consecutive UTC
  hours, ending at 00:00 CEST. Daily aggregates therefore use that
  fixed offset. Nabia's hourly timestamps are still exact instants.
- **Grid cell and elevation.** Open-Meteo looks up the terrain
  altitude of the requested point in a 90 m digital elevation model and
  returns it as `elevation` (Madrid 40.42, -3.70: 667 m from both the
  elevation API and every archive model). It uses that altitude to
  pick a grid cell of similar altitude and to correct temperature:
  declaring the point 1000 m higher (`elevation=1667`) moved the cell
  and lowered the daily mean by about 6.9 °C. The returned
  `latitude`/`longitude` are the chosen cell, so `series.location` and
  `series.elevation` describe different things.
- **Data source changes with the date.** With the default
  `best_match`, the archive answered Madrid 2024 with ECMWF IFS (fine
  grid) and Madrid 1990 with ERA5 (coarser grid); the response does not
  say which source was used. Long series can therefore mix sources.
  ERA5-Land and CERRA returned no precipitation for those requests
  (all values null).
- **Archive delay.** The newest days of the archive appear with a few
  days of delay.
- **Errors** come as HTTP 400 with `{"error": true, "reason": "..."}`;
  the reason is included in `ProviderHTTPError`.
- An unknown variable name is rejected with HTTP 400, which is how a
  renamed variable shows up in the live tests.
