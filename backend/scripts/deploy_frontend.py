"""Build the dashboard and deploy it to AWS Amplify Hosting (manual deployment).

No Git connection is needed: this zips frontend/dist and pushes it through the
Amplify manual-deployment flow (create_deployment -> PUT the zip -> start_deployment
-> poll get_job).

Usage:
    set DEMO_KEY=...                       (never passed on the command line)
    python backend/scripts/deploy_frontend.py --api https://xxxx.execute-api.ap-south-1.amazonaws.com

    python backend/scripts/deploy_frontend.py --api URL --skip-build   # reuse existing dist
    python backend/scripts/deploy_frontend.py --api URL --dry-run      # build and zip only

The demo key is read from the DEMO_KEY environment variable and is never printed,
never logged and never written to a file. Note that Vite inlines it into the
client bundle at build time, so it is a demo-grade control, not a real secret.

The Amplify appId is stored in backend/.amplify_app (untracked, gitignored) so
repeat runs reuse the same app and therefore the same URL.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

BACKEND = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND.parent
FRONTEND = REPO_ROOT / "frontend"
DIST = FRONTEND / "dist"
APP_ID_FILE = BACKEND / ".amplify_app"
ZIP_PATH = BACKEND / "build" / "dashboard.zip"

APP_NAME = "shramshield-dashboard"
BRANCH = "main"
POLL_TIMEOUT_SECONDS = 600
POLL_INTERVAL_SECONDS = 5


def run(cmd: list[str], cwd: Path, extra_env: dict[str, str] | None = None) -> None:
    """Run a command, inheriting stdout, with an optional extra environment."""
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    printable = " ".join(cmd)
    print(f"  $ {printable}  (in {cwd.name}/)")
    result = subprocess.run(cmd, cwd=str(cwd), env=env, shell=(os.name == "nt"))
    if result.returncode != 0:
        raise SystemExit(f"command failed with exit code {result.returncode}: {printable}")


def build_frontend(api_url: str, demo_key: str) -> None:
    """npm ci then npm run build, with the Vite variables set for this process only."""
    if not FRONTEND.is_dir():
        raise SystemExit(f"frontend directory not found at {FRONTEND}")

    print("Building the dashboard")
    run(["npm", "ci"], FRONTEND)
    run(
        ["npm", "run", "build"],
        FRONTEND,
        extra_env={
            "VITE_API_BASE": api_url,
            "VITE_DEMO_KEY": demo_key,
            "VITE_USE_MOCK": "false",
        },
    )
    if not (DIST / "index.html").is_file():
        raise SystemExit("build finished but frontend/dist/index.html is missing")
    print(f"  built {DIST.relative_to(REPO_ROOT)}")


def make_zip() -> Path:
    """Zip the CONTENTS of dist, so index.html sits at the root of the archive."""
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    count = 0
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(DIST.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(DIST).as_posix())
                count += 1

    with zipfile.ZipFile(ZIP_PATH) as archive:
        names = archive.namelist()
    if "index.html" not in names:
        raise SystemExit("index.html is not at the root of the zip; Amplify would reject it")

    size_kb = ZIP_PATH.stat().st_size / 1024
    print(f"  zipped {count} files, {size_kb:.0f} KB, index.html at the archive root")
    return ZIP_PATH


def load_app_id() -> str | None:
    if APP_ID_FILE.is_file():
        value = APP_ID_FILE.read_text(encoding="utf-8").strip()
        return value or None
    return None


def ensure_app(amplify) -> str:
    """Return the Amplify appId, creating the app once if needed."""
    app_id = load_app_id()
    if app_id:
        try:
            amplify.get_app(appId=app_id)
            print(f"  reusing Amplify app {app_id}")
            return app_id
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NotFoundException":
                raise
            print(f"  stored appId {app_id} no longer exists, creating a new app")

    # An app with this name may already exist from an earlier run on another machine.
    paginator = amplify.get_paginator("list_apps")
    for page in paginator.paginate():
        for app in page["apps"]:
            if app["name"] == APP_NAME:
                app_id = app["appId"]
                print(f"  found existing Amplify app {APP_NAME} ({app_id})")
                APP_ID_FILE.write_text(app_id + "\n", encoding="utf-8")
                return app_id

    print(f"  creating Amplify app {APP_NAME} (this can take a few seconds)")
    app_id = amplify.create_app(name=APP_NAME, platform="WEB")["app"]["appId"]
    APP_ID_FILE.write_text(app_id + "\n", encoding="utf-8")
    print(f"  created {app_id}, stored in {APP_ID_FILE.relative_to(REPO_ROOT)} (untracked)")
    return app_id


def ensure_branch(amplify, app_id: str) -> None:
    try:
        amplify.get_branch(appId=app_id, branchName=BRANCH)
        print(f"  branch {BRANCH} already exists")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NotFoundException":
            raise
        amplify.create_branch(appId=app_id, branchName=BRANCH, stage="PRODUCTION")
        print(f"  created branch {BRANCH}")


def upload_zip(url: str, zip_path: Path) -> None:
    """PUT the archive bytes to the presigned URL Amplify gave us."""
    data = zip_path.read_bytes()
    request = urllib.request.Request(
        url, data=data, method="PUT", headers={"Content-Type": "application/zip"}
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        if response.status not in (200, 204):
            raise SystemExit(f"zip upload failed with HTTP {response.status}")
    print(f"  uploaded {len(data) / 1024:.0f} KB")


def wait_for_job(amplify, app_id: str, job_id: str) -> str:
    """Poll until the deployment succeeds or fails. Returns the final status."""
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last = ""
    while time.time() < deadline:
        job = amplify.get_job(appId=app_id, branchName=BRANCH, jobId=job_id)
        status = job["job"]["summary"]["status"]
        if status != last:
            print(f"  job {job_id}: {status}")
            last = status
        if status in ("SUCCEED", "FAILED", "CANCELLED"):
            return status
        time.sleep(POLL_INTERVAL_SECONDS)
    return "TIMED_OUT"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True, help="API base URL, no trailing slash")
    parser.add_argument("--region", default=None)
    parser.add_argument("--skip-build", action="store_true", help="reuse the existing dist/")
    parser.add_argument("--dry-run", action="store_true", help="build and zip, deploy nothing")
    args = parser.parse_args(argv[1:])

    api_url = args.api.rstrip("/")

    demo_key = os.environ.get("DEMO_KEY", "")
    if not demo_key and not args.skip_build:
        print("DEMO_KEY is not set in the environment.")
        print("Set it first; it must never be passed on the command line:")
        print("  PowerShell:  $env:DEMO_KEY = '...'")
        print("  bash:        export DEMO_KEY='...'")
        return 2

    if args.skip_build:
        if not (DIST / "index.html").is_file():
            return _fail("--skip-build was given but frontend/dist/index.html does not exist")
        print("Skipping the build, reusing the existing dist/")
    else:
        build_frontend(api_url, demo_key)

    zip_path = make_zip()

    if args.dry_run:
        print()
        print(f"DRY RUN: built and zipped only. Archive at {zip_path.relative_to(REPO_ROOT)}")
        return 0

    session = boto3.session.Session(region_name=args.region)
    region = session.region_name
    if not region:
        return _fail("no region configured; pass --region or run aws configure")
    amplify = session.client("amplify")

    print(f"Deploying to Amplify Hosting in {region}")
    app_id = ensure_app(amplify)
    ensure_branch(amplify, app_id)

    deployment = amplify.create_deployment(appId=app_id, branchName=BRANCH)
    job_id = deployment["jobId"]
    upload_zip(deployment["zipUploadUrl"], zip_path)
    amplify.start_deployment(appId=app_id, branchName=BRANCH, jobId=job_id)

    status = wait_for_job(amplify, app_id, job_id)
    url = f"https://{BRANCH}.{app_id}.amplifyapp.com"

    print()
    if status != "SUCCEED":
        print(f"Deployment did not succeed: {status}")
        print("If this fails twice for the same reason, use the S3 website fallback")
        print("described in backend/DEPLOY_NOTES.md and say which path was used.")
        return 1

    print("Deployment succeeded.")
    print(f"  Dashboard URL: {url}")
    print()
    print("Next: redeploy the stack so Telegram messages link to the run page.")
    print("  cd backend && sam deploy --parameter-overrides \\")
    print(f'      "DashboardUrl={url}" \\')
    print('      "DemoKey=<use previous>" "TelegramBotToken=<use previous>" \\')
    print('      "TelegramWebhookSecret=<use previous>"')
    print("  (or let samconfig.toml supply the saved values; see DEPLOY_NOTES.md section 5)")
    return 0


def _fail(message: str) -> int:
    print(message)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
