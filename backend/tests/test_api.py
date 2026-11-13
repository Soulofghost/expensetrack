import pytest
from fastapi.testclient import TestClient
import backend.app.database as db_mod
import backend.app.config as cfg_mod
from backend.app.main import app

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    # Use temporary file database to ensure WAL & persistence during test run
    test_db_dir = tmp_path_factory.mktemp("db")
    test_db = str(test_db_dir / "test_expensetrack.db")

    # Patch DB_PATH in both database and config modules
    cfg_mod.DB_PATH = test_db
    db_mod.DB_PATH = test_db

    # Initialize tables and seed budgets
    holding_conn = db_mod.init_db(test_db)

    with TestClient(app) as c:
        yield c

    holding_conn.close()

def test_healthcheck(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "ExpenseTrack"

def test_forex_rates_and_convert(client):
    res = client.get("/api/forex/rates")
    assert res.status_code == 200
    rates = res.json()["rates"]
    assert "USD" in rates
    assert "EUR" in rates
    assert rates["USD"] == 1.0

    convert_res = client.post("/api/forex/convert", json={
        "amount": 200.0,
        "from_currency": "EUR",
        "to_currency": "USD"
    })
    assert convert_res.status_code == 200
    data = convert_res.json()
    assert data["converted_amount"] == 217.0

def test_create_and_manage_expense_workflow(client):
    # 1. Create Expense in EUR
    create_res = client.post("/api/expenses", json={
        "title": "AWS Cloud Infrastructure",
        "category": "Software & SaaS",
        "amount": 500.0,
        "currency": "EUR",
        "merchant": "Amazon Web Services",
        "tax_amount": 95.0,
        "notes": "Q1 Production Server Cluster",
        "receipt_ref": "INV-2026-AWS-889"
    })
    assert create_res.status_code == 201
    exp_data = create_res.json()
    exp_id = exp_data["id"]
    assert exp_data["status"] == "DRAFT"
    assert exp_data["amount_usd"] == 542.50

    # 2. List Expenses
    list_res = client.get("/api/expenses")
    assert list_res.status_code == 200
    items = list_res.json()["expenses"]
    assert len(items) >= 1

    # 3. Get Details with Audit Logs
    detail_res = client.get(f"/api/expenses/{exp_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["merchant"] == "Amazon Web Services"
    assert len(detail["audit_logs"]) >= 1

    # 4. Status Transition: DRAFT -> SUBMITTED
    sub_res = client.patch(f"/api/expenses/{exp_id}/status", json={
        "status": "SUBMITTED",
        "performed_by": "Senior DevOps Lead",
        "notes": "Ready for manager review"
    })
    assert sub_res.status_code == 200
    assert sub_res.json()["new_status"] == "SUBMITTED"

    # 5. Status Transition: SUBMITTED -> APPROVED
    appr_res = client.patch(f"/api/expenses/{exp_id}/status", json={
        "status": "APPROVED",
        "performed_by": "Finance Director",
        "notes": "Approved under Q1 SaaS budget"
    })
    assert appr_res.status_code == 200
    assert appr_res.json()["new_status"] == "APPROVED"

    # 6. Status Transition: APPROVED -> REIMBURSED
    reimb_res = client.patch(f"/api/expenses/{exp_id}/status", json={
        "status": "REIMBURSED",
        "performed_by": "Treasury",
        "notes": "Wire transfer processed"
    })
    assert reimb_res.status_code == 200
    assert reimb_res.json()["new_status"] == "REIMBURSED"

    # 7. Invalid Transition from REIMBURSED (terminal)
    invalid_res = client.patch(f"/api/expenses/{exp_id}/status", json={
        "status": "DRAFT"
    })
    assert invalid_res.status_code == 400

def test_budgets_and_analytics(client):
    # Check seeded budgets
    budgets_res = client.get("/api/budgets")
    assert budgets_res.status_code == 200
    budgets = budgets_res.json()["budgets"]
    assert len(budgets) >= 6

    # Update budget limit
    update_res = client.post("/api/budgets", json={
        "category": "Client Meals",
        "monthly_limit_usd": 1200.0
    })
    assert update_res.status_code == 200
    assert update_res.json()["monthly_limit_usd"] == 1200.0

    # Analytics summary
    analytics_res = client.get("/api/analytics/summary")
    assert analytics_res.status_code == 200
    summary = analytics_res.json()
    assert summary["total_spend_usd"] >= 542.50
    assert len(summary["breakdown_by_category"]) >= 1
