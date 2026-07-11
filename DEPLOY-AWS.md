# Deploy Versos to AWS — CI/CD with GitHub Actions

**Architecture:** backend (FastAPI + NAT) on **ECS Fargate** behind an **ALB**, DB on **RDS
Postgres**, frontend (Next.js) on **AWS Amplify**. Deploys are automated:

> App Runner stopped accepting new customers (Apr 2026) → the backend runs on ECS Fargate behind an
> internet-facing ALB (stable URL). The Amplify frontend proxies to it **server-side**, so plain HTTP
> is fine (the browser never calls the backend directly).

- **Backend** → GitHub Actions (`.github/workflows/deploy-backend.yml`) builds the image, pushes to
  **ECR**, and forces a new **ECS** deployment. Auth is **OIDC** (no stored AWS keys).
- **Frontend** → Amplify connects to the repo and auto-builds on every push (its own CI/CD).
- **Schema** → the backend self-initializes the DB on first boot (`backend/migrate.py`, idempotent),
  so there's no manual `psql` step.

> Do the one-time **bootstrap** below in **AWS CloudShell** (console → terminal icon) — it's signed
> in and has `aws`/`docker`/`psql`. (Local AWS CLI here is blocked by the corporate proxy's SSL; the
> GitHub Actions runners are on clean networking, so the pipeline itself works fine.)
>
> **Secrets:** `NVIDIA_API_KEY` is set ONLY in the App Runner service config — never committed.

---

## Part A — one-time bootstrap (CloudShell)

```bash
export AWS_REGION=us-east-1
export ACCT=$(aws sts get-caller-identity --query Account --output text)
export ECR=$ACCT.dkr.ecr.$AWS_REGION.amazonaws.com
export REPO=versos-backend
export GH_REPO=BennyDanielT/versos-agent-platform      # owner/repo
export DB_PASS='ChangeMe_strong_pw'
```

### 1. ECR repo
```bash
aws ecr create-repository --repository-name $REPO --region $AWS_REGION || true
```

### 2. RDS Postgres (public endpoint = throwaway demo DB)
```bash
aws rds create-db-instance \
  --db-instance-identifier versos-db --engine postgres --engine-version 16 \
  --db-instance-class db.t4g.micro --allocated-storage 20 \
  --master-username versos --master-user-password "$DB_PASS" \
  --db-name versos --publicly-accessible --region $AWS_REGION
aws rds wait db-instance-available --db-instance-identifier versos-db --region $AWS_REGION
export DB_HOST=$(aws rds describe-db-instances --db-instance-identifier versos-db \
  --query 'DBInstances[0].Endpoint.Address' --output text --region $AWS_REGION)
export SG=$(aws rds describe-db-instances --db-instance-identifier versos-db \
  --query 'DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId' --output text --region $AWS_REGION)
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 5432 --cidr 0.0.0.0/0 --region $AWS_REGION
echo "DATABASE_URL=postgresql://versos:$DB_PASS@$DB_HOST:5432/versos"
```
> No manual schema load — the backend runs `backend/migrate.py` on first boot (idempotent).
> ⚠️ Public DB is demo-only. Scope the SG to your IP, or delete the instance after finals.

### 3. GitHub OIDC → IAM role (lets Actions deploy without stored keys)
```bash
# OIDC provider (skip if it already exists)
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 || true

cat > trust.json <<JSON
{ "Version": "2012-10-17", "Statement": [{
  "Effect": "Allow",
  "Principal": { "Federated": "arn:aws:iam::$ACCT:oidc-provider/token.actions.githubusercontent.com" },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
    "StringLike": { "token.actions.githubusercontent.com:sub": "repo:$GH_REPO:*" }
  }
}]}
JSON
aws iam create-role --role-name versos-gh-deploy --assume-role-policy-document file://trust.json

cat > perms.json <<JSON
{ "Version": "2012-10-17", "Statement": [
  { "Effect": "Allow", "Action": "ecr:GetAuthorizationToken", "Resource": "*" },
  { "Effect": "Allow", "Action": [
      "ecr:BatchCheckLayerAvailability","ecr:InitiateLayerUpload","ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload","ecr:PutImage","ecr:BatchGetImage"],
    "Resource": "arn:aws:ecr:$AWS_REGION:$ACCT:repository/$REPO" },
  { "Effect": "Allow", "Action": "apprunner:StartDeployment", "Resource": "*" }
]}
JSON
aws iam put-role-policy --role-name versos-gh-deploy --policy-name deploy --policy-document file://perms.json
echo "AWS_DEPLOY_ROLE_ARN=arn:aws:iam::$ACCT:role/versos-gh-deploy"
```

### 4. First backend image (built by GitHub Actions — no local Docker)
CloudShell's Docker disk is too small for this image, so let the pipeline build it:
1. Set the repo secret/vars from step 5 first (`AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`, `ECR_REPOSITORY`).
2. **Actions → Deploy backend → Run workflow** on `main`. It builds + pushes `$REPO:latest` to ECR
   and skips the rollout (no ECS service yet). Wait for green.

Add `ecs:UpdateService` to the deploy role so future pushes can roll ECS:
```bash
cat > ecs-perms.json <<JSON
{ "Version": "2012-10-17", "Statement": [
  { "Effect": "Allow", "Action": ["ecs:UpdateService","ecs:DescribeServices"], "Resource": "*" }
]}
JSON
aws iam put-role-policy --role-name versos-gh-deploy --policy-name ecs-deploy --policy-document file://ecs-perms.json
```

### 4b. ECS Fargate service (ALB + cluster + service)
Set `DB_URL` + `NVIDIA_API_KEY`, then run the bootstrap script (clones nothing heavy, no Docker):
```bash
export DB_URL='postgresql://<user>:<password>@<rds-endpoint>:5432/versos'
export NVIDIA_API_KEY='nvapi-...'
bash deploy/ecs-bootstrap.sh          # from a `git clone` of the repo
```
It prints the **`BACKEND_URL` (http://<alb-dns>)** and the `ECS_CLUSTER`/`ECS_SERVICE` values.
`curl http://<alb-dns>/health` → `{"status":"ok"}` once the task is running (~2-3 min).

### 5. GitHub repo secrets + variables
Repo → Settings → Secrets and variables → Actions:
- **Secrets:** `AWS_DEPLOY_ROLE_ARN` (step 3).
- **Variables:** `AWS_REGION` (`us-east-1`), `ECR_REPOSITORY` (`versos-backend`),
  `ECS_CLUSTER` (`versos`), `ECS_SERVICE` (`versos-backend`).

### 6. Frontend on Amplify
Amplify console → New app → Host web app → connect the GitHub repo/branch. Amplify reads
`amplify.yml` (appRoot `frontend`), which writes `BACKEND_URL` into `.env.production` at build so
the SSR runtime picks it up. Set env var **`BACKEND_URL`** = the backend's ALB URL
(`http://<alb-dns>`). Deploy → copy the Amplify URL. Optionally tighten the backend's
`CORS_ORIGINS` to `["<amplify-url>"]` (ECS task env) and redeploy — not required, since the Next.js
proxy calls the backend server-side.

---

## Part B — the CI/CD flow (after bootstrap)

- **Push to `main`** touching `backend/**`, `nat_sandbox/**`, `Dockerfile`, or `requirements-deploy.txt`
  → the **Deploy backend** workflow builds → ECR → `ecs update-service --force-new-deployment` (the
  task def pins `:latest`, so ECS re-pulls the fresh image). Or run it manually via
  *Actions → Deploy backend → Run workflow*.
- **Any push** → **Amplify** rebuilds the frontend automatically.
- New RDS? The backend self-migrates on first boot. Existing DB? Migration is skipped (sentinel guard).

## Extras (Guardrails LLM rail / Phoenix)
NeMo Guardrails already ships in the image (flag-gated: flip `system_flags.input_rail` from the
Settings page). PII masking is the dependency-free regex masker. Phoenix is dev-only.

## Pause / resume (cost control — keeps everything, ~$2/day → ~$0.55/day)

Running cost is roughly **$2/day**: Fargate task (~$1, 1 vCPU/4 GB 24/7), ALB (~$0.55, charged
even idle), RDS `db.t4g.micro` (~$0.40). To park it overnight/between demos **without destroying
anything** (URLs, data, and config all survive), scale the task to 0 and stop the DB:

```bash
# ── PAUSE (nightly) ──────────────────────────────────────────────
curl -s -X POST http://<alb-dns>/sim/stop                       # stop the simulator (only per-call LLM cost)
aws ecs update-service --cluster versos --service versos-backend --desired-count 0 --region us-east-1
aws rds stop-db-instance --db-instance-identifier versos-db --region us-east-1
```
```bash
# ── RESUME (morning, ~3-4 min to healthy) ────────────────────────
aws rds start-db-instance --db-instance-identifier versos-db --region us-east-1
aws ecs update-service --cluster versos --service versos-backend --desired-count 1 --region us-east-1
# wait, then verify:
curl http://<alb-dns>/health          # → {"status":"ok"}
```

> `<alb-dns>` = `versos-alb-1284193883.us-east-1.elb.amazonaws.com` (the current ALB DNS).
> **Do NOT delete the ALB** — its DNS name is baked into Amplify's `BACKEND_URL`. Deleting it mints a
> new URL and breaks the frontend until you reconfigure it. The ~$0.55/day is the price of a stable URL.
> RDS auto-restarts after 7 days if left stopped; the backend self-migration is skipped on resume
> (schema already present), so no data is touched.

## Teardown (delete everything — stop the meter completely)
```bash
R=us-east-1
aws ecs update-service --cluster versos --service versos-backend --desired-count 0 --region $R
aws ecs delete-service --cluster versos --service versos-backend --force --region $R
aws ecs delete-cluster --cluster versos --region $R
# ALB + target group
ALB=$(aws elbv2 describe-load-balancers --names versos-alb --query 'LoadBalancers[0].LoadBalancerArn' --output text --region $R)
aws elbv2 delete-load-balancer --load-balancer-arn $ALB --region $R
aws elbv2 delete-target-group --target-group-arn $(aws elbv2 describe-target-groups --names versos-tg --query 'TargetGroups[0].TargetGroupArn' --output text --region $R) --region $R
# database
aws rds delete-db-instance --db-instance-identifier versos-db --skip-final-snapshot --region $R
# Amplify + ECR: delete the app / repo in the console (or `aws amplify delete-app`, `aws ecr delete-repository --force`).
```
