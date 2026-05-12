# UCV Judge

A self-hosted [DomJudge](https://www.domjudge.org/) deployment used to run
programming contests at the Universidad Central de Venezuela. The repository
bundles three things:

- A `docker-compose.yml` stack that starts a domserver, a MariaDB instance, and
  two judgehost workers.
- A CDK project under `infra/` that provisions an EC2 instance on AWS where
  this stack runs.
- Python scripts under `contest/` to create a contest and import the team
  accounts via the DomJudge REST API.

## Repository layout

```
.
├── docker-compose.yml      # DomJudge stack (domserver, mariadb, judgehosts)
├── setup.py                # Post-boot hook run inside the domserver container
├── .env.example            # Template for the runtime environment file
├── connect.sh              # SSH shortcut into the AWS instance
├── contest/                # Contest, teams, and upload script
│   ├── contest.yaml
│   ├── teams.csv
│   ├── problems.json
│   └── upload.py
├── infra/                  # AWS CDK stack
└── docs/                   # Detailed documentation (INFRA.md, SCRIPTS.md)
```

## Prerequisites

- Docker and Docker Compose v2 (the EC2 image installs them automatically; on a
  developer machine install them manually).
- Python 3.10+ with the `requests` package for the contest upload script.

## Configuring the environment

Copy the example file and adjust the values:

```bash
cp .env.example .env
```

The variables consumed by `docker-compose.yml` are:

| Variable             | Used by                                            |
|----------------------|----------------------------------------------------|
| `ADMIN_USERNAME`     | DomJudge admin account created on first boot.      |
| `ADMIN_PASSWORD`     | Password for the admin account above.              |
| `JUDGEHOST_PASSWORD` | Shared password the judgehost containers use to authenticate with the domserver. |
| `DOMSERVER_PORT`     | Host port the web UI listens on (default `8080`). |

The same `.env` is loaded by `contest/upload.py` to read the admin credentials.

## Starting the stack

From the repository root:

```bash
docker-compose up -d
```

The first run will pull the DomJudge images, initialize the MariaDB database,
and run `setup.py` inside the domserver to set the admin and judgehost
passwords from the `.env` file. After a minute or two the web UI is reachable
at `http://localhost:${DOMSERVER_PORT}` (default `http://localhost:8080`).

Useful commands:

```bash
docker-compose ps                       # check running services
docker-compose logs -f domserver        # tail domserver logs
docker-compose down                     # stop the stack (data is kept)
```

## Creating a contest and importing teams

Once the stack is healthy, run the upload script to create a contest and
register the teams listed in `contest/teams.csv`:

```bash
python3 contest/upload.py http://localhost:8080
```

The script reads:

- `contest/contest.yaml`  — contest metadata; the start time is filled in at
  upload time.
- `contest/problems.json` — labels and colors used by the contest scoreboard.
- `contest/teams.csv`     — one team per line, format
  `team_name,username,password`.

See [`docs/SCRIPTS.md`](docs/SCRIPTS.md) for a full description of the upload
flow and the DomJudge endpoints it uses.

## Running on AWS

The production instance lives on AWS and is provisioned by the CDK app in
`infra/`. Once deployed, the EBS volume is mounted at `/mnt/domjudge` and the
repository is cloned into it; the docker-compose stack runs from that
directory. SSH in with `./connect.sh` and `cd /mnt/domjudge` to inspect or
restart the stack.

See [`docs/INFRA.md`](docs/INFRA.md) for the full infrastructure description
and deployment instructions.
