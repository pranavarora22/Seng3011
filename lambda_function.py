import os
import json
import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Disease configuration registry
# ---------------------------------------------------------------------------

DISEASE_CONFIG = {
    "influenza": {
        "endpoint": "https://xmart-api-public.who.int/FLUMART/VIW_FNT",
        "cases_field": "INF_ALL",
        "country_field": "COUNTRY_CODE",
        "year_field": "ISO_YEAR",
        "week_field": "ISO_WEEK",
        "style": "flunet",
        "start_year": 1997,  # FluNet global surveillance data starts ~1997
    },
    "rsv": {
        # RSV data is in the same FluNet table as influenza (VIW_FNT), field RSV
        "endpoint": "https://xmart-api-public.who.int/FLUMART/VIW_FNT",
        "cases_field": "RSV",
        "country_field": "COUNTRY_CODE",
        "year_field": "ISO_YEAR",
        "week_field": "ISO_WEEK",
        "style": "flunet",
        "start_year": 2016,  # RSV reporting in VIW_FNT begins ~2016
    },
    "sars-cov-2": {
        # WHO NCOV weekly aggregate — no year filter supported, fetches all rows
        "endpoint": "https://xmart-api-public.who.int/NCOV/DATADOT_COVID_FACT_WEEKLY_AGG",
        "cases_field": "COVID_NEW_CASES",
        "country_field": "ISO3",   # already 3-letter, ISO2_TO_ISO3 falls back gracefully
        "date_field": "REPORT_DATE",
        "style": "covid",
        # No start_year — NCOV endpoint returns all rows, no Python year filtering applied
    },
}

# Inline ISO 3166-1 alpha-2 → alpha-3 mapping for the COVID endpoint.
# Avoids adding a pip dependency; covers all UN-recognised territories.
# fmt: off
ISO2_TO_ISO3 = {
    "AF":"AFG","AL":"ALB","DZ":"DZA","AD":"AND","AO":"AGO","AG":"ATG","AR":"ARG",
    "AM":"ARM","AU":"AUS","AT":"AUT","AZ":"AZE","BS":"BHS","BH":"BHR","BD":"BGD",
    "BB":"BRB","BY":"BLR","BE":"BEL","BZ":"BLZ","BJ":"BEN","BT":"BTN","BO":"BOL",
    "BA":"BIH","BW":"BWA","BR":"BRA","BN":"BRN","BG":"BGR","BF":"BFA","BI":"BDI",
    "CV":"CPV","KH":"KHM","CM":"CMR","CA":"CAN","CF":"CAF","TD":"TCD","CL":"CHL",
    "CN":"CHN","CO":"COL","KM":"COM","CG":"COG","CD":"COD","CR":"CRI","CI":"CIV",
    "HR":"HRV","CU":"CUB","CY":"CYP","CZ":"CZE","DK":"DNK","DJ":"DJI","DM":"DMA",
    "DO":"DOM","EC":"ECU","EG":"EGY","SV":"SLV","GQ":"GNQ","ER":"ERI","EE":"EST",
    "SZ":"SWZ","ET":"ETH","FJ":"FJI","FI":"FIN","FR":"FRA","GA":"GAB","GM":"GMB",
    "GE":"GEO","DE":"DEU","GH":"GHA","GR":"GRC","GD":"GRD","GT":"GTM","GN":"GIN",
    "GW":"GNB","GY":"GUY","HT":"HTI","HN":"HND","HU":"HUN","IS":"ISL","IN":"IND",
    "ID":"IDN","IR":"IRN","IQ":"IRQ","IE":"IRL","IL":"ISR","IT":"ITA","JM":"JAM",
    "JP":"JPN","JO":"JOR","KZ":"KAZ","KE":"KEN","KI":"KIR","KP":"PRK","KR":"KOR",
    "KW":"KWT","KG":"KGZ","LA":"LAO","LV":"LVA","LB":"LBN","LS":"LSO","LR":"LBR",
    "LY":"LBY","LI":"LIE","LT":"LTU","LU":"LUX","MG":"MDG","MW":"MWI","MY":"MYS",
    "MV":"MDV","ML":"MLI","MT":"MLT","MH":"MHL","MR":"MRT","MU":"MUS","MX":"MEX",
    "FM":"FSM","MD":"MDA","MC":"MCO","MN":"MNG","ME":"MNE","MA":"MAR","MZ":"MOZ",
    "MM":"MMR","NA":"NAM","NR":"NRU","NP":"NPL","NL":"NLD","NZ":"NZL","NI":"NIC",
    "NE":"NER","NG":"NGA","MK":"MKD","NO":"NOR","OM":"OMN","PK":"PAK","PW":"PLW",
    "PA":"PAN","PG":"PNG","PY":"PRY","PE":"PER","PH":"PHL","PL":"POL","PT":"PRT",
    "QA":"QAT","RO":"ROU","RU":"RUS","RW":"RWA","KN":"KNA","LC":"LCA","VC":"VCT",
    "WS":"WSM","SM":"SMR","ST":"STP","SA":"SAU","SN":"SEN","RS":"SRB","SC":"SYC",
    "SL":"SLE","SG":"SGP","SK":"SVK","SI":"SVN","SB":"SLB","SO":"SOM","ZA":"ZAF",
    "SS":"SSD","ES":"ESP","LK":"LKA","SD":"SDN","SR":"SUR","SE":"SWE","CH":"CHE",
    "SY":"SYR","TW":"TWN","TJ":"TJK","TZ":"TZA","TH":"THA","TL":"TLS","TG":"TGO",
    "TO":"TON","TT":"TTO","TN":"TUN","TR":"TUR","TM":"TKM","TV":"TUV","UG":"UGA",
    "UA":"UKR","AE":"ARE","GB":"GBR","US":"USA","UY":"URY","UZ":"UZB","VU":"VUT",
    "VE":"VEN","VN":"VNM","YE":"YEM","ZM":"ZMB","ZW":"ZWE","XK":"XKX",
}
# fmt: on

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

S3_BUCKET = os.environ.get("S3_BUCKET", "")
DYNAMO_TABLE = os.environ.get("DYNAMO_TABLE", "")
RAW_PREFIX = "raw-data"
CLEAN_PREFIX = "normalized-data"
LOCAL_RAW_PATH = os.path.join("tests", "mock_s3", "raw-data")
LOCAL_CLEAN_PATH = os.path.join("tests", "mock_s3", "normalized-data")


def is_local_mock() -> bool:
    return os.environ.get("LOCAL_MOCK", "").strip().lower() == "true"


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------


def fetch_odata_records(endpoint: str, year: int, year_field: str = "ISO_YEAR") -> list:
    """Fetch all OData records for a calendar year, following nextLink pagination."""
    url = f"{endpoint}?$filter={year_field} eq {year}"
    records = []
    while url:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        records.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
    return records


def fetch_covid_records(endpoint: str) -> list:
    """Fetch all COVID-19 records — NCOV endpoint doesn't support year-based OData filters."""
    url = endpoint
    records = []
    while url:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        data = response.json()
        records.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
    return records


# Backward-compatible wrapper so existing tests that patch fetch_flunet_records pass.
def fetch_flunet_records(year: int) -> list:
    return fetch_odata_records(DISEASE_CONFIG["influenza"]["endpoint"], year)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_flunet_style(raw: dict, disease: str, config: dict, timestamp: str) -> dict | None:
    """Parse a FluNet/RSV-style row (ISO_YEAR + ISO_WEEK + 3-letter country code)."""
    cases = raw.get(config["cases_field"])
    if not cases:
        return None
    country_code = raw.get(config["country_field"], "")
    epi_week = f"{raw[config['year_field']]}-W{int(raw[config['week_field']]):02d}"
    return {
        "event_id": f"{disease}-{country_code}-{epi_week}",
        "timestamp": timestamp,
        "event_type": "PUBLIC_HEALTH_RECORD",
        "domain": "HEALTH",
        "payload": {
            "disease": disease,
            "country_code": country_code,
            "epi_week": epi_week,
            "cases_detected": int(cases),
        },
    }


def parse_covid_style(raw: dict, disease: str, config: dict, timestamp: str) -> dict | None:
    """Parse a COVID-style row (Date_reported YYYY-MM-DD + 2-letter country code)."""
    cases = raw.get(config["cases_field"], 0)
    if not cases or int(cases) <= 0:
        return None
    iso2 = raw.get(config["country_field"], "")
    country_code = ISO2_TO_ISO3.get(iso2.upper(), iso2)
    date_str = raw.get(config["date_field"], "")
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        iso_year, iso_week, _ = dt.isocalendar()
        epi_week = f"{iso_year}-W{iso_week:02d}"
    except (ValueError, AttributeError):
        logger.warning("sars-cov-2: could not parse date %r — skipping row", date_str)
        return None
    return {
        "event_id": f"{disease}-{country_code}-{epi_week}",
        "timestamp": timestamp,
        "event_type": "PUBLIC_HEALTH_RECORD",
        "domain": "HEALTH",
        "payload": {
            "disease": disease,
            "country_code": country_code,
            "epi_week": epi_week,
            "cases_detected": int(cases),
        },
    }


# ---------------------------------------------------------------------------
# Disease processor
# ---------------------------------------------------------------------------


def process_disease(disease_name: str, config: dict) -> list:
    """Fetch and normalise records for one disease.

    In LOCAL_MOCK mode reads a pre-built fixture from raw-data/ and returns
    it directly (no HTTP calls). In live mode fetches from the WHO OData API
    and normalises each row into the project schema.
    """
    if is_local_mock():
        fixture = os.path.join(LOCAL_RAW_PATH, f"{disease_name}_who.json")
        if os.path.exists(fixture):
            with open(fixture, encoding="utf-8") as f:
                return json.load(f)
        logger.warning(
            "%s: LOCAL_MOCK mode, no fixture at %s — returning []", disease_name, fixture
        )
        return []

    timestamp = datetime.now(timezone.utc).isoformat()
    current_year = datetime.now(timezone.utc).year
    style = config.get("style", "flunet")

    raw = []
    if style == "covid":
        # NCOV endpoint has no year filter — fetch all rows and keep everything
        raw = fetch_covid_records(config["endpoint"])
    else:
        start_year = config.get("start_year", current_year)
        for year in range(start_year, current_year + 1):
            raw.extend(fetch_odata_records(config["endpoint"], year, config["year_field"]))

    records = []
    for r in raw:
        parsed = (
            parse_covid_style(r, disease_name, config, timestamp)
            if style == "covid"
            else parse_flunet_style(r, disease_name, config, timestamp)
        )
        if parsed:
            records.append(parsed)
    return records


# Backward-compatible wrapper so existing tests keep passing without changes.
def process_flunet_disease() -> list:
    return process_disease("influenza", DISEASE_CONFIG["influenza"])


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def save_output(disease_name: str, records: list) -> None:
    """Write normalised JSON to local disk or S3, then index into DynamoDB."""
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
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data, ContentType="application/json")
        logger.info(
            "Uploaded %s (%d records) to s3://%s/%s", filename, len(records), S3_BUCKET, key
        )
        _index_to_dynamo(records)


def _index_to_dynamo(records: list) -> None:
    """Batch-write records to DynamoDB for fast filtered queries."""
    if not DYNAMO_TABLE or not records:
        return
    import boto3

    dynamo = boto3.resource("dynamodb")
    table = dynamo.Table(DYNAMO_TABLE)
    with table.batch_writer() as batch:
        for rec in records:
            p = rec["payload"]
            batch.put_item(
                Item={
                    "pk": f"{p['disease']}#{p['country_code']}",  # main PK
                    "epi_week": p["epi_week"],                    # main SK
                    "disease": p["disease"],                      # GSI 1 PK
                    "country_code": p["country_code"],
                    "cases_detected": p["cases_detected"],
                    "event_id": rec["event_id"],
                    "timestamp": rec["timestamp"],
                }
            )
    logger.info("Indexed %d records to DynamoDB table %s", len(records), DYNAMO_TABLE)


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------


def lambda_handler(event, context):
    """Main Lambda entry point — collects all configured diseases."""
    logger.info("Starting data collection pipeline")
    results = {}

    for disease_name, config in DISEASE_CONFIG.items():
        try:
            records = process_disease(disease_name, config)
            save_output(disease_name, records)
            results[disease_name] = {"status": "success", "records": len(records)}
            logger.info("%s: processed %d records", disease_name, len(records))
        except Exception as e:
            logger.error("%s: failed — %s", disease_name, e, exc_info=True)
            results[disease_name] = {"status": "error", "message": str(e)}

    logger.info("Pipeline complete: %s", results)
    return {"statusCode": 200, "body": json.dumps(results)}
