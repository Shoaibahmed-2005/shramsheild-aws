# ShramShield — submission

**Tagline:** Heat-safety screening for outdoor worksites in India, with a Hindi voice alert
that someone has to acknowledge.

**Track:** Heat and Water.

## Summary

Outdoor workers in India work through heat that an air-temperature alert describes badly,
because heat stress depends on humidity, sun and wind together. ShramShield computes an hourly
WBGT heat-stress score for each worksite from open weather data, converts it into a work/rest
plan using published ACGIH screening limits, and sends that plan to the site supervisor on
Telegram with a Hindi voice message from Amazon Polly. AWS Step Functions then waits for a
human acknowledgement and escalates to a backup contact if nobody answers, so there is a record
of who was told and when. A replay of April to June 2024 across four cities shows that a plain
40 C thermometer rule would have missed 88.9 percent of the hours our model rates dangerous.

## Problem

Heat is the hazard that does not look like one. The body cools itself by evaporating sweat, and
when humidity is high that stops working — so 31 C in humid Chennai can be more dangerous than
41 C in dry, windy Delhi. Alerts built on air temperature therefore fire in the wrong places
and stay silent in the right ones. On a worksite, the practical gap is not knowledge but
delivery: nobody tells the supervisor, in a language and form they will act on, that the next
four hours need 15 minutes of work and 45 of rest.

## Solution

1. **Score the hazard properly.** For each site and each hour, compute WBGT with the Liljegren
   model from ECMWF's `thermofeel`, using temperature, humidity, pressure, wind and both
   global and direct radiation from Open-Meteo.
2. **Turn it into an instruction.** Classify every hour against the ACGIH screening table into
   GREEN / YELLOW / ORANGE / RED / STOP, which carry 60 / 45 / 30 / 15 / 0 working minutes per
   hour.
3. **Deliver it to a person.** Send the plan on Telegram with a Hindi voice message, plus an
   Acknowledge button.
4. **Make sure it landed.** Step Functions holds a task token and waits. No answer in the time
   limit escalates to the backup contact; everything is recorded as a timeline.

## How it works

See [ARCHITECTURE.md](ARCHITECTURE.md) for the diagram and the eight-step sequence of one run.

## AWS usage

Ten AWS services, eight of them evidenced as deployed with CLI output in
[AWS_EVIDENCE.md](AWS_EVIDENCE.md): Lambda, API Gateway HTTP API, DynamoDB, Step Functions, S3,
IAM, CloudWatch Logs and CloudFormation/SAM, plus Amazon Polly and EventBridge Scheduler which
are declared in the template. The interesting one is Step Functions: the human-in-the-loop wait
uses `waitForTaskToken`, so a 15-minute wait for a supervisor costs no compute and leaves an
execution graph that shows exactly what happened.

## What is novel

Not the WBGT model, and not the limits — both are published and we use them unchanged. What we
put together is:

- **Physics plus published limits, end to end**, from an open weather API to a specific
  instruction ("at most 15 minutes of work this hour"), with no invented thresholds.
- **Escalation with proof of acknowledgement.** The alert is not fire-and-forget. There is a
  task token, a timeout, a backup contact and a recorded timeline of who was told and when.
- **A Hindi voice message**, because the person who must act may not read comfortably.
- **A replay that quantifies the gap.** We measured what a thermometer-based alert would have
  missed on the same historical data, rather than asserting that it misses things.

## Results

All figures from [NUMBERS.md](NUMBERS.md), which records the command that produced each one.
Replay of 1 April to 30 June 2024, four city sites, moderate work, acclimatized, 07:00–18:00:
4004 work hours, every hour with data.

| Measure | Value |
|---|---|
| Work hours rated RED or STOP | 2097 |
| Missed by a 37 C rule | 1507 (71.9%) |
| **Missed by a 40 C rule** | **1864 (88.9%)** |
| Missed by a 42 C rule | 1981 (94.5%) |
| False alarms at 40 C | 59 of 345 alert hours |

Per city, dangerous hours and the share a 40 C rule misses: Chennai 679 (99.1%), Delhi 320
(49.4%), Kolkata 764 (93.7%), Hyderabad 334 (94.9%).

The result holds across work profiles: 89.1% missed for heavy acclimatized work and 89.8% for
moderate unacclimatized work, against 88.9% for the main profile.

**The illustration judges remember:** Delhi had 268 work hours at or above 40 C but only 320
dangerous hours; Chennai had 6 hours reaching 40 C and 679 dangerous hours.

## Limitations and honesty

We would rather state these than be asked about them.

- **"Dangerous hour" means our model rated it RED or STOP.** It does not mean anyone was
  harmed. No health outcome was observed or inferred.
- **The backtest is a method comparison**, on the same historical weather. It is **not**
  validated against heat illness cases.
- It uses **reanalysis data, not archived forecasts**, so real-time forecast error is not
  included. Live plans rest on a forecast and carry its error.
- WBGT is **estimated from a city-point weather model** of roughly 10–25 km, not measured at
  the worksite. Microclimate — bitumen, metal roofs, trenches, heavy clothing — is not
  modelled and can make real exposure considerably worse.
- The ACGIH limits are a **screening tool for an 8-hour day**, not a prescription of work and
  rest periods, and not a medical standard that fits every individual.
- **The Hindi text is machine-drafted and has not been reviewed by a native speaker.** See
  [HINDI_REVIEW.md](HINDI_REVIEW.md), which is marked pending with no reviewer name.
- In 6 of 8736 hours examined, all near-dead-calm (wind below the 0.62 m/s floor the Liljegren
  method applies), WBGT exceeded air temperature by more than 3 C. That is expected for a
  sunlit globe in still air; we report those hours rather than hide them.
- CORS is `*` and the demo key is embedded in the frontend bundle at build time, so it is a
  demo-grade control, not a real secret. Mutating routes are also throttled.

ShramShield is **not** clinically validated, **not** certified, does **not** measure anything
on site, and we make no claim that it prevents illness or saves lives.

## What we would do next

1. **Pilot at one real site** with a willing contractor: run it daily for a month, log whether
   supervisors act on the plan, and find out what actually breaks in the field.
2. **Calibrate against on-site WBGT meters.** Put a real WBGT instrument on the site and
   measure the gap between the city-point model estimate and the worksite, including the
   microclimate effects we currently cannot model.
3. **More languages and lower literacy load.** Tamil, Bengali and Telugu to start, plus a
   purely iconographic work/rest card for workers who read none of them.

## AI tools used

- **Claude (Anthropic)** — the planning documents, and an agent that wrote the core engine, the
  backtest, the method and numbers documentation and parts of the backend hardening.
- TODO-human: add any other AI tools used (for example Google Antigravity agents) and what each
  did.

Every safety number is produced by deterministic code from published physics and a published
limits table. No language model decides a threshold, a level or a work/rest minute. A validator
written independently of the engine re-checks every plan against the contract.

## Accessibility

Checked by hand on the dashboard:

- Keyboard-only pass through every route: sites list, site plan, run timeline, backtest,
  method. All interactive controls reachable and operable with Tab, Shift+Tab and Enter.
- Heat level is **never conveyed by colour alone** — every level shows its text label
  (GREEN / YELLOW / ORANGE / RED / STOP) and its work/rest minutes.
- Status changes on the run page are announced to assistive technology (`role="alert"` on the
  status and failure messages).
- Semantic headings per page and a visible focus indicator.
- Checked at 360 px, 768 px and 1280 px widths.
- TODO-human: confirm the contrast ratios with a checker and note the result here, and re-run
  the keyboard pass on the deployed Amplify URL once it exists.

## Links

- **Repository:** https://github.com/Shoaibahmed-2005/shramsheild-aws
- **Dashboard:** TODO-human (Amplify URL)
- **Video:** TODO-human (YouTube)
- **Blog:** TODO-human (AWS Builder Center)

## Submission checklist

- [ ] Public GitHub repository, MIT licence, README complete, no secrets (the P2 audit over the
      whole history was clean)
- [ ] Commit history by all three people, dates inside the event, no force pushes
- [ ] Video: 3 minutes or less, on YouTube, shows the AWS console and services running, shows
      the Telegram flow, shows the dashboard, uses only NUMBERS.md numbers
- [ ] Writeup (this file) pasted or linked; lists AI tools used; states limitations
- [ ] Builder Center blog published (if the event asks for it; re-read the rules page)
- [ ] Dashboard and API are live and will stay live until results
- [ ] AWS_EVIDENCE.md screenshots added
- [ ] Hindi review status stated truthfully
- [ ] Each teammate checked the submission form fields and the track selection (Heat and Water)
- [ ] Submitted at least 3 hours before any deadline
- [ ] After submitting: do not push breaking changes to main; keep the stack running
