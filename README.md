# RiskDesk

An operational risk incident register with automatic triage. You log an incident; RiskDesk
classifies it into one of the seven Basel II event types and gives it a severity rating with
the reasons written down, so every rating can be explained to whoever reviews it.

**Stack:** Python 3.13, FastAPI, Pydantic, DynamoDB, Docker, AWS Lambda, AWS SAM,
GitHub Actions. Optional classification by Claude through the Anthropic SDK.

## How it works

```
POST /incidents ──> validate (Pydantic) ──> classify ──> score severity ──> store
                                              │                              │
                         rules (free, default)│                    DynamoDB on AWS,
                  or Claude, falling back to  │                    in memory locally
                  the rules on any failure ───┘
```

- **Classification.** A keyword classifier always works and costs nothing. If
  `ANTHROPIC_API_KEY` is set, Claude classifies instead using structured output, and any
  API error or refusal falls back to the rules, so logging an incident never fails because
  a model did.
- **Severity.** Rules, not a model, because a risk rating has to be explainable. The loss
  amount sets a band (low, medium, high, critical); customer impact and a possible
  regulatory breach each raise it one level; each step is recorded in `severity_reasons`.
- **Security.** Every incident endpoint needs the `X-API-Key` header. The deploy pipeline
  uses short-lived OIDC credentials, never stored AWS keys, and the function's IAM role sits
  under a permissions boundary, so even a misused deploy role can't grant it more than its
  own table and logs.

## Endpoints

| Method | Path | |
|---|---|---|
| GET | `/health` | No key needed |
| POST | `/incidents` | Log an incident; returns it classified and scored |
| GET | `/incidents?event_type=&severity=` | List, newest first, with optional filters |
| GET | `/incidents/{id}` | One incident |
| GET | `/summary` | Counts by event type and severity, total loss |

Interactive docs at `/docs` when running.

## Run it locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
API_KEY=local-dev-key-123456 .venv/bin/uvicorn app.main:app --reload
```

Or in the same container that runs on AWS:

```bash
docker build -t riskdesk . && docker run -p 8080:8080 -e API_KEY=local-dev-key-123456 riskdesk
```

## Tests

```bash
.venv/bin/pytest --cov=app
```

- **Unit:** classifier and severity rules.
- **Integration:** the API through FastAPI's test client, and the DynamoDB store against a
  mocked AWS (moto).
- **End to end:** `tests/e2e` calls the live deployment; CI runs it after every deploy.

## CI/CD

`.github/workflows/ci-cd.yml` runs on every push:

1. Lint (ruff) and the test suite with coverage.
2. Build the Docker image, run it, and call it over HTTP.
3. On `main`: deploy to AWS with SAM, then run the end-to-end tests against the live URL.

The same image runs locally and on Lambda: the
[Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter) extension turns
Lambda invocations into ordinary HTTP requests to uvicorn.

## Cost

Built to stay inside AWS's free allowances: Lambda (1M requests a month, always free),
DynamoDB at 1 read and 1 write unit (always free up to 25 each), and 14-day log retention.
Container image storage in ECR is a few cents a month. Claude classification is off unless
an API key is set.

## Deploying to your own AWS account (one-time setup)

1. **AWS account**, region Sydney (`ap-southeast-2`). Set a budget alert in AWS Budgets.
2. **CloudFormation console > Create stack > upload `infra/bootstrap.yaml`.** It creates the
   GitHub OIDC trust, the permissions boundary and the deploy role. Copy the `DeployRoleArn`
   output.
3. **GitHub repo > Settings > Secrets and variables > Actions:**
   - Variable `AWS_DEPLOY_ROLE_ARN` = the ARN from step 2.
   - Secret `RISKDESK_API_KEY` = any random string of 16+ characters.
   - Secret `ANTHROPIC_API_KEY` (optional) = turns on Claude classification.
4. Push to `main`. The deploy job prints the live URL.
