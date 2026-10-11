# Screenshots

The human captures these; an agent cannot. Save each one here under the exact file name in the
table, because `README.md`, `SUBMISSION.md` and `AWS_EVIDENCE.md` link to these names.

**Before saving any AWS console shot:** crop or blur the account id. It appears in the
top-right account menu and inside full ARNs. The same goes for the Telegram bot token and the
demo key.

PNG, and keep each under about 500 KB so the repository stays small.

## Product screenshots

| File name | What it shows | Where to get it |
|---|---|---|
| `dashboard-sites.png` | The sites list with the four demo sites and their level badges | Dashboard `#/` — used at the top of README.md |
| `dashboard-site-plan.png` | A site's hourly plan, the heat strip and the work/rest window | Dashboard `#/site/chn-01` |
| `dashboard-run-timeline.png` | A finished run: stage tracker, status, event timeline, voice player | Dashboard `#/run/{run_id}` after a run is acknowledged |
| `dashboard-backtest.png` | The backtest table with the per-city numbers | Dashboard `#/backtest` |
| `telegram-hindi-message.png` | The Telegram message with the Hindi voice note and the Acknowledge button | Supervisor's phone, during a run |

## AWS console screenshots

Full click paths for each of these are in [../AWS_EVIDENCE.md](../AWS_EVIDENCE.md) section 7.
Take numbers 2, 3 and 4 during or just after a rehearsal run, because the Step Functions graph
needs a live or recent execution.

| File name | What it shows |
|---|---|
| `aws-stack-resources.png` | CloudFormation stack resource list |
| `aws-stepfunctions-escalated.png` | Step Functions graph on the escalation path |
| `aws-stepfunctions-acknowledged.png` | Step Functions graph for an acknowledged run |
| `aws-dynamodb-run-item.png` | The stored run item with its events |
| `aws-lambda-list.png` | The four Lambda functions |
| `aws-s3-voice-objects.png` | The generated MP3 objects in the voice bucket |
| `aws-polly-voice.png` | Polly with the Hindi neural voice Kajal |
| `aws-apigateway-throttling.png` | The HTTP API stage and its throttling settings |
| `aws-cloudwatch-logretention.png` | Log groups showing 14-day retention |
| `aws-amplify-app.png` | The Amplify app and its public URL (once deployed) |

## Design notes

`docs/design/` already holds earlier design images. Those are mockups from the design phase and
are **not** screenshots of the running product — do not use them as evidence of what was built.
