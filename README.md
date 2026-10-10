# Cloud Student Result and Attendance Portal

A small cloud-native portal on AWS. Teachers record attendance and marks, students look up
their attendance %, grade and exam eligibility, and a containerised ML service predicts
whether a student is **at risk**.

Covers the CloudOps capstone modules: VM web server, VPC/firewall, S3 + lifecycle, DynamoDB,
Lambda + API Gateway, Docker + Kubernetes, IAM + encryption, CloudWatch alarms, Terraform,
GitHub Actions, ML, and a no-code front end (optional).

## Folder map
| Folder | What it is |
|---|---|
| `terraform/` | All AWS resources as code (deliverable 2) |
| `lambda/` | Serverless API `portal.py` + unit tests |
| `frontend/` | Single-page portal served by nginx on EC2 |
| `service/` | Flask risk-prediction microservice + Dockerfile + tests |
| `k8s/` | Deployment, Service, Ingress manifests (deliverable 4) |
| `.github/workflows/` | CI/CD pipeline (deliverable 3) |
| `seed/` | Script that loads demo students |
| `docs/architecture.md` | Architecture document (deliverable 1) |

## Prerequisites
AWS account (free tier), AWS CLI configured (`aws configure`), Terraform, Docker, minikube + kubectl, Python 3.12, a GitHub account.
Turn on MFA for your root and admin users in the AWS console first.

## 1. Deploy the cloud part
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # edit email, your IP, admin key
terraform init
terraform apply
```
Outputs: `api_url`, `web_url`, `audit_bucket`. Confirm the two SNS subscription emails AWS sends you.

## 2. Load demo data and try it
```bash
cd ../seed
pip install -r requirements.txt
python seed_data.py <api_url> <admin_key>
curl <api_url>/students/ECE01
```
Open `web_url` in a browser to use the portal page.

## 3. Run the ML microservice on Kubernetes (local)
```bash
minikube start
eval $(minikube docker-env)
docker build -t risk-service ./service
kubectl apply -f k8s/
kubectl get pods
kubectl port-forward svc/risk-service 8080:80
```
In the portal page: look up `ECE03`, then click **Check risk** (URL `http://localhost:8080`).

## 4. CI/CD
Push the repo to GitHub. On every push the workflow runs the tests, `terraform validate`,
then builds and pushes the Docker image to GitHub Container Registry.

## 5. Clean up (avoid charges)
```bash
cd terraform && terraform destroy
minikube delete
```

## Run tests locally
```bash
pip install -r service/requirements.txt boto3
cd service && python train.py && pytest -q && cd ..
cd lambda && pytest -q
```

## Screenshots to take (deliverables 5 and 6)
EC2 running, portal page, `curl` output, CloudWatch dashboard, alarm in OK state, billing alarm,
S3 lifecycle rule, DynamoDB items, `kubectl get pods`, GitHub Actions green run.
