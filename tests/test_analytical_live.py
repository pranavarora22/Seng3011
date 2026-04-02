import requests
import pytest
 
ANALYTICAL_URL = "https://ukswk4og70.execute-api.us-east-1.amazonaws.com"
 
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
 
 
# --- Basic health ---
 
def test_valid_request_returns_200():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza"})
    assert r.status_code == 200
 
def test_response_has_signals_field():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza"})
    body = r.json()
    assert "signals" in body
 
def test_response_has_count_field():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza"})
    body = r.json()
    assert "count" in body
 
def test_count_matches_signals_length():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza"})
    body = r.json()
    assert body["count"] == len(body["signals"])
 
 
# --- Schema validation ---
 
def test_each_signal_has_required_payload_fields():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza"})
    body = r.json()
    for signal in body["signals"]:
        if "payload" in signal:
            assert REQUIRED_PAYLOAD_FIELDS.issubset(signal["payload"].keys()), \
                f"Missing fields in signal: {signal}"
 
def test_each_signal_has_event_type():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza"})
    body = r.json()
    for signal in body["signals"]:
        if "payload" in signal:  # skip error entries
            assert signal.get("event_type") == "PUBLIC_HEALTH_SIGNAL"
 
def test_each_signal_has_event_id():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza"})
    body = r.json()
    for signal in body["signals"]:
        if "payload" in signal:  # skip error entries
            assert "event_id" in signal
 
 
# --- Risk level validation ---
 
def test_risk_level_is_always_valid():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza"})
    body = r.json()
    for signal in body["signals"]:
        if "payload" in signal:
            assert signal["payload"]["risk_level"] in VALID_RISK_LEVELS, \
                f"Unexpected risk_level: {signal['payload']['risk_level']}"
 
def test_risk_score_is_numeric():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza"})
    body = r.json()
    for signal in body["signals"]:
        if "payload" in signal and signal["payload"]["risk_level"] != "INSUFFICIENT_DATA":
            assert isinstance(signal["payload"]["risk_score"], (int, float))
 
 
# --- Disease filter ---
 
def test_disease_filter_rsv():
    r = requests.get(ANALYTICAL_URL, params={"disease": "rsv"})
    assert r.status_code == 200
    body = r.json()
    assert "signals" in body
 
def test_disease_filter_sars_cov_2():
    r = requests.get(ANALYTICAL_URL, params={"disease": "sars-cov-2"})
    assert r.status_code == 200
    body = r.json()
    assert "signals" in body
 
def test_unknown_disease_returns_400():
    r = requests.get(ANALYTICAL_URL, params={"disease": "fakevirus"})
    assert r.status_code == 400
 
 
# --- Country filter ---
 
def test_country_filter_returns_only_matching_country():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza", "country_code": "AUS"})
    body = r.json()
    for signal in body["signals"]:
        if "payload" in signal:
            assert signal["payload"]["country_code"] == "AUS"
 
def test_invalid_country_returns_no_error():
    r = requests.get(ANALYTICAL_URL, params={"disease": "influenza", "country_code": "INVALID"})
    assert r.status_code == 200
    body = r.json()
    assert "signals" in body
 
 
# --- Docs route ---
 
def test_docs_route_returns_200():
    r = requests.get(ANALYTICAL_URL + "/docs")
    assert r.status_code == 200
 
def test_docs_route_returns_html():
    r = requests.get(ANALYTICAL_URL + "/docs")
    assert "text/html" in r.headers.get("Content-Type", "")
 
 
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
