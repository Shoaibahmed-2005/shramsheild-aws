# Draft: AWS Builder Center blog post

About 600 words. The human publishes this; fill the TODO-human links first.

---

## The alert that fires in the wrong city

**ShramShield — heat safety for outdoor worksites, built on AWS in three days**

Heat is the hazard that does not look like one. Your body cools itself by evaporating sweat,
and when the air is already saturated that stops working. Which is why 31 C in humid Chennai
can be harder on a bricklayer than 41 C in dry, windy Delhi — and why an alert built on air
temperature fires in the wrong place and stays quiet in the right one.

We wanted to know how big that gap actually is, so we measured it. We replayed 1 April to
30 June 2024 for four Indian cities: 4004 working hours of real reanalysis weather. Our model
rated 2097 of those hours RED or STOP. A plain "alert above 40 °C" rule would have caught 233
of them and **missed 1864 — 88.9 percent.** The clearest line in the data: Delhi had 268 work
hours at or above 40 °C but only 320 dangerous hours; Chennai had six hours reaching 40 °C and
679 dangerous hours.

To be precise about what that means: a "dangerous hour" is one our model rates RED or STOP
against published screening limits. It is a comparison of two methods on the same weather, not
a medical finding, and nobody's health outcome was observed.

### What we built

ShramShield computes an hourly **WBGT** (wet bulb globe temperature) score for each worksite
from Open-Meteo data, converts it into a work/rest plan using the ACGIH screening table, sends
that plan to the site supervisor on Telegram with a **Hindi voice message**, and then refuses
to let it drop: AWS Step Functions waits for a human acknowledgement and escalates to a backup
contact if nobody answers.

The stack is Lambda, API Gateway HTTP API, DynamoDB, Step Functions, S3, Polly, EventBridge
Scheduler and CloudWatch, all defined in one SAM template, in `ap-south-1`.

### Three things we learned

**1. Step Functions callbacks are the right tool for waiting on a human.** Our first instinct
was a Lambda that polls. That is wrong twice over: you pay for sleep, and you die at the
15-minute wall. `waitForTaskToken` suspends the workflow at zero compute cost, applies the
timeout itself, and the acknowledgement arrives from somewhere else entirely — a Telegram
webhook or a web button — calling `SendTaskSuccess` with the stored token. The subtle part is
that the notifying Lambda must return *without* completing the task, which feels wrong until
it clicks. The payoff is an execution graph that shows a judge exactly what happened, which is
better evidence than any log line.

**2. Polly's Hindi neural voice is genuinely good, and the plumbing around it is the hard
part.** `Kajal` on the neural engine reads a Hindi safety message clearly enough to act on. The
trap was the delivery: we stored the presigned S3 URL on the run, and discovered that reopening
a run an hour later gave a dead link. Presigned URLs last an hour — and Lambda signs with
*temporary* credentials, so raising the expiry does not help; the URL dies with the session
token. The fix was to store the S3 **object key** and sign a fresh URL on every read. If you
are serving presigned URLs from Lambda, assume they are single-session and re-sign.

**3. A Lambda layer makes scientific Python viable.** We needed ECMWF's `thermofeel` and numpy
for the WBGT physics. Built with `--platform manylinux2014_x86_64 --python-version 3.12` into a
layer, it fits comfortably and keeps the function packages small. Deterministic physics in a
layer also meant our safety numbers never depend on a model's opinion — same inputs, same
output, every time, checked by a validator written independently of the engine.

### Honest limits

It is not clinically validated, not certified, and measures nothing on site: WBGT is estimated
from a city-point weather model, so microclimate like bitumen and metal roofs is invisible to
it. The Hindi text is machine-drafted and still awaiting a native speaker's review. We put all
of that in the README rather than the footnotes.

Code, method and every number with the command that produced it:
https://github.com/Shoaibahmed-2005/shramsheild-aws

Dashboard: TODO-human · Video: TODO-human
