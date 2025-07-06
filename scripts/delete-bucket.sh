#!/bin/bash
set -euo pipefail

if [[ -z "${BUCKET:-}" ]]; then
  echo "Set \$BUCKET first"; exit 1
fi

AWS_CLI_ARGS=()
[ -n "${AWS_PROFILE:-}" ] && AWS_CLI_ARGS+=(--profile "$AWS_PROFILE")

# --force empties the bucket then deletes it
aws s3 rb "s3://$BUCKET" --force "${AWS_CLI_ARGS[@]}"
echo "Bucket $BUCKET wiped and removed."
