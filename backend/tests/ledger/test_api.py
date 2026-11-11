from __future__ import annotations

from fastapi.testclient import TestClient


def make_customer(api: TestClient, name: str = "Ramesh Sharma") -> int:
    r = api.post("/api/customers", json={"display_name": name, "aliases": ["Sharma ji"]})
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def test_full_ledger_flow(api: TestClient) -> None:
    cid = make_customer(api)
    r = api.post("/api/ledger/entries", json={
        "type": "credit_sale", "amount_paise": 12000, "customer_id": cid,
        "lines": [{"item_name": "Cheeni", "qty": "2", "unit": "kilo"}],
    })  # fmt: skip
    assert r.status_code == 201, r.text
    entry = r.json()
    assert (entry["amount_display"], entry["customer_name"]) == ("₹120", "Ramesh Sharma")
    api.post("/api/ledger/entries",
             json={"type": "payment_received", "amount_paise": 5000, "customer_id": cid})  # fmt: skip

    detail = api.get(f"/api/customers/{cid}").json()
    assert (detail["balance_paise"], detail["balance_display"]) == (7000, "₹70")
    assert [e["type"] for e in detail["entries"]] == ["payment_received", "credit_sale"]
    assert detail["entries"][1]["lines"][0]["item_name"] == "cheeni"

    r = api.post(f"/api/ledger/entries/{entry['id']}/reverse")
    assert r.json()["amount_paise"] == -12000
    detail = api.get(f"/api/customers/{cid}").json()
    assert detail["balance_paise"] == -5000  # paid more than owed now -> advance
    credit = next(e for e in detail["entries"] if e["id"] == entry["id"])
    assert credit["reversed_by"] == r.json()["id"]


def test_undo_and_errors_are_friendly(api: TestClient) -> None:
    r = api.post("/api/ledger/undo")
    assert r.status_code == 409
    assert r.json()["error"]["message"] == "Cancel karne ke liye koi entry nahi hai."
    api.post("/api/ledger/entries", json={"type": "cash_sale", "amount_paise": 5000})
    r = api.post("/api/ledger/undo")
    assert r.status_code == 200
    assert r.json()["speak"] == "Pichhli entry cancel ho gayi."


def test_reports(api: TestClient) -> None:
    a, b = make_customer(api, "Gupta ji"), make_customer(api, "Verma ji")
    for cid, amt in ((a, 30000), (b, 12000)):
        api.post("/api/ledger/entries", json={"type": "credit_sale", "amount_paise": amt,
                                              "customer_id": cid})  # fmt: skip
    api.post("/api/ledger/entries", json={"type": "cash_sale", "amount_paise": 5000})
    today = api.get("/api/reports/today").json()
    assert (today["total_paise"], today["entries"], today["total_display"]) == (47000, 3, "₹470")
    assert today["speak"] == (
        "Aaj ki bikri chaar sau sattar rupaye, 3 entry. Usme udhaar chaar sau bees rupaye."
    )
    dues = api.get("/api/reports/dues").json()
    assert [c["display_name"] for c in dues["customers"]] == ["Gupta ji", "Verma ji"]
    assert dues["speak"].startswith("Sabse zyada baaki: Gupta ji teen sau rupaye")
    listed = api.get("/api/customers").json()
    assert {c["display_name"]: c["balance_paise"] for c in listed} == {"Gupta ji": 30000,
                                                                        "Verma ji": 12000}  # fmt: skip


def test_input_validation(api: TestClient) -> None:
    cid = make_customer(api)
    for bad in (120.5, "120", 0, -1, True):
        r = api.post("/api/ledger/entries", json={"type": "credit_sale", "amount_paise": bad,
                                                  "customer_id": cid})  # fmt: skip
        assert r.status_code == 422, bad
    r = api.post("/api/ledger/entries", json={"type": "adjustment", "amount_paise": 100})
    assert r.status_code == 422
    r = api.post("/api/ledger/entries", json={"type": "credit_sale", "amount_paise": 100})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "customer_required"
    assert api.post("/api/customers", json={"display_name": "Ramesh Sharma"}).status_code == 409
    assert api.get("/api/customers/999999").status_code == 404


def test_alias_learning(api: TestClient) -> None:
    cid = make_customer(api)
    r = api.post(f"/api/customers/{cid}/aliases", json={"alias": "Sharma uncle"})
    assert r.json()["aliases"] == ["Sharma ji", "Sharma uncle"]
