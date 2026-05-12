# Scripts

This page documents the Python tooling used to populate a running DomJudge
instance. The only script in scope here is `contest/upload.py`, which talks to
DomJudge over its REST API.

## `contest/upload.py`

A single-purpose CLI that:

1. Creates the contest defined in `contest/contest.yaml`.
2. Links contest problems (using the labels and colors in
   `contest/problems.json`).
3. Creates the participant group, teams, and team accounts from
   `contest/teams.csv`.

The script needs administrator credentials because it hits admin-only
endpoints. It loads them from the `.env` file in the repository root (the same
file used by `docker-compose.yml`) before falling back to CLI flags.

### Usage

```bash
python3 contest/upload.py <host> \
    [--yaml PATH] [--problems PATH] [--teams PATH] \
    [--user USER] [--password PASS]
```

Examples:

```bash
# Local development stack
python3 contest/upload.py http://localhost:8080

# Remote AWS instance
python3 contest/upload.py http://18.211.164.127
```

Notes:

- The host argument **must include the scheme** (`http://...`). A bare
  `localhost:8080` will fail because `requests` cannot guess the scheme.
- Credentials default to `ADMIN_USERNAME` / `ADMIN_PASSWORD` from the
  environment or `.env`. Override with `--user` / `--password` when needed.
- The default file paths point to `contest/contest.yaml`,
  `contest/problems.json`, and `contest/teams.csv`. Pass `--yaml`, `--problems`,
  or `--teams` to use alternate locations.

### Required input files

#### `contest/contest.yaml`

Standard DomJudge contest descriptor. The `start_time` field uses the literal
placeholder `__START_TIME__`; the script replaces it with the current UTC
time at upload, so the contest starts right after import. Example:

```yaml
short-name: test
name: Test Contest
formal_name: Test Contest
start_time: __START_TIME__
duration: 0:30:00.000
penalty_time: 20
```

#### `contest/problems.json`

A JSON array describing the contest scoreboard entries. The script does **not**
upload problem content; it only links problems that already exist on the
domserver to the contest, setting their label and color. Each entry accepts:

```json
{
  "id":   "a",        // problem external id (matches the slot on the domserver)
  "label":"A",        // letter shown on the scoreboard
  "rgb":  "#ff0000",  // hex color
  "color":"red",      // optional human-readable color name
  "points":1,         // optional, defaults to 1
  "lazy_eval_results":0  // optional
}
```

If the file does not exist the script logs a warning and continues.

#### `contest/teams.csv`

One team per line, with three comma-separated fields:

```
# team_name,username,password
Team Alpha,alpha,alpha123
Team Beta,beta,beta456
```

Lines beginning with `#` are ignored. The username is reused as the team id
and as the account login.

### How the script talks to DomJudge

All requests use HTTP Basic auth with the admin credentials. The endpoints
involved are:

| Step             | Method | Endpoint                                        | Payload                              |
|------------------|--------|-------------------------------------------------|--------------------------------------|
| Create contest   | `POST` | `/api/contests`                                 | `multipart` upload of `contest.yaml` |
| Link problem     | `PUT`  | `/api/contests/{cid}/problems/{problem_id}`     | JSON: `label`, `color`, `rgb`, `points`, `lazyEvalResults` |
| Create group     | `POST` | `/api/users/groups`                             | JSON array (uploaded as `multipart` file field `json`) |
| Create teams     | `POST` | `/api/users/teams`                              | JSON array (same upload pattern)     |
| Create accounts  | `POST` | `/api/users/accounts`                           | JSON array (same upload pattern)     |

A few quirks worth knowing:

- `POST /api/contests` returns the new contest's external id as a quoted JSON
  string. The script strips the quotes before using it as `cid`.
- The bulk import endpoints (`/api/users/...`) take their JSON body as a
  `multipart/form-data` file field called `json`, not as a regular JSON
  body. The script wraps the payload in `files={"json": ...}` accordingly.
- The participant group is named `participants` and every team is assigned to
  it via `group_ids: ["participants"]`. Teams without a group are not
  visible on the scoreboard.

### Behavior on partial failure

The script is **not** idempotent. If a step fails (for example, a duplicate
contest short-name) it prints the HTTP status and body to stderr and continues
with the next step. Re-running the script will attempt to recreate the
already-existing entities and fail again on the same step.

To start fresh during testing, delete the existing contest and teams from the
DomJudge admin UI (or wipe the database by removing the `mariadb-data` Docker
volume) before re-running.

### Dependencies

The script depends only on [`requests`](https://pypi.org/project/requests/):

```bash
pip install requests
```

No other libraries from `contest/` are required.
