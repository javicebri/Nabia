# Open-Meteo

Global weather forecast and historical reanalysis. No API key for
non-commercial use.

| Dataset    | Endpoint                                         | Docs |
|------------|--------------------------------------------------|------|
| `forecast` | `https://api.open-meteo.com/v1/forecast`         | <https://open-meteo.com/en/docs> |
| `archive`  | `https://archive-api.open-meteo.com/v1/archive`  | <https://open-meteo.com/en/docs/historical-weather-api> |

Equivalence tables: `mapping.py` (last verified: see `VERIFIED_ON`).

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

## Quirks (verified 2026-11-07)

- **Fixed UTC offset per response.** Open-Meteo applies the offset of
  the start of the range to the whole response, even across a DST
  change: a 2-day request starting in CET returns 48 consecutive UTC
  hours, ending at 00:00 CEST. Daily aggregates therefore use that
  fixed offset. Nabia's hourly timestamps are still exact instants.
- **Grid snapping.** Returned coordinates are the model grid cell, not
  the requested point; Nabia exposes them as `series.location`.
- **Archive delay.** The newest days of the archive appear with a few
  days of delay.
- **Errors** come as HTTP 400 with `{"error": true, "reason": "..."}`;
  the reason is included in `ProviderHTTPError`.
- An unknown variable name is rejected with HTTP 400, which is how a
  renamed variable shows up in the live tests.
