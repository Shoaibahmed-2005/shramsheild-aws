# Video script and shot list

**3 minutes maximum.** The submission form requires the video to cover four points, so the
script below is built around them in order:

1. About the project
2. Tech stack and architecture
3. How you have used AWS
4. Learning and growth (optional)

Every figure is from [NUMBERS.md](NUMBERS.md). Do not improvise a number on camera.

---

## Who records what

Most of this needs **no AWS access**. Only the console segment does.

| Segment | Needs | Who |
|---|---|---|
| A — dashboard, backtest, method, repo | A browser. Nothing else. | **P1 (you)** |
| B — live Telegram run | The dashboard + the demo key + a phone with the bot | **P1 (you)**, once P2 points a chat id at your phone |
| C — AWS console (~30 s) | Console login | **P2 only** |

If P2 cannot record segment C at all, see **Fallback** at the end. You can still satisfy "How
you have used AWS" without console footage.

---

## Recording checklist

- [ ] Start a **fresh run** shortly before recording, so the voice link is live.
- [ ] `curl -s $API_URL/health` returns `ok: true`.
- [ ] 1080p, browser zoom 110%, cursor visible.
- [ ] Close every notification (Slack, mail, Telegram desktop) and hide the bookmarks bar.
- [ ] Mic test: record 10 seconds and listen back before doing the real take.
- [ ] Phone mirrored to the screen, or filmed, for the Telegram part.
- [ ] **Never on camera:** the AWS account menu, the Telegram bot token, the demo key, a full ARN.
- [ ] Record the live section twice and keep the better take.

---

## The script

### 1. About the project — 0:00 to 0:40

**Screen:** dashboard `#/` sites list, then `#/site/chn-01` with the heat strip.

> "Outdoor workers in India work through heat that an air-temperature alert describes badly,
> because heat stress depends on humidity, sun and wind together, not just temperature.
>
> ShramShield turns open weather data into an hourly work-and-rest plan for each worksite,
> sends it to the supervisor in Hindi as a voice message, and keeps escalating until a human
> acknowledges it.
>
> This is a Chennai site. Every hour has a WBGT heat-stress score. At the peak hour the level
> is **[read it off the screen]**, which means at most **[read the minutes]** minutes of work
> that hour and the rest in shade. That instruction comes from published ACGIH screening
> limits — we invented no thresholds."

### 2. Tech stack and architecture — 0:40 to 1:15

**Screen:** the backtest page `#/backtest`, then the architecture diagram in
`docs/ARCHITECTURE.md` (render it on GitHub so the Mermaid diagram draws).

> "The science is deterministic, not a language model. WBGT comes from the Liljegren model in
> ECMWF's thermofeel library, in a Python core with 194 tests and a validator written
> independently of the engine.
>
> To show it matters, we replayed April to June 2024 for four cities. Four thousand and four
> work hours; two thousand and ninety-seven were RED or STOP. A 40-degree thermometer rule
> would have missed one thousand eight hundred and sixty-four of them — **88.9 percent**.
> Look at the contrast: Delhi had 268 hours above 40 degrees but 320 dangerous hours. Chennai
> had six hours above 40 and 679 dangerous hours. Dry heat trips a thermometer; humid heat
> does not.
>
> The architecture is serverless: a React dashboard, an HTTP API, Lambda for the compute, and
> Step Functions holding the human in the loop."

### 3. How you have used AWS — 1:15 to 2:25

**Screen:** click **Send today's plan now** → cut to the **phone** → back to the run timeline
→ then the AWS console (segment C).

> "Now the live part. I send today's plan.
>
> Lambda builds the plan and starts a Step Functions execution. Amazon Polly speaks the Hindi
> message with the neural voice Kajal, the audio goes to a private S3 bucket, and the
> supervisor gets it on Telegram with an Acknowledge button.
>
> Step Functions is now **holding a task token and waiting** — not polling, not burning
> compute. If nobody answers inside the timeout it escalates to the backup contact
> automatically.
>
> I'll acknowledge… and the run closes. Status, who acknowledged it, and by which route — all
> recorded in DynamoDB.
>
> *(console)* Here it is on AWS: the Step Functions execution graph, the run item in DynamoDB,
> the four Lambda functions, and the whole stack defined in one SAM template. API Gateway,
> Lambda, DynamoDB, Step Functions, Polly, S3, CloudWatch, IAM and CloudFormation — ten
> services, in ap-south-1."

### 4. Learning and growth — 2:25 to 3:00

**Screen:** the method page `#/method`, then the GitHub repo.

> "Two things we learned the hard way. Step Functions callbacks are the right way to wait on a
> human — a Lambda that sleeps dies at fifteen minutes and bills you for the wait. And
> presigned S3 URLs expire with the Lambda session token, so we had to store the object key
> and sign a fresh link on every read, not store the link.
>
> We also say what this is not: not a measurement, not medical advice, not clinically
> validated. The Hindi is machine-drafted and still waiting on a native speaker. The backtest
> compares two methods on the same weather — it is not evidence about heat illness.
>
> Open source, MIT, built during this hackathon. Thank you."

---

## Shot list

| # | Shot | Screen | Who | Notes |
|---|---|---|---|---|
| 1 | Sites list | `#/` with four cities | P1 | Open here, not on the console |
| 2 | Hourly detail | `#/site/chn-01`, click the peak hour | P1 | The text level label must be readable, not just the colour |
| 3 | Backtest | `#/backtest` | P1 | Hold on the per-city table for the Delhi/Chennai line |
| 4 | Architecture | `docs/ARCHITECTURE.md` on GitHub | P1 | The Mermaid diagram renders there |
| 5 | Start a run | "Send today's plan now" → confirm | P1 | Pick a 60 s timeout |
| 6 | Telegram | Phone: Hindi voice note + Acknowledge button | P1 | Play one second of the audio aloud |
| 7 | Acknowledge | Tap it → timeline flips to ACKNOWLEDGED | P1 | Let the countdown stopping land |
| 8 | Step Functions graph | Execution → Graph view | **P2** | ≥ 8 s. An escalated execution is best |
| 9 | DynamoDB item | Table → Explore items → a `RUN#` item | **P2** | Show `acked_by` and `acked_via` |
| 10 | Lambda list | Functions filtered to `shramshield` | **P2** | 3 s, runtime python3.12 visible |
| 11 | CloudFormation | Stack → Resources tab | **P2** | 3 s, account menu off screen |
| 12 | Method page | `#/method`, disclaimer legible | P1 | |
| 13 | Repo | GitHub front page | P1 | End here |

---

## Numbers you may say, and nothing else

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
Hindi text was reviewed.

---

## Fallback if P2 cannot record the console

You can still answer "How you have used AWS" without console footage. Replace shots 8–11 with:

1. **`backend/template.yaml` open on screen**, scrolling slowly through the resources — this is
   the infrastructure as code, and it is more convincing than a console screenshot to a
   technical judge.
2. **`docs/ARCHITECTURE.md`** rendered on GitHub, pointing at each AWS box as you name it.
3. **`docs/AWS_EVIDENCE.md`**, which contains the real `describe-stack-resources` output with
   physical resource ids and the stack status `UPDATE_COMPLETE`.

Say: "the stack is deployed in ap-south-1; this is the template that defines it, and the
evidence document in the repo has the live resource listing." That is accurate and verifiable.
Do not claim to be showing a live console if you are not.
