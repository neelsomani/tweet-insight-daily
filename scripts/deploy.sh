#!/bin/bash

set -euo pipefail

# Load env vars
if [ ! -f .env ]; then
  echo "Missing .env file. Copy .env.template and fill it in."
  exit 1
fi
set -a && source .env && set +a

LAMBDA_NAME="tweet-insight-daily"
SNS_TOPIC_NAME="lambda-failures"
REGION="us-west-2"
ZIPFILE="function.zip"
HANDLER="lambda_function.lambda_handler"
ROLE_NAME="LambdaExecutionRole"

# AWS CLI profile handling
AWS_CLI_ARGS=()
[ -n "${AWS_PROFILE:-}" ] && AWS_CLI_ARGS+=(--profile "$AWS_PROFILE")

# Identify account and user
AWS_USER_ID=$(aws sts get-caller-identity "${AWS_CLI_ARGS[@]}" --query 'UserId' --output text 2>/dev/null || echo "")
ACCOUNT_ID=$(aws sts get-caller-identity "${AWS_CLI_ARGS[@]}" --query 'Account' --output text 2>/dev/null || echo "")
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

# Create IAM role if not exists
if ! aws iam get-role --role-name "$ROLE_NAME" "${AWS_CLI_ARGS[@]}" >/dev/null 2>&1; then
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document file://<(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Service": "lambda.amazonaws.com" },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
  ) "${AWS_CLI_ARGS[@]}"

  aws iam attach-role-policy --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole "${AWS_CLI_ARGS[@]}"
  aws iam attach-role-policy --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess "${AWS_CLI_ARGS[@]}"
fi

# Create S3 bucket if it doesn't exist
aws s3api create-bucket \
  --bucket "$BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION" \
  "${AWS_CLI_ARGS[@]}" || true

aws s3control put-public-access-block \
  --account-id "$ACCOUNT_ID" \
  --public-access-block-configuration '{
    "BlockPublicAcls": false,
    "IgnorePublicAcls": false,
    "BlockPublicPolicy": false,
    "RestrictPublicBuckets": false
  }' \
  "${AWS_CLI_ARGS[@]}"

aws s3api put-bucket-ownership-controls \
  --bucket "$BUCKET" \
  --ownership-controls '{
    "Rules": [{
      "ObjectOwnership": "ObjectWriter"
    }]
  }' \
  "${AWS_CLI_ARGS[@]}"

aws s3api put-bucket-policy --bucket "$BUCKET" --policy "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {
      \"Sid\": \"AllowPublicRead\",
      \"Effect\": \"Allow\",
      \"Principal\": \"*\",
      \"Action\": \"s3:GetObject\",
      \"Resource\": \"arn:aws:s3:::$BUCKET/*\"
    },
    {
      \"Sid\": \"DenyUnauthorizedWrite\",
      \"Effect\": \"Deny\",
      \"Principal\": \"*\",
      \"Action\": \"s3:PutObject\",
      \"Resource\": \"arn:aws:s3:::$BUCKET/*\",
      \"Condition\": {
        \"StringNotEquals\": {
          \"aws:userid\": \"$AWS_USER_ID\"
        }
      }
    }
  ]
}" "${AWS_CLI_ARGS[@]}"

# Create SNS topic
SNS_TOPIC_ARN=$(aws sns create-topic --name "$SNS_TOPIC_NAME" --query 'TopicArn' --output text "${AWS_CLI_ARGS[@]}")
aws sns subscribe --topic-arn "$SNS_TOPIC_ARN" --protocol email --notification-endpoint "$EMAIL" "${AWS_CLI_ARGS[@]}"
exit 1  # FIXME
# Zip deployment package
pip install openai --target .
zip -r "$ZIPFILE" .

# Assemble environment variables
ENV_VARS_JSON=$(jq -n \
  --arg OPENAI_API_KEY "$OPENAI_API_KEY" \
  --arg BUCKET "$BUCKET" \
  --arg AUTH_TOKEN "$AUTH_TOKEN" \
  --arg CT0 "$CT0" \
  --arg GUEST_ID "$GUEST_ID" \
  --arg PERSONALIZATION_ID "$PERSONALIZATION_ID" \
  --arg BEARER_TOKEN "$BEARER_TOKEN" \
  --arg QUERY_ID "$QUERY_ID" \
  '{
    OPENAI_API_KEY: $OPENAI_API_KEY,
    BUCKET: $BUCKET,
    AUTH_TOKEN: $AUTH_TOKEN,
    CT0: $CT0,
    GUEST_ID: $GUEST_ID,
    PERSONALIZATION_ID: $PERSONALIZATION_ID,
    BEARER_TOKEN: $BEARER_TOKEN,
    QUERY_ID: $QUERY_ID
  }')

# Create or update Lambda
aws lambda create-function \
  --function-name "$LAMBDA_NAME" \
  --runtime python3.10 \
  --handler "$HANDLER" \
  --timeout 300 \
  --memory-size 1024 \
  --zip-file "fileb://$ZIPFILE" \
  --region "$REGION" \
  --role "$ROLE_ARN" \
  --environment "Variables=$ENV_VARS_JSON" \
  "${AWS_CLI_ARGS[@]}" || \
aws lambda update-function-code \
  --function-name "$LAMBDA_NAME" \
  --zip-file "fileb://$ZIPFILE" \
  "${AWS_CLI_ARGS[@]}"

aws lambda update-function-configuration \
  --function-name "$LAMBDA_NAME" \
  --environment "Variables=$ENV_VARS_JSON" \
  "${AWS_CLI_ARGS[@]}"

# Retry config
aws lambda put-function-event-invoke-config \
  --function-name "$LAMBDA_NAME" \
  --maximum-retry-attempts 2 \
  --destination-config "{\"OnFailure\":{\"Destination\":\"$SNS_TOPIC_ARN\"}}" \
  "${AWS_CLI_ARGS[@]}"

# Create scheduled EventBridge rule
RULE_NAME="daily-tweet-job"
CRON_EXPR="cron(0 0 * * ? *)"

aws events put-rule --schedule-expression "$CRON_EXPR" --name "$RULE_NAME" --region "$REGION" "${AWS_CLI_ARGS[@]}"
aws events put-targets --rule "$RULE_NAME" \
  --targets "Id"="1","Arn"="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$LAMBDA_NAME" \
  "${AWS_CLI_ARGS[@]}"
aws lambda add-permission \
  --function-name "$LAMBDA_NAME" \
  --statement-id eventbridge \
  --action 'lambda:InvokeFunction' \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:$REGION:$ACCOUNT_ID:rule/$RULE_NAME" \
  "${AWS_CLI_ARGS[@]}"
