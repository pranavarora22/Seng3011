import requests
import pytest

RETRIEVAL_URL = "https://nllt9cwjk7.execute-api.us-east-1.amazonaws.com"

VALID_FIELDS = {"event_id", "timestamp", "event_type", "domain", "payload"}


@pytest.fixture(scope="session")
def influenza_response():
    return requests.get(RETRIEVAL_URL, params={"disease": "influenza"})


@pytest.fixture(scope="session")
def influenza_body(influenza_response):
    return influenza_response.json()


@pytest.fixture(scope="session")
def limited_body():
    return requests.get(RETRIEVAL_URL, params={"disease": "influenza", "limit": "5"}).json()


@pytest.fixture(scope="session")
def aus_body():
    return requests.get(RETRIEVAL_URL, params={"disease": "influenza", "country_code": "AUS"}).json()


@pytest.fixture(scope="session")
def docs_response():
    return requests.get(RETRIEVAL_URL + "/docs")


# --- Basic health ---

def test_valid_request_returns_200(influenza_response):
    assert influenza_response.status_code == 200


def test_response_has_items_field(influenza_body):
    assert "items" in influenza_body


def test_response_has_count_field(influenza_body):
    assert "count" in influenza_body


def test_count_matches_items_length(influenza_body):
    assert influenza_body["count"] == len(influenza_body["items"])


# --- Schema validation ---

def test_each_item_has_required_fields(limited_body):
    for item in limited_body["items"]:
        assert VALID_FIELDS.issubset(item.keys()), f"Missing fields in item: {item}"


def test_payload_has_required_fields(limited_body):
    required_payload = {"disease", "country_code", "epi_week", "cases_detected"}
    for item in limited_body["items"]:
        assert required_payload.issubset(item["payload"].keys())


# --- Disease filter ---

def test_disease_filter_influenza(influenza_body):
    for item in influenza_body["items"]:
        assert item["payload"]["disease"] == "influenza"


def test_disease_filter_rsv():
    body = requests.get(RETRIEVAL_URL, params={"disease": "rsv"}).json()
    for item in body["items"]:
        assert item["payload"]["disease"] == "rsv"


def test_disease_filter_sars_cov_2():
    body = requests.get(RETRIEVAL_URL, params={"disease": "sars-cov-2"}).json()
    for item in body["items"]:
        assert item["payload"]["disease"] == "sars-cov-2"


def test_unknown_disease_returns_empty():
    r = requests.get(RETRIEVAL_URL, params={"disease": "fakevirus"})
    assert r.status_code == 400
    assert r.json()["count"] == 0


# --- Country filter ---

def test_country_filter_returns_only_matching_country(aus_body):
    for item in aus_body["items"]:
        assert item["payload"]["country_code"] == "AUS"


def test_invalid_country_returns_empty():
    r = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "country_code": "INVALID"})
    assert r.status_code == 200
    assert r.json()["count"] == 0


# --- Limit ---

def test_limit_param_respected(limited_body):
    assert len(limited_body["items"]) <= 5


def test_default_limit_applied_when_not_specified(influenza_body):
    assert len(influenza_body["items"]) <= 100


# --- Week range filter ---

def test_start_epi_week_filters_correctly():
    body = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "start_epi_week": "2024-W01"}).json()
    for item in body["items"]:
        assert item["payload"]["epi_week"] >= "2024-W01"


def test_end_epi_week_filters_correctly():
    body = requests.get(RETRIEVAL_URL, params={"disease": "influenza", "end_epi_week": "2024-W52"}).json()
    for item in body["items"]:
        assert item["payload"]["epi_week"] <= "2024-W52"


def test_week_range_both_bounds():
    body = requests.get(RETRIEVAL_URL, params={
        "disease": "influenza",
        "start_epi_week": "2024-W01",
        "end_epi_week": "2024-W52"
    }).json()
    for item in body["items"]:
        assert "2024-W01" <= item["payload"]["epi_week"] <= "2024-W52"


# --- Docs route ---

def test_docs_route_returns_200(docs_response):
    assert docs_response.status_code == 200


def test_docs_route_returns_html(docs_response):
    assert "text/html" in docs_response.headers.get("Content-Type", "")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
