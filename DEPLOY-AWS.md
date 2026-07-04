# Deploy Versos to AWS (slim) — get a public URL

Two container images (backend, frontend) on **App Runner** + one **RDS Postgres**.
Run everything from **AWS CloudShell** (console → top-right terminal icon) — it's already
signed in to your account and has `docker`, `aws`, and `psql`. Nothing to install locally.

> **Secrets rule:** your `NVIDIA_API_KEY` is entered *only* in the CloudShell command / App
> Runner console below — never commit it, never paste it into chat. It lives in the App
> Runner service config (or Secrets Manager) at runtime.

Set these once at the top of your CloudShell session:

```bash
export AWS_REGION=us-east-1
export ACCT=$(aws sts get-caller-identity --query Account --output text)
export ECR=$ACCT.dkr.ecr.$AWS_REGION.amazonaws.com
export DB_PASS='ChangeMe_strong_pw'          # you choose; used below
```

---

## 1. Build + push both images to ECR

```bash
aws ecr create-repository --repository-name versos-backend  --region $AWS_REGION || true
aws ecr create-repository --repository-name versos-frontend --region $AWS_REGION || true
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR

# clone your branch in CloudShell
git clone <YOUR_REPO_URL> versos && cd versos
git checkout claude/versos-agent-platform-3qab10

# backend (context = repo root; uses ./Dockerfile)
docker build -t $ECR/versos-backend:latest .
docker push $ECR/versos-backend:latest

# frontend
docker build -t $ECR/versos-frontend:latest ./frontend
docker push $ECR/versos-frontend:latest
```

---

## 2. RDS Postgres (public endpoint for a throwaway demo DB)

> ⚠️ This makes the DB reachable from the internet to avoid VPC-connector setup. It only
> holds seeded demo data. **Lock the security group down or delete the instance after finals.**

```bash
aws rds create-db-instance \
  --db-instance-identifier versos-db \
  --engine postgres --engine-version 16 \
  --db-instance-class db.t4g.micro --allocated-storage 20 \
  --master-username versos --master-user-password "$DB_PASS" \
  --db-name versos --publicly-accessible \
  --region $AWS_REGION

# wait until available, then grab the endpoint
aws rds wait db-instance-available --db-instance-identifier versos-db --region $AWS_REGION
export DB_HOST=$(aws rds describe-db-instances --db-instance-identifier versos-db \
  --query 'DBInstances[0].Endpoint.Address' --output text --region $AWS_REGION)
echo "DB_HOST=$DB_HOST"
```

Open port 5432 on the instance's security group (demo-only; scope to your IP if you can):

```bash
export SG=$(aws rds describe-db-instances --db-instance-identifier versos-db \
  --query 'DBInstances[0].VpcSecurityGroups[0].VpcSecurityGroupId' --output text --region $AWS_REGION)
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 5432 --cidr 0.0.0.0/0 --region $AWS_REGION
```

Load all three schemas (creates tables + seeds the demo pipeline jobs):

```bash
export PGPASSWORD="$DB_PASS"
for f in schema index_hygiene pipeline_healer; do
  psql -h $DB_HOST -U versos -d versos -f nat_sandbox/severity_lab/sql/$f.sql
done
```

Your backend DSN (note: **asyncpg wants plain `postgresql://`**, which the app normalizes):
```
postgresql://versos:$DB_PASS@$DB_HOST:5432/versos
```

---

## 3. Backend on App Runner

Easiest via the **console** (auto-creates the ECR access role):
App Runner → **Create service** → Source: **Container registry** → Browse → `versos-backend:latest`
→ Deployment: Automatic → **Port `8090`** → **Environment variables**:

| Key | Value |
|---|---|
| `DATABASE_URL` | `postgresql://versos:<DB_PASS>@<DB_HOST>:5432/versos` |
| `NVIDIA_API_KEY` | *(your key — paste here in the console, free at build.nvidia.com)* |
| `CORS_ORIGINS` | `["*"]` (tighten to the frontend URL after step 4) |

Create → wait for **Running** → copy the service URL, e.g. `https://xxxx.us-east-1.awsapprunner.com`.
Sanity check: `curl <BACKEND_URL>/health` → `{"status":"ok"}`.

> No NVIDIA key yet? Leave it out — Index Hygiene + Pipeline Healer work without it; only
> Triage/Copilot needs it.

---

## 4. Frontend on App Runner

App Runner → **Create service** → `versos-frontend:latest` → **Port `3000`** →
Environment variable:

| Key | Value |
|---|---|
| `BACKEND_URL` | the backend service URL from step 3 |

Create → wait for **Running** → open the frontend URL. **That's your demo link.** 🎉

(Optional hardening: set the backend's `CORS_ORIGINS` to `["<frontend-url>"]` and redeploy.)

---

## Add the extras later (Guardrails / Presidio / Phoenix)
In `Dockerfile`, uncomment the EXTRAS block (installs `requirements-extras.txt` + the spaCy
model), rebuild/push the backend image, and for Phoenix set `PHOENIX_TRACING=1`. No app-code
change — the runtime auto-detects them.

## Teardown (stop the meter)
```bash
aws apprunner list-services --region $AWS_REGION      # get the two service ARNs
aws apprunner delete-service --service-arn <arn> --region $AWS_REGION   # x2
aws rds delete-db-instance --db-instance-identifier versos-db --skip-final-snapshot --region $AWS_REGION
```
