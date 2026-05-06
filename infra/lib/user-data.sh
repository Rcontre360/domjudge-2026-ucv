#!/bin/bash
# EC2 UserData script for the DomJudge instance.
# Expected env vars (injected by CDK before this runs):
#   VOLUME_ID      — EBS volume ID (e.g. vol-0abc123)
#   AWS_REGION     — AWS region (e.g. us-east-1)
#   DOMJUDGE_DIR   — app directory (default: /mnt/domjudge)
set -euxo pipefail

install_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y docker.io git nvme-cli curl xfsprogs
  systemctl start docker
  systemctl enable docker
  usermod -aG docker ubuntu
}

install_docker_compose() {
  curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
  chmod +x /usr/local/bin/docker-compose
}

setup_storage() {
  local vol_id_clean device
  vol_id_clean=$(echo "$VOLUME_ID" | sed 's/-//')
  # CloudFormation attaches the volume in parallel — wait for the NVMe device to appear
  until device=$(readlink -f /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_"$vol_id_clean" 2>/dev/null) && [ -b "$device" ]; do
    sleep 2
  done
  mkdir -p "${DOMJUDGE_DIR:-/mnt/domjudge}"
  blkid "$device" || mkfs -t xfs "$device"
  mount "$device" "${DOMJUDGE_DIR:-/mnt/domjudge}"
  echo "$device ${DOMJUDGE_DIR:-/mnt/domjudge} xfs defaults,nofail 0 2" >> /etc/fstab
}

start_app() {
  local dir="${DOMJUDGE_DIR:-/mnt/domjudge}"
  git config --global --add safe.directory "$dir"
  cd "$dir"
  if [ ! -d ".git" ]; then
    git clone https://github.com/Rcontre360/domjudge-2026-ucv.git .
  else
    git pull
  fi
  docker-compose up -d
}

main() {
  export HOME=/root
  install_packages
  install_docker_compose
  setup_storage
  start_app
}

# Run main only when executed directly, not when sourced (allows test overrides)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main
fi
