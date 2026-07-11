import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from vigilex.api.main import app


TEST_API_KEY = "test-secret"
AUTH = {"X-API-Key": TEST_API_KEY}

SAMPLE_RESULT = {
    "id": 1,
    "mdr_report_key": "TEST-001",
    "pt_code": 10020635,
    "pt_name": "Hyperglycaemia",
    "llt_code": None,
    "llt_name": None,
    "soc_name": "Metabolism and nutrition disorders",
    "vector_similarity": 0.82,
    "crossencoder_score": 0.75,
    "llm_confidence": 0.8,
    "final_confidence": 0.78,
    "model_version": "v1",
    "coded_at": datetime(2024, 6, 1, 12, 0, 0),
}

SAMPLE_STATS = {
    "total_records": 100,
    "records_with_llm": 80,
    "fallback_count": 20,
    "avg_final_confidence": 0.65,
    "median_final_confidence": 0.70,
    "high_confidence_count": 50,
    "distinct_pt_codes": 12,
    "earliest_coded_at": datetime(2024, 1, 1),
    "latest_coded_at": datetime(2024, 6, 1),
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("API_KEY", TEST_API_KEY)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test/test")


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_db():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    with patch("vigilex.api.main.get_connection", return_value=mock_conn), \
         patch("vigilex.api.main.get_cursor", return_value=mock_cur):
        yield mock_conn, mock_cur


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_ok(client, mock_db):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"


def test_health_db_error(client):
    with patch("vigilex.api.main.get_connection", side_effect=Exception("conn refused")):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "conn refused" in data["db"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def test_auth_missing(client):
    response = client.get("/coding-results")
    assert response.status_code == 401


def test_auth_wrong_key(client):
    response = client.get("/coding-results", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /coding-results
# ---------------------------------------------------------------------------

def test_list_default(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchall.return_value = [SAMPLE_RESULT]
    response = client.get("/coding-results", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["pt_name"] == "Hyperglycaemia"


def test_list_pagination(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchall.return_value = []
    client.get("/coding-results?limit=10&offset=20", headers=AUTH)
    params = mock_cur.execute.call_args.args[1]
    assert params[-2] == 10
    assert params[-1] == 20


def test_list_exclude_fallback(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchall.return_value = []
    client.get("/coding-results", headers=AUTH)
    sql = mock_cur.execute.call_args.args[0]
    assert "llm_confidence IS DISTINCT FROM 0.3" in sql


def test_list_include_fallback(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchall.return_value = []
    client.get("/coding-results?exclude_fallback=false", headers=AUTH)
    sql = mock_cur.execute.call_args.args[0]
    assert "llm_confidence IS DISTINCT FROM 0.3" not in sql


def test_list_filter_min_confidence(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchall.return_value = []
    client.get("/coding-results?min_confidence=0.5", headers=AUTH)
    sql = mock_cur.execute.call_args.args[0]
    params = mock_cur.execute.call_args.args[1]
    assert "final_confidence >= %s" in sql
    assert 0.5 in params


# ---------------------------------------------------------------------------
# GET /coding-results/stats
# ---------------------------------------------------------------------------

def test_stats_returns_stats(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchone.return_value = SAMPLE_STATS
    response = client.get("/coding-results/stats", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["total_records"] == 100
    assert data["fallback_count"] == 20


# ---------------------------------------------------------------------------
# GET /coding-results/{id}
# ---------------------------------------------------------------------------

def test_get_by_id_found(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchone.return_value = SAMPLE_RESULT
    response = client.get("/coding-results/1", headers=AUTH)
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_by_id_not_found(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchone.return_value = None
    response = client.get("/coding-results/999", headers=AUTH)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /coding-results/{id}/decision
# ---------------------------------------------------------------------------

SAMPLE_DECISION_RESPONSE = {
    "id": 1,
    "reviewer_action": "accepted",
    "reviewer_at": datetime(2024, 6, 1, 12, 0, 0),
    "reviewer_note": None,
}


def test_save_decision_accepted(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchone.side_effect = [
        {"id": 1},                 # existence check
        SAMPLE_DECISION_RESPONSE,  # UPDATE ... RETURNING
    ]
    resp = client.post(
        "/coding-results/1/decision",
        json={"action": "accepted"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["reviewer_action"] == "accepted"
    assert data["id"] == 1


def test_save_decision_overridden_with_note(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchone.side_effect = [
        {"id": 1},
        {**SAMPLE_DECISION_RESPONSE, "reviewer_action": "overridden",
         "reviewer_note": "Changed to DKA"},
    ]
    resp = client.post(
        "/coding-results/1/decision",
        json={"action": "overridden", "note": "Changed to DKA"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    assert resp.json()["reviewer_note"] == "Changed to DKA"


def test_save_decision_invalid_action(client, mock_db):
    resp = client.post(
        "/coding-results/1/decision",
        json={"action": "wrong"},
        headers=AUTH,
    )
    assert resp.status_code == 400


def test_save_decision_not_found(client, mock_db):
    _, mock_cur = mock_db
    mock_cur.fetchone.return_value = None
    resp = client.post(
        "/coding-results/99999/decision",
        json={"action": "accepted"},
        headers=AUTH,
    )
    assert resp.status_code == 404


def test_save_decision_no_auth(client):
    resp = client.post(
        "/coding-results/1/decision",
        json={"action": "accepted"},
    )
    assert resp.status_code == 401
