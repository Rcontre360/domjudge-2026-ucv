"""Upload the contest and its teams to a running DomJudge instance.

Usage:
    python3 upload.py <host> [--yaml PATH] [--teams PATH] [--user USER] [--password PASS]

Examples:
    python3 upload.py http://localhost:8080
    python3 upload.py http://1.2.3.4

Credentials default to the ADMIN_USERNAME / ADMIN_PASSWORD env vars,
falling back to admin / adminpassword.
"""
import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("Missing dependency. Install with: pip install requests")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)


def load_dotenv(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_dotenv(os.path.join(REPO_ROOT, ".env"))


def upload_contest(host: str, auth, yaml_path: str) -> str:
    """Create the contest and return its external id (short-name)."""
    with open(yaml_path) as f:
        yaml_text = f.read()
    start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    yaml_text = yaml_text.replace("__START_TIME__", start)

    url = host.rstrip("/") + "/api/contests"
    files = {"yaml": ("contest.yaml", yaml_text, "application/x-yaml")}
    r = requests.post(url, files=files, auth=auth)
    if not r.ok:
        sys.exit(f"Error creating contest: {r.status_code} {r.text}")
    print(f"Contest created: {r.text}")

    # The endpoint returns the contest's external id as a quoted JSON string
    cid = r.text.strip().strip('"')
    return cid


def link_problems(host: str, auth, cid: str, problems_path: str) -> None:
    if not os.path.isfile(problems_path):
        print(f"No problems file at {problems_path} — skipping problem linking")
        return

    with open(problems_path) as f:
        entries = json.load(f)

    base = host.rstrip("/") + f"/api/contests/{cid}/problems"
    for entry in entries:
        problem_id = entry["id"]
        payload = {
            "label": entry["label"],
            "color": entry.get("color"),
            "rgb": entry.get("rgb"),
            "points": entry.get("points", 1),
            "lazyEvalResults": entry.get("lazy_eval_results", 0),
        }
        r = requests.put(f"{base}/{problem_id}", json=payload, auth=auth)
        if r.ok:
            print(f"Linked problem {problem_id} as {entry['label']}")
        else:
            print(f"Error linking {problem_id}: {r.status_code} {r.text}", file=sys.stderr)


def post_json(host: str, auth, endpoint: str, payload) -> None:
    url = host.rstrip("/") + "/api/" + endpoint.lstrip("/")
    body = json.dumps(payload)
    files = {"json": (endpoint.replace("/", "_") + ".json", body, "application/json")}
    r = requests.post(url, files=files, auth=auth)
    if r.ok:
        print(f"Imported {endpoint}: {r.text}")
    else:
        print(f"Error importing {endpoint}: {r.status_code} {r.text}", file=sys.stderr)


def upload_teams(host: str, auth, csv_path: str) -> None:
    if not os.path.isfile(csv_path):
        print(f"No teams file found at {csv_path} — skipping teams import")
        return

    teams = []
    accounts = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        for row in reader:
            row = [cell.strip() for cell in row]
            if not row or not row[0] or row[0].startswith("#"):
                continue
            team_name, username, password = row[0], row[1], row[2]
            teams.append({
                "id": username,
                "name": team_name,
                "group_ids": ["participants"],
            })
            accounts.append({
                "type": "team",
                "username": username,
                "password": password,
                "team_id": username,
            })

    groups = [{"id": "participants", "name": "Participants", "visible": True}]
    post_json(host, auth, "users/groups", groups)
    if teams:
        post_json(host, auth, "users/teams", teams)
    if accounts:
        post_json(host, auth, "users/accounts", accounts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload the contest and its teams to DomJudge.")
    parser.add_argument("host", help="DomJudge host URL (e.g. http://localhost:8080)")
    parser.add_argument("--yaml", default=os.path.join(HERE, "contest.yaml"))
    parser.add_argument("--problems", default=os.path.join(HERE, "problems.json"))
    parser.add_argument("--teams", default=os.path.join(HERE, "teams.csv"))
    parser.add_argument("--user", default=os.environ.get("ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", "adminpassword"))
    args = parser.parse_args()

    auth = (args.user, args.password)
    # cid = upload_contest(args.host, auth, args.yaml)
    # link_problems(args.host, auth, cid, args.problems)
    upload_teams(args.host, auth, args.teams)


if __name__ == "__main__":
    main()
