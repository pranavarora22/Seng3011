import requests
import pytest

ANALYTICAL_URL = "https://40gmhk7vb9.execute-api.us-east-1.amazonaws.com"

VALID_RISK_LEVELS = {
    "Normal",
    "Elevated",
    "Emerging Outbreak",
    "Sustained Outbreak",
    "Severe Outbreak",
    "Declining",
    "INSUFFICIENT_DATA",
}

REQUIRED_PAYLOAD_FIELDS = {
    "disease",
    "country_code",
    "epi_week",
    "current_cases",
    "seasonal_mean",
    "seasonal_std_dev",
    "seasonal_z_score",
    "growth_rate",
    "acceleration",
    "persistence_weeks",
    "risk_score",
    "risk_level",
}


@pytest.fixture(scope="session")
def influenza_response():
    return requests.get(ANALYTICAL_URL, params={"disease": "influenza"})


@pytest.fixture(scope="session")
def influenza_body(influenza_response):
    return influenza_response.json()


@pytest.fixture(scope="session")
def aus_response():
    return requests.get(ANALYTICAL_URL, params={"disease": "influenza", "country_code": "AUS"})


@pytest.fixture(scope="session")
def aus_body(aus_response):
    return aus_response.json()


# --- Basic health ---

def test_valid_request_returns_200(influenza_response):
    assert influenza_response.status_code == 200

def test_response_has_signals_field(influenza_body):
    assert "signals" in influenza_body

def test_response_has_count_field(influenza_body):
    assert "count" in influenza_body

def test_count_matches_signals_length(influenza_body):
    assert influenza_body["count"] == len(influenza_body["signals"])


# --- Schema validation ---

def test_each_signal_has_required_payload_fields(influenza_body):
    for signal in influenza_body["signals"]:
        if "payload" in signal:
            assert REQUIRED_PAYLOAD_FIELDS.issubset(signal["payload"].keys()), \
                f"Missing fields in signal: {signal}"

def test_each_signal_has_event_type(influenza_body):
    for signal in influenza_body["signals"]:
        if "payload" in signal:
            assert signal.get("event_type") == "PUBLIC_HEALTH_SIGNAL"

def test_each_signal_has_event_id(influenza_body):
    for signal in influenza_body["signals"]:
        if "payload" in signal:
            assert "event_id" in signal


# --- Risk level validation ---

def test_risk_level_is_always_valid(influenza_body):
    for signal in influenza_body["signals"]:
        if "payload" in signal:
            assert signal["payload"]["risk_level"] in VALID_RISK_LEVELS, \
                f"Unexpected risk_level: {signal['payload']['risk_level']}"

def test_risk_score_is_numeric(influenza_body):
    for signal in influenza_body["signals"]:
        if "payload" in signal and signal["payload"]["risk_level"] != "INSUFFICIENT_DATA":
            assert isinstance(signal["payload"]["risk_score"], (int, float))


# --- Disease filter ---

def test_disease_filter_rsv():
    r = requests.get(ANALYTICAL_URL, params={"disease": "rsv"})
    assert r.status_code == 200
    assert "signals" in r.json()

def test_disease_filter_sars_cov_2():
    r = requests.get(ANALYTICAL_URL, params={"disease": "sars-cov-2"})
    assert r.status_code == 200
    assert "signals" in r.json()

def test_unknown_disease_returns_400():
    r = requests.get(ANALYTICAL_URL, params={"disease": "fakevirus"})
    assert r.status_code == 400


# --- Country filter ---

def test_country_filter_returns_only_matching_country(aus_body):
    for signal in aus_body["signals"]:
        if "payload" in signal:
            assert signal["payload"]["country_code"] == "AUS"

def test_invalid_country_returns_no_error():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza", "country_code": "INVALID"})
    assert r.status_code == 200
    assert "signals" in r.json()


# --- Docs route ---

def test_docs_route_returns_200():
    r = requests.get(ANALYTICAL_URL + "/docs")
    assert r.status_code == 200

def test_docs_route_returns_html():
    r = requests.get(ANALYTICAL_URL + "/docs")
    assert "text/html" in r.headers.get("Content-Type", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
