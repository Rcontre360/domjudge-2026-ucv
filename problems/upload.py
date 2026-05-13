"""Upload every problem subdirectory in problems/ to a DomJudge instance.

For each subdirectory it zips the contents and POSTs to /api/problems.
Usage:
    python3 upload.py <host>
"""
import argparse
import os
import sys
import tempfile
import zipfile

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


def zip_problem(pdir: str, zip_path: str) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(pdir):
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, pdir))


def upload_problem(host: str, auth, name: str, zip_path: str) -> None:
    url = host.rstrip("/") + "/api/problems"
    with open(zip_path, "rb") as f:
        files = {"zip": (f"{name}.zip", f, "application/zip")}
        r = requests.post(url, files=files, auth=auth)
    if r.ok:
        print(f"Uploaded {name}: {r.text}")
    else:
        print(f"Error uploading {name}: {r.status_code} {r.text}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload all problem directories to DomJudge.")
    parser.add_argument("host", help="DomJudge host URL (e.g. http://localhost:8080)")
    parser.add_argument("--user", default=os.environ.get("ADMIN_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD", "adminpassword"))
    args = parser.parse_args()

    auth = (args.user, args.password)
    print(args.user,args.password)

    for entry in sorted(os.listdir(HERE)):
        pdir = os.path.join(HERE, entry)
        if not os.path.isdir(pdir):
            continue
        with tempfile.TemporaryDirectory() as td:
            zip_path = os.path.join(td, f"{entry}.zip")
            zip_problem(pdir, zip_path)
            upload_problem(args.host, auth, entry, zip_path)


if __name__ == "__main__":
    main()
