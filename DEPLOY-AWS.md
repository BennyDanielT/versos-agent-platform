# Deploy Versos to AWS — CI/CD with GitHub Actions

**Architecture:** backend (FastAPI + NAT) on **App Runner**, DB on **RDS Postgres**, frontend
(Next.js) on **AWS Amplify**. Deploys are automated:

- **Backend** → GitHub Actions (`.github/workflows/deploy-backend.yml`) builds the image, pushes to
  **ECR**, and triggers an **App Runner** deployment. Auth is **OIDC** (no stored AWS keys).
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

### 4. First backend image + App Runner service
Push an initial image so App Runner has something to point at:
```bash
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR
git clone https://github.com/$GH_REPO versos && cd versos
docker build -t $ECR/$REPO:latest . && docker push $ECR/$REPO:latest
```
Then in the **App Runner console** → Create service → Container registry → `$REPO:latest`:
- **Deployment trigger: Manual** (the workflow controls rollouts).
- **Port: 8090**
- **Env vars:** `DATABASE_URL` (from step 2), `NVIDIA_API_KEY` (your key), `CORS_ORIGINS=["*"]`.
- Create → copy the **service ARN** and the **service URL**; `curl <URL>/health` → `{"status":"ok"}`.

### 5. GitHub repo secrets + variables
Repo → Settings → Secrets and variables → Actions:
- **Secrets:** `AWS_DEPLOY_ROLE_ARN` (step 3), `APPRUNNER_SERVICE_ARN` (step 4).
- **Variables:** `AWS_REGION` (e.g. `us-east-1`), `ECR_REPOSITORY` (`versos-backend`).

### 6. Frontend on Amplify
Amplify console → New app → Host web app → connect the GitHub repo/branch. Amplify reads
`amplify.yml` (appRoot `frontend`). Set env var **`BACKEND_URL`** = the App Runner backend URL.
Deploy → copy the Amplify URL. Then set the backend's `CORS_ORIGINS=["<amplify-url>"]` (App Runner
env) and redeploy for a tighter CORS.

---

## Part B — the CI/CD flow (after bootstrap)

- **Push to `main`** touching `backend/**`, `nat_sandbox/**`, `Dockerfile`, or `requirements-deploy.txt`
  → the **Deploy backend** workflow builds → ECR → App Runner. (Or run it manually via
  *Actions → Deploy backend → Run workflow*.)
- **Any push** → **Amplify** rebuilds the frontend automatically.
- New RDS? The backend self-migrates on first boot. Existing DB? Migration is skipped (sentinel guard).

## Extras (Guardrails LLM rail / Phoenix)
NeMo Guardrails already ships in the image (flag-gated: flip `system_flags.input_rail` from the
Settings page). PII masking is the dependency-free regex masker. Phoenix is dev-only.

## Teardown (stop the meter)
```bash
aws apprunner list-services --region $AWS_REGION      # get the service ARN
aws apprunner delete-service --service-arn <arn> --region $AWS_REGION
aws rds delete-db-instance --db-instance-identifier versos-db --skip-final-snapshot --region $AWS_REGION
# Amplify: delete the app in the console.
```
