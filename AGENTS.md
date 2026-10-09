# ShramShield: rules for every AI agent in this repository

You are the coding agent of ONE of three teammates (P1, P2 or P3). The three of you share this
single repository. Read this file fully before every task. These rules are always on.

## The project in one paragraph

ShramShield is a heat-safety system for outdoor worksites in India (hackathon project, Environmental
Hacks 2026, Heat and Water track). For each worksite it estimates an hourly heat-stress score (WBGT)
from open weather data, turns it into a work/rest plan using published screening limits, sends the plan
to a supervisor (Telegram, with a Hindi voice message), waits for acknowledgement, and escalates to a
backup contact if nobody responds. It is deployed on AWS (Lambda, Step Functions, DynamoDB, Polly,
API Gateway, S3, Amplify Hosting) with AWS SAM. The master plan is docs/BUILD_PLAN.md.

## Who owns what (hard boundary)

| Folder or file | Owner |
|---|---|
| core/, shared/, docs/METHOD.md, docs/NUMBERS.md, docs/HINDI_REVIEW.md, docs/BUILD_PLAN.md (section 3 "Shared contract" only) | P1 |
| backend/, docs/AWS_EVIDENCE.md | P2 |
| frontend/, README.md, docs/ARCHITECTURE.md, docs/SUBMISSION.md, docs/VIDEO_SCRIPT.md, docs/BLOG_DRAFT.md, docs/design/, docs/img/ | P3 |

- Edit ONLY the folders your task card lists. If another owner's file must change, STOP and tell
  the human. Do not edit it yourself, even for a one-line fix.
- The contract (docs/BUILD_PLAN.md section 3) is frozen after task P1.0. Do not change field names,
  endpoints or enums. If the contract looks wrong, stop and tell the human.

## Git rules (one repo, one branch: main)

1. Start every task with a clean working tree, then run: git pull --rebase origin main
2. Work only on your own folders. Stage only your own paths (never "git add ." from the repo root
   if other people's files are modified).
3. Commit message starts with the task id, for example: "P1.1: add WBGT engine and tests".
4. Finish with: git pull --rebase origin main, then git push origin main.
5. Never use force push, never rewrite history, never amend pushed commits, never use --no-verify.
6. If a rebase conflict appears, STOP. Do not resolve conflicts in files you do not own. Tell the human.
7. Commit small and often. Do not commit generated folders (node_modules, dist, .aws-sam, .venv).

## Secrets (zero tolerance)

- Never write real tokens, keys, passwords or account IDs into any tracked file.
  This includes the Telegram bot token, the Telegram webhook secret, the demo key, AWS access keys.
- Secrets live only in untracked files: backend/samconfig.toml, frontend/.env.local, shell variables.
- Commit only *.example files with placeholder values.
- Before every commit run: git diff --cached | grep -i -E "token|secret|AKIA|password" and read the result.
- If a secret was committed by mistake: stop, tell the human immediately (it must be rotated).

## Scope and honesty rules

- Do exactly what the task card says. No extra features, no refactors of other people's code,
  no new dependencies unless the card allows them.
- Never present fixture or mock data as real results. Fixtures carry "_fixture": true.
- Never claim the system is clinically validated, certified or "prevents" illness. The product gives
  screening guidance from modelled weather data and always shows the disclaimer text from the contract.
- Do not invent numbers, thresholds, citations or API fields. If you are unsure, say so and ask.
- Every threshold must come from the table in the contract (section 3.7). Never "improve" it.

## Quality rules

- Write tests for logic. Run them. Show the real output. A task is not done until its verification
  commands pass.
- Python 3.12, standard library first. Dates and hours are India time (UTC+05:30, no daylight saving).
- Frontend: plain React + Vite, no UI framework, accessible (keyboard, labels, contrast),
  never rely on colour alone (always show a text label for the heat level).
- Keep functions small and typed. No dead code, no TODO left in finished work.

## Hackathon rules that can disqualify the whole team

- Everything must be written new during the event. Do not copy code from older projects.
  Any third-party code needs credit and a licence that allows use.
- Do not back-date commits or change the history. The repository history must match the event dates.
- Using AI coding tools is allowed but must be listed in the writeup (P3 keeps docs/SUBMISSION.md updated).

## Stop and ask the human when

- A verification command fails twice for the same reason.
- The task card contradicts this file, the contract or reality (for example an API field is different).
- You would need to touch a file you do not own.
- You are about to delete data, run anything that costs money, or change AWS permissions broadly.
