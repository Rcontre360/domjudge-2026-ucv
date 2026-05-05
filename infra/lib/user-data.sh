#!/bin/bash
# EC2 UserData script for the DomJudge instance.
# Expected env vars (injected by CDK before this runs):
#   VOLUME_ID      — EBS volume ID (e.g. vol-0abc123)
#   ALLOCATION_ID  — EIP allocation ID (e.g. eipalloc-0abc123)
#   AWS_REGION     — AWS region (e.g. us-east-1)
set -euxo pipefail

install_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y docker.io git nvme-cli curl xfsprogs unzip
  systemctl start docker
  systemctl enable docker
  # AWS CLI v2 (removed from Ubuntu 24.04 apt repos)
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
  unzip -q /tmp/awscliv2.zip -d /tmp && /tmp/aws/install
}

setup_aws_resources() {
  # Fetch instance ID via IMDSv2
  TOKEN=$(curl -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
  INSTANCE_ID=$(curl -H "X-aws-ec2-metadata-token: $TOKEN" -s http://169.254.169.254/latest/meta-data/instance-id)

  # Associate the static EIP — ALLOCATION_ID is used, not the public IP
  aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOCATION_ID" --region "$AWS_REGION"

  # Attach the persistent EBS volume and wait until it's ready
  aws ec2 attach-volume --volume-id "$VOLUME_ID" --instance-id "$INSTANCE_ID" --device /dev/sdf --region "$AWS_REGION"
  aws ec2 wait volume-in-use --volume-ids "$VOLUME_ID" --region "$AWS_REGION"
  sleep 5

  # On Nitro (t3), /dev/sdf is exposed as an NVMe device — resolve via the stable by-id symlink
  DEVICE=$(readlink -f /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_"$(echo "$VOLUME_ID" | sed 's/-//')")
}

setup_storage() {
  mkdir -p /mnt/domjudge
  blkid "$DEVICE" || mkfs -t xfs "$DEVICE"
  mount "$DEVICE" /mnt/domjudge
  echo "$DEVICE /mnt/domjudge xfs defaults,nofail 0 2" >> /etc/fstab
}

install_docker_compose() {
  curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
  chmod +x /usr/local/bin/docker-compose
}

start_app() {
  git config --global --add safe.directory /mnt/domjudge
  cd /mnt/domjudge
  if [ ! -d ".git" ]; then
    git clone https://github.com/Rcontre360/domjudge-2026-ucv.git .
  else
    git pull
  fi
  docker-compose up -d

  # Wait for domserver to pass its health check before running setup
  echo "Waiting for domserver to be healthy..."
  until [ "$(docker inspect -f '{{.State.Health.Status}}' domjudge-domserver 2>/dev/null)" = "healthy" ]; do
    sleep 5
  done

  # setup.py runs inside the domserver container — it needs bin/console and mysql,
  # which only exist there. The container already has ADMIN_PASSWORD etc. from .env via compose.
  docker cp setup.py domjudge-domserver:/setup.py
  docker exec domjudge-domserver python3 /setup.py
}

main() {
  install_packages
  setup_aws_resources
  setup_storage
  install_docker_compose
  start_app
}

# Run main only when executed directly, not when sourced (allows test overrides)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main
fi
