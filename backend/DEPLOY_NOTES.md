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

## 8. Deleting the Stack (Teardown)

> **DO NOT RUN THIS DURING THE HACKATHON.** Only use after project completion or if completely resetting.

```powershell
# 1. Empty the voice S3 bucket first if it has audio files
$BUCKET = aws cloudformation describe-stacks --stack-name shramshield --query "Stacks[0].Outputs[?OutputKey=='VoiceBucketName'].OutputValue" --output text
aws s3 rm "s3://$BUCKET" --recursive

# 2. Delete the CloudFormation stack
sam delete --stack-name shramshield --region ap-south-1 --no-prompts
```
