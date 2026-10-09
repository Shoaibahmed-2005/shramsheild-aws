# ShramShield method

How the heat-stress numbers are produced, what the screening limits mean, and what this
method cannot tell you. All numbers in section 6 come from the run recorded in
`core/data/backtest/backtest.json`; nothing here is estimated or rounded by hand.

## 1. The problem

Outdoor work in India continues through months when the combination of heat and humidity
makes the body unable to shed heat fast enough. A thermometer alone does not capture that,
so a site can be dangerous on a day the air temperature looks unremarkable.

## 2. What WBGT is, and why air temperature alone misleads

WBGT (Wet Bulb Globe Temperature) is an occupational heat-stress index. It combines a
natural wet-bulb temperature, which responds to humidity, a black globe temperature, which
responds to sun and wind, and the air temperature, as
`WBGT = 0.7 x Tnw + 0.2 x Tg + 0.1 x Ta`. Humidity and radiation therefore carry most of
the weight, and air temperature only a tenth of it.

The consequence is visible in our own data. Over April to June 2024, Delhi had 268 work
hours at or above 40 C air temperature but 320 dangerous hours, while Chennai had only 6
work hours reaching 40 C and 679 dangerous hours. Dry heat trips a thermometer; humid
coastal heat does not. Wind matters in the same way: still air removes the convective
cooling of the globe, so a calm sunny hour can be more stressful than a hotter, windier one.

## 3. Data and model

**Weather.** Hourly data from Open-Meteo: `temperature_2m`, `relative_humidity_2m`,
`surface_pressure`, `wind_speed_10m`, `shortwave_radiation` and `direct_radiation`,
requested with `wind_speed_unit=ms` and `timezone=Asia/Kolkata`. Live plans use the forecast
API; the backtest uses the historical archive API, which is ERA5-based reanalysis.

**WBGT.** Computed with `calculate_wbgt_liljegren` from ECMWF's `thermofeel` 2.3.0, the
physically based Liljegren et al. (2008) method, which solves the globe and natural wet-bulb
energy balances. Inputs are converted to the units it documents: temperature in kelvin,
humidity in percent, pressure in hPa, wind in m/s, radiation in W/m2.

**Solar angle.** The direct-beam fraction needs the cosine of the solar zenith angle, which
we compute with a standard-library NOAA approximation (`core/shramshield_core/solar.py`),
checked against six known angles for Chennai and Delhi and agreeing within 0.0011.
Open-Meteo radiation values are the mean of the *preceding* hour, so the solar angle is
evaluated 30 minutes before the hour label. At night the shortwave and direct terms are set
to zero. The direct fraction is `direct_radiation / shortwave_radiation` when shortwave
exceeds 10 W/m2, clamped to 0 to 1, and zero otherwise.

**Fallback.** If wind or radiation is missing for an hour we use `calculate_wbgt_simple`,
which has no radiation or wind term, and label that hour `simple_fallback`. It assumes
sunshine and so overestimates at night and under cloud; it is a conservative substitute,
never an improvement. If only pressure is missing we substitute 1010 hPa and still call it
Liljegren. If temperature or humidity is missing the hour has no WBGT and no advice at all:
it is reported as `UNKNOWN` rather than guessed. In the backtest run none of the four
archive responses contained a null value, so no hour used the fallback.

One further guard: at exactly 0% relative humidity the Liljegren solver takes the logarithm
of a zero vapour pressure and returns NaN. We never pass that on as a number. Such an hour
falls back to the simple formula, and if that also fails to produce a number the hour is
`UNKNOWN`. Open-Meteo does not report 0% humidity in practice, but a plan must never carry
an invented or non-numeric value.

## 4. Screening limits

WBGT limits in degrees Celsius. Source: ACGIH 2026 TLV Table 1 as summarised by CCOHS. A
dash means the table lists no value for that combination.

| Work allocation | Level | light | moderate | heavy | very heavy |
|---|---|---|---|---|---|
| **Acclimatized** | | | | | |
| 75-100% | GREEN | 31.0 | 28.0 | -- | -- |
| 50-75% | YELLOW | 31.0 | 29.0 | 27.5 | -- |
| 25-50% | ORANGE | 32.0 | 30.0 | 29.0 | 28.0 |
| 0-25% | RED | 32.5 | 31.5 | 30.5 | 30.0 |
| **Unacclimatized** | | | | | |
| 75-100% | GREEN | 28.0 | 25.0 | -- | -- |
| 50-75% | YELLOW | 28.5 | 26.0 | 24.0 | -- |
| 25-50% | ORANGE | 29.5 | 27.0 | 25.5 | 24.5 |
| 0-25% | RED | 30.0 | 29.0 | 28.0 | 27.0 |

An hour is classified by taking the first band, most permissive first, whose limit is listed
and is at or above the hour's WBGT. If no band fits, the level is STOP. Because the table
lists no value for the most permissive bands at heavy and very heavy work, the best level
reachable is capped: YELLOW for heavy work and ORANGE for very heavy work, however mild the
weather. Each hour's reason text says so when that cap applies.

This table is a screening tool for an 8-hour day. ACGIH notes it is more protective than
the TLV itself and is **not** a prescription of work and recovery periods.

## 5. Levels

| Level | Work per hour | Rest per hour | Meaning |
|---|---|---|---|
| GREEN | 60 min | 0 min | Within the screening limits |
| YELLOW | 45 min | 15 min | Moderate heat stress |
| ORANGE | 30 min | 30 min | High heat stress |
| RED | 15 min | 45 min | Very high heat stress |
| STOP | 0 min | 60 min | Above every screening limit |
| UNKNOWN | -- | -- | Weather data missing; no advice given |

## 6. The backtest

**Question.** Over a past period, how many dangerous work hours would a plain
air-temperature alert have missed, compared with the WBGT levels above?

**Definitions.** A *dangerous hour* is a work hour at level RED or STOP. A *baseline alert
hour* is a work hour whose air temperature is at or above a threshold. *Caught* means
dangerous and alerting; *missed* means dangerous and not alerting; *false alarm* means
alerting while rated GREEN or YELLOW.

**Setup.** 1 April to 30 June 2024, four city-point sites, moderate work, acclimatized, work
hours 07:00 to 18:00 (11 hours a day, 1001 work hours per site, 4004 in total). Every hour
had data. 2097 of the 4004 work hours were dangerous.

| Site | Dangerous hours | Missed at 37 C | at 40 C | at 42 C |
|---|---|---|---|---|
| Chennai | 679 | 632 (93.1%) | 673 (99.1%) | 679 (100.0%) |
| Delhi | 320 | 67 (20.9%) | 158 (49.4%) | 208 (65.0%) |
| Kolkata | 764 | 615 (80.5%) | 716 (93.7%) | 760 (99.5%) |
| Hyderabad | 334 | 193 (57.8%) | 317 (94.9%) | 334 (100.0%) |
| **All sites** | **2097** | **1507 (71.9%)** | **1864 (88.9%)** | **1981 (94.5%)** |

Alert hours, caught and false alarms across all sites: 904 / 590 / 198 at 37 C, 345 / 233 /
59 at 40 C, and 169 / 116 / 27 at 42 C. So a 40 C rule fires on 345 hours, 59 of which are
not dangerous at all, and still misses 1864 dangerous hours.

**Example hours** (the coolest dangerous work hour at each site, where a thermometer is
least likely to help):

| Site | Hour (India time) | Air temp | Humidity | WBGT | Level |
|---|---|---|---|---|---|
| Chennai | 2024-05-21 09:00 | 28.8 C | 84% | 30.8 C | RED |
| Delhi | 2024-06-30 08:00 | 29.2 C | 81% | 30.3 C | RED |
| Kolkata | 2024-05-21 13:00 | 28.9 C | 84% | 31.8 C | STOP |
| Hyderabad | 2024-06-05 09:00 | 28.5 C | 78% | 30.5 C | RED |

**Robustness.** Repeating the run with other work profiles moves the headline very little:
heavy work, acclimatized gives 2618 dangerous hours and 89.1% missed at 40 C; moderate work,
unacclimatized gives 3350 dangerous hours and 89.8% missed. The main run gives 88.9%.
Details are in `core/data/backtest/sensitivity.json`.

## 7. Limitations and honesty

This is a comparison of two methods on the same historical weather data. It is **not**
evidence about heat illness, and ShramShield is not a clinical or certified instrument.

- Compares two methods on the same historical data; it is not validated against heat
  illness cases.
- Uses historical reanalysis data, not archived forecasts, so real-time forecast error is
  not included.
- WBGT is estimated from modelled weather at a city point, not measured at the worksite.
- Screening limits are for an 8-hour workday and are not a prescription of work and rest
  periods.
- Live plans rest on a forecast, which carries its own error; a plan can be wrong about the
  day ahead even when the method is right.
- Reanalysis weather is a grid value of roughly 10 to 25 km, so it can differ from a nearby
  station, and a city point is not the site.
- Microclimate is not modelled at all. Bitumen, metal roofs, trenches, reflective walls and
  heavy or impermeable clothing can all make real exposure considerably worse than these
  numbers.
- People differ. Age, fitness, medication, illness, pregnancy, hydration and acclimatization
  state all change individual risk, and the screening limits are not a medical standard that
  fits everyone.
- The Hindi message text is machine-drafted and has **not** been reviewed by a native Hindi
  speaker. `docs/HINDI_REVIEW.md` holds the text awaiting review and is marked pending.
- In 6 of the 8736 hours examined, all with wind below the 0.62 m/s floor that the Liljegren
  method applies, WBGT exceeded air temperature by more than 3 C. This is expected for a
  sunlit globe in near-still air rather than an error, and those hours are reported
  explicitly by `core/scripts/run_backtest.py` instead of being hidden.

Use on-site judgement. Stop work and seek help if anyone feels unwell, whatever the level
says.

## 8. References

- Open-Meteo weather API — https://open-meteo.com/ (historical weather API:
  https://open-meteo.com/en/docs/historical-weather-api). Archive data generated using
  Copernicus Climate Change Service information.
- ECMWF `thermofeel` (Apache 2.0) — https://github.com/ecmwf/thermofeel and
  https://pypi.org/project/thermofeel/
- Liljegren, J. C. et al. (2008), the WBGT method used above —
  https://doi.org/10.1080/15459620802310770
- CCOHS, Hot Environments: Assessment and Control Measures, which summarises the ACGIH
  screening table — https://www.ccohs.ca/oshanswers/phys_agents/heat/heat_control.html
- ACGIH, 2026 TLVs and BEIs, Table 1 (the primary source of the limits) —
  https://www.acgih.org/
- OHCOW (Occupational Health Clinics for Ontario Workers), heat response plan guidance,
  source of the "about 240 mL every 20 minutes" hydration prompt — https://www.ohcow.on.ca/
