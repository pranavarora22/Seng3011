import os
import io
import json
import logging
import pandas as pd
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DISEASE_CONFIG = {
    "influenza": {
        "file": "influenza.csv",
        "date_col_candidates": ["Week Ending (Friday)", "Week ending (Friday)"],
        "date_format": "%d/%m/%Y",
        "state_col": "State",
        "mode": "date_column",
    },
    "salmonella": {
        "file": "salmonella.csv",
        "date_col_candidates": ["Week ending (Friday)", "Week Ending (Friday)"],
        "date_format": "%d/%m/%Y",
        "state_col": "State",
        "mode": "date_column",
    },
    "meningococcal": {
        "file": "meningococcal.csv",
        "year_col": "Year",
        "month_col": "Month",
        "state_col": "State",
        "mode": "year_month",
    },
    "pneumococcal": {
        "file": "pneumococcal.csv",
        "year_col": "Year",
        "state_col": "State",
        "mode": "year_only",
    },
}

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}

S3_BUCKET = os.environ.get("S3_BUCKET", "")
RAW_PREFIX = "raw-data"
CLEAN_PREFIX = "normalized-data"
LOCAL_RAW_PATH = os.path.join("tests", "mock_s3", "raw-data")
LOCAL_CLEAN_PATH = os.path.join("tests", "mock_s3", "normalized-data")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_local_mock():
    """Check if we should use local file I/O instead of S3."""
    return os.environ.get("LOCAL_MOCK", "").strip().lower() == "true"


def find_header_row(filepath_or_buffer):
    """Scan the first 20 rows to find the header containing 'State'."""
    preview = pd.read_csv(filepath_or_buffer, header=None, nrows=20,
                          encoding="utf-8", on_bad_lines="skip")
    for idx, row in preview.iterrows():
        if "State" in row.values:
            return idx
    raise ValueError("Could not find header row containing 'State'")


def read_csv(disease_name, config):
    """Read a disease CSV, auto-detecting the header row."""
    filename = config["file"]

    if is_local_mock():
        path = os.path.join(LOCAL_RAW_PATH, filename)
        header_row = find_header_row(path)
        df = pd.read_csv(path, header=0, skiprows=range(0, header_row),
                         encoding="utf-8", on_bad_lines="skip")
    else:
        import boto3
        s3 = boto3.client("s3")
        key = f"{RAW_PREFIX}/{filename}"
        obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
        raw = obj["Body"].read().decode("utf-8")
        header_row = find_header_row(io.StringIO(raw))
        df = pd.read_csv(io.StringIO(raw), header=0,
                         skiprows=range(0, header_row),
                         encoding="utf-8", on_bad_lines="skip")

    df.columns = df.columns.str.strip()
    logger.info("%s: loaded %d rows, columns: %s",
                disease_name, len(df), list(df.columns))
    return df


def resolve_column(df, candidates):
    """Return the first matching column name from candidates."""
    for col in candidates:
        if col in df.columns:
            return col
    raise ValueError(
        f"None of {candidates} found in columns {list(df.columns)}"
    )


def normalize_state(state):
    """Normalize Australian state codes to uppercase."""
    if pd.isna(state):
        return None
    return str(state).strip().upper()


def build_records(disease_name, grouped_df):
    """Convert a grouped DataFrame into the universal JSON schema records."""
    timestamp = datetime.now(timezone.utc).isoformat()
    records = []
    for _, row in grouped_df.iterrows():
        records.append({
            "event_id": f"{disease_name}-{row['state']}-{row['date']}",
            "timestamp": timestamp,
            "event_type": "PUBLIC_HEALTH_RECORD",
            "domain": "HEALTH",
            "payload": {
                "disease": disease_name,
                "state": row["state"],
                "date": row["date"],
                "cases_detected": int(row["cases_detected"]),
            },
        })
    return records


def distribute_annual_to_weeks(year, state, total_cases):
    """Distribute annual cases evenly across 52 weekly Friday dates.

    Returns a list of (date_str, cases) tuples.
    """
    fridays = pd.date_range(
        start=f"{year}-01-01", periods=52, freq="W-FRI"
    )
    base = total_cases // 52
    remainder = total_cases % 52
    result = []
    for i, friday in enumerate(fridays):
        cases = base + (1 if i < remainder else 0)
        result.append((friday.strftime("%Y-%m-%d"), cases))
    return result

# ---------------------------------------------------------------------------
# Disease processors
# ---------------------------------------------------------------------------

def process_date_column_disease(disease_name, config):
    """Process diseases that have an explicit date column (influenza, salmonella)."""
    df = read_csv(disease_name, config)
    date_col = resolve_column(df, config["date_col_candidates"])
    state_col = config["state_col"]

    df["date"] = pd.to_datetime(
        df[date_col], format=config["date_format"],
        dayfirst=True, errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    df["state"] = df[state_col].apply(normalize_state)

    df = df.dropna(subset=["date", "state"])
    grouped = (df.groupby(["state", "date"])
                 .size()
                 .reset_index(name="cases_detected"))
    return build_records(disease_name, grouped)


def process_year_month_disease(disease_name, config):
    """Process diseases with Year + Month columns (meningococcal)."""
    df = read_csv(disease_name, config)
    year_col = config["year_col"]
    month_col = config["month_col"]
    state_col = config["state_col"]

    df["month_num"] = df[month_col].map(MONTH_MAP)
    df["date"] = df.apply(
        lambda r: f"{int(r[year_col])}-{int(r['month_num']):02d}-01"
        if pd.notna(r["month_num"]) else None,
        axis=1,
    )
    df["state"] = df[state_col].apply(normalize_state)

    df = df.dropna(subset=["date", "state"])
    grouped = (df.groupby(["state", "date"])
                 .size()
                 .reset_index(name="cases_detected"))
    return build_records(disease_name, grouped)


def process_year_only_disease(disease_name, config):
    """Process diseases with only a Year column (pneumococcal).

    Distributes annual case totals evenly across 52 weekly records.
    """
    df = read_csv(disease_name, config)
    year_col = config["year_col"]
    state_col = config["state_col"]

    df["state"] = df[state_col].apply(normalize_state)
    df = df.dropna(subset=["state"])

    annual = (df.groupby(["state", year_col])
                .size()
                .reset_index(name="total_cases"))

    timestamp = datetime.now(timezone.utc).isoformat()
    records = []
    for _, row in annual.iterrows():
        weekly = distribute_annual_to_weeks(
            int(row[year_col]), row["state"], int(row["total_cases"])
        )
        for date_str, cases in weekly:
            records.append({
                "event_id": f"{disease_name}-{row['state']}-{date_str}",
                "timestamp": timestamp,
                "event_type": "PUBLIC_HEALTH_RECORD",
                "domain": "HEALTH",
                "payload": {
                    "disease": disease_name,
                    "state": row["state"],
                    "date": date_str,
                    "cases_detected": cases,
                },
            })
    return records


PROCESSORS = {
    "date_column": process_date_column_disease,
    "year_month": process_year_month_disease,
    "year_only": process_year_only_disease,
}

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_output(disease_name, records):
    """Write normalized JSON records to local disk or S3."""
    filename = f"{disease_name}_clean.json"
    data = json.dumps(records, indent=2)

    if is_local_mock():
        os.makedirs(LOCAL_CLEAN_PATH, exist_ok=True)
        path = os.path.join(LOCAL_CLEAN_PATH, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
        logger.info("Saved %s (%d records) to %s", filename, len(records), path)
    else:
        import boto3
        s3 = boto3.client("s3")
        key = f"{CLEAN_PREFIX}/{filename}"
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data,
                      ContentType="application/json")
        logger.info("Uploaded %s (%d records) to s3://%s/%s",
                    filename, len(records), S3_BUCKET, key)

# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """Main Lambda entry point. Processes all configured diseases."""
    logger.info("Starting data collection pipeline")
    results = {}

    for disease_name, config in DISEASE_CONFIG.items():
        try:
            processor = PROCESSORS[config["mode"]]
            records = processor(disease_name, config)
            save_output(disease_name, records)
            results[disease_name] = {
                "status": "success",
                "records": len(records),
            }
            logger.info("%s: processed %d records", disease_name, len(records))
        except Exception as e:
            logger.error("%s: processing failed — %s", disease_name, e,
                         exc_info=True)
            results[disease_name] = {
                "status": "error",
                "message": str(e),
            }

    logger.info("Pipeline complete: %s", results)
    return {"statusCode": 200, "body": json.dumps(results)}
