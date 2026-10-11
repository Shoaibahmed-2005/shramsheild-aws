# ShramShield Backend Deployment Notes

This document describes the exact steps to build, validate, deploy, and verify the ShramShield AWS infrastructure.

---

## 1. Prerequisites

- **AWS CLI v2** configured with credentials for `shram-deployer` in region `ap-south-1`.
- **AWS SAM CLI** (v1.100+).
- **Python 3.12** installed and on `PATH`.
- Check configuration:
  ```powershell
  aws sts get-caller-identity
  aws configure get region
  ```

---

## 2. Secrets and Environment Variables

> **CRITICAL SECURITY RULE:** Never commit secrets to git. Real tokens live in untracked files (`backend/samconfig.toml`) or shell variables only.

Choose a 20+ character random string for `DEMO_KEY` (letters and digits).
Store it in your password manager.

---

## 3. Preparation & Build Steps

Every deployment begins with these steps:

### Step 3.1: Copy shared core library into Lambda package
```powershell
python backend\scripts\prepare.py
```
This syncs `core/shramshield_core/*.py` into `backend/src/shramshield_core/`.

### Step 3.2: Build the thermofeel Lambda Layer
```powershell
python backend\scripts\build_layer.py
```
This uses `--platform manylinux2014_x86_64` and `--python-version 3.12` to install binary wheels for Lambda, cleans test directories and `__pycache__`, and verifies unzipped size is well below 200 MB.

### Step 3.3: Validate the SAM template
```powershell
sam validate --lint -t backend\template.yaml
```

---

## 4. First Deployment (`sam deploy --guided`)

Run from the `backend/` directory:

```powershell
cd backend
sam deploy --guided
```

When prompted:
1. **Stack Name**: `shramshield`
2. **AWS Region**: `ap-south-1`
3. **Parameter DemoKey**: Enter your secret `DEMO_KEY` (hidden or typed by human).
4. **Parameter TelegramBotToken**: Leave default `not-set` (or enter token if ready).
5. **Parameter TelegramWebhookSecret**: Leave default `not-set`.
6. **Parameter PollyRegion**: `ap-south-1`
7. **Parameter DashboardUrl**: Leave empty `""` (updated in P2.4).
8. **Parameter WeatherCacheSeconds**: `1200`
9. **Confirm changes before deploy**: `Y`
10. **Allow SAM CLI IAM role creation**: `Y`
11. **Disable rollback for faster debugging**: `N`
12. **ApiFunction may not have authorization defined, Is this okay?**: `Y` (Authorization is enforced in code via HMAC x-demo-key)
13. **Save arguments to configuration file**: `Y`
14. **SAM configuration file**: `samconfig.toml` (ignored by git)
15. **SAM configuration environment**: `default`

> **Note on `sam build`:** If `sam build` complains about missing Metadata for `DepsLayer`, proceed directly with `sam deploy`. SAM packages local `CodeUri` folders directly.

---

## 5. Subsequent Deployments

Once `samconfig.toml` exists:
```powershell
python backend\scripts\prepare.py
python backend\scripts\build_layer.py
cd backend
sam deploy
```

---

## 6. Reading Stack Outputs

To read deployed endpoints and resources:
```powershell
aws cloudformation describe-stacks --stack-name shramshield --query "Stacks[0].Outputs" --output table
```

To extract the API base URL:
```powershell
$API_URL = aws cloudformation describe-stacks --stack-name shramshield --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text
Write-Host "API Base URL: $API_URL"
```

---

## 7. Verifying Deployment

Run the smoke checks against the deployed URL:
```powershell
# 1. Health check (expects 200 with ok: true and thermofeel: "2.3.0")
curl -s "$API_URL/health"

# 2. Unknown route (expects 404)
curl -s -X POST "$API_URL/anything" -H "content-type: application/json" -d "{}"

# 3. Mutating route without demo key (expects 401)
curl -s -X POST "$API_URL/sites" -H "content-type: application/json" -d "{}"
```

---

## 8. Log retention (cost control)

Lambda creates its log groups with retention "Never expire", so logs accumulate
and are billed for ever. `set_log_retention.py` sets a finite retention on every
log group the stack owns.

```powershell
# See what would change, without changing anything
python backend\scripts\set_log_retention.py --dry-run

# Apply 14 days
python backend\scripts\set_log_retention.py
```

It resolves log groups from `describe-stack-resources` (so it follows the real
physical function names), also sweeps any log group whose name contains the stack
name, and skips groups that do not exist yet because a function has never been
invoked. Re-running it is safe: groups already at the target retention are
reported as `unchanged`.

**Status: done.** Run by P2 on 11 October 2026 against the live stack. All three
Lambda log groups (`ApiFunction`, `NotifyFunction`, `RecordFunction`) are at
**14 days**, confirmed separately with
`aws logs describe-log-groups --region ap-south-1`. `SchedulerFunction` and the
state machine were reported `absent` and skipped, which is correct: the schedule
is `DISABLED` so that function has never run, and the state machine has no
`Logging` property. Full output is in `docs/AWS_EVIDENCE.md` section 5.

Note: the state machine has no `Logging` property in `template.yaml`, so Step
Functions does not write to CloudWatch Logs and has no log group. The script
reports it as `absent` rather than failing. Execution history is still visible in
the Step Functions console, which is what the demo and the screenshots use.

---

## 9. Rehearsals (P2.4 step 7)

Three full end-to-end rehearsals with a stopwatch. Tests A, B and C are the ones
defined in P2.3, each now also checked through the dashboard.

| # | Test | Date | Start time (IST) | Result | Duration | Notes |
|---|---|---|---|---|---|---|
| A | Telegram button acknowledgement | | | | | |
| B | Timeout escalation to backup | | | | | |
| C | Web acknowledgement via `POST /ack` | | | | | |

**Status: not yet run.** These send real Telegram messages to real phones, so
they are started by the human, not by an agent. Fill in the date, start time,
result and duration for each row as they are run. All three must pass before
P2.4 is considered done.

---

## 10. Teardown

> **Do this ONLY AFTER the results are announced.** Judges may open the demo link
> at any time during judging, so the stack and the dashboard must stay alive
> until then. Deleting early loses the submission demo.

Order matters: empty the buckets before deleting the stack, or the stack delete
fails on a non-empty bucket.

```powershell
# 1. Empty the voice S3 bucket (it holds the generated MP3 files)
$BUCKET = aws cloudformation describe-stacks --stack-name shramshield --query "Stacks[0].Outputs[?OutputKey=='VoiceBucketName'].OutputValue" --output text
aws s3 rm "s3://$BUCKET" --recursive

# 2. Delete the CloudFormation stack (Lambdas, API, DynamoDB table, state machine, layer)
sam delete --stack-name shramshield --region ap-south-1 --no-prompts

# 3. Delete the Amplify app that hosts the dashboard.
#    The appId is in the untracked file backend/.amplify_app
$APP_ID = Get-Content backend\.amplify_app
aws amplify delete-app --app-id $APP_ID

# 4. ONLY if the S3 static-website fallback was used instead of Amplify:
#    empty and delete that site bucket as well (its name is in DEPLOY_NOTES
#    section 11 if the fallback path was taken)
# aws s3 rm "s3://<site-bucket>" --recursive
# aws s3api delete-bucket --bucket "<site-bucket>" --region ap-south-1
```

### Revoking keys and secrets

Deleting the stack does **not** invalidate anything that was issued outside it.
After teardown:

1. **Telegram bot token** — in Telegram, message `@BotFather`, choose the bot, then
   `API Token` -> `Revoke current token`. Deleting the bot entirely also works
   (`/deletebot`). Do this even though the token was never committed.
2. **Telegram webhook** — `aws` cannot do this; call the Telegram API with the old
   token before revoking it, or simply revoke the token (which breaks the webhook):
   `curl "https://api.telegram.org/bot<TOKEN>/deleteWebhook"`.
3. **DEMO_KEY** — it only exists as a CloudFormation parameter and in the team
   password manager. Delete it from the password manager; the stack delete removes
   it from AWS. If it ever leaked, it must be changed and the stack redeployed.
4. **TELEGRAM_WEBHOOK_SECRET** — same as DEMO_KEY: remove from the password manager.
5. **`shram-deployer` IAM user access keys** — if a dedicated deploy user was
   created for this project, deactivate and delete its access keys in the IAM
   console (IAM -> Users -> `shram-deployer` -> Security credentials -> Access
   keys -> Actions -> Deactivate, then Delete), or delete the user.
6. **Local untracked files** — delete `backend/samconfig.toml` (holds the parameter
   values including the secrets), `backend/.amplify_app` and
   `frontend/.env.local`.

### Confirming nothing is left billing

```powershell
aws cloudformation describe-stacks --stack-name shramshield   # should error: stack does not exist
aws amplify list-apps --query "apps[].[appId,name]" --output table
aws s3 ls | Select-String shramshield
aws logs describe-log-groups --query "logGroups[?contains(logGroupName,'shramshield')].logGroupName" --output table
```

The CloudWatch log groups are **not** deleted by `sam delete` (Lambda owns them,
not the stack). Remove them explicitly if you want a clean account:

```powershell
aws logs describe-log-groups --query "logGroups[?contains(logGroupName,'shramshield')].logGroupName" --output text |
  ForEach-Object { $_ -split "\s+" } | Where-Object { $_ } | ForEach-Object { aws logs delete-log-group --log-group-name $_ }
```
