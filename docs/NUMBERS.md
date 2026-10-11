# NUMBERS: every figure we may say in public

Single source of truth for the team. **If a number is not in this file, do not say it** in the
video, the writeup, the README or a demo. Every value below was produced by the command next
to it, run in task P1.4 on 11 October 2026.

Core version 1.0.0. Backtest output `generated_at` 2026-10-11T08:06:33Z, reproduced bit for
bit from the committed raw archive data (only the timestamp differs from the P1.2 run).

Commands are shown for Windows. On macOS or Linux replace `.venv/Scripts/python` with
`.venv/bin/python`.

## What "dangerous hour" means

**A dangerous hour is a work hour that our WBGT model rates RED or STOP.** It is a model
output about heat stress, not an observation about any worker. It does **not** mean anyone was
harmed, fell ill, or was at a measured risk. The backtest compares two screening methods on
the same historical weather; it is not evidence about heat illness.

A *baseline alert hour* is a work hour whose air temperature is at or above the threshold.
*Caught* = dangerous and alerting. *Missed* = dangerous and not alerting. *False alarm* =
alerting while rated GREEN or YELLOW.

## Headline numbers

| Claim | Value | How to reproduce (exact command) | Source file |
|---|---|---|---|
| Period covered | 1 Apr to 30 Jun 2024 (91 days) | `cd core && .venv/Scripts/python scripts/run_backtest.py` | `core/data/backtest/backtest.json` |
| Profile used | moderate work, acclimatized, 07:00 to 18:00 India time | same | same |
| Number of sites | 4 | same | `shared/fixtures/sites.json` |
| Number of baseline thresholds | 3 (37, 40, 42 C) | same | `core/data/backtest/backtest.json` |
| Work hours examined | 4004 (1001 per site) | same | same |
| Work hours with data | 4004 (no nulls in any archive response) | same | same |
| **Dangerous hours, all sites** | **2097** | same | same |
| **Missed by a 40 C rule, all sites** | **1864 of 2097 = 88.9%** | same | same |
| Missed by a 37 C rule, all sites | 1507 of 2097 = 71.9% | same | same |
| Missed by a 42 C rule, all sites | 1981 of 2097 = 94.5% | same | same |
| False alarm hours at 40 C, all sites | 59 (of 345 alert hours) | same | same |
| False alarm hours at 37 C, all sites | 198 (of 904 alert hours) | same | same |
| False alarm hours at 42 C, all sites | 27 (of 169 alert hours) | same | same |

## Per city

All four rows come from the same command:
`cd core && .venv/Scripts/python scripts/run_backtest.py`, source
`core/data/backtest/backtest.json`.

| Site | Dangerous hours | Missed at 37 C | Missed at 40 C | Missed at 42 C | False alarms at 40 C |
|---|---|---|---|---|---|
| Chennai (chn-01) | 679 | 632 (93.1%) | 673 (99.1%) | 679 (100.0%) | 0 |
| Delhi (del-01) | 320 | 67 (20.9%) | 158 (49.4%) | 208 (65.0%) | 57 |
| Kolkata (kol-01) | 764 | 615 (80.5%) | 716 (93.7%) | 760 (99.5%) | 0 |
| Hyderabad (hyd-01) | 334 | 193 (57.8%) | 317 (94.9%) | 334 (100.0%) | 2 |
| **All sites** | **2097** | **1507 (71.9%)** | **1864 (88.9%)** | **1981 (94.5%)** | **59** |

Alert hours at 40 C, if needed: Chennai 6, Delhi 268, Kolkata 48, Hyderabad 23, total 345.

The contrast worth quoting: **Delhi had 268 work hours at or above 40 C but only 320 dangerous
hours, while Chennai had 6 work hours reaching 40 C and 679 dangerous hours.** Dry heat trips a
thermometer; humid coastal heat does not.

## Example hours

The coolest dangerous work hour at each site, where a thermometer helps least. Same command,
same source file.

| Site | Hour (India time) | Air temp | Humidity | WBGT | Level |
|---|---|---|---|---|---|
| Chennai | 2024-05-21 09:00 | 28.8 C | 84% | 30.8 C | RED |
| Delhi | 2024-06-30 08:00 | 29.2 C | 81% | 30.3 C | RED |
| Kolkata | 2024-05-21 13:00 | 28.9 C | 84% | 31.8 C | STOP |
| Hyderabad | 2024-06-05 09:00 | 28.5 C | 78% | 30.5 C | RED |

## Sensitivity (robustness)

Same data and period, different work profile. Baseline threshold 40 C.
Command: `cd core && .venv/Scripts/python scripts/run_backtest.py`,
source `core/data/backtest/sensitivity.json`.

| Profile | Dangerous hours | Missed at 40 C | Missed % at 40 C |
|---|---|---|---|
| moderate, acclimatized (main run) | 2097 | 1864 | 88.9% |
| heavy, acclimatized | 2618 | 2332 | 89.1% |
| moderate, unacclimatized | 3350 | 3009 | 89.8% |

The headline barely moves across profiles, so "about 89% missed at 40 C" is safe to say.

## Tests

| Claim | Value | How to reproduce (exact command) | Source |
|---|---|---|---|
| Core tests passing | 194 | `cd core && .venv/Scripts/python -m pytest -q` | `core/tests/` |
| Core fixtures valid | 7 of 7 OK | `cd core && .venv/Scripts/python scripts/validate_fixtures.py` | `shared/fixtures/` |
| Live sites verified today | 4 of 4 OK | `cd core && .venv/Scripts/python scripts/verify_live.py` | live Open-Meteo |

Backend tests are **not** counted here. P2's handover document reports 21 passing in
`backend/tests/`, but that suite needs `boto3` and `moto`, which are not installed in the core
virtual environment, so P1 could not run it in this task. If the team wants to say a combined
test count in public, P2 must run it and add the number to this file. Until then, say
"194 core tests".

## AWS services

Counted by reading `backend/template.yaml` (P2's file, read only).
Command: `grep -n -E "Type: AWS::|polly:|Type: ScheduleV2|^Transform" backend/template.yaml`

**9 AWS services are evidenced in the template:**

| # | Service | What evidences it in template.yaml |
|---|---|---|
| 1 | AWS Lambda | 4 x `AWS::Serverless::Function`, plus 1 `AWS::Serverless::LayerVersion` |
| 2 | AWS Step Functions | 1 x `AWS::Serverless::StateMachine` |
| 3 | Amazon API Gateway | 1 x `AWS::Serverless::HttpApi` |
| 4 | Amazon DynamoDB | 1 x `AWS::DynamoDB::Table` |
| 5 | Amazon S3 | 1 x `AWS::S3::Bucket` |
| 6 | Amazon Polly | IAM statement `polly:SynthesizeSpeech` |
| 7 | Amazon EventBridge Scheduler | `Events:` of type `ScheduleV2`, `cron(30 0 * * ? *)` |
| 8 | AWS CloudFormation | `Transform: AWS::Serverless-2016-10-31` (the stack is deployed by SAM) |
| 9 | AWS IAM | 5 `Policies:` blocks, from which SAM generates execution roles |

**Open point for the human:** P2's handover document says "12 AWS services". P1 can evidence
only these 9 from `template.yaml`, and cannot say which the other three are: Amplify Hosting
is added in P2.4 and CloudWatch Logs is created implicitly by Lambda, but neither appears in
the template at this commit, and the remaining one is unknown to P1. Say **9** in public, or
wait until P2 lists all twelve with evidence in `docs/AWS_EVIDENCE.md` and then update this
row. Do not say 12 on P1's authority.

## Hindi text review status

| Claim | Exact current state |
|---|---|
| Hindi review status | **PENDING. No native Hindi speaker has reviewed the text.** |
| Source | `docs/HINDI_REVIEW.md`, first line: "Status: PENDING. No native Hindi speaker has reviewed this text yet." |
| Rows awaiting review | 14 (4 rendered messages, 5 level names, 5 hour words) |
| Reviewer cells filled | 0 of 14 |
| Reviewer name recorded | none |
| Date of review | none |

Command to confirm: `sed -n '1,3p' docs/HINDI_REVIEW.md`

**What this means for what we say.** The Hindi messages and the Hindi voice are
machine-drafted and have had no native review. The video, writeup and README must say so.
Never say the Hindi was "reviewed", "checked by a native speaker", "verified" or
"localised". Saying "machine-drafted Hindi, awaiting native review" is accurate.

## Near-calm hours exempted from the +3 C plausibility bound

The backtest sanity check "WBGT never exceeds air temperature + 3 C" is applied only to hours
with wind at or above 0.62 m/s, the floor the Liljegren method itself applies, because below
it the convective cooling term is saturated and a sunlit globe genuinely runs far above air
temperature. **6 of the 8736 hours examined are exempt.** They are printed on every run and
are listed in `docs/METHOD.md`.

Command: `cd core && .venv/Scripts/python scripts/run_backtest.py` (see the "NOTE" line under
SANITY CHECKS).

| Site | Hour (India time) | Air temp | WBGT | Excess | Wind |
|---|---|---|---|---|---|
| chn-01 | 2024-05-13 10:00 | 29.8 C | 33.5 C | +3.7 | 0.58 m/s |
| chn-01 | 2024-05-19 10:00 | 32.0 C | 35.1 C | +3.1 | 0.50 m/s |
| chn-01 | 2024-05-23 11:00 | 31.8 C | 35.9 C | +4.1 | 0.14 m/s |
| kol-01 | 2024-04-03 08:00 | 30.5 C | 34.2 C | +3.7 | 0.51 m/s |
| kol-01 | 2024-04-03 09:00 | 32.6 C | 36.3 C | +3.7 | 0.51 m/s |
| kol-01 | 2024-05-10 10:00 | 30.1 C | 33.7 C | +3.6 | 0.32 m/s |

At wind at or above 0.62 m/s, **0 hours** exceed the bound. If asked, the honest answer is:
"six near-calm hours exceed our plausibility bound; that is expected behaviour of the
published method in still air, and we report them rather than hide them."

## Other verified facts

| Claim | Value | How to reproduce | Source |
|---|---|---|---|
| WBGT method | Liljegren, via ECMWF thermofeel 2.3.0 | `cd core && .venv/Scripts/python -c "import thermofeel; print(thermofeel.__version__)"` | `core/shramshield_core/wbgt.py` |
| Weather source (live) | Open-Meteo forecast API | `cd core && .venv/Scripts/python scripts/make_plan.py chn-01` | `core/shramshield_core/weather.py` |
| Weather source (backtest) | Open-Meteo archive API, ERA5 based reanalysis | `cd core && .venv/Scripts/python scripts/run_backtest.py` | `core/data/backtest/backtest.json` |
| Screening limits source | ACGIH 2026 TLV Table 1 as summarised by CCOHS | `cd core && .venv/Scripts/python -m pytest -q -k limits_match_contract` | `core/shramshield_core/contract.py` |
| Levels | 5 (GREEN, YELLOW, ORANGE, RED, STOP) plus UNKNOWN | same | same |
| Plan size | about 10 KB of JSON | `cd core && .venv/Scripts/python -m pytest -q -k smaller_than_30_kb` | `core/tests/test_edge_cases.py` |
| Plan build time | about 26 ms per plan | `cd core && .venv/Scripts/python -m pytest -q -k plan_is_fast` | `core/tests/test_edge_cases.py` |
| Core version | 1.0.0 | `cd core && .venv/Scripts/python -c "import shramshield_core; print(shramshield_core.__version__)"` | `core/shramshield_core/__init__.py` |

## Claims we must NOT make

None of these are supported by anything we built or measured. Do not say them, do not imply
them, and do not let them appear in the video, writeup, README, slide or demo script.

| Forbidden claim | Why it is wrong | Say this instead |
|---|---|---|
| "Clinically validated" | No clinical study, no medical data, no patient outcomes of any kind. | "Screening guidance from published occupational limits." |
| "Prevents heat illness" / "prevents heat stroke" | We never observed a health outcome. We send modelled guidance; prevention is unproven. | "Gives supervisors a work/rest plan and an acknowledgement trail." |
| "Certified" / "approved" / "compliant" | No certification body has assessed this. The ACGIH table is a screening tool, not a certification. | "Uses the ACGIH screening limits as summarised by CCOHS." |
| "Real-time sensor measurement" / "measures WBGT" | There is no sensor. WBGT is **estimated** from a weather model at a city point. | "Estimated from open weather-model data, not measured on site." |
| "Saves lives" / "will save N lives" | Unmeasurable and unmeasured. | "Aims to make dangerous hours visible that a thermometer misses." |
| Any accuracy percentage ("95% accurate") | We never computed an accuracy against ground truth. Our 88.9% is **disagreement between two methods**, not accuracy. | "A 40 C rule misses 88.9% of the hours our model rates dangerous." |
| "88.9% of dangerous hours would have harmed workers" | Dangerous = RED or STOP in our model. No harm was observed or inferred. | See "What dangerous hour means" above. |
| "Validated against heat illness cases" | Explicitly not done; it is caveat 1 of the backtest. | "Compares two methods on the same historical weather." |
| "Reviewed by a Hindi speaker" | No review has happened. See the Hindi section above. | "Machine-drafted Hindi, awaiting native review." |
| "Works anywhere in the world" | Coordinates are validated to India only (lat 6 to 37, lon 68 to 98), and limits assume this context. | "Built and tested for Indian worksites." |

## Consistency check done in P1.4

- `docs/METHOD.md`: every backtest figure in it was compared field by field against
  `core/data/backtest/backtest.json`, and the limits table against
  `contract.LIMITS_C`. No disagreement found.
- `README.md`: still the P1.0 stub ("Work in progress"). It contains no numbers, so nothing
  in it conflicts with this file. P3 rewrites it in P3.4 and must take every number from here.
