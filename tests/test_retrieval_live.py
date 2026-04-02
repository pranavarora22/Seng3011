import requests
import pytest
 
RETRIEVAL_URL = "https://asj2v7o8lj.execute-api.us-east-1.amazonaws.com"
 
VALID_FIELDS = {"event_id", "timestamp", "event_type", "domain", "payload"}
 
 
# --- Basic health ---
 
def test_valid_request_returns_200():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza"})
    assert r.status_code == 200
 
def test_response_has_items_field():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza"})
    body = r.json()
    assert "items" in body
 
def test_response_has_count_field():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza"})
    body = r.json()
    assert "count" in body
 
def test_count_matches_items_length():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza"})
    body = r.json()
    assert body["count"] == len(body["items"])
 
 
# --- Schema validation ---
 
def test_each_item_has_required_fields():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "limit": "5"})
    body = r.json()
    for item in body["items"]:
        assert VALID_FIELDS.issubset(item.keys()), f"Missing fields in item: {item}"
 
def test_payload_has_required_fields():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "limit": "5"})
    body = r.json()
    required_payload = {"disease", "country_code", "epi_week", "cases_detected"}
    for item in body["items"]:
        assert required_payload.issubset(item["payload"].keys())
 
 
# --- Disease filter ---
 
def test_disease_filter_influenza():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza"})
    body = r.json()
    for item in body["items"]:
        assert item["payload"]["disease"] == "influenza"
 
def test_disease_filter_rsv():
    r = requests.get(RETRIEVAL_URL, params={"disease": "rsv"})
    body = r.json()
    for item in body["items"]:
        assert item["payload"]["disease"] == "rsv"
 
def test_disease_filter_sars_cov_2():
    r = requests.get(RETRIEVAL_URL, params={"disease": "sars-cov-2"})
    body = r.json()
    for item in body["items"]:
        assert item["payload"]["disease"] == "sars-cov-2"
 
def test_unknown_disease_returns_empty():
    r = requests.get(RETRIEVAL_URL, params={"disease": "fakevirus"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
 
 
# --- Country filter ---
 
def test_country_filter_returns_only_matching_country():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "country_code": "AUS"})
    body = r.json()
    for item in body["items"]:
        assert item["payload"]["country_code"] == "AUS"
 
def test_invalid_country_returns_empty():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "country_code": "INVALID"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
 
 
# --- Limit ---
 
def test_limit_param_respected():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "limit": "5"})
    body = r.json()
    assert len(body["items"]) <= 5
 
def test_default_limit_applied_when_not_specified():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza"})
    body = r.json()
    assert len(body["items"]) <= 100
 
 
# --- Week range filter ---
 
def test_start_epi_week_filters_correctly():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "start_epi_week": "2024-W01"})
    body = r.json()
    for item in body["items"]:
        assert item["payload"]["epi_week"] >= "2024-W01"
 
def test_end_epi_week_filters_correctly():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "end_epi_week": "2024-W52"})
    body = r.json()
    for item in body["items"]:
        assert item["payload"]["epi_week"] <= "2024-W52"
 
def test_week_range_both_bounds():
    r = requests.get(RETRIEVAL_URL, params={
        "disease": "influenza",
        "start_epi_week": "2024-W01",
        "end_epi_week": "2024-W52"
    })
    body = r.json()
    for item in body["items"]:
        assert "2024-W01" <= item["payload"]["epi_week"] <= "2024-W52"
 
 
# --- Docs route ---
 
def test_docs_route_returns_200():
    r = requests.get(RETRIEVAL_URL + "/docs")
    assert r.status_code == 200
 
def test_docs_route_returns_html():
    r = requests.get(RETRIEVAL_URL + "/docs")
    assert "text/html" in r.headers.get("Content-Type", "")
 
 
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
