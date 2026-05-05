#!/bin/bash
# Tears down the full DomJudge deployment, including the retained EBS volume.
# Run from the infra/ directory.
set -e

STACK="InfraStack"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== DomJudge Teardown ==="
echo "Stack : $STACK"
echo "Region: $REGION"
echo ""
read -rp "This will delete ALL resources including contest data. Continue? [y/N] " confirm
[ "$confirm" = "y" ] || { echo "Aborted."; exit 0; }

# Grab the EBS volume ID now — once the stack is gone we can't look it up via CloudFormation
VOLUME_ID=$(aws cloudformation describe-stack-resources \
  --stack-name "$STACK" \
  --region "$REGION" \
  --query "StackResources[?LogicalResourceId=='DomjudgeDataVolume'].PhysicalResourceId" \
  --output text 2>/dev/null || true)

echo ""
echo "Destroying CloudFormation stack (EC2, EIP, CloudFront, Key Pair)..."
cd "$DIR"
npx cdk destroy --force

# The EBS volume is retained by CloudFormation on purpose (protects data if
# the instance crashes mid-contest). We delete it explicitly here on teardown.
if [ -n "$VOLUME_ID" ] && [ "$VOLUME_ID" != "None" ]; then
  echo "Deleting retained EBS volume $VOLUME_ID..."
  aws ec2 delete-volume --volume-id "$VOLUME_ID" --region "$REGION"
  echo "Volume deleted."
else
  echo "No EBS volume found in stack (already deleted or stack was not deployed)."
fi

echo ""
echo "Teardown complete. All resources removed."
