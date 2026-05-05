#!/bin/bash
# Local test of the EC2 UserData script — runs inside a Docker container.
# Sources lib/user-data.sh and overrides the AWS-specific functions with stubs.
#
# Run from the repo root:
#
#   docker run --rm \
#     -v /var/run/docker.sock:/var/run/docker.sock \
#     -v /tmp/domjudge-test:/mnt/domjudge \
#     -v "$(pwd)/infra:/infra" \
#     ubuntu:24.04 bash /infra/test-userdata.sh
set -euxo pipefail

export VOLUME_ID="vol-test00000000"
export ALLOCATION_ID="eipalloc-test000"
export AWS_REGION="us-east-1"

# Source the shared script — main() is NOT called yet (guarded by BASH_SOURCE check)
source /infra/lib/user-data.sh

# ── Override AWS-specific functions ───────────────────────────────────────────

setup_aws_resources() {
  echo "[STUB] EIP association skipped"
  echo "[STUB] EBS attach + wait skipped"
  echo "[STUB] NVMe device lookup skipped"
}

setup_storage() {
  echo "[STUB] /mnt/domjudge already provided via Docker bind-mount"
}

# Override install_packages to skip the AWS CLI v2 download (not needed, calls are stubbed)
install_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y docker.io git curl xfsprogs unzip
  # systemctl is stubbed below — docker is reached via the mounted host socket
}

# No systemd in Docker — stub systemctl so install_packages doesn't error
systemctl() {
  echo "[STUB] systemctl $*"
}
export -f systemctl

# Override start_app to tear down leftover containers before starting
# (test-only: on EC2 the instance is always fresh so there are no leftovers)
start_app() {
  git config --global --add safe.directory /mnt/domjudge
  cd /mnt/domjudge
  if [ ! -d ".git" ]; then
    git clone https://github.com/Rcontre360/domjudge-2026-ucv.git .
  else
    git pull
  fi
  docker-compose down --remove-orphans 2>/dev/null || true
  docker-compose up -d

  echo "Waiting for domserver to be healthy..."
  until [ "$(docker inspect -f '{{.State.Health.Status}}' domjudge-domserver 2>/dev/null)" = "healthy" ]; do
    sleep 5
  done

  docker cp setup.py domjudge-domserver:/setup.py
  docker exec domjudge-domserver python3 /setup.py
}

# ── Run ───────────────────────────────────────────────────────────────────────
main

echo ""
echo "=== Running containers ==="
docker ps
echo ""
echo "SUCCESS: UserData completed without errors."
