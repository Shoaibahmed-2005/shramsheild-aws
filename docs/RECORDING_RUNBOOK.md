# Recording runbook — P2, solo

Everything needed to record the 3-minute submission video alone, from a machine that has AWS
credentials, the Telegram bot and the phones.

Read this once end to end before starting. Part 1 takes about 20 minutes and **must** be done
before you record anything.

---

# Part 1 — Pre-flight (do this first)

## 1.1 Get the latest code

```bash
git pull --rebase origin main
```

There are unpushed-to-AWS fixes waiting. Recording before deploying them will put a visible
bug on camera.

## 1.2 Deploy the pending fix

**This matters.** The live API currently stores a one-hour presigned S3 URL on each run, so
reopening a run shows *"voice link expired"* and a dead audio player. On camera that reads as
broken. The fix stores the S3 object key and signs a fresh URL on every read.

```bash
python backend/scripts/prepare.py
```

```bash
python backend/scripts/build_layer.py
```

```bash
cd backend && sam validate --lint -t template.yaml
```

```bash
sam deploy
```

This deploy also adds `S3ReadPolicy` to `ApiFunction` — without it the API would mint voice
URLs that S3 rejects with 403, so the IAM change and the code change must land together.

**Verify the deploy actually landed:**

```bash
curl -s https://5lca7upa95.execute-api.ap-south-1.amazonaws.com/health
```

It should now report `"version": "1.0.0"`. Before this deploy it reported `0.1.0`, so that
string is your proof the new code is live.

## 1.3 Point both contacts at your phones

You want to control both ends of the escalation on camera. Message your bot `/start` from each
phone — it replies with that phone's chat id.

```bash
python backend/scripts/seed_sites.py set-chat chn-01 supervisor <PHONE_1_CHAT_ID>
```

```bash
python backend/scripts/seed_sites.py set-chat chn-01 backup <PHONE_2_CHAT_ID>
```

If you only have one phone, set the supervisor only and skip the escalation shot.

## 1.4 Run the dashboard

```bash
cd frontend && npm ci
```

Create `frontend/.env.local` (untracked, never commit it):

```
VITE_API_BASE=https://5lca7upa95.execute-api.ap-south-1.amazonaws.com
VITE_DEMO_KEY=<the DemoKey stack parameter>
VITE_USE_MOCK=false
```

```bash
npm run dev
```

Open http://localhost:5173. The site page must show **today's date** — if it shows fixture
data you are in mock mode and `VITE_USE_MOCK` is wrong.

## 1.5 Do one full practice run, off camera

Press **Send today's plan now** on `chn-01`, watch the phone, acknowledge. Confirm:

- [ ] The Telegram message arrives with the Hindi voice note and the Acknowledge button
- [ ] Tapping the button flips the dashboard to ACKNOWLEDGED within a few seconds
- [ ] Reopening the run page **plays the audio** (this is what 1.2 fixed)

If any of those fail, fix it before recording. Do not record around a broken step.

## 1.6 Recording setup

- [ ] 1080p, browser zoom 110%, cursor visible
- [ ] Every notification closed: Slack, mail, Telegram desktop, calendar
- [ ] Bookmarks bar hidden, a clean browser profile if possible
- [ ] Phone mirrored to the screen (scrcpy / QuickTime) or filmed on a stand
- [ ] Mic test: record 10 seconds, listen back, then start properly
- [ ] **Never on camera:** the AWS account menu, the Telegram bot token, the demo key, a full ARN

Record **one section at a time**. Redoing a 40-second section beats redoing three minutes.

---

# Part 2 — The script

The submission form asks the video to cover four points. The script is in that order. Every
figure is from `NUMBERS.md` — do not improvise a number.

## Section 1 — About the project (0:00–0:40)

**Screen:** dashboard `#/` sites list → `#/site/chn-01`, click the peak hour on the heat strip.

> "Outdoor workers in India work through heat that an air-temperature alert describes badly,
> because heat stress depends on humidity, sun and wind together, not just temperature.
>
> ShramShield turns open weather data into an hourly work-and-rest plan for each worksite,
> sends it to the supervisor in Hindi as a voice message, and keeps escalating until a human
> acknowledges it.
>
> This is a Chennai site. Every hour has a WBGT heat-stress score. At the peak hour the level
> is **[read it off the screen]** — at most **[read the minutes]** minutes of work that hour,
> the rest in shade. That instruction comes from published ACGIH screening limits. We invented
> no thresholds."

## Section 2 — Tech stack and architecture (0:40–1:15)

**Screen:** `#/backtest`, hold on the per-city table → then `docs/ARCHITECTURE.md` on GitHub
(the Mermaid diagram renders there).

> "The science is deterministic, not a language model. WBGT comes from the Liljegren model in
> ECMWF's thermofeel library, in a Python core with 194 tests and a validator written
> independently of the engine.
>
> To show it matters, we replayed April to June 2024 for four cities. Four thousand and four
> work hours; two thousand and ninety-seven were RED or STOP. A forty-degree thermometer rule
> would have missed one thousand eight hundred and sixty-four of them — **88.9 percent**.
>
> Look at the contrast: Delhi had 268 hours above forty degrees but 320 dangerous hours.
> Chennai had six hours above forty, and 679 dangerous hours. Dry heat trips a thermometer.
> Humid heat does not.
>
> The architecture is serverless: a React dashboard, an HTTP API, Lambda for compute, and Step
> Functions holding the human in the loop."

## Section 3 — How you have used AWS (1:15–2:25)

**Screen:** click **Send today's plan now** → cut to the phone → back to the run timeline →
then the AWS console.

> "Now the live part. I send today's plan.
>
> Lambda builds the plan and starts a Step Functions execution. Amazon Polly speaks the Hindi
> message with the neural voice Kajal, the audio goes to a private S3 bucket, and the
> supervisor gets it on Telegram with an Acknowledge button.
>
> Step Functions is now holding a task token and waiting — not polling, not burning compute.
> If nobody answers inside the timeout, it escalates to the backup contact automatically.
>
> I'll acknowledge… and the run closes. Status, who acknowledged it, by which route, all
> recorded in DynamoDB.
>
> *(switch to console)* Here it is on AWS. The Step Functions execution graph. The run item in
> DynamoDB. The four Lambda functions. And the whole stack defined in one SAM template — API
> Gateway, Lambda, DynamoDB, Step Functions, Polly, S3, CloudWatch, IAM and CloudFormation.
> Ten services, in ap-south-1."

## Section 4 — Learning and growth (2:25–3:00)

**Screen:** `#/method` with the disclaimer visible → the GitHub repo front page.

> "Two things we learned the hard way. Step Functions callbacks are the right way to wait on a
> human — a Lambda that sleeps dies at fifteen minutes and bills you for the wait. And
> presigned S3 URLs expire with the Lambda session token, so we had to store the object key
> and sign a fresh link on every read, rather than storing the link.
>
> We also say what this is not. Not a measurement. Not medical advice. Not clinically
> validated. The Hindi is machine-drafted and still waiting on a native speaker. The backtest
> compares two methods on the same weather — it is not evidence about heat illness.
>
> Open source, MIT, built during this hackathon. Thank you."

---

# Part 3 — Shot list

| # | Shot | Exact screen | Hold for | Notes |
|---|---|---|---|---|
| 1 | Sites list | `#/`, four cities with level badges | 4 s | Open here, not on the console |
| 2 | Hourly detail | `#/site/chn-01`, click the peak hour | 8 s | The text level label must be readable, not just the colour |
| 3 | Backtest | `#/backtest` | 10 s | Hold on the per-city table for the Delhi/Chennai line |
| 4 | Architecture | `docs/ARCHITECTURE.md` on GitHub | 6 s | Scroll the diagram slowly |
| 5 | Start a run | "Send today's plan now" → pick 60 s → confirm | 5 s | 60 s makes the countdown visible |
| 6 | Telegram | Phone: Hindi voice note + message + button | 10 s | Play one second of the audio out loud |
| 7 | Acknowledge | Tap ✅ → timeline flips to ACKNOWLEDGED | 6 s | Let the countdown stopping land; do not cut early |
| 8 | Step Functions | Execution → **Graph view** | 8 s | Use an escalated execution if you have one |
| 9 | DynamoDB | Table → Explore items → a `RUN#` item | 6 s | Show `acked_by` and `acked_via` |
| 10 | Lambda | Functions filtered to `shramshield` | 4 s | Runtime `python3.12` visible |
| 11 | CloudFormation | Stack `shramshield` → **Resources** tab | 4 s | Account menu off screen |
| 12 | Method page | `#/method`, disclaimer legible | 5 s | The disclaimer sentence must be readable |
| 13 | Repo | GitHub front page, README visible | 4 s | End here |

**Optional extra shot:** if you have two phones, let the first timeout expire on camera and
show the escalation arriving on the backup phone. It is the single most distinctive thing the
project does. Budget 15 s and trim elsewhere.

---

# Part 4 — Numbers you may say

Nothing outside this table.

| Figure | Value |
|---|---|
| Period | 1 April – 30 June 2024 |
| Sites | 4 |
| Work hours | 4004 |
| Dangerous hours (RED or STOP) | 2097 |
| Missed at 40 C | 1864, i.e. 88.9% |
| Missed at 37 C | 1507, i.e. 71.9% |
| Missed at 42 C | 1981, i.e. 94.5% |
| Delhi hours ≥ 40 C / dangerous | 268 / 320 |
| Chennai hours ≥ 40 C / dangerous | 6 / 679 |
| Robustness | 89.1% heavy acclimatized, 89.8% moderate unacclimatized |
| Tests | 258 (194 core, 29 backend, 35 frontend) |
| AWS services | 10 declared, 8 evidenced deployed |

## Words to avoid on camera

"Prevents", "saves lives", "clinically validated", "certified", "accurate to X percent",
"AI-powered" (AI wrote code; it does not decide the safety numbers), and anything implying the
Hindi text was reviewed by a speaker.

---

# Part 5 — After recording

- [ ] Watch it once, muted, checking no secret is visible in any frame
- [ ] Watch it once with sound, checking every number against Part 4
- [ ] Under 3 minutes
- [ ] Upload to YouTube as public or unlisted
- [ ] Put the link in `docs/SUBMISSION.md` and `README.md` (replacing `TODO-human`)
- [ ] Keep the stack running until results are announced

## If something fails mid-recording

| Symptom | Cause | Fix |
|---|---|---|
| Button returns 401 | `VITE_DEMO_KEY` missing or wrong | Fix `.env.local`; Vite hot-reloads |
| Run appears then fails immediately | No chat id on the contact | Re-run `set-chat` (step 1.3) |
| Telegram text arrives, no audio | Polly or S3 failed | Check the run timeline for a `telegram_failed` event; the text alone still demos fine |
| Audio player empty on an old run | The 1.2 deploy did not land | `curl .../health` — if it says `0.1.0`, deploy again |
| Dashboard shows fixture data | Mock mode | `VITE_USE_MOCK=false` in `.env.local`, restart `npm run dev` |
