#!/bin/bash
# Usage: ./connect.sh [path-to-private-key]
# Default key path: ~/domjudge_key
set -e

KEY="${1:-$HOME/domjudge_key}"
STACK="InfraStack"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"

if [ ! -f "$KEY" ]; then
  echo "Error: Private key not found at '$KEY'."
  echo "Usage: ./connect.sh /path/to/domjudge_key"
  exit 1
fi

IP=$(aws cloudformation describe-stacks \
  --stack-name "$STACK" \
  --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='StaticIP'].OutputValue" \
  --output text 2>/dev/null || true)

if [ -z "$IP" ] || [ "$IP" = "None" ]; then
  echo "Error: Could not retrieve instance IP from CloudFormation stack '$STACK'."
  echo "Make sure the stack is deployed and your AWS credentials are configured."
  exit 1
fi

echo "Connecting to ec2-user@$IP using key: $KEY"
exec ssh -i "$KEY" -o StrictHostKeyChecking=no ec2-user@"$IP"
