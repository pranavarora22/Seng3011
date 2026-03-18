# SENG3011 — Disease Surveillance Microservice

Collects, stores, and analyses global disease surveillance data from WHO APIs.
Covers influenza (1997+), RSV (2016+), and SARS-CoV-2 (all available history).

---

## Architecture

```
EventBridge (weekly)
    → Data Collector Lambda      — fetches from WHO APIs, writes S3 + DynamoDB

DynamoDB (seng3011-disease-records)
    → Retrieval Lambda URL       — query raw records by disease / country / week
    → Analytical Lambda URL      — z-score risk signals per disease + country
```

---

## API

Both APIs are public HTTPS Lambda Function URLs. Get the URLs after `terraform apply`:

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

Risk levels: `LOW` (z<1) · `MEDIUM` (1≤z<2) · `HIGH` (2≤z<3) · `CRITICAL` (z≥3) · `STABLE` · `INSUFFICIENT_DATA`

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
pip install -r requirements.txt

# Run tests
LOCAL_MOCK=True python -m pytest tests/ -v

# Run local mock pipeline (writes to tests/mock_s3/)
python test_run.py
```

---

## Deployment

```bash
# Package Lambda code
pip install -r requirements.txt --target package/
cp *.py openapi.yaml package/
cd package && zip -r ../deployment.zip . && cd ..

# Deploy
terraform init
terraform apply
```

Requires AWS Academy credentials active in your session.
