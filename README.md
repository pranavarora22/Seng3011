# SENG3011 — Disease Surveillance Microservice

Collects, stores, and analyses global disease surveillance data from WHO APIs.
Covers influenza (1997+), RSV (2016+), and SARS-CoV-2 (all available history).

---

## Architecture

```
EventBridge (weekly)
    → Data Collector Lambda      — fetches from WHO APIs, writes S3 + DynamoDB

DynamoDB (seng3011-disease-records)
    → Retrieval API Gateway      — query raw records by disease / country / week
    → Analytical API Gateway     — z-score risk signals per disease + country
```

---

## API

Both APIs are public HTTPS endpoints via API Gateway HTTP APIs. Get the URLs after deploying:

```bash
terraform output retrieval_function_url
terraform output analytical_model_function_url
```

### Retrieval API

Query raw weekly case records.

```
GET <retrieval_url>?disease=influenza&country_code=AUS&start_epi_week=2024-W01
```

| Parameter        | Description                                               |
| ---------------- | --------------------------------------------------------- |
| `disease`        | `influenza`, `rsv`, or `sars-cov-2`                       |
| `country_code`   | ISO3 code (e.g. `AUS`) or country name (e.g. `australia`) |
| `start_epi_week` | `YYYY-Www` inclusive start                                |
| `end_epi_week`   | `YYYY-Www` inclusive end                                  |
| `limit`          | Max results, 1–1000 (default 100)                         |

**Interactive docs:** `GET <retrieval_url>/docs`

### Analytical API

Z-score risk signals — one per (disease, country) for the most recent epi-week.

```
GET <analytical_url>?disease=influenza&country_code=AUS
```

Risk levels: `Normal` · `Elevated` · `Emerging Outbreak` · `Sustained Outbreak` · `Severe Outbreak` · `Declining` · `INSUFFICIENT_DATA`

**Interactive docs:** `GET <analytical_url>/docs`

---

## Data schema

```json
{
  "event_id": "influenza-AUS-2025-W03",
  "timestamp": "2026-03-18T00:00:00+00:00",
  "event_type": "PUBLIC_HEALTH_RECORD",
  "domain": "HEALTH",
  "payload": {
    "disease": "influenza",
    "country_code": "AUS",
    "epi_week": "2025-W03",
    "cases_detected": 142
  }
}
```

---

## Data Sources

| Disease    | WHO Endpoint                         | History       |
| ---------- | ------------------------------------ | ------------- |
| influenza  | `FLUMART/VIW_FNT` (field `INF_ALL`)  | ~1997 onwards |
| rsv        | `FLUMART/VIW_FNT` (field `RSV`)      | ~2016 onwards |
| sars-cov-2 | `NCOV/DATADOT_COVID_FACT_WEEKLY_AGG` | 2020 onwards  |

Updated every Monday at 00:00 UTC via EventBridge.

---

## Local development

```bash
# Install dependencies
pip install -r ../backend/requirements.txt pytest coverage flake8

# Run tests
LOCAL_MOCK=True python3 -m pytest ../backend/tests/ -v

# Run local mock pipeline (writes to tests/mock_s3/)
python3 ../backend/test_run.py

# Validate code quality
flake8 . --max-line-length=120
```

---

## Deployment

```bash
# One-command deploy (builds zip + imports existing resources + applies)
cd infra && ./deploy.sh                  # AWS Academy (default)
cd infra && ./deploy.sh --personal       # Personal AWS account

# Or manually:
cd infra && ./build.sh                  # Package Lambda code into deployment.zip
terraform init
terraform apply              # AWS Academy
terraform apply -var="use_lab_role=false"  # Personal account
```

After deploying, run the data collector Lambda once to populate the database:

**Console → Lambda → `seng3011-data-collector` → Test → `{}` → Run**

This fetches all historical data (~3 minutes, ~177k records).
