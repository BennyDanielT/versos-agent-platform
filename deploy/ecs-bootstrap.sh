#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# One-time ECS Fargate bootstrap for the Versos backend (run in AWS CloudShell).
# App Runner stopped accepting new customers (Apr 2026), so the backend runs on
# ECS Fargate behind an internet-facing ALB (stable URL across redeploys).
#
# The container image is already in ECR (built + pushed by GitHub Actions).
# This script does NOT build anything — it just wires up AWS infra.
#
# Before running, export these (edit the two secrets):
#   export AWS_REGION=us-east-1
#   export ACCT=$(aws sts get-caller-identity --query Account --output text)
#   export DB_URL='postgresql://<user>:<password>@<rds-endpoint>:5432/versos'
#   export NVIDIA_API_KEY='nvapi-...'
# Then:  bash deploy/ecs-bootstrap.sh
# ---------------------------------------------------------------------------
set -euo pipefail

: "${AWS_REGION:?set AWS_REGION}"; : "${ACCT:?set ACCT}"
: "${DB_URL:?set DB_URL}"; : "${NVIDIA_API_KEY:?set NVIDIA_API_KEY}"

REPO=versos-backend
IMAGE=$ACCT.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO:latest
CLUSTER=versos
SERVICE=versos-backend

echo "== default VPC + subnets =="
VPC=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION")
SUBNETS=$(aws ec2 describe-subnets --filters Name=vpc-id,Values="$VPC" \
  --query 'Subnets[].SubnetId' --output text --region "$AWS_REGION" | tr '\t' ',')
echo "VPC=$VPC  SUBNETS=$SUBNETS"

echo "== ECS task execution role (pull ECR + write logs) =="
aws iam create-role --role-name versos-ecs-exec \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  2>/dev/null || echo "  (role exists)"
aws iam attach-role-policy --role-name versos-ecs-exec \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
EXEC_ROLE=arn:aws:iam::$ACCT:role/versos-ecs-exec

echo "== log group =="
aws logs create-log-group --log-group-name /ecs/versos-backend --region "$AWS_REGION" \
  2>/dev/null || echo "  (log group exists)"

echo "== security groups =="
ALB_SG=$(aws ec2 create-security-group --group-name versos-alb-sg --description "Versos ALB" \
  --vpc-id "$VPC" --query GroupId --output text --region "$AWS_REGION" 2>/dev/null \
  || aws ec2 describe-security-groups --filters Name=group-name,Values=versos-alb-sg Name=vpc-id,Values="$VPC" \
       --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION")
aws ec2 authorize-security-group-ingress --group-id "$ALB_SG" --protocol tcp --port 80 \
  --cidr 0.0.0.0/0 --region "$AWS_REGION" 2>/dev/null || true
SVC_SG=$(aws ec2 create-security-group --group-name versos-svc-sg --description "Versos ECS tasks" \
  --vpc-id "$VPC" --query GroupId --output text --region "$AWS_REGION" 2>/dev/null \
  || aws ec2 describe-security-groups --filters Name=group-name,Values=versos-svc-sg Name=vpc-id,Values="$VPC" \
       --query 'SecurityGroups[0].GroupId' --output text --region "$AWS_REGION")
aws ec2 authorize-security-group-ingress --group-id "$SVC_SG" --protocol tcp --port 8090 \
  --source-group "$ALB_SG" --region "$AWS_REGION" 2>/dev/null || true
echo "ALB_SG=$ALB_SG  SVC_SG=$SVC_SG"

echo "== task definition =="
cat > /tmp/taskdef.json <<JSON
{
  "family": "versos-backend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "$EXEC_ROLE",
  "containerDefinitions": [{
    "name": "backend",
    "image": "$IMAGE",
    "essential": true,
    "portMappings": [{"containerPort": 8090, "protocol": "tcp"}],
    "environment": [
      {"name": "DATABASE_URL", "value": "$DB_URL"},
      {"name": "NVIDIA_API_KEY", "value": "$NVIDIA_API_KEY"},
      {"name": "CORS_ORIGINS", "value": "[\"*\"]"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/versos-backend",
        "awslogs-region": "$AWS_REGION",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }]
}
JSON
aws ecs register-task-definition --cli-input-json file:///tmp/taskdef.json --region "$AWS_REGION" >/dev/null

echo "== ALB + target group + listener =="
ALB_ARN=$(aws elbv2 create-load-balancer --name versos-alb --type application \
  --subnets ${SUBNETS//,/ } --security-groups "$ALB_SG" \
  --query 'LoadBalancers[0].LoadBalancerArn' --output text --region "$AWS_REGION" 2>/dev/null \
  || aws elbv2 describe-load-balancers --names versos-alb \
       --query 'LoadBalancers[0].LoadBalancerArn' --output text --region "$AWS_REGION")
TG_ARN=$(aws elbv2 create-target-group --name versos-tg --protocol HTTP --port 8090 \
  --vpc-id "$VPC" --target-type ip --health-check-path /health \
  --query 'TargetGroups[0].TargetGroupArn' --output text --region "$AWS_REGION" 2>/dev/null \
  || aws elbv2 describe-target-groups --names versos-tg \
       --query 'TargetGroups[0].TargetGroupArn' --output text --region "$AWS_REGION")
aws elbv2 create-listener --load-balancer-arn "$ALB_ARN" --protocol HTTP --port 80 \
  --default-actions Type=forward,TargetGroupArn="$TG_ARN" --region "$AWS_REGION" 2>/dev/null \
  || echo "  (listener exists)"
ALB_DNS=$(aws elbv2 describe-load-balancers --load-balancer-arns "$ALB_ARN" \
  --query 'LoadBalancers[0].DNSName' --output text --region "$AWS_REGION")

echo "== ECS service-linked role (needed for the first ECS service in an account) =="
aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com 2>/dev/null \
  || echo "  (already exists)"

echo "== cluster + service =="
aws ecs create-cluster --cluster-name "$CLUSTER" --region "$AWS_REGION" >/dev/null 2>&1 || true

# Is the service already there and ACTIVE? (re-runs update instead of failing)
EXISTS=$(aws ecs describe-services --cluster "$CLUSTER" --services "$SERVICE" \
  --query 'services[?status==`ACTIVE`].serviceName' --output text --region "$AWS_REGION" 2>/dev/null || true)
if [ -n "$EXISTS" ]; then
  echo "  (service exists → forcing new deployment)"
  aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" \
    --task-definition versos-backend --force-new-deployment --region "$AWS_REGION" >/dev/null
else
  # No suppression here — if create fails we want to SEE why.
  aws ecs create-service \
    --cluster "$CLUSTER" --service-name "$SERVICE" \
    --task-definition versos-backend \
    --desired-count 1 --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SVC_SG],assignPublicIp=ENABLED}" \
    --load-balancers "targetGroupArn=$TG_ARN,containerName=backend,containerPort=8090" \
    --health-check-grace-period-seconds 120 \
    --region "$AWS_REGION" >/dev/null
  echo "  (service created)"
fi

echo
echo "=========================================================="
echo " BACKEND_URL = http://$ALB_DNS"
echo " (set this as BACKEND_URL in Amplify env vars)"
echo " Health check: curl http://$ALB_DNS/health   (allow ~2-3 min for the task to start)"
echo
echo " GitHub repo VARIABLES to add for push-to-deploy:"
echo "   ECS_CLUSTER = $CLUSTER"
echo "   ECS_SERVICE = $SERVICE"
echo "=========================================================="
