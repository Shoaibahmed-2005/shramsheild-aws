# ShramShield

**Heat-safety screening for outdoor worksites in India.** It turns open weather data into an
hourly work/rest plan for each site, sends it to the supervisor in Hindi with a voice message,
and keeps escalating until a human acknowledges it.

Built for Environmental Hacks 2026, Heat and Water track.

## The problem

Outdoor work in India continues through months when heat and humidity together stop the body
shedding heat fast enough. A thermometer does not describe that: the same 35 C is a different
danger in dry Delhi and humid Chennai. So a site can be dangerous on a day the air temperature
looks unremarkable, and nobody is told.

## What it does

- Pulls hourly weather for each site from Open-Meteo and computes an hourly **WBGT**
  heat-stress score that accounts for humidity, sun and wind, not just air temperature.
- Converts each hour to a work/rest plan using the published **ACGIH screening limits**
  (60/45/30/15/0 working minutes per hour across five levels).
- Sends the plan to the site supervisor on **Telegram**, with a **Hindi voice message** from
  Amazon Polly.
- **Waits for acknowledgement** with AWS Step Functions and escalates to a backup contact if
  nobody answers, recording every step.
- Shows everything on a web dashboard, including a **backtest** that replays April to June 2024
  and counts the dangerous hours a plain air-temperature alert would have missed.

![ShramShield dashboard](docs/img/dashboard-sites.png)

<!-- TODO-human: capture docs/img/dashboard-sites.png so the image above renders.
     The file list and click paths are in docs/img/README.md. -->


## How it works

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full diagram and the sequence of one
run.

```
Open-Meteo ──► Lambda (WBGT + ACGIH limits) ──► DynamoDB
                        │
                        ▼
               Step Functions (waitForTaskToken)
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
   Polly (Hindi) ──► S3           Telegram ──► supervisor
         │                             │
         └──────► dashboard ◄──────────┘ acknowledge
                        │
                   (no answer) ──► escalate to backup
```

## Results

From a replay of 1 April to 30 June 2024 across four Indian cities — 4004 work hours, every
hour with data. Full provenance for every figure is in [docs/NUMBERS.md](docs/NUMBERS.md).

| | Value |
|---|---|
| Work hours our model rated RED or STOP | **2097** |
| Missed by a 40 C air-temperature rule | **1864 (88.9%)** |
| Missed by a 37 C rule | 1507 (71.9%) |
| Missed by a 42 C rule | 1981 (94.5%) |

The sharpest illustration: **Delhi had 268 work hours at or above 40 C but 320 dangerous
hours, while Chennai had 6 hours reaching 40 C and 679 dangerous hours.**

A "dangerous hour" is a work hour our WBGT model rates RED or STOP. It is a model output about
heat stress, not an observation that anyone was harmed.

## Try it

- **Dashboard:** TODO-human (Amplify URL, once the dashboard is deployed)
- **API:** `https://5lca7upa95.execute-api.ap-south-1.amazonaws.com`
- **Video:** TODO-human (YouTube link)

A read-only tour needs no key: browse the sites, open a plan, read the method and backtest
pages. Starting a run or acknowledging one is a mutating action and needs the demo key, which
is **not** in this repository and is shared on request. The video shows a full live run end to
end if you would rather watch than click.

```bash
curl -s https://5lca7upa95.execute-api.ap-south-1.amazonaws.com/health
curl -s "https://5lca7upa95.execute-api.ap-south-1.amazonaws.com/sites/chn-01/plan"
```

## Run it yourself

Core engine and its tests (Python 3.12 or newer):

```bash
cd core && py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/make_plan.py chn-01
```

Deploy the backend (full detail in [backend/DEPLOY_NOTES.md](backend/DEPLOY_NOTES.md)):

```bash
python backend/scripts/prepare.py          # copy core into the Lambda package
python backend/scripts/build_layer.py      # build the thermofeel layer
cd backend && sam validate --lint -t template.yaml
sam deploy --guided                        # stack name shramshield, region ap-south-1
python scripts/seed_sites.py               # load the four demo sites
python scripts/smoke.py --api "$API_URL"
```

Frontend:

```bash
cd frontend && npm ci
cp .env.example .env.local                 # set VITE_API_BASE, VITE_USE_MOCK=false
npm run dev
```

## AWS services

Ten services; eight are evidenced as deployed in
[docs/AWS_EVIDENCE.md](docs/AWS_EVIDENCE.md), which also lists what proves each.

| Service | Role |
|---|---|
| AWS Lambda | Four Python 3.12 functions: API router, notifier, run recorder, scheduler, plus a shared layer |
| Amazon API Gateway (HTTP API) | Public HTTPS endpoint, throttled, for the dashboard and the Telegram webhook |
| Amazon DynamoDB | Single table: sites, cached plans, runs and task tokens, with TTL |
| AWS Step Functions | The wait-for-acknowledgement and escalate workflow, using `waitForTaskToken` |
| Amazon S3 | Private bucket for the generated Hindi voice files, served by presigned URLs |
| AWS IAM | Per-function execution roles |
| Amazon CloudWatch | Logs with 14-day retention, plus an alarm on failed workflow executions |
| AWS CloudFormation / SAM | Defines and deploys the whole stack |
| Amazon Polly | The neural Hindi voice (`Kajal`, `hi-IN`) |
| Amazon EventBridge Scheduler | Daily 06:00 IST trigger (disabled outside demos) |

## Method and honesty

The full method, the limits table and every caveat are in
[docs/METHOD.md](docs/METHOD.md).

> Screening guidance estimated from weather-model data. It is not a measurement or medical
> advice.

Specifically, ShramShield is **not** clinically validated, is **not** certified, does **not**
measure anything on site, and the backtest is a comparison of two methods on the same
historical weather — not evidence about heat illness. The Hindi text is machine-drafted and
awaiting review by a native speaker
([docs/HINDI_REVIEW.md](docs/HINDI_REVIEW.md)).

## Data and credits

- **Open-Meteo.com** — hourly forecast and historical weather API, free for non-commercial use.
- **Copernicus Climate Change Service information**, via the Open-Meteo ERA5 archive.
- **thermofeel** by **ECMWF** (Apache 2.0) — the Liljegren WBGT implementation.
- **ACGIH** 2026 TLV Table 1 screening values, as summarised by **CCOHS**.
- **OHCOW** — occupational heat response guidance, source of the hydration prompt.

## AI tools used

- **Claude (Anthropic)** — planning documents, and an agent used for the core engine, backtest,
  documentation and parts of the backend hardening.
- TODO-human: add any other AI tools the team used (for example Google Antigravity agents) with
  one line on what each was used for.

All safety numbers come from published physics and published limits, not from a language model.

## Team

TODO-human: the three names and roles (P1 core engine, P2 cloud and AWS, P3 frontend and
submission).

## Licence

MIT — see [LICENSE](LICENSE).
