# AWS evidence

Evidence that ShramShield runs on AWS, for the judges and for the video. Every fact below
comes either from read-only AWS CLI output captured by P2 on 11 October 2026, or from
`backend/template.yaml` in this repository. Anything not shown by one of those two is marked
**pending** rather than claimed.

> **Account id rule.** The AWS account number never appears in this file or in any other
> tracked file. ARNs are written with `<ACCOUNT_ID>` in place of the number. When you take the
> console screenshots, crop or blur the account menu and any visible ARN.

---

## 1. Region and deploy identity

| Item | Value | Evidence |
|---|---|---|
| Region | `ap-south-1` (Mumbai) | `aws configure get region` |
| Stack name | `shramshield` | `aws cloudformation describe-stacks` |
| Stack status | `UPDATE_COMPLETE` | same |
| Deploy identity | IAM user `shram-deployer` | `aws sts get-caller-identity` (account id withheld) |

---

## 2. AWS services in use

Ten services. The first eight are confirmed deployed by the CLI output; the last two are
declared in `template.yaml` and are marked with what is and is not yet proven.

| # | Service | Role in ShramShield | Evidence |
|---|---|---|---|
| 1 | **AWS Lambda** | Runs the four Python 3.12 functions: the API router, the notifier, the run recorder and the morning scheduler. Shared code ships as a layer. | `AWS::Lambda::Function` and `AWS::Lambda::LayerVersion` in `describe-stack-resources` |
| 2 | **Amazon API Gateway (HTTP API)** | Public HTTPS endpoint for the dashboard and the Telegram webhook, with request throttling. | `AWS::ApiGatewayV2::Api` + `AWS::ApiGatewayV2::Stage` in `describe-stack-resources` |
| 3 | **Amazon DynamoDB** | Single table holding sites, cached plans, runs and state machine task tokens, with TTL. | `AWS::DynamoDB::Table` in `describe-stack-resources` |
| 4 | **AWS Step Functions** | Standard state machine running the wait-for-acknowledgement and escalate-to-backup workflow using the task token pattern. | `AWS::StepFunctions::StateMachine` in `describe-stack-resources` |
| 5 | **Amazon S3** | Private bucket storing the generated Hindi voice MP3 files, served by presigned URLs. | `VoiceBucketName` stack output; `AWS::S3::Bucket` in `template.yaml` |
| 6 | **AWS IAM** | Per-function execution roles generated from the template's policy blocks. | `AWS::IAM::Role` entries in `describe-stack-resources` |
| 7 | **Amazon CloudWatch Logs** | Log groups for each Lambda function. | `aws logs describe-log-groups` |
| 8 | **AWS CloudFormation** (via AWS SAM) | Defines and deploys the whole stack from `backend/template.yaml`. | The stack itself; `Transform: AWS::Serverless-2016-10-31` |
| 9 | **Amazon Polly** | Neural Hindi voice (`Kajal`, `hi-IN`) that speaks the heat-safety message. | `polly:SynthesizeSpeech` IAM statement in `template.yaml`. Polly creates no CloudFormation resource, so it does not appear in `describe-stack-resources`; it is exercised at runtime. **Console evidence still to be captured.** |
| 10 | **Amazon EventBridge Scheduler** | Daily 06:00 IST trigger for the morning run, `cron(30 0 * * ? *)`. | `ScheduleV2` event on `SchedulerFunction` in `template.yaml`. **Currently `DISABLED` on purpose** (see Pending). |

**Not used / not deployed:** AWS Amplify Hosting is planned for the dashboard but has **not**
been deployed yet. AWS Budgets is **not confirmed** (see Pending). Do not count either of
these in a public service count until they are evidenced here.

---

## 3. Deployed resources

From `aws cloudformation describe-stack-resources --stack-name shramshield`.

> **Incomplete.** The console pager cut this listing off after `NotifyFunctionRole`
> (`-- More`). The rows below are the ones actually visible in P2's capture. The remaining
> rows are **pending** and must be re-captured by P2 with `--output json > resources.json`
> or by piping through `| cat` so the pager does not truncate it.

| Logical id | Type | Physical id | Status |
|---|---|---|---|
| ApiFunction | `AWS::Lambda::Function` | `shramshield-ApiFunction-boJ3dFpgrSLF` | UPDATE_COMPLETE |
| ApiFunctionProxyRoutePermission | `AWS::Lambda::Permission` | `shramshield-ApiFunctionProxyRoutePermission-mYOScwBNBRZP` | CREATE_COMPLETE |
| ApiFunctionRole | `AWS::IAM::Role` | `shramshield-ApiFunctionRole-mJAicalmIKwz` | UPDATE_COMPLETE |
| ApiFunctionRootRoutePermission | `AWS::Lambda::Permission` | `shramshield-ApiFunctionRootRoutePermission-LRtuOwoEibEr` | CREATE_COMPLETE |
| DataTable | `AWS::DynamoDB::Table` | `shramshield-DataTable-1DCHR0EZFIJ6H` | CREATE_COMPLETE |
| DepsLayerb0b01f3ddc | `AWS::Lambda::LayerVersion` | `arn:aws:lambda:ap-south-1:<ACCOUNT_ID>:layer:DepsLayer:4` | CREATE_COMPLETE |
| EscalationStateMachine | `AWS::StepFunctions::StateMachine` | `arn:aws:states:ap-south-1:<ACCOUNT_ID>:stateMachine:EscalationStateMachine-pGn7KMFttx9F` | UPDATE_COMPLETE |
| EscalationStateMachineRole | `AWS::IAM::Role` | `shramshield-EscalationStateMachineRole-inBV3v8bdBZF` | CREATE_COMPLETE |
| HttpApi | `AWS::ApiGatewayV2::Api` | `5lca7upa95` | CREATE_COMPLETE |
| HttpApiApiGatewayDefaultStage | `AWS::ApiGatewayV2::Stage` | `$default` | CREATE_COMPLETE |
| NotifyFunction | `AWS::Lambda::Function` | `shramshield-NotifyFunction-En8It1k1V4RJ` | UPDATE_COMPLETE |
| NotifyFunctionRole | `AWS::IAM::Role` | *(cut off by the pager)* | pending |

For reference, `backend/template.yaml` declares these ten logical resources, so the full
listing should contain all of them plus the roles and permissions SAM generates:
`DataTable`, `VoiceBucket`, `DepsLayer`, `HttpApi`, `ApiFunction`, `NotifyFunction`,
`RecordFunction`, `SchedulerFunction`, `EscalationStateMachine`, `EscalationFailedAlarm`.

Note: `EscalationFailedAlarm` was added to the template in commit `P2.4a` and has **not been
deployed yet**, so it will not appear until the next `sam deploy`.

---

## 4. Stack outputs

From `aws cloudformation describe-stacks --query "Stacks[0].Outputs"`.

| Output key | Description | Value |
|---|---|---|
| `ApiUrl` | Base URL of the HTTP API without trailing slash | `https://5lca7upa95.execute-api.ap-south-1.amazonaws.com` |
| `TableName` | DynamoDB single table name | `shramshield-DataTable-1DCHR0EZFIJ6H` |
| `VoiceBucketName` | Private S3 voice bucket name | `shramshield-voicebucket-lgrwcwt106n9` |
| `EscalationStateMachineArn` | ARN of the escalation state machine | `arn:aws:states:ap-south-1:<ACCOUNT_ID>:stateMachine:EscalationStateMachine-pGn7KMFttx9F` |

The API URL is public by design and is not a secret. The demo key that protects mutating
routes is a stack parameter (`NoEcho`) and appears nowhere in this repository.

---

## 5. CloudWatch log groups and retention

From `aws logs describe-log-groups`.

| Log group | Retention |
|---|---|
| `/aws/lambda/shramshield-ApiFunction-boJ3dFpgrSLF` | `None` (never expire) |
| `/aws/lambda/shramshield-NotifyFunction-En8It1k1V4RJ` | `None` (never expire) |
| `/aws/lambda/shramshield-RecordFunction-cLvzBMyc0WJm` | `None` (never expire) |

Two things this shows:

1. **Retention is unset on all three groups**, so logs are kept for ever and billed for ever.
   `backend/scripts/set_log_retention.py` fixes this. It has **not been run yet** because the
   machine P2.4a was written on has no AWS credentials. P2 should run:
   `python backend\scripts\set_log_retention.py --dry-run` then without the flag.
2. **There is no log group for `SchedulerFunction`**, which is expected: the morning schedule
   is `DISABLED`, so that function has never been invoked and Lambda has not created its log
   group yet. The retention script reports such groups as `absent` and skips them.

There is also no Step Functions log group, because `template.yaml` sets no `Logging` property
on the state machine. Execution history is still fully visible in the Step Functions console,
which is where the screenshots come from.

---

## 6. Security notes and accepted simplifications

**Controls that are in place** (all from `backend/template.yaml`):

- The voice bucket sets all four `PublicAccessBlockConfiguration` flags to `true`, uses
  `AES256` server-side encryption and expires objects after 7 days. Audio reaches Telegram
  through time-limited presigned URLs, not public objects.
- Every secret parameter (`DemoKey`, `TelegramBotToken`, `TelegramWebhookSecret`) is
  `NoEcho: true`. `DemoKey` has no default, so the stack cannot be deployed with a blank key.
- The HTTP API throttles at `ThrottlingBurstLimit: 20` and `ThrottlingRateLimit: 10`.
- Mutating routes require the `x-demo-key` header, compared in constant time in code.
- The Telegram webhook verifies `X-Telegram-Bot-Api-Secret-Token`.
- DynamoDB is `PAY_PER_REQUEST` with TTL enabled, so idle cost is effectively zero.
- `states:StartExecution` and the DynamoDB and S3 policies are scoped to the specific table,
  bucket and state machine, not to `*`.

**Accepted simplifications**, deliberate for a hackathon demo and named here rather than
hidden:

| Simplification | Why it is acceptable | Risk if left in production |
|---|---|---|
| CORS `AllowOrigins: "*"` | The dashboard origin is not known until Amplify is deployed. Mutating routes still require the demo key, and the API is throttled. | Any site could call the read-only routes from a browser. Restrict to the dashboard origin for real use. |
| `states:SendTaskSuccess` / `SendTaskFailure` on `Resource: "*"` | IAM has no resource-level permission for the SendTask\* actions; they are authorised by the task token itself. There is no narrower form. | None practical; this is the documented pattern. |
| `polly:SynthesizeSpeech` on `Resource: "*"` | `SynthesizeSpeech` is a resourceless action and cannot be scoped in IAM. | None practical. |
| `DynamoDBCrudPolicy` action breadth | Scoped to the one table, but grants Scan, Delete and BatchWrite that some functions never use (for example `RecordFunction` only updates items). | A compromised function could delete or scan the table. Tighten to per-function action lists for real use. |
| No WAF, no API key per client | Out of scope for a three-day event. | Abuse and cost risk at scale. |

---

## 7. Screenshots for the human to take

The agent cannot take these. Save each as `docs/img/<file name>`. **Before saving, crop or
blur the account id**, which appears in the console's top-right account menu and inside full
ARNs.

| # | File name | What it must show | Exact click path |
|---|---|---|---|
| 1 | `aws-stack-resources.png` | The stack's resource list | Console → search **CloudFormation** → *Stacks* → `shramshield` → **Resources** tab → set the page size so all rows are visible |
| 2 | `aws-stepfunctions-escalated.png` | The graph of a run that escalated to the backup | Console → **Step Functions** → *State machines* → `EscalationStateMachine-…` → **Executions** → pick an execution from rehearsal Test B → **Graph view**; the `NotifyPrimary → RecordEscalated → NotifyBackup` path should be highlighted |
| 3 | `aws-stepfunctions-acknowledged.png` | The graph of a run that was acknowledged | Same path, pick the execution from rehearsal Test A → status `Succeeded`, `NotifyPrimary` completing without timeout |
| 4 | `aws-dynamodb-run-item.png` | The stored run item with its event timeline | Console → **DynamoDB** → *Tables* → `shramshield-DataTable-…` → **Explore table items** → filter `PK` begins with `RUN#` → open one item → show `status`, `acked_by`, `acked_via` and the `events` list |
| 5 | `aws-lambda-list.png` | The four functions | Console → **Lambda** → *Functions* → filter by `shramshield` → show `ApiFunction`, `NotifyFunction`, `RecordFunction`, `SchedulerFunction` with runtime `python3.12` |
| 6 | `aws-s3-voice-objects.png` | The generated MP3 audio objects | Console → **S3** → *Buckets* → `shramshield-voicebucket-…` → open the `voice/` prefix → show the `{run_id}_{lang}.mp3` objects with sizes and timestamps |
| 7 | `aws-polly-voice.png` | Hindi neural voice available in the region | Console → **Amazon Polly** → *Text-to-Speech* → Language `Hindi (hi-IN)` → Voice `Kajal` → Engine **Neural** → paste the Hindi message and press **Listen** |
| 8 | `aws-apigateway-throttling.png` | The API and its throttling settings | Console → **API Gateway** → `shramshield` HTTP API → *Stages* → `$default` → **Default route throttling**: burst 20, rate 10 |
| 9 | `aws-cloudwatch-logretention.png` | Log groups after retention is set | Console → **CloudWatch** → *Log groups* → filter `shramshield` → the **Retention** column should read `14 days` once the script has been run |
| 10 | `aws-amplify-app.png` | The hosted dashboard | Console → **Amplify** → the `shramshield-dashboard` app → the `main` branch showing a successful deployment and the public URL. **Pending: Amplify is not deployed yet.** |
| 11 | `aws-budgets.png` | The cost budget | Console → **Billing and Cost Management** → *Budgets* → open the budget created in H2 → show its limit and current spend. **Pending: not confirmed yet.** |

The Step Functions graph needs a recent or live execution, so take screenshots 2, 3 and 4
during or straight after a rehearsal run.

---

## 8. Pending

Everything here is **not yet proven** and must not be claimed in the video, writeup or README
until it is.

| # | Item | Why it is pending | Who clears it |
|---|---|---|---|
| 1 | **Budget alarm** | The `describe-budgets` command failed. P2 ran it in `cmd.exe` with PowerShell syntax (`$acct = aws sts …`), so `$acct` was never set and the CLI rejected `--account-id` with "Invalid length for parameter AccountId, value: 5". The budget itself may well exist; it simply was not read. | P2, re-run it (see below) |
| 2 | **Full resource list** | The `describe-stack-resources` table was truncated by the console pager after `NotifyFunctionRole`. | P2, re-run with `--output json` or pipe through `cat` |
| 3 | **Log retention** | Still `None` on all three groups. `set_log_retention.py` is written but has not been run. | P2, run the script |
| 4 | **Amplify Hosting** | The dashboard is not deployed. `deploy_frontend.py` is not written yet (Phase B). | P2, in P2.4 Phase B |
| 5 | **`EscalationFailedAlarm`** | Added to `template.yaml` but not deployed; it ships with the Phase B redeploy that sets `DashboardUrl`. | P2, Phase B |
| 6 | **EventBridge schedule** | `ScheduleState` is `DISABLED` by design, so the daily run has never fired and `SchedulerFunction` has no log group. This is intentional, not a fault. Decide before the demo whether to enable it. | Human |
| 7 | **Three rehearsals** | Tests A, B and C with a stopwatch are not yet recorded. The empty table is in `backend/DEPLOY_NOTES.md` section 9. | Human + P2 |
| 8 | **Polly console evidence** | Polly is exercised at runtime and proven by the voice notes the phones received, but no console screenshot exists yet. | Human, screenshot 7 |

To clear item 1, in **PowerShell** (not `cmd.exe`):

```powershell
$acct = aws sts get-caller-identity --query Account --output text
aws budgets describe-budgets --account-id $acct --query "Budgets[].[BudgetName,BudgetLimit.Amount,BudgetLimit.Unit]" --output table
```

or in a single `cmd.exe` line:

```
for /f %i in ('aws sts get-caller-identity --query Account --output text') do aws budgets describe-budgets --account-id %i --output table
```

To clear item 2:

```powershell
aws cloudformation describe-stack-resources --stack-name shramshield --output json > resources.json
```

Then paste `resources.json` (with the account id removed) and section 3 above can be completed.
