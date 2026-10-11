# ShramShield — Backend Progress & Team Handover Walkthrough

**Project:** ShramShield (Environmental Hacks 2026 — Heat and Water Track)  
**Date:** 11 October 2026  
**AWS Stack:** `shramshield`  
**AWS Region:** `ap-south-1` (Mumbai)  
**Base API URL:** `https://5lca7upa95.execute-api.ap-south-1.amazonaws.com`  
**Git Branch:** `main` (Fully synchronized with `origin/main`)  

---

## 1. Executive Summary & Current Status

The backend and cloud infrastructure for ShramShield (**Tasks P2.1, P2.2, and P2.3**) are **100% complete, deployed to AWS, and validated with live end-to-end tests**.

- **Live Serverless Stack:** API Gateway HTTP API, DynamoDB single-table database, private S3 voice bucket, Amazon Polly neural voice synthesis, and Step Functions escalation workflow.
- **Human-in-the-Loop Escalation:** Real Telegram notifications with Hindi voice audio and interactive inline callback buttons (`[✅ Acknowledge / मिल गया]`), backed by Step Functions `waitForTaskToken`.
- **Live Tested:** Successfully completed real-world verification on physical devices:
  - **Test A:** Telegram button acknowledgement by supervisor.
  - **Test B:** Automated timeout escalation to backup contact.
  - **Test C:** Web acknowledgement via `POST /ack` with dynamic timeout overrides.
  - **Test D:** Concurrent race condition handling (conditional DynamoDB updates prevent double-ack).
- **Unit & Integration Tests:** 21/21 pytest tests passing in `backend/tests/`.

---

## 2. What Has Been Built & Deployed (P2.1 → P2.3)

### A. AWS Serverless Resources (`backend/template.yaml`)
1. **API Gateway HTTP API (`HttpApi`):**
   - High performance, low latency endpoint with CORS enabled.
   - Throttling limits: 20 burst / 10 rate.
   - Constant-time HMAC authentication (`x-demo-key`) for mutating endpoints.
2. **Lambda Functions (Python 3.12 on AWS Graviton/x86):**
   - `ApiFunction`: High-speed router for sites, plans, runs, and Telegram webhooks.
   - `NotifyFunction`: Invoked by Step Functions with task tokens. Synthesizes Hindi voice, saves task tokens, sends Telegram messages and audio.
   - `RecordFunction`: Handles state machine transitions (`escalate`, `unacknowledge`, `fail`) with conditional DynamoDB writes.
   - `SchedulerFunction`: Triggered by EventBridge cron (`cron(30 0 * * ? *)` = 06:00 AM IST) to automatically start daily runs for all active sites. (Default `ScheduleState=DISABLED` until demo day).
3. **AWS Step Functions Standard State Machine (`EscalationStateMachine`):**
   - Implements human-in-the-loop task token pattern (`waitForTaskToken`).
   - `NotifyPrimary` → waits for `ack_timeout_seconds` → on timeout escalates to `RecordEscalated` → `NotifyBackup` → on timeout transitions to `RecordUnacknowledged`.
   - Acknowledgements occur cleanly outside the state machine via `SendTaskSuccess`.
4. **Amazon Polly (Neural Engine):**
   - Hindi neural voice `Kajal` (`hi-IN`) produces clear, natural spoken heat-safety advisories.
5. **Private S3 Voice Bucket (`shramshield-voicebucket-lgrwcwtl06n9`):**
   - Stores synthesized MP3 audio objects (`voice/{run_id}_{lang}.mp3`).
   - Serves presigned SigV4 HTTPS URLs valid for 1 hour with a 7-day lifecycle expiration policy.
6. **DynamoDB Single-Table (`shramshield-DataTable-1DCHR0EZFIJ6H`):**
   - Pay-per-request billing mode.
   - Stores Sites (`SITE#{id}`), Cached Plans (`PLAN#{id}#{date}` with TTL), Runs (`RUN#{run_id}`), Latest Run Pointers (`LATEST_RUN#{site_id}`), and State Machine Task Tokens (`TOKEN#{stage}#{run_id}`).

---

## 3. Live API Reference (Ready for Frontend Dashboard)

**Base URL:** `https://5lca7upa95.execute-api.ap-south-1.amazonaws.com`

| Method & Route | Auth Required | Purpose & Key Details |
|---|---|---|
| `GET /health` | None | System status, version info, and `thermofeel 2.3.0` confirmation. |
| `GET /sites` | None | Returns list of all worksites: `{"sites": [Site, ...]}`. |
| `POST /sites` | `x-demo-key` | Creates a new worksite (max 25). Validated via `shramshield_core`. |
| `GET /sites/{site_id}` | None | Returns a single site object. |
| `GET /sites/{site_id}/plan?date=YYYY-MM-DD` | None | Generates/returns WBGT screening plan. Returns `x-cache: HIT` or `MISS`. |
| `POST /sites/{site_id}/run` | `x-demo-key` | Initiates an escalation workflow. Body: `{"ack_timeout_seconds": 60}` (optional). Returns `202 {"run_id": "...", "status": "STARTED"}`. |
| `GET /sites/{site_id}/runs/latest` | None | Returns the latest run object for the site (or 404). |
| `GET /runs/{run_id}` | None | Returns full run object with timeline events, voice URL, ack deadline, and status. |
| `POST /ack` | `x-demo-key` | Acknowledges active run stage via web. Body: `{"run_id": "...", "by": "name"}`. Returns `200 {"ok": true, "status": "ACKNOWLEDGED"}` (or 409 if closed). |
| `POST /telegram/webhook` | `X-Telegram-Bot-Api-Secret-Token` | Receives updates from Telegram. Handles `/start` and `ack:{run_id}` inline button presses. |

### Example cURL Commands for Testing
```bash
# 1. Check health
curl -s https://5lca7upa95.execute-api.ap-south-1.amazonaws.com/health

# 2. Get today's plan for Chennai
curl -s "https://5lca7upa95.execute-api.ap-south-1.amazonaws.com/sites/chn-01/plan"

# 3. Start a test run with a 60-second timeout
curl -s -X POST "https://5lca7upa95.execute-api.ap-south-1.amazonaws.com/sites/chn-01/run" \
  -H "x-demo-key: <DEMO_KEY>" \
  -H "content-type: application/json" \
  -d '{"ack_timeout_seconds": 60}'

# 4. Inspect run status and events
curl -s "https://5lca7upa95.execute-api.ap-south-1.amazonaws.com/runs/<RUN_ID>"

# 5. Acknowledge via Web API
curl -s -X POST "https://5lca7upa95.execute-api.ap-south-1.amazonaws.com/ack" \
  -H "x-demo-key: <DEMO_KEY>" \
  -H "content-type: application/json" \
  -d '{"run_id": "<RUN_ID>", "by": "Web Supervisor"}'
```

---

## 4. Live Test Evidence Completed

All four validation tests specified in `docs/BUILD_PLAN.md` have been executed against live AWS resources:

1. **Test A (Telegram Button Acknowledge):**
   - Run `chn-01_20261011T072435` triggered.
   - Supervisor phone received Hindi advisory message + Kajal neural voice audio + inline button.
   - Button pressed: DynamoDB updated to `ACKNOWLEDGED`, `acked_by: "Sara"`, `acked_via: "telegram"`. Step Functions execution completed `Succeeded`.
2. **Test B (Escalation to Backup):**
   - Triggered workflow with supervisor inactive.
   - After timeout expired, state machine transitioned from `NotifyPrimary` → `RecordEscalated` → `NotifyBackup`.
   - Backup phone received escalated message.
3. **Test C (Web Acknowledge):**
   - Run `chn-01_20261011T073822` started with `ack_timeout_seconds: 60`.
   - Verified `ack_deadline` dynamically set to `+60s`.
   - Called `POST /ack` with `by: "Web user"`.
   - Run closed with `status: "ACKNOWLEDGED"`, `acked_via: "web"`, `acked_by: "Web user"`.
4. **Test D (Race Condition Double-Tap):**
   - Pressed Telegram button twice in rapid succession.
   - First tap returned callback notification: `Acknowledged ✅`.
   - Second tap returned: `Already closed` (DynamoDB conditional expression prevented duplicate close).

---

## 5. Next Steps for Each Teammate

```
+-----------------------------------------------------------------------------------+
|                                 TEAM ROADMAP                                      |
+-----------------------------------------------------------------------------------+
|  P2: Backend Live & Tested  -->  P3: Task P3.3 Dashboard (Runs, Audio, Ack)      |
|                                         |                                         |
|                                         v                                         |
|  P1: Task P1.4 Core Freeze  -->  P2: Task P2.4 Amplify Hosting & AWS Evidence     |
|  (docs/NUMBERS.md)                      |                                         |
|                                         v                                         |
|                                  P3: Task P3.4 Video & Submission                 |
+-----------------------------------------------------------------------------------+
```

### 👤 For Teammate P3 (Frontend / UI — Task P3.3)
Your task is to build the live Run timeline and interactive dashboard controls:

1. **Configure Environment:**
   - In `frontend/.env.local` (untracked):
     ```ini
     VITE_API_BASE=https://5lca7upa95.execute-api.ap-south-1.amazonaws.com
     VITE_DEMO_KEY=<SHARED_DEMO_KEY>
     VITE_USE_MOCK=false
     ```
2. **Site Page (`#/site/{site_id}`):**
   - Add the **"Send today's plan now"** panel.
   - Include a timeout picker (30s, 60s, 5 min, site default) and a confirmation dialog before calling `POST /sites/{site_id}/run`.
   - Display a **"Last run"** card by querying `GET /sites/{site_id}/runs/latest`.
3. **Run Page (`#/run/{run_id}`):**
   - Poll `GET /runs/{run_id}` every 2 seconds while status is active (`STARTED`, `WAITING_ACK`, `ESCALATED`), stopping once final.
   - Display status badge: `WAITING FOR ACKNOWLEDGEMENT`, `ESCALATED TO BACKUP`, `ACKNOWLEDGED`, `NOT ACKNOWLEDGED`, `FAILED`.
   - Implement a 3-step stage tracker: `Plan built` → `Supervisor notified` → `Backup notified`.
   - Show a live countdown timer derived from `ack_deadline` (mm:ss).
   - Render the event timeline with user-friendly English labels:
     - `plan_built` → *"Heat plan built"*
     - `voice_ready` → *"Hindi voice message created"*
     - `telegram_sent` → *"Message sent on Telegram"*
     - `telegram_failed` → *"Telegram delivery failed"*
     - `notified_primary` → *"Supervisor notified"*
     - `escalated` → *"No answer: escalating to backup"*
     - `notified_backup` → *"Backup notified"*
     - `acknowledged` → *"Acknowledged"*
     - `unacknowledged` → *"Nobody acknowledged"*
     - `error` → *"Error"*
   - Add an HTML5 `<audio>` player with controls for `voice_url`.
   - Add an **"Acknowledge (web)"** button calling `POST /ack`.
4. **Verification:**
   - Run `cd frontend && npm run test && npm run build`.

---

### 👤 For Teammate P1 (Core & Methodology — Task P1.4)
Your task is to freeze the scientific core and create the single source of truth for claims:

1. **Re-run Backtest:**
   - Run `cd core && .venv/bin/python scripts/run_backtest.py` to ensure all historical 2024 ERA5 weather reanalysis metrics are reproducible.
2. **Create `docs/NUMBERS.md`:**
   - Document all verified statistics (dangerous hours, missed alert percentages at 37°C, 40°C, 42°C, and false alarm hours).
   - Detail the "Claims we must NOT make" table (never claim clinically validated, certified, or "saves lives").
3. **Version Bump & Freeze:**
   - Set version to `1.0.0` in `core/shramshield_core/__init__.py` and `core/pyproject.toml`.
   - Verify `cd core && .venv/bin/python -m pytest -q` and `python scripts/verify_live.py`.

---

### 👤 For Teammate P2 (Cloud & DevOps — Task P2.4, After P3.3)
Once P3 has pushed the completed dashboard build (`frontend/dist/`):

1. **Host on AWS Amplify:**
   - Run `backend/scripts/deploy_frontend.py` to deploy `frontend/dist/` directly to AWS Amplify Hosting.
   - Update `DashboardUrl` in the SAM template parameters so Telegram messages include direct links to `https://main.<appId>.amplifyapp.com/#/run/{run_id}`.
2. **Hardening & Cost Control:**
   - Run `backend/scripts/set_log_retention.py` to enforce a 14-day CloudWatch log retention policy across all log groups.
   - Verify CloudWatch budget alarms and API Gateway throttling.
3. **Evidence Collection (`docs/AWS_EVIDENCE.md`):**
   - Document all 12 AWS services used and generate resource listings via `aws cloudformation describe-stack-resources`.
   - Prepare clickpaths for the human to capture screenshots of Step Functions executions, DynamoDB items, S3 audio objects, and Polly synthesis.
4. **Final Rehearsals:**
   - Run three timed end-to-end rehearsals (Tests A, B, and C) and log durations in `backend/DEPLOY_NOTES.md`.

---

## 6. Safety & Repository Rules

- **Zero Secrets Policy:** Never commit real tokens, keys, passwords, or account IDs.
- **Ownership Boundaries:**
  - P1 edits: `core/`, `shared/`, `docs/METHOD.md`, `docs/NUMBERS.md`.
  - P2 edits: `backend/`, `docs/AWS_EVIDENCE.md`.
  - P3 edits: `frontend/`, `README.md`, `docs/ARCHITECTURE.md`, `docs/SUBMISSION.md`.
- **Git Flow:** Always `git pull --rebase origin main` before starting, work only in owned directories, and prefix commits with task IDs (`P3.3: ...`, `P1.4: ...`, `P2.4: ...`).
