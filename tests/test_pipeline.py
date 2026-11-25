from fastapi.testclient import TestClient
from app.main import app
from app.schemas import RiskDisposition

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_exact_sanctions_alias_hit_escalates_sar():
    """High-confidence alias + country match must force ESCALATE_SAR even without tx/network data."""
    payload = {
        "case_id": "CASE-101",
        "entity": {
            "entity_id": "ENT-001",
            "name": "Victor Sokolov",
            "entity_type": "INDIVIDUAL",
            "country": "RU",
            "dob": "1974-08-19",
        },
    }
    res = client.post("/investigate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["disposition"] == RiskDisposition.ESCALATE_SAR
    assert data["stages"][0]["metadata"]["tier"] == "HIGH_RISK_HIT"
    assert "CASE-101" in data["audit_narrative"]


def test_corporate_suffix_normalization_catches_sanctioned_entity():
    """Legal designators (LLC, Ltd) should strip cleanly so underlying entity matches."""
    payload = {
        "case_id": "CASE-102",
        "entity": {
            "entity_id": "ENT-002",
            "name": "Al Noor Trading LLC",
            "entity_type": "CORPORATE",
            "country": "AE",
        },
    }
    res = client.post("/investigate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["stages"][0]["flagged"] is True
    assert data["stages"][0]["metadata"]["matched_watchlist_id"] == "OFAC-1002"


def test_conflicting_dob_reduces_false_positive_score():
    """Conflicting DOB should penalize a fuzzy name match rather than auto-escalating."""
    payload = {
        "case_id": "CASE-103",
        "entity": {
            "entity_id": "ENT-003",
            "name": "Viktor Petrovich Sokolov",
            "entity_type": "INDIVIDUAL",
            "country": "US",
            "dob": "1992-03-11",
        },
    }
    res = client.post("/investigate", json=payload)
    assert res.status_code == 200
    data = res.json()
    # 100 base - 8 country mismatch - 12 DOB conflict = 80.0 (MANUAL_REVIEW, not HIGH_RISK_HIT)
    assert data["stages"][0]["score"] == 80.0
    assert data["stages"][0]["metadata"]["tier"] == "MANUAL_REVIEW"


def test_clean_sanctions_caught_by_network_and_structuring_compounding():
    """Clean entity name must escalate when structuring + hidden UBO / circular flow trigger together."""
    payload = {
        "case_id": "CASE-104",
        "entity": {
            "entity_id": "ENT-CLEAN-99",
            "name": "Bluewater Horizon Exports Pvt Ltd",
            "entity_type": "CORPORATE",
            "country": "SG",
        },
        "transaction": {
            "amount_usd": 9400.0,
            "tx_count_24h": 5,
            "total_volume_24h": 47000.0,
            "counterparty_country": "AE",
        },
        "network_edges": [
            {"source": "ENT-CLEAN-99", "target": "SHELL-77", "relation": "BENEFICIAL_OWNER"},
            {"source": "SHELL-77", "target": "MULE-55", "relation": "TRANSFER"},
            {"source": "MULE-55", "target": "ENT-CLEAN-99", "relation": "TRANSFER"},
        ],
        "known_high_risk_nodes": ["SHELL-77"],
    }
    res = client.post("/investigate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["stages"][0]["flagged"] is False  # Sanctions clean
    assert data["stages"][1]["flagged"] is True   # Structuring + high volume flagged
    assert data["stages"][2]["flagged"] is True   # 1-hop UBO + circular cycle flagged
    assert data["disposition"] == RiskDisposition.ESCALATE_SAR
    assert "Circular flow detected" in data["audit_narrative"]


def test_benign_customer_auto_clears():
    """Low-risk customer with normal activity and no bad links should AUTO_CLEAR."""
    payload = {
        "case_id": "CASE-105",
        "entity": {
            "entity_id": "ENT-SAFE-01",
            "name": "Priya Nair",
            "entity_type": "INDIVIDUAL",
            "country": "IN",
        },
        "transaction": {
            "amount_usd": 450.0,
            "tx_count_24h": 1,
            "total_volume_24h": 450.0,
            "counterparty_country": "IN",
        },
    }
    res = client.post("/investigate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["disposition"] == RiskDisposition.AUTO_CLEAR
    assert data["composite_risk_score"] < 30.0