# ShramShield: Master Build Plan (3 people, 1 repository)

Project: heat-safe worksites for Environmental Hacks 2026 (Heat and Water track).
Working name "ShramShield" (rename freely, it is only a folder and title).
Plan prepared 8 Oct 2026. Put this file at docs/BUILD_PLAN.md and AGENTS.md at the repo root.

## 0. Read first

### 0.1 What we build

For each outdoor worksite the system:

1. Pulls hourly weather (Open-Meteo) and computes an hourly **WBGT** heat-stress score
   (a heat-stress measure that also counts humidity, sun and wind, not just air temperature).
2. Converts it to a work/rest plan using published ACGIH screening limits.
3. Sends the plan to the site supervisor on Telegram, with a Hindi voice message (Amazon Polly).
4. Waits for acknowledgement (AWS Step Functions). If nobody acknowledges in time, it escalates to a
   backup contact, and records the outcome.
5. Shows everything on a web dashboard, plus a "backtest" page that replays April to June 2024 and counts
   the dangerous hours a plain air-temperature alert would have missed.

### 0.2 How agents and humans use this document

- Humans: read sections 0 to 2, do the human setup steps, paste prompt cards (section 2).
- Agents: read AGENTS.md, then sections 0 and 3 of this file, then ONLY your task card in section 4.
- One task card = one unit of work = one commit batch. Never do two cards in one go.
- This document is the single source of truth. If reality disagrees with it, stop and tell the human.

### 0.3 Team, ownership, rounds

| | P1 "Core" | P2 "Cloud" | P3 "Face" |
|---|---|---|---|
| Owns | core/, shared/, docs/METHOD.md | backend/ (AWS, SAM, Lambdas, workflow) | frontend/, README.md, docs/SUBMISSION.md, docs/ARCHITECTURE.md |
| Strength needed | Python, careful with numbers | AWS, YAML, debugging | React, design, storytelling |

We do NOT wait for whole parts. We work in **rounds**. Inside a round the three tasks touch different
folders, so they run in parallel without conflicts. At the end of each round there is a **gate**: everyone
pulls, a short check runs, and only then the next round starts.

| Round | P1 | P2 | P3 | Gate |
|---|---|---|---|---|
| R0 (blocking, about 45 min) | P1.0 repo + contract + fixtures | H2 AWS setup (human) | H3 tools setup (human) | repo cloned by all |
| R1 | P1.1 core engine | P2.1 AWS skeleton and first deploy | P3.1 UI shell on fixtures | G1 |
| R2 | P1.2 backtest and evidence | P2.2 sites and plan API | P3.2 UI on the real API | G1b (quick) |
| R3 | P1.3 hardening and review | P2.3 workflow, Telegram, voice | P3.3 run timeline and pages | G2 (end to end) |
| R4 | P1.4 final numbers and freeze | P2.4 hardening, hosting, final deploy | P3.4 polish, README, video kit | G3 (freeze) |

Handoff order inside every round if two people touch the same thing: P1, then P2, then P3.
In practice this only matters at the gates.

### 0.4 Architecture

```
 Telegram (supervisor / backup)
     ^  sendMessage / sendAudio      | button press
     |                               v (webhook)
 +--------------+   +-----------------------------+
 | NotifyLambda |<--| Step Functions (wait for    |
 | + Polly voice|   | ack, timeout, escalate)     |
 +------+-------+   +--------------+--------------+
        |                          |
        v                          v
  S3 (mp3 files)            RecordLambda
                                   |
 Amplify Hosting (React)           v
        | HTTPS             +-------------+
        v                   |  DynamoDB   |
 API Gateway (HTTP) ------> | single table|
   ApiLambda (router)       +-------------+

 EventBridge schedule 06:00 IST -> SchedulerLambda
   -> starts the workflows
 Core library (thermofeel + our code) is in the
 Lambda layer and package.
 Weather: Open-Meteo API (public, no key).
```

### 0.5 Timeline (India time)

The kickoff hour and the submission deadline hour were NOT announced when this was written. Check the
event schedule page and Discord. Plan to be finished by **Saturday night**; treat Sunday as buffer.

| When | What |
|---|---|
| Thu 8 Oct, after the clock starts | R0, R1, gate G1 |
| Fri 9 Oct | R2, R3, gate G2 (end to end works) |
| Sat 10 Oct | R4, feedback from mentors, gate G3 (freeze). Delhi build day is optional and adds no score |
| Sun 11 Oct | Buffer. Record video, publish blog, submit EARLY. Deadline hour unknown |

### 0.6 What was verified and what must be verified on your machine

Verified while preparing this plan:
- thermofeel 2.3.0 installs with numpy only, supports Python 3.10 to 3.14, Apache 2.0 licence, and fits in a
  Lambda layer (about 70 MB unzipped). It has calculate_wbgt_liljegren and calculate_wbgt_simple. We ran
  both and the numbers in section 3.7 are real outputs.
- Our solar-angle function was tested against known noon zenith angles.
- ACGIH screening limits (section 3.7) come from the CCOHS summary of ACGIH 2026 TLV Table 1.
- Antigravity reads AGENTS.md at the repo root (always on, max 24,000 bytes).
- Amazon Polly has Hindi voices: Kajal (neural) and Aditi (standard).
- Step Functions waitForTaskToken pattern for Lambda is documented by AWS.

NOT verified (could not be tested from the preparation environment). Each has a check in a task card:
- Live Open-Meteo calls (check in P1.1 step 1).
- Polly Hindi voice in the Mumbai region (check in H2, step 6).
- Telegram bot, webhook and inline buttons (check in P2.3).
- Amplify manual (zip) deployment (check in P2.4).
- Hindi message wording (needs a Hindi speaker, P1.3).

---

## 1. Human setup steps (agents cannot do these)

Everyone: verify student status on AWS Builder Center, check in on the event page, join the WeMakeDevs
Discord, run "git config --global user.name" and "user.email", log in to Antigravity.

### H1 (P1)

1. Install Python 3.12 and Git. Check: python --version, git --version.
2. **After the hackathon clock has started**: create a GitHub repository named shramshield. Public, MIT licence,
   no starter code, add .gitignore later (P1.0 does it). Add P2 and P3 as collaborators with write access.
3. Create the local folder, put AGENTS.md at its root and this file at docs/BUILD_PLAN.md. Open the folder in Antigravity.
4. Check Open-Meteo is reachable from your network:
   curl "https://api.open-meteo.com/v1/forecast?latitude=13.08&longitude=80.27&hourly=temperature_2m&forecast_days=1"
   Expected: JSON with an hourly block. If it fails, tell the team now.

### H2 (P2): the AWS side

1. Sign up at https://aws.amazon.com/free (Free Tier). A debit card or RuPay works, the verification charge is about 2 rupees.
   The event gives new accounts up to $200 in credits. If credits run out, the organisers' form gives $25 more.
2. Turn on MFA for the root user. Then create an IAM user for daily work (name shram-deployer) with the policy
   AdministratorAccess (hackathon only) and create one access key for the CLI. Never commit it. Delete the key after the event.
3. Install: AWS CLI v2 and AWS SAM CLI (both from the official AWS documentation pages), Python 3.12, Git.
   Docker is optional.
4. Run: aws configure   (region ap-south-1, output json). Check: aws sts get-caller-identity
5. Set a cost alarm: Billing, Budgets, create a monthly cost budget of 10 USD with email alerts at 50%, 80%, 100%.
6. Check Hindi voices exist in your region:
   aws polly describe-voices --language-code hi-IN --engine neural --region ap-south-1
   Expected: a voice named Kajal. If the command errors or is empty, run the same with --region us-east-1; if that works,
   we set POLLY_REGION=us-east-1 later (the code supports a separate Polly region). Write down the result.
7. Telegram: in the Telegram app talk to @BotFather, send /newbot, choose a name, copy the token. Keep it in a password
   manager. Create two Telegram accounts or two people to play "supervisor" and "backup" for the demo.
8. Choose three random strings (letters and digits only, 20+ characters): TELEGRAM_WEBHOOK_SECRET and DEMO_KEY. Keep them private.

### H3 (P3)

1. Install Node.js 20 or newer (LTS) and Git. Check: node --version, npm --version.
2. Create your AWS Builder Center profile for the blog post. Create or choose a YouTube account for the demo video.
3. Install a screen recorder (OBS Studio) and test your microphone. Test uploading a 10 second unlisted video to YouTube.
4. Open the folder in Antigravity after P1.0 is pushed.
5. Design references: save 4 to 8 reference images (dashboard, status timeline, hourly strip look) into docs/design/ and, if you like, a docs/design/NOTES.md with a few words on what you like in each. The P3.1 agent reads them. Commit them yourself (git add docs/design) before pasting card P3.1.

---

## 2. Prompt cards (paste these into the Antigravity agent, one per task)

Rules for using them:
- Start every card with a clean working tree (nothing uncommitted).
- Paste exactly one card. Wait for the agent to finish and show the verification output. Read it.
- If the agent asks something, answer it. If it reports failure twice, ask the team before continuing.
- The same text with a different task id is used for every card. The task id decides which card the agent reads.

### Card template (copy, then change role and task id)

```
You are P1 (core engine) on the ShramShield repository.
Step 1: run "git pull --rebase origin main" (the working tree must be clean).
Step 2: read AGENTS.md, then docs/BUILD_PLAN.md sections 0 and 3, then ONLY the task card "P1.1" in section 4. Ignore every other task card.
Step 3: do ONLY task P1.1. Edit only the folders that card lists.
Step 4: when finished, run every verification command in the card and show me the real output.
Step 5: commit with a message starting "P1.1:", run "git pull --rebase origin main", then "git push origin main", then stop.
If a command fails twice or the card is unclear, stop and ask me. Do not invent data, thresholds or API fields. Do not skip tests.
```

### The 13 cards

| Order | Who | Paste this line in step 1 to 3 |
|---|---|---|
| 1 | P1 | You are P1 (core engine) ... card "P1.0" |
| 2 | P1 | You are P1 (core engine) ... card "P1.1" |
| 2 | P2 | You are P2 (cloud) ... card "P2.1" |
| 2 | P3 | You are P3 (frontend) ... card "P3.1" |
| 3 | P1 | card "P1.2" |
| 3 | P2 | card "P2.2" |
| 3 | P3 | card "P3.2" |
| 4 | P1 | card "P1.3" |
| 4 | P2 | card "P2.3" |
| 4 | P3 | card "P3.3" |
| 5 | P1 | card "P1.4" |
| 5 | P2 | card "P2.4" |
| 5 | P3 | card "P3.4" |

Ready-to-paste versions follow. The role words are the only difference.

**P1.0**
```
You are P1 (core engine) on the ShramShield repository.
Step 1: run "git pull --rebase origin main" if the repo already has commits, otherwise continue.
Step 2: read AGENTS.md, then docs/BUILD_PLAN.md sections 0 and 3, then ONLY the task card "P1.0" in section 4.
Step 3: do ONLY task P1.0. Edit only the folders that card lists.
Step 4: when finished, run every verification command in the card and show me the real output.
Step 5: commit with a message starting "P1.0:", run "git pull --rebase origin main", then "git push origin main", then stop.
If a command fails twice or the card is unclear, stop and ask me. Do not invent data, thresholds or API fields. Do not skip tests.
```

**P1.1**
```
You are P1 (core engine) on the ShramShield repository.
Step 1: run "git pull --rebase origin main" (the working tree must be clean).
Step 2: read AGENTS.md, then docs/BUILD_PLAN.md sections 0 and 3, then ONLY the task card "P1.1" in section 4. Ignore every other task card.
Step 3: do ONLY task P1.1. Edit only the folders that card lists.
Step 4: when finished, run every verification command in the card and show me the real output.
Step 5: commit with a message starting "P1.1:", run "git pull --rebase origin main", then "git push origin main", then stop.
If a command fails twice or the card is unclear, stop and ask me. Do not invent data, thresholds or API fields. Do not skip tests.
```

**P2.1**
```
You are P2 (cloud and AWS) on the ShramShield repository.
Step 1: run "git pull --rebase origin main" (the working tree must be clean).
Step 2: read AGENTS.md, then docs/BUILD_PLAN.md sections 0 and 3, then ONLY the task card "P2.1" in section 4. Ignore every other task card.
Step 3: do ONLY task P2.1. Edit only the folders that card lists. Never write secrets into tracked files; I will type tokens myself.
Step 4: when finished, run every verification command in the card and show me the real output.
Step 5: commit with a message starting "P2.1:", run "git pull --rebase origin main", then "git push origin main", then stop.
If a command fails twice or the card is unclear, stop and ask me. Ask before running any command that creates paid resources or changes AWS permissions.
```

**P3.1**
```
You are P3 (frontend and story) on the ShramShield repository.
Step 1: run "git pull --rebase origin main" (the working tree must be clean).
Step 2: read AGENTS.md, then docs/BUILD_PLAN.md sections 0 and 3, then ONLY the task card "P3.1" in section 4. Ignore every other task card.
Step 3: do ONLY task P3.1. Edit only the folders that card lists.
Step 4: when finished, run every verification command in the card, show me the real output, and describe what I should see in the browser.
Step 5: commit with a message starting "P3.1:", run "git pull --rebase origin main", then "git push origin main", then stop.
If a command fails twice or the card is unclear, stop and ask me. Do not add UI libraries. Do not present fixture data as real.
```

For every later card, use the same text and change only the task id and the commit prefix:

- P1.2, P1.3, P1.4: the P1 text (role "P1 (core engine)").
- P2.2, P2.3, P2.4: the P2 text (role "P2 (cloud and AWS)").
- P3.2, P3.3, P3.4: the P3 text (role "P3 (frontend and story)").

---
## 3. Shared contract (frozen after P1.0, only P1 may edit this section)

Everything the three folders must agree on. If an agent finds this wrong, it stops and tells the human.

### 3.1 Repository layout

```
shramshield/
  AGENTS.md
  README.md                         (P3; P1.0 creates a stub once)
  LICENSE                           (MIT)
  .gitignore
  docs/  BUILD_PLAN.md  METHOD.md  ARCHITECTURE.md  SUBMISSION.md  HINDI_REVIEW.md  NUMBERS.md  AWS_EVIDENCE.md
  shared/fixtures/                  (P1) sites.json, plan_chennai_moderate.json, run_*.json, backtest.json
  core/                             (P1)
    pyproject.toml  requirements.txt
    shramshield_core/  __init__.py  solar.py  weather.py  wbgt.py  limits.py  plan.py  messages.py  backtest.py
    scripts/  run_backtest.py  validate_fixtures.py
    tests/
    data/raw/                       cached Open-Meteo archive responses (committed, small)
    data/backtest/                  outputs
  backend/                          (P2)
    template.yaml  samconfig.toml.example  DEPLOY_NOTES.md
    src/  api.py  notify.py  record.py  scheduler.py  common/
    statemachine/escalation.asl.json
    scripts/  prepare.py  smoke.py  seed_sites.py
    tests/
  frontend/                         (P3) Vite + React app
```

### 3.2 Conventions

- Temperatures in degrees Celsius, wind in m/s, pressure in hPa, radiation in W/m2.
- Times are India time (fixed UTC+05:30). Hour strings look like "2026-10-09T14:00". Timestamps with a Z are UTC.
- site_id matches ^[a-z0-9-]{3,20}$. run_id is site_id + "_" + UTC time "YYYYMMDDTHHMMSS" (example chn-01_20261009T003012).
- plan_id is site_id + "_" + date (example chn-01_2026-10-09).
- JSON keys are snake_case. Enum values are UPPER_CASE strings.
- Disclaimer text (exact, shown wherever a plan is shown):
  "Screening guidance estimated from weather-model data. It is not a measurement or medical advice. Use on-site judgement and stop work if anyone feels unwell."

### 3.3 Site object

```json
{
  "site_id": "chn-01",
  "name": "Anna Nagar tower site",
  "lat": 13.085, "lon": 80.2101,
  "workload": "moderate",
  "acclimatized": true,
  "work_start_hour": 7, "work_end_hour": 18,
  "language": "hi",
  "supervisor": {"name": "Supervisor", "telegram_chat_id": null},
  "backup": {"name": "Backup", "telegram_chat_id": null},
  "ack_timeout_seconds": 900
}
```
Rules: workload is light, moderate, heavy or very_heavy. lat 6 to 37, lon 68 to 98 (India only). work_end_hour is exclusive
and greater than work_start_hour. language is hi or en. ack_timeout_seconds is 30 to 3600. name up to 60 characters.

### 3.4 Plan object (core output, API output)

```json
{
  "plan_id": "chn-01_2026-10-09",
  "site_id": "chn-01",
  "date": "2026-10-09",
  "generated_at": "2026-10-09T00:30:12Z",
  "source": {"weather": "open-meteo", "wbgt_method": "liljegren", "thermofeel": "2.3.0"},
  "profile": {"workload": "moderate", "acclimatized": true},
  "hours": [
    {
      "hour": 14, "time": "2026-10-09T14:00", "in_work_hours": true,
      "air_temp_c": 36.1, "rh_pct": 55, "wind_ms": 3.1, "ghi_wm2": 780,
      "wbgt_c": 32.0, "wbgt_method": "liljegren",
      "level": "STOP", "max_work_min": 0, "min_rest_min": 60, "limit_c": null,
      "reason": "WBGT 32.0 C is above every screening limit for moderate work (acclimatized); highest limit is 31.5 C."
    }
  ],
  "summary": {
    "worst_level": "STOP", "peak_wbgt_c": 32.0, "peak_hour": 14,
    "windows": [{"start_hour": 13, "end_hour": 16, "level": "STOP", "max_work_min": 0, "min_rest_min": 60}]
  },
  "messages": {"en": "...", "hi": "..."},
  "disclaimer": "..."
}
```
- hours has one entry for each of the 24 hours of the date, in order.
- summary windows are runs of consecutive work hours with the same level, only levels other than GREEN. end_hour is exclusive.
- wbgt_method is "liljegren" or "simple_fallback" (see 3.6).
- Fixtures and test data carry "_fixture": true at the top level.
- An hour whose temperature or humidity is missing has wbgt_c null, level "UNKNOWN", max_work_min null, min_rest_min null,
  limit_c null and a reason saying the data was missing. UNKNOWN hours are never part of summary windows and never count as
  worst_level (unless EVERY work hour is UNKNOWN, then worst_level is "UNKNOWN", peak_wbgt_c and peak_hour are null, windows is []).
- summary.peak_wbgt_c and peak_hour are the maximum over work hours (earliest hour on a tie).

### 3.5 Run object

```json
{
  "run_id": "chn-01_20261009T003012", "site_id": "chn-01", "plan_id": "chn-01_2026-10-09",
  "status": "WAITING_ACK",
  "active_stage": "primary",
  "ack_deadline": "2026-10-09T00:45:12Z",
  "voice_url": null,
  "acked_by": null, "acked_via": null,
  "created_at": "2026-10-09T00:30:12Z",
  "events": [{"ts": "2026-10-09T00:30:13Z", "step": "plan_built", "detail": "peak WBGT 32.0 at 14:00"}]
}
```
status values: STARTED, WAITING_ACK, ESCALATED, ACKNOWLEDGED, UNACKNOWLEDGED, FAILED.
Meaning: WAITING_ACK = primary contact notified. ESCALATED = primary timed out, backup notified and now waited on.
ACKNOWLEDGED and UNACKNOWLEDGED and FAILED are final. active_stage is primary, backup or null.
event step values: plan_built, voice_ready, telegram_sent, telegram_failed, notified_primary, escalated, notified_backup,
acknowledged, unacknowledged, error. acked_via is telegram or web.

### 3.6 WBGT method

1. Primary: thermofeel calculate_wbgt_liljegren(t2_k, rh, pressure, va, ssrd, fdir, cossza). It needs air temperature in
   kelvin, relative humidity in percent, surface pressure in hPa, 10 m wind in m/s, global horizontal radiation, direct fraction
   (0 to 1) and cosine of the solar zenith angle. Output is kelvin, minus 273.15 gives Celsius.
2. Open-Meteo gives: temperature_2m, relative_humidity_2m, surface_pressure, wind_speed_10m (request wind_speed_unit=ms),
   shortwave_radiation (ssrd), direct_radiation. fdir = direct_radiation / shortwave_radiation when shortwave_radiation > 10
   W/m2, clamped to 0..1, else 0.
3. Open-Meteo radiation values are the mean of the PRECEDING hour, so cossza is computed for the time 30 minutes before the
   hour label. Night (cossza = 0): ssrd = 0 and fdir = 0.
4. Fallback ("simple_fallback"): only when an input other than pressure is missing. Use calculate_wbgt_simple(t2_k, rh).
   This simple formula assumes sunshine and OVERESTIMATES at night and when cloudy. It is a conservative fallback only.
   If pressure is missing use 1010 hPa and still call it liljegren.
5. If temperature or humidity is missing the hour has wbgt_c null, level "UNKNOWN", and no work/rest advice. Never guess.

### 3.7 Levels and limits (verified source: ACGIH 2026 TLV Table 1 as summarised by CCOHS)

Limits are WBGT in degrees Celsius. A cell with None means the table lists no value ("--").
The table is a screening tool for an 8-hour day, not a prescription of work and rest periods.

Work allocation bands, most permissive first:

| Band | Meaning | max_work_min per hour | Level when this band is the one that fits |
|---|---|---|---|
| A | 75-100% work | 60 | GREEN |
| B | 50-75% work | 45 | YELLOW |
| C | 25-50% work | 30 | ORANGE |
| D | 0-25% work | 15 | RED |
| none | above every limit | 0 | STOP |

```python
LIMITS_C = {
  "acclimatized": {
    "light":      {"A": 31.0, "B": 31.0, "C": 32.0, "D": 32.5},
    "moderate":   {"A": 28.0, "B": 29.0, "C": 30.0, "D": 31.5},
    "heavy":      {"A": None, "B": 27.5, "C": 29.0, "D": 30.5},
    "very_heavy": {"A": None, "B": None, "C": 28.0, "D": 30.0},
  },
  "unacclimatized": {
    "light":      {"A": 28.0, "B": 28.5, "C": 29.5, "D": 30.0},
    "moderate":   {"A": 25.0, "B": 26.0, "C": 27.0, "D": 29.0},
    "heavy":      {"A": None, "B": 24.0, "C": 25.5, "D": 28.0},
    "very_heavy": {"A": None, "B": None, "C": 24.5, "D": 27.0},
  },
}
```
Classification: for the bands A, B, C, D in order, take the first band whose limit is not None and where
wbgt_c <= limit (equal counts as inside). If none fits the level is STOP. min_rest_min = 60 - max_work_min.
For heavy and very heavy work the table lists no value for the most permissive bands, so the best reachable level is
capped (heavy: YELLOW, very heavy: ORANGE). The UI explains this with the reason text. This is deliberate and honest.

### 3.8 Message templates

English level names: GREEN low, YELLOW moderate, ORANGE high, RED very high, STOP extreme.
Hindi level names: GREEN कम, YELLOW मध्यम, ORANGE ज़्यादा, RED बहुत ज़्यादा, STOP अत्यधिक.

English hour text: "9 AM", "12 PM", "5 PM", "12 AM" (12-hour clock).
Hindi hour text (hi_hour): hours 0 to 3 "रात", 4 to 11 "सुबह", 12 to 15 "दोपहर", 16 to 18 "शाम", 19 to 23 "रात",
followed by the 12-hour number and " बजे". Examples: 9 gives "सुबह 9 बजे", 12 gives "दोपहर 12 बजे", 17 gives "शाम 5 बजे", 0 gives "रात 12 बजे".

Templates (python format fields in braces). start and end are hour texts, end is the exclusive end of the worst window,
peak_time is the hour text of the peak, peak is the peak WBGT, work and rest are minutes.

```python
EN_WINDOW = ("{site}: today from {start} to {end} the heat-stress level is {level} (peak WBGT {peak:.1f} C at {peak_time}). "
             "In this window work at most {work} minutes per hour and rest at least {rest} minutes in shade. "
             "Drink about 240 mL of cool water every 20 minutes. Stop work and tell your supervisor if you feel dizzy, sick or confused.")
EN_STOP = ("{site}: today from {start} to {end} heat stress is above the screening limits (peak WBGT {peak:.1f} C at {peak_time}). "
           "Stop non-essential work. Do only essential tasks, with a supervisor present, in shade, with frequent rests. "
           "Drink about 240 mL of cool water every 20 minutes.")
EN_GREEN = ("{site}: heat stress is within the screening limits all day. Keep drinking water, about 240 mL every 20 minutes "
            "when working hard, and stop and tell your supervisor if you feel unwell.")

HI_WINDOW = ("{site} साइट: आज {start} से {end} तक गर्मी का खतरा {level} रहेगा। सबसे ज़्यादा गर्मी {peak_time} के आसपास होगी। "
             "इस दौरान हर घंटे में ज़्यादा से ज़्यादा {work} मिनट काम करें और कम से कम {rest} मिनट छाया में आराम करें। "
             "हर 20 मिनट में लगभग एक गिलास ठंडा पानी पिएं। चक्कर, उल्टी या घबराहट हो तो तुरंत काम रोकें और सुपरवाइज़र को बताएं।")
HI_STOP = ("{site} साइट: आज {start} से {end} तक गर्मी का खतरा अत्यधिक रहेगा। इस समय ज़रूरी काम के अलावा बाकी सारा काम रोक दें। "
           "ज़रूरी काम भी सुपरवाइज़र की निगरानी में, छाया में और बार-बार आराम करके ही करें। "
           "हर 20 मिनट में लगभग एक गिलास ठंडा पानी पिएं।")
HI_GREEN = ("{site} साइट: आज दिन भर गर्मी का खतरा कम है। पानी पास रखें और भारी काम में हर 20 मिनट में पानी पिएं। "
            "तबीयत ठीक न लगे तो काम रोककर सुपरवाइज़र को बताएं।")
```
The worst window is the window with the highest level; if several, the earliest. If the worst level is GREEN use the GREEN
template. If it is STOP use the STOP template. Otherwise use WINDOW. If the worst level is UNKNOWN use the UNKNOWN template.
Message fields for a window: {peak} and {peak_time} are the maximum WBGT inside the worst window (earliest hour on a tie).
Level names in messages use the English or Hindi level names above. The text is always lowercase level word, for example "high".

```python
EN_UNKNOWN = ("{site}: weather data was not available, so no heat plan could be made for today. "
              "Keep shade and water close, and stop work and tell your supervisor if you feel unwell.")
HI_UNKNOWN = ("{site} साइट: मौसम का डेटा अभी उपलब्ध नहीं है, इसलिए आज का गर्मी का अनुमान नहीं बन सका। "
              "छाया और पानी पास रखें, और तबीयत ठीक न लगे तो काम रोककर सुपरवाइज़र को बताएं।")
```
These Hindi texts must be reviewed by a Hindi speaker (task P1.3).
"240 mL every 20 minutes" follows an occupational heat-response plan guidance (OHCOW); it is a general hydration prompt.

### 3.9 HTTP API (base URL is the API Gateway URL)

Errors always: {"error": {"code": "bad_request", "message": "..."}} with codes bad_request (400), unauthorized (401), not_found (404),
conflict (409), upstream_error (502), internal (500). CORS is handled by the gateway.
Mutating requests (all POST except the Telegram webhook) need the header x-demo-key equal to the DEMO_KEY.
The Telegram webhook needs header X-Telegram-Bot-Api-Secret-Token equal to TELEGRAM_WEBHOOK_SECRET.

| Method and path | Body | Success |
|---|---|---|
| GET /health | none | 200 {"ok": true, "service": "shramshield", "version": "...", "thermofeel": "2.3.0 or null"} (thermofeel is the version the Lambda can import, proves the layer works) |
| GET /sites | none | 200 {"sites": [Site]} |
| POST /sites | Site (site_id optional, generated if absent) | 201 Site |
| GET /sites/{site_id} | none | 200 Site |
| GET /sites/{site_id}/plan?date=YYYY-MM-DD | none | 200 Plan. date defaults to today (India), allowed from yesterday to 2 days ahead. Header x-cache HIT or MISS |
| POST /sites/{site_id}/run | {"ack_timeout_seconds": int, optional} | 202 {"run_id": "...", "status": "STARTED"} |
| GET /sites/{site_id}/runs/latest | none | 200 Run, or 404 |
| GET /runs/{run_id} | none | 200 Run |
| POST /ack | {"run_id": "...", "by": "name, optional"} | 200 {"ok": true, "status": "ACKNOWLEDGED"}; 409 if the run is already closed |
| POST /telegram/webhook | Telegram update | 200 {"ok": true} always |

POST /ack acknowledges whatever stage is currently active (primary or backup). Whoever responds first closes the run.

### 3.10 DynamoDB single table (name from the stack, partition key PK, sort key SK, TTL attribute ttl)

| Item | PK | SK |
|---|---|---|
| Site | SITE#{site_id} | META |
| Cached plan | SITE#{site_id} | PLAN#{date} (ttl = now + 1200 s) |
| Run | RUN#{run_id} | META |
| Latest run pointer | SITE#{site_id} | LATEST (attribute run_id) |
| Task token | RUN#{run_id} | TOKEN#{stage} (ttl = now + 7200 s) |

### 3.11 Environment variables of the Lambdas

TABLE_NAME, VOICE_BUCKET, STATE_MACHINE_ARN, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, DEMO_KEY, POLLY_REGION,
POLLY_VOICE_ID (Kajal), POLLY_ENGINE (neural), DASHBOARD_URL, WEATHER_CACHE_SECONDS (1200).
Frontend build variables: VITE_API_BASE, VITE_DEMO_KEY, VITE_USE_MOCK (true or false).

### 3.12 Open-Meteo calls (parameter names from the official documentation)

Forecast: https://api.open-meteo.com/v1/forecast with latitude, longitude,
hourly=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,shortwave_radiation,direct_radiation,
wind_speed_unit=ms, timezone=Asia/Kolkata, past_days=1, forecast_days=3 (that is yesterday, today and 2 days ahead; P1.1 step 1 must confirm past_days works).
Archive: https://archive-api.open-meteo.com/v1/archive with the same hourly list and wind_speed_unit=ms, timezone=Asia/Kolkata,
start_date and end_date as YYYY-MM-DD. The archive data has about a 5 day delay, fine for 2024.
Response shape: {"hourly": {"time": ["2026-10-09T00:00", ...], "temperature_2m": [...], ...}, "hourly_units": {...}}.
Null values can appear and must be handled. Free use is for non-commercial purposes (this hackathon). Acknowledge Open-Meteo.com and,
for archive data, "Generated using Copernicus Climate Change Service information" in the README.
The agent must confirm the live response shape in task P1.1 step 1 and stop if it differs.

### 3.13 Backtest object (core/data/backtest/backtest.json, copied to shared/fixtures/backtest.json)

```json
{
  "_fixture": false,
  "generated_at": "2026-10-09T10:00:00Z",
  "period": {"start": "2024-04-01", "end": "2024-06-30"},
  "profile": {"workload": "moderate", "acclimatized": true, "work_start_hour": 7, "work_end_hour": 18},
  "dangerous_levels": ["RED", "STOP"],
  "baseline_thresholds_c": [37, 40, 42],
  "sites": [{
    "site_id": "chn-01", "name": "Chennai", "lat": 13.085, "lon": 80.2101,
    "work_hours_total": 1001, "work_hours_with_data": 1001,
    "level_counts": {"GREEN": 0, "YELLOW": 0, "ORANGE": 0, "RED": 0, "STOP": 0},
    "dangerous_hours": 0,
    "by_threshold": [{"threshold_c": 40, "alert_hours": 0, "caught": 0, "missed": 0, "missed_pct": 0.0, "false_alarm_hours": 0}],
    "example_hour": {"time": "2024-05-15T14:00", "air_temp_c": 0.0, "rh_pct": 0, "wbgt_c": 0.0, "level": "RED"}
  }],
  "totals": {"dangerous_hours": 0, "by_threshold": [ ...same shape as above... ]},
  "caveats": ["text", "text"],
  "sources": {"weather": "Open-Meteo archive (ERA5 based reanalysis)", "wbgt_method": "liljegren", "thermofeel": "2.3.0"}
}
```
Definitions: a dangerous hour is a work hour whose level is RED or STOP. A baseline alert hour is a work hour whose air
temperature is at or above the threshold. caught = dangerous hours that are also alert hours. missed = dangerous hours that
are not alert hours. missed_pct = 100 * missed / dangerous_hours (0.0 if there are none). false_alarm_hours = alert hours whose
level is GREEN or YELLOW. example_hour is the dangerous hour with the lowest air temperature (null if none).
The backtest compares two methods on the same historical weather data. It is NOT a validation against heat illness cases.

### 3.14 Dashboard routes and fixture files

Hash routes (no server rewrite needed): #/ (sites), #/site/{site_id}, #/run/{run_id}, #/backtest, #/method.
Fixture files (all in shared/fixtures, created by P1.0): sites.json ({"sites": [Site x4]}, no _fixture key because sites are configuration),
plan_chennai_moderate.json, run_waiting.json, run_escalated.json, run_acknowledged.json, run_unacknowledged.json, backtest.json.
The four demo sites: chn-01 Chennai (13.085, 80.2101), del-01 Delhi (28.6139, 77.209), kol-01 Kolkata (22.5726, 88.3639),
hyd-01 Hyderabad (17.385, 78.4867). These are approximate city-centre coordinates used for the demo. Frontend copies fixtures into
frontend/src/fixtures with "npm run sync-fixtures" (the frontend must not read outside its own folder at build time).

---
## 4. Task cards

Every card has the same layout: Goal, You may edit, Needs (what must already exist), Steps, Definition of done,
Verify (commands to run and show), Pitfalls. Agents: do ONLY your card. Humans: the "Human does" lines are for you.

---

### P1.0: repository, contract files, fixtures, validators (P1, round R0, blocking, about 45 min)

**Goal.** Create the repository skeleton so P2 and P3 can start. Turn the contract (section 3) into working code:
fixtures that follow it and a validator that proves they do.

**You may edit.** Everything at the repo root created here (.gitignore, README.md stub), core/, shared/, docs/METHOD.md (stub).
You may also commit AGENTS.md and docs/BUILD_PLAN.md exactly as the human placed them (do not change them).

**Needs.** The empty GitHub repository exists and is cloned (H1). AGENTS.md and docs/BUILD_PLAN.md are in the folder.

**Steps.**
1. Check state: git status, git log. If the repo already has commits, run git pull --rebase origin main first.
2. Create .gitignore with at least these lines: `.venv/`, `venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `node_modules/`, `dist/`,
   `.aws-sam/`, `backend/build/`, `backend/samconfig.toml`, `backend/src/shramshield_core/`, `frontend/.env.local`, `frontend/.env.*.local`,
   `.env`, `*.env`, `.DS_Store`, `.idea/`, `.vscode/`. (The backend/src/shramshield_core/ line matters: it is a generated copy.)
3. Create README.md as a stub with the title, one sentence and "work in progress" (P3 rewrites it in P3.4).
4. Create the folders from contract 3.1 that belong to P1: core/shramshield_core, core/scripts, core/tests, core/data/raw,
   core/data/backtest, shared/fixtures. Add an empty file .gitkeep where a folder would otherwise be empty.
5. core/pyproject.toml: project name shramshield-core, version 0.1.0, requires-python ">=3.12", dependency thermofeel==2.3.0,
   optional dev dependency pytest. core/requirements.txt: thermofeel==2.3.0 and pytest (pin pytest to the installed major, for example pytest>=8).
   `core/shramshield_core/__init__.py`: `__version__ = "0.1.0"`.
6. Create a virtual environment OUTSIDE tracked files: python3.12 -m venv core/.venv (it is ignored by .gitignore:
   add core/.venv/ to .gitignore if the line is missing), install the requirements, run `python -c "import thermofeel; print(thermofeel.__version__)"`.
7. Write core/shramshield_core/contract.py (standard library only). It exports:
   - LEVELS = ["GREEN","YELLOW","ORANGE","RED","STOP"], WORKLOADS, DISCLAIMER (exact text from 3.2), RUN_STATUSES, RUN_STEPS,
     LIMITS_C (copy EXACTLY from 3.7) and LEVEL_FOR_BAND = {"A":"GREEN","B":"YELLOW","C":"ORANGE","D":"RED"}, MAX_WORK_MIN = {"GREEN":60,"YELLOW":45,"ORANGE":30,"RED":15,"STOP":0}.
   - validate_site(obj) -> list of error strings (empty list means valid). Implements every rule in 3.3 (site_id regex, lat 6..37, lon 68..98, workload,
     work hours, language, timeout 30..3600, name up to 60 characters, supervisor and backup objects with name and telegram_chat_id that is null, int or str).
   - validate_plan(obj) -> list of errors. Checks 3.4: 24 hours in order, hour matches time, level matches max_work_min and min_rest_min (STOP=0/60 and so on),
     level is consistent with wbgt_c using LIMITS_C for the plan profile (use the classify rule in 3.7, written separately inside this validator so it is an independent check),
     UNKNOWN rules, windows are consecutive work hours of the same non-GREEN level with exclusive end_hour, summary peak matches the hours, messages has en and hi, disclaimer is exact.
   - validate_run(obj) -> list of errors (3.5: status and step enums, final statuses have active_stage null, events have ts, step, detail, run_id format, plan_id format).
   - validate_backtest(obj) -> list of errors (3.13: keys present, counts add up: caught + missed == dangerous_hours, level_counts sum equals work_hours_with_data).
8. Create fixtures in shared/fixtures (all JSON, UTF-8, ensure_ascii=False, indent 2):
   - sites.json: {"sites": [four Site objects from 3.14]}. Workloads: chn-01 moderate, del-01 heavy, kol-01 moderate, hyd-01 light. All acclimatized true,
     work hours 7 to 18, language hi, chat ids null, ack_timeout_seconds 900 (del-01: 600). Names: "Chennai demo site", "Delhi demo site", "Kolkata demo site", "Hyderabad demo site".
   - plan_chennai_moderate.json: a FULL plan for site chn-01, date 2026-10-09, profile moderate acclimatized, with "_fixture": true and source.weather "fixture".
     Make a believable hot day: 24 hours, WBGT about 25 C at night, rising from 6 AM, peak about 32.0 C at 14:00, falling to 27 C by 18:00.
     Compute each level by hand from LIMITS_C (do not guess) and make the windows, summary, and both messages consistent with the templates in 3.8
     (en and hi, using the exact templates; peak_time for English "2 PM", Hindi "दोपहर 2 बजे"). Mark in a top-level key "_note": "fixture, not real data".
   - run_waiting.json (status WAITING_ACK, active_stage primary), run_escalated.json (ESCALATED, active_stage backup, events show notified_primary, escalated, notified_backup),
     run_acknowledged.json (ACKNOWLEDGED, acked_by "Supervisor", acked_via "telegram"), run_unacknowledged.json (UNACKNOWLEDGED, both stages notified, no ack). Each with "_fixture": true,
     voice_url null, plausible timestamps 2026-10-09 (UTC, ending with Z), events in time order.
   - backtest.json: a backtest object (3.13) with "_fixture": true, the 4 demo sites, small made-up counts that are internally consistent (caught + missed = dangerous_hours,
     level_counts sum equals work_hours_with_data), caveats list with at least these two strings: "Compares two methods on the same historical data; it is not validated against heat illness cases."
     and "Uses historical reanalysis data, not archived forecasts." This fixture is replaced by real numbers in P1.2. It is visibly fake only through the _fixture flag; the frontend shows the DEMO badge from that flag.
9. core/scripts/validate_fixtures.py: loads every file in shared/fixtures, picks the validator by file name (`sites.json`, `plan_*`, `run_*`, `backtest*`), prints OK or the errors, exits 1 on any error.
10. core/tests/test_contract.py: tests that every fixture validates; that a plan with a wrong level fails; that LIMITS_C matches 3.7 (compare to a literal copy in the test);
    that validate_site rejects lat 40, a bad site_id, work_end_hour <= work_start_hour, language "fr", and accepts the four demo sites.
11. docs/METHOD.md stub: title, "to be written in P1.2".
12. Commit AGENTS.md and docs/BUILD_PLAN.md if they are untracked (unchanged), then commit everything with the prefix "P1.0:". Push to origin main.

**Definition of done.** Fresh clone on another machine has the structure; validate_fixtures prints OK for all files; tests pass; .gitignore contains the lines above; nothing secret is committed.

**Verify (show the output).**
```
cd core && .venv/bin/python scripts/validate_fixtures.py     (Windows: .venv\Scripts\python)
cd core && .venv/bin/python -m pytest -q
git ls-files | head -50
git diff HEAD~1 --stat
```

**Human does.** After the push, tell P2 and P3 "R0 done, pull". P2 and P3 run: git clone, then open the folder in Antigravity.

**Pitfalls.** Do not compute levels with a function you wrote for the engine (that does not exist yet); the validator's independent classifier is the point.
Hindi text must be saved as UTF-8. Do not use the word "fixture" inside real messages. Do not put chat ids or tokens in sites.json.

---

### P1.1: core engine: weather, solar angle, WBGT, limits, plan, messages (P1, round R1)

**Goal.** A tested Python library: given a site and weather data, produce a plan object that passes validate_plan.

**You may edit.** core/ only (not shared/fixtures, except you may add new files there if a step says so).

**Needs.** P1.0 done. The virtual environment exists (core/.venv).

**Steps.**
1. **Live check (do this first).** Using python and urllib, call the Open-Meteo forecast URL for Chennai with the parameters of contract 3.12
   (including past_days=1 and forecast_days=3). Confirm: HTTP 200, the response has hourly.time and every hourly variable in 3.12, 96 time entries (4 days x 24),
   hourly_units show W/m2 for radiation, hPa for surface_pressure, m/s for wind_speed_10m, and times look like "2026-10-09T14:00". Save the first 6 hours of the response
   as core/tests/data/forecast_sample.json (a real response, trimmed, with a "_note" explaining it). If the call fails with 403 or a network error, or any variable is missing,
   STOP and tell the human: the whole plan depends on this.
2. **Inspect thermofeel.** Run python -c with inspect.signature on thermofeel.calculate_wbgt_liljegren and calculate_wbgt_simple and print them with the docstring.
   Confirm the argument names and units match contract 3.6 (kelvin, percent, hPa, m/s, W/m2). If they differ, STOP and tell the human.
3. core/shramshield_core/solar.py: cos_zenith(lat_deg, lon_deg, when_utc) exactly as below (standard library only).
```python
import math
from datetime import datetime

def cos_zenith(lat_deg: float, lon_deg: float, when_utc: datetime) -> float:
    doy = when_utc.timetuple().tm_yday
    hour = when_utc.hour + when_utc.minute / 60 + when_utc.second / 3600
    g = 2 * math.pi / 365 * (doy - 1 + (hour - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g)
                       - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    tst = hour * 60 + eqtime + 4 * lon_deg
    ha = math.radians(tst / 4 - 180)
    lat = math.radians(lat_deg)
    c = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    return max(0.0, min(1.0, c))
```
   Tests (tolerance 0.01): Chennai (13.085, 80.2101) at 2024-05-15 12:05 IST = 06:35 UTC gives 0.995; 06:00 IST gives 0.053; 15:00 IST gives 0.739; 20:00 IST gives 0.0;
   Delhi (28.6139, 77.209) at 2024-06-21 12:20 IST gives 0.996; Delhi at 2024-12-21 12:10 IST gives 0.614. (IST = UTC + 5:30; convert before calling. when_utc must be timezone-naive UTC or aware UTC; document which you choose and be consistent.)
   If any test fails, STOP: do not adjust the numbers, tell the human.
4. core/shramshield_core/weather.py (standard library only: urllib, json):
   - fetch_forecast(lat, lon, *, urlopen=None) and fetch_archive(lat, lon, start_date, end_date, *, urlopen=None): build the URL from 3.12, timeout 15 s, up to 2 retries with 1 s pause on network errors or HTTP 5xx or 429,
     raise WeatherError (a custom exception with a short message) otherwise. The urlopen argument lets tests inject a fake. User-Agent "shramshield/0.1 (hackathon)".
   - parse_hourly(response) -> list of rows {"time": "2026-10-09T14:00", "air_temp_c", "rh_pct", "pressure_hpa", "wind_ms", "ghi_wm2", "direct_wm2"}; any value can be None. Check that all lists have the same length as time, else WeatherError.
   - rows_for_date(rows, date_str) -> exactly 24 rows for that date or raise WeatherError("date not covered").
5. core/shramshield_core/wbgt.py:
   - compute_wbgt(row, lat, lon) -> (wbgt_c or None, method). Rules exactly as 3.6: temperature or humidity missing gives (None, None); other missing input (wind, ghi, direct) gives calculate_wbgt_simple and method "simple_fallback";
     pressure missing uses 1010 hPa and still "liljegren". cossza from solar.cos_zenith at the hour label minus 30 minutes (IST to UTC first). When cossza == 0: ssrd=0 and fdir=0.
     fdir = direct/ghi when ghi > 10 else 0, clamped 0..1. Convert units as thermofeel requires (kelvin). Return rounded to 1 decimal (Celsius).
   - Tests: a hot humid noon (36 C, 55 %, 1005 hPa, 3 m/s, 800 W/m2 ghi, 560 direct, Chennai midday) gives a WBGT between 28 and 36 and below air temperature + 2; the same weather at night (ghi 0) is lower than the noon value; missing humidity gives (None, None);
     missing wind gives method "simple_fallback"; the fallback value is never below the liljegren value for a night hour (it overestimates). Do not assert exact decimals you did not compute; print the real values once in the test output and keep ranges.
6. core/shramshield_core/limits.py: classify(wbgt_c, workload, acclimatized) -> dict with keys level, max_work_min, min_rest_min, limit_c, reason. Rules exactly as 3.7 (first band in A,B,C,D order whose limit is not None and wbgt <= limit; else STOP).
   limit_c is the limit of the matched band (for STOP it is null). wbgt None gives level "UNKNOWN", numbers null, reason "Temperature or humidity data missing for this hour; no advice given.".
   Reason texts (use these exact formats, one decimal):
   - Matched band: "WBGT 29.5 C is within the 30.0 C limit for 25-50% work ({workload} work, {acclimatized or unacclimatized})." (band label: A "75-100%", B "50-75%", C "25-50%", D "0-25%")
   - STOP: "WBGT 32.0 C is above every screening limit for moderate work (acclimatized); highest limit is 31.5 C."
   - When the best reachable band is capped (heavy or very heavy, the table lists no value for the more permissive bands) and the result is the first available band, append " The table lists no limit for more permissive bands at this workload, so the best level is capped at YELLOW." (ORANGE for very heavy). Use the right level word.
   Tests at the boundaries: moderate acclimatized 28.0 GREEN, 28.1 YELLOW, 29.0 YELLOW, 29.1 ORANGE, 30.0 ORANGE, 30.1 RED, 31.5 RED, 31.6 STOP; heavy acclimatized 15.0 YELLOW with the cap sentence; very_heavy acclimatized 15.0 ORANGE;
   light unacclimatized 28.0 GREEN, 28.1 YELLOW; very_heavy unacclimatized 27.0 RED, 27.1 STOP. One more test loops over every workload x acclimatization x wbgt from 10.0 to 40.0 step 0.1 and asserts the level never decreases as wbgt rises.
7. core/shramshield_core/messages.py: en_hour(h), hi_hour(h) per 3.8, level names in both languages, build_messages(site, summary, hours) -> {"en": ..., "hi": ...} using the templates in 3.8 exactly (copy them as constants).
   Choose the worst window as defined in 3.8 (highest level, earliest). Tests: hi_hour(9) == "सुबह 9 बजे", hi_hour(12) == "दोपहर 12 बजे", hi_hour(17) == "शाम 5 बजे", hi_hour(0) == "रात 12 बजे", hi_hour(21) == "रात 9 बजे", hi_hour(4) == "सुबह 4 बजे", hi_hour(13) == "दोपहर 1 बजे";
   en_hour(0) == "12 AM", en_hour(12) == "12 PM", en_hour(17) == "5 PM". A GREEN day, a STOP day, a WINDOW day and an UNKNOWN day each produce text without leftover braces.
8. core/shramshield_core/plan.py: build_plan(site, rows, date_str, generated_at) -> plan dict that satisfies 3.4 (generated_at is a string given by the caller so tests are deterministic).
   Hour entries: rounded air_temp_c (1 decimal), rh_pct (integer), wind_ms (1 decimal), ghi_wm2 (integer), none stays null. source.weather "open-meteo" (a parameter weather_source="open-meteo" lets tests say "fixture"), wbgt_method "liljegren" at plan level
   is the method used for the majority of hours (if any hour used the fallback add "simple_fallback_hours": N in source; this field is allowed; otherwise omit it). Windows, summary and UNKNOWN rules exactly as 3.4.
   Also add build_plan_for_site(site, *, now_utc=None, date_str=None, fetch=weather.fetch_forecast) that fetches and builds, so the backend has one call. If date_str is None use today in India.
9. core/scripts/make_plan.py SITE_ID [--date YYYY-MM-DD]: loads shared/fixtures/sites.json, fetches the live forecast, builds the plan, validates it with contract.validate_plan, prints a compact table (hour, air temp, humidity, WBGT, level) and the English and Hindi messages.
10. Tests for plan.py use hand-made rows (no network) for: a hot day, a cool day (all GREEN), a heavy-workload day (YELLOW cap), a day with two separate windows, a day with missing humidity for 2 work hours (UNKNOWN, windows skip them), a day where all work hours are UNKNOWN.
    Every produced plan must pass validate_plan.
11. Run everything, commit "P1.1: ..." and push.

**Definition of done.** pytest passes; make_plan.py prints a valid live plan for chn-01 and del-01; the live-check sample is saved; the thermofeel signature was confirmed.

**Verify (show the output).**
```
cd core && .venv/bin/python -m pytest -q
cd core && .venv/bin/python scripts/make_plan.py chn-01
cd core && .venv/bin/python scripts/make_plan.py del-01
cd core && .venv/bin/python scripts/validate_fixtures.py
```

**Human does.** Read the printed Chennai table once. Does WBGT look sensible (below air temperature on a humid evening? night values lower than noon?). Tell the team the time you see the output.

**Pitfalls.** Open-Meteo radiation is the mean of the preceding hour: cos-zenith must use hour minus 30 minutes. Pressure from Open-Meteo is already hPa. thermofeel wants kelvin and returns kelvin.
Never put the plan's disclaimer into the code twice: import DISCLAIMER from contract.py. Python round() on x.x5 values is banker-like; tests must not depend on a tie.

---

### P2.1: AWS skeleton and first deploy (P2, round R1)

**Goal.** A deployed stack in ap-south-1 with a DynamoDB table, a private S3 bucket, a Lambda layer with thermofeel, and an HTTP API whose /health works from the internet.

**You may edit.** backend/ only (and nothing else). Never write secrets into tracked files.

**Needs.** P1.0 pushed. H2 finished (aws sts get-caller-identity works, SAM CLI installed, region ap-south-1).

**Steps.**
1. Print and show: aws --version, sam --version, python --version, aws sts get-caller-identity (hide nothing but do not paste the account id into any file), aws configure get region.
2. backend/template.yaml (AWS SAM, Transform AWS::Serverless-2016-10-31). Globals for functions: Runtime python3.12, Architectures [x86_64], Timeout 30, MemorySize 512, Layers [DepsLayer].
   Parameters: DemoKey (String, NoEcho true, no default), TelegramBotToken (NoEcho, Default "not-set"), TelegramWebhookSecret (NoEcho, Default "not-set"), PollyRegion (Default ap-south-1), DashboardUrl (Default ""), WeatherCacheSeconds (Default "1200").
   Resources now:
   - DataTable: AWS::DynamoDB::Table, BillingMode PAY_PER_REQUEST, KeySchema PK (HASH) and SK (RANGE) both String, TimeToLiveSpecification AttributeName ttl Enabled true.
   - VoiceBucket: AWS::S3::Bucket, PublicAccessBlockConfiguration all four true, BucketEncryption SSE-S3, LifecycleConfiguration expire objects after 7 days.
   - DepsLayer: AWS::Serverless::LayerVersion, ContentUri build/layer, CompatibleRuntimes [python3.12], CompatibleArchitectures [x86_64], RetentionPolicy Delete.
   - HttpApi: AWS::Serverless::HttpApi with CorsConfiguration (AllowOrigins ["*"], AllowMethods [GET, POST, OPTIONS], AllowHeaders [content-type, x-demo-key], ExposeHeaders [x-cache], MaxAge 600) and DefaultRouteSettings ThrottlingBurstLimit 20, ThrottlingRateLimit 10.
   - ApiFunction: AWS::Serverless::Function, Handler api.handler, CodeUri src/, Environment variables from contract 3.11 (TABLE_NAME !Ref DataTable, VOICE_BUCKET !Ref VoiceBucket, DEMO_KEY !Ref DemoKey, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, POLLY_REGION, POLLY_VOICE_ID Kajal, POLLY_ENGINE neural, DASHBOARD_URL, WEATHER_CACHE_SECONDS, STATE_MACHINE_ARN "" for now).
     Policies: DynamoDBCrudPolicy for the table. Events: Type HttpApi, ApiId !Ref HttpApi, Path /{proxy+}, Method ANY; and Path / with Method ANY.
   Outputs: ApiUrl (the API base URL without a trailing slash), TableName, VoiceBucketName.
3. backend/scripts/build_layer.py (standard library only): removes backend/build/layer, runs pip install with these exact options so the wheels match Lambda even on Windows or Mac:
   python -m pip install --platform manylinux2014_x86_64 --python-version 3.12 --implementation cp --only-binary=:all: --target backend/build/layer/python thermofeel==2.3.0
   then deletes `__pycache__` and tests folders inside the layer, prints the layer size in MB. Fail loudly if the size is above 200 MB unzipped.
4. backend/scripts/prepare.py: copies core/shramshield_core/*.py into backend/src/shramshield_core/ (only .py files), after deleting the old copy. If core/shramshield_core is missing or has no wbgt.py yet, print a clear warning and exit 0 (P1.1 may not be pushed yet).
   Add "python backend/scripts/prepare.py" as step 1 of every deploy in DEPLOY_NOTES.md.
5. backend/src/common/http.py and backend/src/api.py (standard library plus boto3, which Lambda provides):
   - Event format is API Gateway payload 2.0: event["requestContext"]["http"]["method"], event["rawPath"], event["headers"] (lowercase keys), event.get("queryStringParameters"), event.get("body"), event.get("isBase64Encoded").
   - Helpers: json_response(status, body_dict, extra_headers=None) with Content-Type application/json; error(code, message) producing the contract error body and the right status (bad_request 400, unauthorized 401, not_found 404, conflict 409, upstream_error 502, internal 500).
   - require_demo_key(event): compare header x-demo-key with env DEMO_KEY using hmac.compare_digest; missing or wrong gives unauthorized. If DEMO_KEY is empty or "not-set" all mutating routes fail closed.
   - A tiny router: (method, regex path) -> function. Unknown path gives not_found. Wrap everything in try/except that logs the exception type and message (never the headers or body) and returns the internal error.
   - GET /health returns {"ok": true, "service": "shramshield", "version": "0.1.0", "thermofeel": <version string or null>} where the thermofeel version comes from a guarded import (try/except ImportError) so a missing layer shows null instead of crashing.
   - All other contract routes are NOT implemented yet: they return 501-style not_found with message "not implemented yet" (use code not_found).
6. backend/tests/test_api.py (pytest): call api.handler with hand-made events: health 200 and keys present, unknown path 404 with error body, POST without demo key 401, with wrong key 401, with right key reaches the handler (use a dummy POST route registered only in the test), OPTIONS not needed (gateway handles it).
   backend/requirements-dev.txt: pytest. Create backend/.venv (ignored) to run them.
7. backend/samconfig.toml.example with placeholder values (stack_name "shramshield", region "ap-south-1", resolve_s3 true, capabilities CAPABILITY_IAM, parameter_overrides with placeholders such as DemoKey=\"CHANGE_ME\"). Confirm backend/samconfig.toml is in .gitignore.
8. backend/DEPLOY_NOTES.md: exact commands: prepare, build_layer, sam validate --lint, sam build, sam deploy, how to read outputs (aws cloudformation describe-stacks --stack-name shramshield --query "Stacks[0].Outputs"), how to delete the stack (do not run).
9. **Ask the human before deploying** ("this creates a DynamoDB table, an S3 bucket, a Lambda and an API in your account; cost is near zero"). After yes: run sam validate --lint, python backend/scripts/build_layer.py, python backend/scripts/prepare.py, sam build, and sam deploy --guided with these answers:
   stack name shramshield; region ap-south-1; DemoKey = the human types it (the agent must NOT see or write it; ask the human to run that one command in their own terminal if the agent cannot pause for input);
   other parameters keep defaults; confirm changes before deploy Y; allow IAM role creation Y; "ApiFunction may not have authorization defined, is this okay" Y; save arguments to samconfig.toml Y.
   If sam build fails on the layer (no Metadata for DepsLayer) skip sam build and run sam deploy directly: SAM packages local CodeUri folders itself and there are no compiled dependencies in the function folder. Report which path worked.
10. Show the outputs, run curl "$API_URL/health" and show the response. Expected: ok true and "thermofeel": "2.3.0". If thermofeel is null the layer is wrong: fix before finishing.
11. Commit "P2.1: ..." and push (samconfig.toml must NOT be in git status).

**Definition of done.** /health returns 200 with thermofeel 2.3.0 from the internet; tests pass; nothing secret is tracked; DEPLOY_NOTES.md lets another person redeploy.

**Verify (show the output).**
```
cd backend && .venv/bin/python -m pytest -q
sam validate --lint
curl -s "$API_URL/health"
curl -s -X POST "$API_URL/anything" -H "content-type: application/json" -d "{}"      (expect 401 or 404, never 200)
git status --short                                                                  (samconfig.toml must not appear)
```

**Human does.** Tell P1 and P3 the API URL (it is not secret). Keep the DEMO_KEY in the team password manager and give it to P3 privately (they put it in frontend/.env.local).

**Pitfalls.** Always deploy in ap-south-1 (Mumbai) unless H2 step 6 said otherwise for Polly only. pip --platform needs --only-binary=:all: and --target together. Windows paths: use pathlib. Do not name the table (let CloudFormation name it).
HttpApi throttling keys are ThrottlingBurstLimit and ThrottlingRateLimit under DefaultRouteSettings. NoEcho parameters still appear in samconfig.toml: keep that file untracked.

---

### P3.1: dashboard shell on fixtures (P3, round R1)

**Goal.** A good-looking, accessible React app that runs on fixture data: site list, site plan page, backtest page, method page. No backend needed yet.

**You may edit.** frontend/ only (and README.md stub if you want a one-line change; do not).

**Needs.** P1.0 pushed (fixtures exist in shared/fixtures).

**Steps.**
0. **Design references.** Look in docs/design/ (the human may have put 4 to 8 reference images there, plus an optional docs/design/NOTES.md). If images exist, open and study each one and write docs/design/DESIGN_SUMMARY.md (P3 owns it): the layout pattern, colour mood, typography feel, card style, spacing, what to copy and what NOT to copy (never copy another product's logo, brand name, text or exact artwork; take only the general layout and mood). The UI should be a compact operations dashboard: site cards, a 24-hour heat strip, a status timeline. If the folder is empty, say so and continue with a clean, high-contrast, light theme. The five level colours below always win over the reference palette.
1. Create the app in frontend/ with Vite and React (JavaScript, not TypeScript): npm create vite@latest frontend -- --template react (accept defaults) or write the files by hand. Allowed dependencies: react, react-dom, vite, @vitejs/plugin-react, vitest. NOTHING else (no router, no UI kit, no chart library, no CSS framework, no icon packs).
2. frontend/scripts/sync-fixtures.mjs copies every file from ../shared/fixtures into frontend/src/fixtures. package.json scripts: dev, build, preview, test (vitest run), sync-fixtures. Run sync-fixtures and commit the copied files (they are small).
3. frontend/.env.example: VITE_API_BASE=https://example.execute-api.ap-south-1.amazonaws.com, VITE_DEMO_KEY=CHANGE_ME, VITE_USE_MOCK=true. frontend/.env.local is untracked. Default in code: mock mode when VITE_USE_MOCK is "true" or VITE_API_BASE is empty.
4. src/api.js: functions listSites(), getSite(id), getPlan(id, date), getLatestRun(id), getRun(runId), startRun(id), ack(runId), createSite(site), getBacktest(). In this task only the mock implementation exists (reads the imported fixtures, small artificial delay of 300 ms).
   Mock plan exists only for chn-01; other sites reject with {code:"not_found"} so the error UI is exercised. Every function returns the contract shapes exactly.
5. src/levels.js: for each level (GREEN, YELLOW, ORANGE, RED, STOP, UNKNOWN) a name (English and Hindi from contract 3.8), a background colour, a text colour, and a short symbol character (for example "G Y O R S ?" is NOT allowed; use words: "LOW", "MODERATE", "HIGH", "VERY HIGH", "EXTREME", "NO DATA").
   Use these colours: GREEN bg #1b7f3b text #ffffff; YELLOW bg #f2c200 text #111111; ORANGE bg #e8710a text #111111; RED bg #c62828 text #ffffff; STOP bg #5b0f12 text #ffffff; UNKNOWN bg #6b7280 text #ffffff.
   A vitest test computes the WCAG contrast ratio for each pair and asserts at least 4.5.
6. src/App.jsx with a tiny hash router (window.location.hash, a hashchange listener) for the routes in contract 3.14. Header with the product name, nav links (Sites, Backtest, Method), and a language switch EN/HI for message text (the UI chrome stays English).
   Footer on every page: the disclaimer text (import from fixtures/plan, or constant identical to contract 3.2).
7. Sites page (#/): a card grid from listSites(): name, workload, hours, language, and a button/link "View plan". Loading skeleton, error state with retry, empty state.
8. Site page (#/site/{id}): title, profile line ("Moderate work, acclimatized, 7 AM to 6 PM"), the plan:
   - A "heat strip": 24 cells in a row (stacked in two rows on narrow screens), each cell is a focusable button element with an aria-label like "2 PM: EXTREME, WBGT 32.0 C, work 0 minutes per hour". Cell shows hour and the level word; not-working hours are visibly dimmed and labelled.
   - Selecting a cell shows a detail panel: air temperature, humidity, wind, sun radiation, WBGT, level, max work and min rest minutes, and the reason text.
   - A "Today's windows" list from summary.windows in plain words (EN or HI by the language switch).
   - The message box with the EN or HI message and a copy button.
   - A badge "DEMO DATA (fixture)" at the top of the page whenever the loaded object has _fixture true. Never show that badge for real data.
   - Buttons "Run now" and "Acknowledge" are NOT built in this task.
9. Backtest page (#/backtest): headline sentence generated from the totals ("Between 1 April and 30 June 2024, N work hours were RED or STOP across 4 cities. An air-temperature alert at 40 C would have missed M of them (P%)."), a table per threshold, a small bar for each city built with plain divs (with text numbers next to the bars), the caveats list, the example hour, and the "DEMO DATA" badge when _fixture is true.
10. Method page (#/method): static text: what WBGT is in two sentences, the five levels with their max minutes per hour, the data sources (Open-Meteo, thermofeel from ECMWF, ACGIH screening limits as summarised by CCOHS), the limits table for the profile of the site if available, and an honest "What this is not" paragraph (not a measurement, not medical advice, not validated against illness data).
11. Accessibility: one h1 per page, landmarks (header, main, footer), visible focus outlines, buttons are real buttons, colour is never the only signal, text can zoom to 200% without overflow, works at 360 px width.
12. Tests (vitest): levels contrast, a pure function that builds the headline sentence, a pure function that formats hour text (EN and HI per 3.8). Keep UI logic in pure functions so they can be tested.
13. Run: npm install, npm run sync-fixtures, npm run test, npm run build, then npm run dev and describe in words what the three pages show. Commit "P3.1: ..." and push.

**Definition of done.** npm run build and npm run test pass; the app works offline on fixtures; all pages have loading, error and empty states; no extra dependencies; keyboard-only use works.

**Verify (show the output).**
```
cd frontend && npm install && npm run sync-fixtures && npm run test && npm run build
npm ls --depth=0           (only the allowed dependencies)
cd .. && git status --short
```

**Human does.** Open the dev server URL on your laptop and your phone (same Wi-Fi: npm run dev -- --host). Check the heat strip and the Hindi message. Take two screenshots for later (docs/img is created in P3.4).

**Pitfalls.** Vite env variables must start with VITE_. Devanagari needs a font fallback in CSS (font-family: system-ui, "Noto Sans Devanagari", "Nirmala UI", sans-serif). Do not import from outside frontend/ (build breaks on other machines).
The heat strip must be reachable by keyboard Tab and activated with Enter or Space. Do not render the fixture badge using CSS only (screen readers must hear it).

---
### P1.2: backtest on real historical data and the method document (P1, round R2)

**Goal.** Real numbers for the headline claim: over April to June 2024, how many dangerous work hours would a plain air-temperature alert have missed, compared with our WBGT levels? Plus the written method.

**You may edit.** core/, shared/fixtures/backtest.json (replace the fixture), docs/METHOD.md.

**Needs.** P1.1 pushed and working. Network access to the Open-Meteo archive API.

**Steps.**
1. Pull. Run the P1.1 tests to make sure the base is healthy.
2. core/scripts/run_backtest.py with arguments --start 2024-04-01 --end 2024-06-30 --workload moderate --acclimatized true --work-start 7 --work-end 18 (these are the defaults). For each of the four demo sites in shared/fixtures/sites.json:
   - Use weather.fetch_archive once for the whole period. Cache the raw JSON response to core/data/raw/archive_{site_id}_{start}_{end}.json. If the cache file exists the script uses it and does not call the network (flag --refresh forces a download). Commit the cache files (each is a few hundred KB; check sizes with du -h and tell the human if any is above 2 MB).
   - Confirm the response covers every hour (91 days x 24 = 2184 rows). Report any null values (count per variable).
   - For every hour compute WBGT with wbgt.compute_wbgt and classify with limits.classify for the profile. Count only work hours (7 to 18, end exclusive, so 11 hours per day, 1001 work hours per site for 91 days).
   - Compute the numbers defined in contract 3.13 for thresholds 37, 40 and 42 degrees C of air temperature (alert when air temp >= threshold). Choose example_hour as defined there.
   - Per-site and total results. Write core/data/backtest/backtest.json (valid under validate_backtest, "_fixture": false, generated_at in UTC now) and copy it to shared/fixtures/backtest.json. The script runs validate_backtest and fails if invalid.
   - The caveats list must contain at least: (1) "Compares two methods on the same historical data; it is not validated against heat illness cases." (2) "Uses historical reanalysis data, not archived forecasts, so real-time forecast error is not included." (3) "WBGT is estimated from modelled weather at a city point, not measured at the worksite." (4) "Screening limits are for an 8-hour workday and are not a prescription of work and rest periods."
3. Print a readable summary table: per site and total, dangerous hours, and for each threshold caught, missed, missed percent, false alarm hours. Print the example hours.
4. Sanity checks (the script prints PASS or FAIL for each; if one fails do not fix by editing numbers, STOP and tell the human):
   - Chennai in April to June has more dangerous hours than zero, and Delhi has some RED or STOP in May or June (June 2024 had a severe heatwave in north India). If a hot city shows zero dangerous hours, the unit handling is probably wrong: check units, cossza and pressure.
   - Night hours are never RED or STOP in the data (check the whole 24 hours too, count it).
   - WBGT never exceeds air temperature + 3 C in any hour (physical plausibility; list the hours that do).
5. Sensitivity (add a "sensitivity" key to the script output file core/data/backtest/sensitivity.json, not part of the contract): repeat for workload heavy acclimatized and for moderate unacclimatized, only the dangerous hour counts and missed percent at 40 C. Used in the writeup as "robustness".
6. docs/METHOD.md (write it properly, plain English, about 1.5 pages): 1 the problem in two sentences; 2 what WBGT is and why air temperature alone is misleading (humidity, sun, wind; no numbers you did not compute); 3 data and model: Open-Meteo, Liljegren method from thermofeel (ECMWF, Apache 2.0), solar angle function and the half-hour offset; fallback; 4 limits table copied from contract 3.7 with the source named exactly as in the contract;
   5 levels and what they mean; 6 the backtest: definition, the real numbers from this run (copy them from the output), the example hour; 7 limitations and honesty (list the four caveats plus: forecast uncertainty, city-point weather, microclimate such as bitumen and metal roofs, individual variation, the screening limits are not a medical standard for everyone); 8 references (names and URLs: Open-Meteo, ECMWF thermofeel, CCOHS ACGIH page, ACGIH, OHCOW for hydration prompt).
7. Tests: a small synthetic archive response (24 x 3 hours written in the test) goes through the whole backtest function and gives hand-computed counts; validate_backtest on the real output passes; a test that totals equal the sum of the sites.
8. Commit "P1.2: ..." and push.

**Definition of done.** shared/fixtures/backtest.json is real (_fixture false) and valid; sanity checks PASS; METHOD.md contains the real numbers; tests pass.

**Verify (show the output).**
```
cd core && .venv/bin/python -m pytest -q
cd core && .venv/bin/python scripts/run_backtest.py
cd core && .venv/bin/python scripts/validate_fixtures.py
git diff --stat HEAD~1
```

**Human does.** Read the summary table. The headline number (missed percent at 40 C) is what the team will quote: write it in the team chat as "P1.2 numbers: ..." and do not quote any other number in public until P1.4.

**Pitfalls.** If Open-Meteo's archive returns radiation as null for some hours, count them and let the plan treat them as the simple fallback (do not drop hours silently). Reanalysis air temperature is a grid value (about 10 to 25 km) and can differ from a station: that is why it is a method comparison. Do not tune thresholds to make the result look better.
If the result is weaker than expected, report it honestly; the team can still use it (the point is that the two methods disagree in specific hours).

---

### P2.2: sites and plan API (P2, round R2)

**Goal.** The deployed API serves sites and live plans exactly as the contract says (3.9), with caching and input validation.

**You may edit.** backend/ only.

**Needs.** G1 passed (P1.1 core pushed, P2.1 deployed). Pull, then run python backend/scripts/prepare.py.

**Steps.**
1. Pull. Run prepare.py: backend/src/shramshield_core now exists locally (ignored by git). Run the backend tests and core import: python -c "import sys; sys.path.insert(0,'backend/src'); import shramshield_core.plan".
2. backend/requirements-dev.txt: pytest, boto3, moto[dynamodb,s3]>=5. These are for tests only, never in the Lambda.
3. backend/src/common/db.py: functions get_site(table, site_id), put_site, list_sites, get_cached_plan(table, site_id, date), put_cached_plan(table, site_id, date, plan, ttl_seconds). Item keys exactly as contract 3.10.
   DynamoDB does not accept Python floats: convert on write with json.loads(json.dumps(obj), parse_float=Decimal) and on read convert Decimal back to int when integral, else float (write helper to_ddb and from_ddb and test them with a plan object). Store the site/plan as an attribute "data" (a map) plus "ttl" (number, epoch seconds) for cache items.
4. api.py routes (replace the "not implemented" answers for these):
   - GET /sites: all sites, sorted by site_id (scan with a begins_with filter on PK "SITE#" and SK "META", or query a small index; the table is tiny, scan is acceptable here; note it in a comment).
   - GET /sites/{site_id}: 200 or not_found.
   - POST /sites (demo key): validate with shramshield_core.contract.validate_site (single source of truth); if site_id missing generate "site-" plus 6 random lowercase letters or digits; duplicate gives conflict 409; refuse when the table already has 25 sites (conflict, "site limit reached"); telegram_chat_id stays whatever was given (null allowed). Return 201 with the stored Site.
   - GET /sites/{site_id}/plan?date=: date default today India (compute with datetime.now(timezone(timedelta(hours=5, minutes=30)))). Allowed from yesterday to 2 days ahead, else bad_request with a clear message. Check the cache first (HIT) else build with plan.build_plan_for_site (MISS), store with ttl now + WEATHER_CACHE_SECONDS, return the plan with header x-cache. WeatherError gives upstream_error 502 with message "weather service unavailable".
     The plan for a cached date must carry generated_at from when it was built.
   - Everything else stays not implemented (runs and ack come in P2.3).
5. Input hardening: reject bodies above 8 KB (bad_request), reject invalid JSON (bad_request), site ids are validated against the regex before any DynamoDB key is built, unknown fields in POST /sites are ignored (not stored).
6. backend/scripts/seed_sites.py: reads shared/fixtures/sites.json, writes the four sites into the table named by --table (or the stack output via --stack shramshield using boto3 cloudformation) using db.put_site. Add the command "set-chat SITE_ID supervisor|backup CHAT_ID" that updates only that field. Chat ids are typed at the command line and never written to a tracked file. Idempotent (running twice is fine; it must not overwrite chat ids already set: only create sites that do not exist, unless --overwrite).
7. backend/scripts/smoke.py --api URL [--key KEY]: checks health, sites (4 sites), plan for chn-01 (24 hours, validate with contract.validate_plan, disclaimer text exact), second call returns x-cache HIT, bad date returns 400, POST /sites without key returns 401, a valid POST with key returns 201 and then a second identical site_id returns 409 (then it leaves the created test site; mention it in the output). Print PASS/FAIL per check and exit 1 on any FAIL. The key comes from the --key flag or the DEMO_KEY environment variable and is never printed.
8. Tests with moto: sites CRUD, validation errors, the cache (second call HIT, expired item is a MISS: set ttl in the past and check), to_ddb/from_ddb, date range, upstream error mapping (monkeypatch the fetch function to raise WeatherError). Use a fake fetch that returns rows from core tests so no network is needed.
9. Deploy: python backend/scripts/prepare.py, sam build, sam deploy (uses samconfig.toml). Ask the human before running deploy. Then run seed_sites.py and smoke.py against the deployed API and show the output.
10. Commit "P2.2: ..." and push. Tell P3 the API now serves /sites and /sites/{id}/plan.

**Definition of done.** smoke.py all PASS against the deployed API; tests pass; plan response time (MISS) below 5 s (print the time); the cache HIT below 1 s.

**Verify (show the output).**
```
cd backend && .venv/bin/python -m pytest -q
python backend/scripts/seed_sites.py --stack shramshield
python backend/scripts/smoke.py --api "$API_URL"
curl -s "$API_URL/sites/chn-01/plan" -o /dev/null -w "%{http_code} %{time_total}s\n"
git status --short
```

**Human does.** Open the plan URL in a browser and read the JSON of Chennai. Compare WBGT with P1's make_plan output for the same hour (they should agree within rounding).

**Pitfalls.** DynamoDB Decimal vs float is the classic bug (TypeError: Float types are not supported). Lambda is read-only except /tmp: Python code must not write files. The core package inside the Lambda is the prepare.py copy: if you change core you re-run prepare.py. API Gateway HTTP API v2 lowercases header names. Cold start imports thermofeel and numpy (about 1 s): fine, but do not import at module level in routes that do not need it (import inside the plan function).

---

### P3.2: dashboard on the real API (P3, round R2)

**Goal.** The same dashboard now talks to the deployed API, with a switch between mock and live, proper loading/error states, and an "add site" form.

**You may edit.** frontend/ only.

**Needs.** P3.1 done. P2.2 deployed (the live check is the LAST step; do the rest first, and do the live check as soon as P2 says the API is up).

**Steps.**
1. Pull. frontend/.env.local (untracked, create it yourself): VITE_API_BASE=<API URL from P2, no trailing slash>, VITE_DEMO_KEY=<key from P2>, VITE_USE_MOCK=false.
2. src/api.js: add the live implementation next to the mock. A request helper with: base URL, 10 s timeout (AbortController), JSON parsing, and mapping of the contract error body {"error": {"code", "message"}} to a thrown ApiError with code and message. Network failures become ApiError code "network". POST requests add the x-demo-key header from VITE_DEMO_KEY. GET requests do not send the key.
   Which implementation is used is decided in one place by the env variables (live when VITE_USE_MOCK is "false" and VITE_API_BASE is set).
3. Sites page: loads from the live API. Add an "Add site" form (name, latitude, longitude, workload select, acclimatized checkbox, work start/end hours, language, ack timeout) with client-side checks that mirror contract 3.3 and show the server's error message if the API rejects it. Submitting posts the site and refreshes the list. No telegram chat id field (that is set by P2 with the seed script).
4. Site page: date selector (yesterday, today, tomorrow, day after) calling GET plan?date=; show "data loaded from cache" or "fresh" from the x-cache header (the fetch response header; add expose headers handling: HTTP API CORS might hide x-cache; if the header is not readable show nothing, do not fail), and the time the plan was generated ("generated 11:32 AM India time"). Retry button on errors. Show the DEMO badge only when _fixture is true.
5. A small "System status" line in the footer from GET /health ("API online, v0.1.0" or "API unreachable").
6. Make sure that when live mode is on and the API fails, the app does NOT silently fall back to fixtures. It shows the error. (Fixtures are only used when mock mode is explicitly on.)
7. Tests: the request helper with a fake fetch (success, error body, timeout, network failure); the site form validator.
8. Live check: npm run dev with live mode; load sites, open chn-01, switch dates, add a test site "Test site" then confirm it appears in the list (P2 knows the test site stays in the table; use the name prefix "test-" in site_id).
   Run npm run build with live env variables to confirm the production build works (dist/ is ignored by git).
9. Commit "P3.2: ..." and push. Tell the team the dev server works against the live API.

**Definition of done.** Live mode shows the four seeded sites and real plans; mock mode still works; errors are visible and recoverable; build and tests pass.

**Verify (show the output).**
```
cd frontend && npm run test && npm run build
git status --short                      (frontend/.env.local must not appear)
grep -rn "execute-api" frontend/src frontend/*.md frontend/.env.example || true     (no real API URL in tracked files)
```

**Human does.** Check in the browser: Chennai plan equals what P1/P2 saw; the Hindi message reads correctly (a Hindi speaker should look now, even before P1.3).

**Pitfalls.** The demo key in VITE_DEMO_KEY ends up inside the built JavaScript, so it is public to anyone who opens the site. That is acceptable only because it protects against random abuse and will be rotated after the event; never put anything more sensitive in a VITE_ variable.
CORS errors in the browser console mean the API Gateway CORS config is missing a header: tell P2, do not work around it. Hash routing means no server rewrite is needed on Amplify.

---
### P1.3: hardening, Hindi review, live verification (P1, round R3)

**Goal.** Make the core trustworthy: edge cases, reviewed Hindi text, a live check script, and a voice-text function for the backend.

**You may edit.** core/, shared/fixtures/, docs/METHOD.md, docs/HINDI_REVIEW.md. If a contract text must change (for example a Hindi sentence), STOP and tell the human: the human edits section 3.8 of docs/BUILD_PLAN.md (you may do it only when the human tells you the exact new text).

**Needs.** P1.2 done. A Hindi-speaking person available (teammate, friend, family) for 10 minutes.

**Steps.**
1. Pull. Run the full core tests.
2. docs/HINDI_REVIEW.md: a table with columns Message id, Hindi text, Reviewer OK?, Suggested change, Reviewer name and date. Rows: HI_WINDOW (print one real rendered example, for ORANGE), HI_STOP (one rendered), HI_GREEN, HI_UNKNOWN, the five level names, the hour words. Also write 5 short questions for the reviewer: Is it polite and clear for a construction worker? Is the speed of reading natural? Are "सुपरवाइज़र" and "साइट" what workers say? Is "गर्मी का खतरा" the right phrase? Is the order of information right? Leave the Reviewer columns empty (the human fills them).
3. Voice text: messages.voice_text(plan, lang) returns the text to send to Polly: the message of that language with these substitutions only: no emoji, no markdown, "C" never appears (templates contain no units). Ensure the Hindi voice text contains no Latin letters except those in the site name (site names with Latin letters are fine). Return the text length too in a test. Maximum 600 characters; if the message is longer, shorten by dropping the last sentence (the hydration sentence) and test it.
4. Edge-case tests (all must pass): leap day and year boundary dates in solar.py; hour labels 23:00 and 00:00 across a date boundary for cossza; a site at the edges (lat 6.0 lon 68.0 and lat 37.0 lon 98.0); WBGT at 0 C and 50 C air temperature (no exceptions, level STOP at 50); RH 0 and 100; wind 0; pressure 1010 default; archive rows with every kind of None; plan built twice with the same input is identical (deterministic); a plan JSON survives json.dumps/loads and still validates; plan size below 30 KB.
5. Property test with hypothesis is NOT allowed (extra dependency); instead write a loop test over a deterministic pseudo-random sample (random.Random(1234)) of 2000 weather rows and assert: plan validates, WBGT is within -10 and 60, level is monotone in wbgt for fixed profile.
6. core/scripts/verify_live.py: for the four demo sites fetch the live forecast, build the plan for today, validate it, print per site: peak WBGT, worst level, fallback hours count, time taken. Exits 1 if any site fails.
7. Performance test: building a plan from rows takes under 100 ms on the developer's machine (print the number; do not fail the build on slow machines, fail only above 1 s).
8. Update docs/METHOD.md only where something changed. Keep numbers synced with P1.2 output (do not recompute here).
9. **Hindi corrections.** After the human returns the reviewed table: apply the corrections ONLY in the way the human states them. Because the Hindi templates live in the contract, the human edits section 3.8 of BUILD_PLAN.md and tells you; you then update messages.py to match, regenerate shared/fixtures/plan_chennai_moderate.json messages, and run all tests. If the human has no reviewer yet, leave HINDI_REVIEW.md as "pending" and say so in the commit message.
10. Commit "P1.3: ..." and push.

**Definition of done.** All tests pass; verify_live prints four OK lines; HINDI_REVIEW.md exists and is either filled or clearly marked pending (never claim a review that did not happen).

**Verify (show the output).**
```
cd core && .venv/bin/python -m pytest -q
cd core && .venv/bin/python scripts/verify_live.py
cd core && .venv/bin/python scripts/validate_fixtures.py
```

**Human does.** Get the Hindi review done today (send the HINDI_REVIEW.md table by chat; listen to the voice sample after P2.3 produces it). Write the reviewer's name in the file. If you cannot get a reviewer, the writeup must say the Hindi text is machine-drafted and awaiting native review.

**Pitfalls.** Do not "improve" Hindi wording yourself. Do not change any threshold. Do not alter validators to make a failing plan pass.

---

### P2.3: the escalation workflow, Telegram, Polly voice (P2, round R3)

**Goal.** Press "run" (API call) and the real thing happens: the plan is built, a Hindi voice message and a message with an Acknowledge button reach Telegram, and the system waits. Acknowledge (Telegram button or API) closes the run. If nobody acknowledges before the timeout the backup is notified and the run records the outcome. All state is visible through GET /runs/{run_id}.

**You may edit.** backend/ only.

**Needs.** G1b passed. P2.2 deployed. The Telegram bot token exists (H2 step 7). Two Telegram accounts for supervisor and backup.

**Design (read before coding).**
- Step Functions Standard state machine "escalation": NotifyPrimary (Lambda task with waitForTaskToken, TimeoutSecondsPath $.ack_timeout_seconds); on States.Timeout go to RecordEscalated then NotifyBackup (same task pattern); on States.Timeout go to RecordUnacknowledged. Any other error: RecordFailed. Acknowledgement happens OUTSIDE the state machine: the ack code sets the run to ACKNOWLEDGED in DynamoDB (conditional write) and then calls SendTaskSuccess with the token of the active stage. The state machine then ends.
- The Notify Lambda is invoked with the task token. It stores the token in DynamoDB (TOKEN#stage item), sends messages, and returns WITHOUT calling SendTaskSuccess (the workflow stays waiting). The only exception: if the run is already final (acknowledged during a race), it calls SendTaskSuccess immediately so the workflow does not hang.
- Race safety: all status changes use conditional updates (ConditionExpression on status). Record functions never overwrite a final status.

**Steps.**
1. Pull and run prepare.py. Add moto-based tests as you go (backend tests must stay green).
2. backend/src/common/telegram.py (standard library urllib only): call(method, payload) POSTs JSON to https://api.telegram.org/bot{TOKEN}/{method}, timeout 10 s, returns the parsed JSON, raises TelegramError with the description on ok false. Functions: send_message(chat_id, text, reply_markup=None), send_audio(chat_id, audio_url, caption=None, title=None), answer_callback(callback_query_id, text), set_webhook(url, secret) and get_webhook_info.
   NEVER log the token, the URL with the token, request headers or full responses. Log only method name and error description. Tests monkeypatch the HTTP call.
3. backend/src/common/voice.py: synthesize(text, run_id, lang) -> presigned HTTPS URL. Steps: polly client in env POLLY_REGION; synthesize_speech(Text=text, OutputFormat="mp3", VoiceId=env POLLY_VOICE_ID, Engine=env POLLY_ENGINE, LanguageCode "hi-IN" for hi or "en-IN" for en); write the bytes to S3 key voice/{run_id}_{lang}.mp3 in VOICE_BUCKET (ContentType audio/mpeg); presign get_object for 3600 seconds with a boto3 client created with botocore Config(signature_version="s3v4") and the bucket's region. Return the URL.
   If POLLY_REGION differs from the bucket region the S3 client uses the stack region (AWS_REGION): they are separate clients.
4. backend/src/common/runs.py: create_run, get_run, add_event(table, run_id, step, detail), set_status with conditional update, close_run_ack(table, run_id, by, via) returning (ok, run) where ok False means it was already final. Run item keys per contract 3.10, run object per 3.5 (events list appended with list_append; ts in UTC with Z).
   Use "ack_deadline" = now + ack_timeout when a stage starts. LATEST pointer item written on run creation.
5. api.py additions:
   - POST /sites/{site_id}/run (demo key): site must exist (not_found); optional ack_timeout_seconds 30..3600 (else the site's own value); if the latest run for the site is STARTED, WAITING_ACK or ESCALATED and was created less than 1 hour ago return conflict 409 "a run is already active"; build the plan (cache first, as in the plan route; WeatherError gives upstream_error); create the run (STARTED) with event plan_built (detail "peak WBGT 32.0 at 14:00"); start the state machine execution (stepfunctions start_execution, name = run_id, input {"run_id","site_id","ack_timeout_seconds"}); return 202 {"run_id","status":"STARTED"}. If start_execution fails mark the run FAILED with an error event and return internal.
   - GET /sites/{site_id}/runs/latest, GET /runs/{run_id} (404 when missing).
   - POST /ack (demo key) body {"run_id","by"}: close_run_ack; if already final return conflict 409; else send_task_success to the active stage token (ignore TaskTimedOut and InvalidToken errors but add an event "acknowledged" anyway).
   - POST /telegram/webhook: verify header X-Telegram-Bot-Api-Secret-Token with hmac.compare_digest against TELEGRAM_WEBHOOK_SECRET; wrong or missing gives 401 unauthorized; otherwise always 200 {"ok": true} even on internal errors (log them). Handle: (a) callback_query whose data starts with "ack:" and the rest is a run_id: ack it with by = the person's first name, via "telegram", then answer_callback("Acknowledged ✅"); if already closed answer_callback("Already closed"). (b) a message with text "/start": reply "Your chat id is {id}. Give it to the project admin." (c) anything else: ignore.
   The callback_data must be under 64 bytes: "ack:" + run_id is 4 + about 21 characters, fine.
6. backend/src/notify.py handler(event, context): event = {"action": "notify", "stage": "primary"|"backup", "run_id", "site_id", "token"}.
   a. Load run and site. If run is final: send_task_success(token, "{}") and return.
   b. Store the token item TOKEN#{stage} with ttl now + 7200.
   c. Chat id = site supervisor (primary) or backup. If missing: add event telegram_failed ("no chat id configured for primary"), then send_task_failure(token, error "NoChatId", cause text) so the workflow records FAILED for primary... Exception: for the BACKUP stage with no chat id, skip notification and call send_task_failure with error "NoBackup" (the state machine maps this to RecordUnacknowledged; see the ASL).
   d. Build the plan from the cached plan item (or rebuild). Compose text: the language message (site language) plus a line "Run {run_id}" and, if DASHBOARD_URL is set, a link line to DASHBOARD_URL + "/#/run/" + run_id, and the disclaimer on its own line.
   e. Voice: on the primary stage synthesize once and store voice_url on the run (event voice_ready); on the backup stage reuse run.voice_url (re-presign if older than 50 minutes). If Polly fails: event telegram_failed? No: add event "error" with the Polly error text (class name only) and continue without voice.
   f. Send the text with an inline keyboard (one button, text "✅ Acknowledge / मिल गया", callback_data "ack:{run_id}"), then send_audio with the voice URL. If the text fails: event telegram_failed and send_task_failure (the workflow records FAILED). If only audio fails: event telegram_failed with detail "voice not delivered" and continue.
   g. Events: telegram_sent, notified_primary (or notified_backup). Set status WAITING_ACK for primary (ESCALATED is set by Record when moving to the backup). Set ack_deadline and active_stage.
7. backend/src/record.py handler(event): event {"action": "escalate"|"unacknowledge"|"fail", "run_id", "error": optional}. escalate: conditional update status WAITING_ACK -> ESCALATED, active_stage backup, event escalated ("primary did not acknowledge in N seconds"); unacknowledge: status ESCALATED or WAITING_ACK -> UNACKNOWLEDGED, active_stage null, event unacknowledged; fail: any non-final status -> FAILED, active_stage null, event error with a short error name. Conditional failures are not errors (the run was already closed): return {"skipped": true}.
8. backend/statemachine/escalation.asl.json (Amazon States Language) with these states (names exact):
   - NotifyPrimary: Type Task, Resource arn:aws:states:::lambda:invoke.waitForTaskToken, Parameters {"FunctionName": "${NotifyFunctionArn}", "Payload": {"action": "notify", "stage": "primary", "run_id.$": "$.run_id", "site_id.$": "$.site_id", "token.$": "$$.Task.Token"}}, TimeoutSecondsPath "$.ack_timeout_seconds", ResultPath "$.primary_result", Catch: [{"ErrorEquals": ["States.Timeout"], "ResultPath": "$.primary_timeout", "Next": "RecordEscalated"}, {"ErrorEquals": ["States.ALL"], "ResultPath": "$.error", "Next": "RecordFailed"}], Next: Done.
   - RecordEscalated: Task, Resource arn:aws:states:::lambda:invoke, Parameters {"FunctionName": "${RecordFunctionArn}", "Payload": {"action": "escalate", "run_id.$": "$.run_id"}}, ResultPath null, Next NotifyBackup.
   - NotifyBackup: like NotifyPrimary with stage backup; Catch Timeout goes to RecordUnacknowledged; Catch ErrorEquals ["NoBackup"] goes to RecordUnacknowledged; Catch States.ALL goes to RecordFailed; Next Done.
   - RecordUnacknowledged: Lambda invoke action unacknowledge; Next Done. RecordFailed: Lambda invoke action fail with "error.$": "$.error.Error" (use States.Format or pass "$.error"); Next Done. Done: Type Succeed.
   Remember: Catch rules are evaluated in order; put the specific ones first.
9. template.yaml additions: NotifyFunction (Handler notify.handler, Timeout 60, policies: DynamoDBCrudPolicy, S3CrudPolicy for VoiceBucket, inline polly:SynthesizeSpeech on Resource "*", inline states:SendTaskSuccess and states:SendTaskFailure on "*"), RecordFunction (DynamoDBCrudPolicy), SchedulerFunction (see step 10), EscalationStateMachine (AWS::Serverless::StateMachine, Type STANDARD, DefinitionUri statemachine/escalation.asl.json, DefinitionSubstitutions NotifyFunctionArn and RecordFunctionArn, Policies: LambdaInvokePolicy for both functions; add CloudWatch Logs logging optional).
   ApiFunction: set STATE_MACHINE_ARN to !Ref EscalationStateMachine, add policies states:StartExecution (on that state machine), states:SendTaskSuccess ("*"), DynamoDB, plus read of the S3 bucket is not needed. Pass all env variables (3.11) to Notify (TELEGRAM_BOT_TOKEN, VOICE_BUCKET, POLLY_*, DASHBOARD_URL, TABLE_NAME, WEATHER_CACHE_SECONDS) and to Api (TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET for the webhook and answerCallback).
10. scheduler.py + schedule: SchedulerFunction starts a run for every site that has a supervisor telegram_chat_id (calls the same code as POST /sites/{id}/run, shared function in common/runs_start.py; skip sites with an active run). In template.yaml an Events entry of Type ScheduleV2 with ScheduleExpression "cron(30 0 * * ? *)" (00:30 UTC = 06:00 India) and State from a parameter ScheduleState (allowed values ENABLED, DISABLED, Default DISABLED). The schedule is OFF until the human turns it on for the demo.
11. backend/scripts/set_webhook.py: reads TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET from environment variables, API URL from --api; calls setWebhook with url API/telegram/webhook, secret_token, allowed_updates ["message","callback_query"]; then prints getWebhookInfo (url, pending_update_count, last_error_message). Never prints the token or the secret.
12. Tests (moto + fakes): notify primary happy path (telegram and polly faked) creates events and token item; ack closes run; double ack returns 409; ack after timeout race (status ESCALATED, active_stage backup) closes via backup token; record escalate is skipped when the run is already ACKNOWLEDGED; webhook rejects wrong secret, accepts callback and /start; run start conflict when active; ASL JSON parses and every Next/Catch target exists (write a small graph check); no tracked file contains the strings of the token format (a test greps backend/ for the regex \d{8,10}:[A-Za-z0-9_-]{35}).
13. Deploy (ask the human first). Human sets parameters in their own terminal: sam deploy --parameter-overrides "DemoKey=... TelegramBotToken=... TelegramWebhookSecret=... ScheduleState=DISABLED" (the agent does not see them; the human may also edit the untracked samconfig.toml). Then:
    - Human: in Telegram send /start to the bot from the supervisor account and from the backup account after set_webhook ran; the bot replies with each chat id.
    - Human or agent: python backend/scripts/seed_sites.py set-chat chn-01 supervisor <id> and set-chat chn-01 backup <id>. Set ack_timeout_seconds small for testing (POST /sites/chn-01/run with {"ack_timeout_seconds": 60}).
    - **Test A (acknowledge):** start a run, the supervisor phone receives text, audio and the button. Press the button. GET /runs/{run_id} shows ACKNOWLEDGED, acked_via telegram, events in order. Step Functions console shows the execution Succeeded.
    - **Test B (escalate):** start a run, do nothing. After 60 s the backup phone receives the message; status ESCALATED then (after another 60 s without action) UNACKNOWLEDGED. Run again and acknowledge on the backup phone: ACKNOWLEDGED.
    - **Test C (web ack):** start a run and call POST /ack with the demo key: ACKNOWLEDGED, acked_via web.
    - **Test D (race):** start a run, press the button twice quickly: second answer "Already closed".
    - Listen to the Hindi voice message: write down in DEPLOY_NOTES.md how it sounds (clear? speed? numbers read right?). If it is unusable, tell the human; do not claim it works.
14. Commit "P2.3: ..." and push. Tell the team: the API URL is unchanged; new endpoints are live.

**Definition of done.** Tests A to D pass on real Telegram with real screenshots taken by the human (execution graph from the Step Functions console for A and B); no secret in git; schedule is DISABLED.

**Verify (show the output).**
```
cd backend && .venv/bin/python -m pytest -q
sam validate --lint
python backend/scripts/set_webhook.py --api "$API_URL"
curl -s -X POST "$API_URL/sites/chn-01/run" -H "x-demo-key: $DEMO_KEY" -H "content-type: application/json" -d '{"ack_timeout_seconds": 60}'
curl -s "$API_URL/sites/chn-01/runs/latest"
git grep -n -i -E "[0-9]{8,10}:[A-Za-z0-9_-]{30,}" -- . || echo "no token-like strings"
```

**Human does.** Do tests A to D with your phones. Keep two screenshots of the Step Functions graph (green path for A, orange path with escalation for B). They are in the video.

**Pitfalls.** waitForTaskToken: the Lambda must NOT return the result itself to complete the step (the workflow completes only on SendTaskSuccess/Failure or timeout). If the Lambda raises an exception, Step Functions fails the task immediately (that is intended for hard failures). Task tokens are long (over 1000 characters): DynamoDB item limit is fine.
The Telegram secret_token characters must be A-Z a-z 0-9 _ - and 1 to 256 long. Telegram sends the webhook only to HTTPS URLs with a valid certificate: the API Gateway URL qualifies. When a webhook is set, getUpdates does not work: that is expected.
If sendAudio with a URL is rejected, check that the presigned URL is HTTPS and that its signature version is v4. A presigned URL created with temporary Lambda role credentials stops working when those credentials expire (the role session lasts hours; a 3600 s expiry is safe).
State machine input must include "ack_timeout_seconds" as a number, otherwise TimeoutSecondsPath fails the execution.

---

### P3.3: run timeline, acknowledgement, voice player, finished pages (P3, round R3)

**Goal.** The dashboard shows the whole workflow live: start a run, watch the timeline (plan built, voice ready, Telegram sent, waiting, escalated, acknowledged), play the voice message, acknowledge from the web.

**You may edit.** frontend/ only.

**Needs.** P3.2 done. For the live check P2.3 must be deployed (code against the contract and mock first; mock runs come from the four run fixtures).

**Steps.**
1. Pull. Mock mode: startRun returns a run that steps through run_waiting, then run_escalated, then run_unacknowledged on a timer of 5 s each (so the UI can be developed without AWS); ack() returns run_acknowledged. The badge "DEMO DATA (fixture)" must show for these. Live mode uses the API for everything.
2. Site page additions: a "Run now" panel. A button "Send today's plan now" opens a confirmation dialog (native dialog element or accessible custom one): "This sends a real Telegram message to {supervisor name}." with timeout choice (30 s, 60 s, 5 min, site default) and Confirm/Cancel. On confirm POST run, then navigate to #/run/{run_id}. A 409 shows the server message ("a run is already active") with a link to the active run (GET latest).
3. Run page (#/run/{run_id}): polls GET /runs/{run_id} every 2 s while status is not final (STARTED, WAITING_ACK, ESCALATED), stops on final, stops when the tab is hidden and resumes on visible, backs off to 5 s after three consecutive errors, shows "connection lost, retrying" without clearing the last good data.
   Show: a big status chip with text (WAITING FOR ACKNOWLEDGEMENT, ESCALATED TO BACKUP, ACKNOWLEDGED, NOT ACKNOWLEDGED, FAILED, STARTED); a stage tracker with three steps "Plan built", "Supervisor notified", "Backup notified" and which one is current; a live countdown to ack_deadline (mm:ss, updated every second, shows "timed out" at zero); the event timeline in plain English (map the step codes to sentences: plan_built "Heat plan built", voice_ready "Hindi voice message created", telegram_sent "Message sent on Telegram", telegram_failed "Telegram delivery failed", notified_primary "Supervisor notified", escalated "No answer: escalating to backup", notified_backup "Backup notified", acknowledged "Acknowledged", unacknowledged "Nobody acknowledged", error "Error") with times in India time (HH:mm:ss) and the detail text; the plan summary with a link to the site page; the voice player if voice_url exists (audio element with controls and a visible label "Hindi voice message", fallback link).
   aria-live="polite" region announces status changes.
4. A "Acknowledge (web)" button on the run page, visible while the status is WAITING_ACK or ESCALATED: asks for a name (optional) and POSTs /ack. Show 409 as "Already closed" with the current status. After success, refresh the run immediately.
5. Run history: on the site page a "Last run" card from GET /sites/{id}/runs/latest (404 means "No runs yet").
6. Backtest page: remove the fixture badge logic dependence: it shows the badge only when _fixture is true (P1.2 made the file real: run npm run sync-fixtures). Use the real numbers; the headline sentence is generated from the file, never hard-coded.
7. Method page: add the real limitations list from docs/METHOD.md (copy text, do not invent numbers), and the line "Hindi text review: <status from docs/HINDI_REVIEW.md>" written by hand after P1.3 (if pending say "pending native review").
8. Tests: the polling controller as a pure state machine (fake timers: stops on final, backoff, pause on hidden), event-step to sentence mapping covers every step enum, countdown formatting.
9. Live check (when P2.3 is up): do Test A and Test B from the P2.3 card from the web UI with the phones next to you; verify the timeline order and countdown match the phones.
10. Commit "P3.3: ..." and push.

**Definition of done.** Mock flow works offline; live flow shows every status transition; no memory leaks (polling stops on route change; check by navigating away and watching the network tab); tests and build pass.

**Verify (show the output).**
```
cd frontend && npm run test && npm run build
```
Describe what appeared on screen during mock mode (statuses in order).

**Human does.** Record a rough screen capture of Test B (escalation) now; it is your insurance clip if the live demo fails during final recording.

**Pitfalls.** setInterval inside React effects must be cleaned up. Do not poll after unmount. Countdown must derive from ack_deadline (server time), not from the click time. The presigned voice URL expires after 1 hour: if the audio fails to load, show "voice link expired (links last 1 hour)".
Never display tokens, chat ids or the demo key.

---
### P1.4: final numbers and core freeze (P1, round R4)

**Goal.** One file with every number the team will say in public, each traceable to a command, and a frozen, tagged core.

**You may edit.** core/, shared/fixtures/, docs/METHOD.md, docs/NUMBERS.md.

**Needs.** P1.3 done. Backend and frontend feature-complete (R3 gate G2 passed).

**Steps.**
1. Pull. Run all core tests and verify_live.py. Re-run run_backtest.py (it must reproduce the committed numbers from the cached raw data; if the numbers changed, find out why before continuing).
2. docs/NUMBERS.md: a table with columns Claim, Value, How to reproduce (exact command), Source file. Include: dangerous hours per city and total; missed percent at 37, 40 and 42 C (total and per city); false alarm hours at 40 C; the example hour (time, air temp, humidity, WBGT, level); sensitivity results (heavy, unacclimatized); number of sites; number of thresholds; number of tests (run pytest and count); number of AWS services used (count them from template.yaml: list them). A second table "Claims we must NOT make": clinically validated, prevents heat illness, certified, real-time sensor measurement, "saves lives", any accuracy percentage.
3. Check docs/METHOD.md and README.md (read only; tell the human any sentence that disagrees with NUMBERS.md).
4. Final polish of core: remove dead code, make sure every public function has a one-line docstring, remove prints from library code (keep them in scripts). Update `__version__` to 1.0.0 in core/shramshield_core/__init__.py and pyproject.toml. Tests still pass.
5. Commit "P1.4: ..." and push. Tell the human to create the tag after G3: git tag -a v1.0 -m "hackathon submission" and git push origin v1.0.

**Definition of done.** NUMBERS.md exists and every value was produced by a command that you ran in this task; tests pass; version 1.0.0.

**Verify (show the output).**
```
cd core && .venv/bin/python -m pytest -q
cd core && .venv/bin/python scripts/run_backtest.py
cd core && .venv/bin/python scripts/verify_live.py
git diff --stat HEAD~1
```

**Human does.** Read NUMBERS.md aloud with the team. Anything said in the video or writeup must be in this file. If a sentence in the writeup has a number that is not here, remove the number.

**Pitfalls.** Do not round in a favourable direction. Do not change the backtest definitions now.

---

### P2.4: hardening, hosting, evidence, final deploy (P2, round R4)

**Goal.** The dashboard is hosted on AWS and talks to the API; costs and abuse are controlled; the AWS evidence the video needs is collected; a clean final deploy and three full rehearsals pass.

**You may edit.** backend/, docs/AWS_EVIDENCE.md.

**Needs.** P3.3 pushed (a working dashboard build). G2 passed.

**Steps.**
1. Pull. Run all backend tests. Review template.yaml for least privilege: replace broad managed policies where practical (S3CrudPolicy is fine for the voice bucket), keep states:SendTask* on "*" (the API requires it). Report anything left broad.
2. Log retention: backend/scripts/set_log_retention.py sets 14 days on every log group of the stack functions and the state machine (aws logs put-retention-policy via boto3). Run it and show the result.
3. Cost guardrails: confirm the Budget alarm from H2 exists (aws budgets describe-budgets --account-id <id>); confirm HttpApi throttling is in place; confirm the scheduled run is DISABLED unless the human wants it; add a CloudWatch alarm on the state machine metric ExecutionsFailed greater than 0 (optional: no email needed).
4. Frontend hosting (AWS Amplify Hosting, manual deployment, no Git connection needed):
   - backend/scripts/deploy_frontend.py --api URL --key KEY (key from the environment variable DEMO_KEY, never printed): runs in frontend/: npm ci, then npm run build with VITE_API_BASE, VITE_DEMO_KEY and VITE_USE_MOCK=false set for that process only; zips frontend/dist (zip root must be the contents of dist, with index.html at the top level); then the Amplify manual flow with the AWS CLI via boto3 (amplify client): create_app (once, name shramshield-dashboard, store the appId in an untracked file backend/.amplify_app), create_branch (once, branchName main, stage PRODUCTION), create_deployment(appId, branchName) which returns jobId and zipUploadUrl, HTTP PUT the zip bytes to zipUploadUrl (Content-Type application/zip), start_deployment(appId, branchName, jobId), poll get_job until SUCCEED or FAILED (timeout 10 minutes).
   - Print the dashboard URL: https://main.<appId>.amplifyapp.com.
   - If the Amplify flow fails twice for the same reason: fallback = a second S3 bucket with static website hosting (public read only for the site bucket, clearly named), upload dist, and use the http website URL. Say which path was used; the fallback is acceptable (the dashboard calls an https API, which browsers allow from an http page).
   - After the dashboard URL is known: redeploy the stack with DashboardUrl set, so Telegram messages link to the run page.
5. Re-check CORS: the dashboard origin calls the API; browser console must show no CORS error. If you restricted AllowOrigins earlier, add the Amplify origin; the default "*" is acceptable for this demo and should be mentioned in the writeup as a known simplification (demo key plus throttling).
6. docs/AWS_EVIDENCE.md: for the AWS part of the video and for judges. Contains: the list of AWS services used and the role of each in one line (Lambda, API Gateway HTTP API, DynamoDB, Step Functions, Polly, S3, EventBridge Scheduler, Amplify Hosting, CloudFormation/SAM, CloudWatch Logs, IAM, Budgets); the region; output of aws cloudformation describe-stack-resources --stack-name shramshield with account ids removed; a table of screenshots to capture (file names under docs/img/aws-*.png: stack resources, Step Functions graph escalation path, Step Functions graph acknowledged path, DynamoDB items for a run, Lambda list, S3 voice objects, Polly voice, Amplify app, Budgets); and the exact click path for each (where to click in the console). The screenshots themselves are taken by the human (the agent cannot).
7. Three full rehearsals (Test A, B, C from P2.3 plus the dashboard) with a stopwatch: record in DEPLOY_NOTES.md date, time, result, duration. All three must pass. If one fails, find the cause before finishing.
8. Clean final deploy from a fresh clone: clone the repo into a new folder, run prepare, build_layer, sam build, sam deploy (to the SAME stack), then smoke.py. This proves the repository alone is enough to deploy. Show the output.
9. Secrets audit: git log -p --all | grep for token-like strings, AKIA, the demo key value (the human provides the value through an environment variable; the agent only checks that it is not found), and any chat id in tracked files. Report the result. If anything is found STOP and tell the human (rotate the secret).
10. Write the "teardown" section in DEPLOY_NOTES.md: how to delete (sam delete, delete the Amplify app, empty and delete the website bucket if used) and how to revoke keys; say "do this AFTER the results are announced".
11. Commit "P2.4: ..." and push.

**Definition of done.** Dashboard reachable on a public URL; three rehearsals pass; clean redeploy works; audit clean; AWS_EVIDENCE.md complete except the screenshots.

**Verify (show the output).**
```
cd backend && .venv/bin/python -m pytest -q
python backend/scripts/smoke.py --api "$API_URL"
curl -sI "$DASHBOARD_URL" | head -5
git grep -n -i -E "AKIA[0-9A-Z]{16}|[0-9]{8,10}:[A-Za-z0-9_-]{30,}" || echo clean
```

**Human does.** Take the AWS console screenshots listed in AWS_EVIDENCE.md while a rehearsal run is in progress (the Step Functions graph needs a live or recent execution). Open the dashboard URL on your phone. Do NOT delete anything until the results are out.

**Pitfalls.** The zip for Amplify must have index.html at the ROOT of the archive. Amplify manual deployments need the app's platform to be WEB; the default is fine. The first create_app can take several seconds. A site name containing spaces is fine but the app name should not be changed after creation. Never print the API key in logs. Keep the stack alive through judging (the demo link may be opened by judges).

---

### P3.4: polish, README, writeup and video kit (P3, round R4)

**Goal.** Everything a judge sees outside the running app: README, architecture picture, submission writeup, video script and shot list, screenshots, accessibility pass.

**You may edit.** frontend/, README.md, docs/ARCHITECTURE.md, docs/SUBMISSION.md, docs/img/, docs/VIDEO_SCRIPT.md.

**Needs.** P3.3 done, P1.4 numbers (docs/NUMBERS.md) and P2.4 AWS evidence available. If they are not yet pushed, write the structure and mark each number as "from NUMBERS.md: fill in" and finish after pulling them. Never invent a number.

**Steps.**
1. Pull. Dashboard polish: responsive check at 360, 768 and 1280 px widths, dark text contrast, focus order, skip link to main, page titles per route (document.title), favicon (a simple generated SVG), meta description, loading states without layout jump. Run an accessibility pass by hand (keyboard only through all pages) and list what you checked in docs/SUBMISSION.md under "Accessibility".
2. README.md (public front door): title and one-line pitch; "The problem" (3 sentences, no invented statistics); "What it does" (5 bullets matching section 0.1); a screenshot; "How it works" with the architecture image or the Mermaid diagram from ARCHITECTURE.md; "Try it" (dashboard URL, API URL, how a judge can see a run: the video, or Test steps; the demo key is NOT in the README: say a read-only tour is available without a key, and runs need the key which is shared on request); "Run it yourself" (core tests, deploy from DEPLOY_NOTES.md in 6 lines, frontend dev); "AWS services" table; "Method and honesty" with link to docs/METHOD.md and the sentence "Screening guidance estimated from weather-model data. It is not a measurement or medical advice."; "Data and credits": Open-Meteo.com (weather data, free non-commercial use), Copernicus Climate Change Service information via the Open-Meteo archive, thermofeel by ECMWF (Apache 2.0), ACGIH screening values as summarised by CCOHS, OHCOW hydration prompt; "AI tools used": list every AI tool the team used (ask the human; expected: Google Antigravity agents for code, Claude for the planning documents); "Team": the three names and roles; "Licence": MIT.
3. docs/ARCHITECTURE.md: a Mermaid flowchart of the real architecture (copy the shape of section 0.4; every box must exist in template.yaml: check it), plus the sequence of one run in 8 numbered lines, plus "Design decisions" (why WBGT; why deterministic rules instead of an LLM for safety numbers; why Step Functions for the wait and escalate; why a web acknowledgement exists next to Telegram; why Polly Hindi) and "Known limitations".
4. docs/SUBMISSION.md: sections: Title and tagline; Track (Heat and Water); Summary (about 120 words); Problem; Solution; How it works; AWS usage (point to AWS_EVIDENCE.md); What is novel (honest: combines WBGT physics, published limits, automatic escalation with proof of acknowledgement, and a replay that quantifies what air-temperature alerts miss); Results (only numbers from NUMBERS.md); Limitations and honesty; What we would do next (3 items, realistic: validate with a pilot site, calibrate with on-site WBGT meters, more languages); AI tools used; Links (repo, video, dashboard, blog); Accessibility; Checklist (copy of section 7 of the plan with boxes for the human to tick).
5. docs/VIDEO_SCRIPT.md: adapt section 7.3 of docs/BUILD_PLAN.md into a final script with the real numbers; shot list with the exact screen for each line; a recording checklist (1080p, cursor visible, close notifications, mic test, browser zoom 110 percent, phone mirrored or filmed for the Telegram part, the AWS console shown for at least 20 seconds).
6. Screenshots into docs/img/ (the human captures; you create the folder, a docs/img/README.md listing what to capture and the file names, and use the names in README and SUBMISSION). Use relative image links.
7. AWS Builder Center blog draft: docs/BLOG_DRAFT.md (about 600 words: problem, build with the AWS services, one lesson learned for each of Step Functions callbacks, Polly Hindi voice, Lambda layer for scientific Python; link to repo). The human publishes it.
8. Final build check: npm run test, npm run build with live variables, and check that the production bundle does not contain the words "TELEGRAM", "AKIA" or any token-like string (grep in dist).
9. Commit "P3.4: ..." and push.

**Definition of done.** README, ARCHITECTURE, SUBMISSION, VIDEO_SCRIPT, BLOG_DRAFT exist and contain no invented number; every number matches NUMBERS.md; links are placeholders marked "TODO-human" ONLY where the URL does not exist yet (video, blog); the list of those placeholders is printed at the end.

**Verify (show the output).**
```
cd frontend && npm run test && npm run build
grep -rn "TODO-human" README.md docs/ | cat
grep -c "" README.md docs/SUBMISSION.md docs/VIDEO_SCRIPT.md
```

**Human does.** Record the video (section 7.3), upload to YouTube as unlisted or public per the event rule, publish the blog on Builder Center, fill the TODO-human links, tick the checklist.

**Pitfalls.** No sentence may say "prevents", "saves lives", "clinically validated" or "AI-powered" for the safety numbers (the numbers are physics plus published limits; AI is only the coding assistant unless P-team added an LLM feature). Do not claim Hindi was reviewed unless HINDI_REVIEW.md shows a reviewer name.

---

## 5. Gates (quick checks between rounds)

Run these on a clean checkout after everyone pushed ("git pull" first). A gate fails if any line fails. Fix the owner's part before the next round.

**G1 (end of R1).**
```
cd core && .venv/bin/python -m pytest -q && .venv/bin/python scripts/make_plan.py chn-01
cd frontend && npm run test && npm run build
curl -s "$API_URL/health"                         (thermofeel 2.3.0)
```
Then P2 runs prepare.py. If core tests fail, R2 does not start for P2 and P3.

**G1b (middle of R2).**
```
python backend/scripts/smoke.py --api "$API_URL"
```
and P3 opens the dashboard in live mode and sees the Chennai plan.

**G2 (end of R3: end to end).** The full flow: dashboard "Send today's plan now" with timeout 60 s, Telegram message with voice arrives on the supervisor phone, press Acknowledge, the dashboard timeline shows ACKNOWLEDGED. Then again without pressing: backup phone receives the message, dashboard shows ESCALATED. Everyone writes "G2 pass" in the team chat with a time. Take the screen recording of this as your insurance footage.

**G3 (end of R4: freeze).**
```
git status --short            (clean)
git log --oneline | head -40  (commits by all three, dates inside the event)
cd core && .venv/bin/python -m pytest -q
cd backend && .venv/bin/python -m pytest -q
cd frontend && npm run test && npm run build
python backend/scripts/smoke.py --api "$API_URL"
```
Then freeze: no feature work. Only fixes for submission blockers, announced in the chat before pushing. Create the tag v1.0.

---

## 6. If something goes wrong (troubleshooting)

| Symptom | Likely cause | What to do |
|---|---|---|
| Agent edits a file it does not own | Card read incorrectly | Stop, git restore the file, paste the card again, remind "edit only the folders the card lists" |
| Rebase conflict | Two people edited the same file | Stop. Owner of the file resolves it; the other person does git rebase --abort and waits |
| Agent asks something the card answers | It did not read the card | Tell it "read card X in docs/BUILD_PLAN.md section 4" |
| Open-Meteo 403 or timeout from the shell | Network filter or rate limit | Try another network (phone hotspot); the code retries twice; do not scrape other sources |
| thermofeel import fails in Lambda (/health thermofeel null) | Layer built for the wrong platform or folder name | Rebuild with build_layer.py; the folder inside the layer must be python/ |
| Lambda: "Unable to import module" | prepare.py not run, or the package is not under backend/src | Run prepare.py, rebuild, redeploy |
| DynamoDB TypeError float | Missing Decimal conversion | Use db.to_ddb |
| Telegram: webhook gets 401 | Secret mismatch | Re-run set_webhook.py with the same secret that is in the stack parameter |
| Telegram: nothing arrives | Chat id not set, or the person never pressed Start | Send /start to the bot from that account; set-chat again |
| Telegram audio missing | Presigned URL not accepted | Check URL is https, region and s3v4 signing; the text message still works |
| Polly error in ap-south-1 | Voice not available in region | Use POLLY_REGION us-east-1 (stack parameter) |
| Workflow never ends | Notify Lambda returned without a token path, or the ack did not call SendTaskSuccess | Check the execution in the console; confirm the TOKEN item exists; check IAM states:SendTaskSuccess |
| Ack works but workflow later says escalated | Race | Check Record handler uses conditional update and skips final runs |
| Amplify deploy stuck | Zip root wrong | Re-zip the contents of dist (index.html at the top) |
| CORS error in browser | Gateway CORS missing header | P2 adds the header to HttpApi CorsConfiguration and redeploys |
| Costs rising | Loop or traffic | Check Budgets email; disable the schedule; check the API throttle; delete the state machine executions if a loop exists |
| Window closes, hackathon clock unclear | Deadline not announced | Check the event page and Discord, submit early |

---

## 7. Final steps (human, with P3 leading)

### 7.1 Freeze and rehearse (Saturday)

1. G3 passed and tagged. 2. Everyone stops feature work. 3. Do one full rehearsal of the video flow from a clean browser profile.

### 7.2 Submission checklist (tick all before pressing submit)

- [ ] Public GitHub repository, MIT licence, README complete, no secrets (P2 audit was clean)
- [ ] Commit history by all three people, dates inside the event, no force pushes
- [ ] Video: 3 minutes or less, on YouTube, shows the AWS console and services running, shows the Telegram flow, shows the dashboard, uses only NUMBERS.md numbers
- [ ] Writeup (docs/SUBMISSION.md) pasted or linked; lists AI tools used; states limitations
- [ ] Builder Center blog published (if the event asks for it; check the rules page again)
- [ ] Dashboard and API are live and will stay live until results
- [ ] AWS_EVIDENCE.md screenshots added
- [ ] Hindi review status stated truthfully
- [ ] Each teammate checked the submission form fields and the track selection (Heat and Water)
- [ ] Submitted at least 3 hours before any deadline (the deadline hour was not known when this plan was written; re-read the event page)
- [ ] After submitting: do not push breaking changes to main; keep the stack running

### 7.3 Three-minute video script (about 420 spoken words; times are targets)

| Time | Screen | Say (adapt, use only NUMBERS.md figures) |
|---|---|---|
| 0:00 to 0:20 | A construction site photo or the dashboard Sites page | "Outdoor workers in India work through heat that air-temperature alerts do not describe well. Heat stress depends on humidity, sun and wind together. We built ShramShield: it turns weather data into a work and rest plan for each site, tells the supervisor in Hindi, and makes sure someone acknowledges it." |
| 0:20 to 0:50 | Site page, heat strip, click the peak hour | "This is a Chennai site. Each hour has a WBGT score, computed with the Liljegren model from ECMWF's thermofeel library. The level comes from published ACGIH screening limits. Here at 2 PM the level is [level]: at most [x] minutes of work per hour." |
| 0:50 to 1:20 | Backtest page | "We replayed April to June 2024 for four cities. [N] work hours were RED or STOP. An air-temperature alert at 40 degrees would have missed [M], that is [P] percent. This compares two methods on the same data; it is not a medical validation." |
| 1:20 to 2:10 | Click "Send today's plan now", then the phone (Telegram) and the run page | "Now the live part. We send today's plan. On the supervisor's phone arrives a Hindi voice message from Amazon Polly and a message with an Acknowledge button. Step Functions is waiting. If nobody answers in the time limit it escalates to the backup" (show the phone, press acknowledge, show status ACKNOWLEDGED) "and everything is recorded." |
| 2:10 to 2:40 | AWS console: Step Functions graph (escalation path), DynamoDB item, Lambda list, stack resources | "On AWS: API Gateway and Lambda serve the API, DynamoDB stores sites and runs, Step Functions runs the wait-and-escalate workflow with a task token, Polly speaks Hindi, S3 holds the audio, EventBridge schedules the morning run, Amplify hosts the dashboard, all deployed with SAM." |
| 2:40 to 3:00 | Method page, then the repo | "The safety numbers are deterministic physics and published limits, not an AI guess. We state what it is not: not a measurement, not medical advice. Open source, built in this hackathon. Thank you." |

Recording notes: record the live part twice and keep the best take; keep the AWS console segment at least 20 seconds; do not show secrets (Telegram token, demo key, account id: blur or avoid the account menu).

### 7.4 Writeup structure

Use docs/SUBMISSION.md as the base. Keep sentences short. The first paragraph must tell a judge what it is, who uses it, and why it is different, without jargon. Put the numbers in a small table. Put limitations in their own section: honesty is a strength with technical judges.

---

## 8. Risk register

| Risk | Impact | Mitigation | Owner |
|---|---|---|---|
| Open-Meteo blocked or down at demo time | No live plan | Cached plan (20 min), insurance recording, archive replay in the backtest page | P1, P3 |
| Telegram delivery fails on stage | Live demo breaks | Web acknowledge button; recorded footage from G2; test phone numbers earlier | P2 |
| Polly Hindi unavailable in region | No voice | POLLY_REGION parameter; text message still works | P2 |
| Hindi wording poor | Credibility | Native review before the video; state review status truthfully | P1 |
| Overclaiming | Judges distrust | AGENTS.md rules; NUMBERS.md "claims we must not make" | all |
| Secrets leaked in the public repo | Account abuse | .gitignore, audit in P2.4, rotate if found | P2 |
| Two agents conflict in git | Lost time | Folder ownership, pull --rebase, stop on conflict | all |
| Costs | Surprise bill | Budget alarm, throttling, schedule disabled | P2 |
| Deadline misunderstanding | Disqualification | Re-check the event page and Discord now and on Saturday | all |
| History looks back-dated or code before the clock | Disqualification | Create the repo only after the hackathon clock starts; no history edits | P1 |
| Judges cannot try the app | Lower score | Public dashboard with read-only tour, video shows everything | P3 |

---

## 9. Sources used to prepare this plan

- Environmental Hacks 2026 pages on wemakedevs.org (rules, tracks, judging).
- ECMWF thermofeel 2.3.0 (PyPI and GitHub): calculate_wbgt_liljegren, calculate_wbgt_simple (run locally during preparation).
- Open-Meteo forecast and historical weather API documentation (parameter names).
- CCOHS: Humidex and Heat Stress, ACGIH TLV screening table summary (2026).
- OHCOW: heat response plan guidance (hydration prompt).
- AWS documentation: Step Functions callback with task token, Lambda layers, SAM, Polly Hindi voices, Amplify manual deployment, API Gateway HTTP API.
- Telegram Bot API documentation: sendMessage, sendAudio, setWebhook with secret_token, callback_query.
- Google Antigravity documentation: AGENTS.md rules file.

End of plan.
