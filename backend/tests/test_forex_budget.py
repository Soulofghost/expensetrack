import pytest
from backend.app.engine.forex_budget import (
    convert_currency,
    calculate_budget_pacing,
    validate_status_transition,
    FX_TO_USD
)

def test_convert_currency_standard():
    # 100 USD to USD is 100
    assert convert_currency(100.0, "USD", "USD") == 100.0
    
    # 100 EUR to USD: 100 * 1.0850 = 108.50
    assert convert_currency(100.0, "EUR", "USD") == 108.50

    # 15,000 JPY to USD: 15000 * 0.00667 = 100.05
    assert convert_currency(15000.0, "JPY", "USD") == 100.05

    # Cross currency: 100 EUR to GBP -> (100 * 1.0850) / 1.2820 = 84.63
    gbp = convert_currency(100.0, "EUR", "GBP")
    assert gbp == 84.63

def test_convert_currency_validation_errors():
    with pytest.raises(ValueError, match="Unsupported source currency"):
        convert_currency(100.0, "XYZ", "USD")

    with pytest.raises(ValueError, match="Unsupported target currency"):
        convert_currency(100.0, "USD", "ABC")

    with pytest.raises(ValueError, match="cannot be negative"):
        convert_currency(-50.0, "USD", "EUR")

def test_budget_pacing_normal():
    res = calculate_budget_pacing(spent_usd=500.0, limit_usd=1000.0)
    assert res["status"] == "ON_TRACK"
    assert res["pacing_percentage"] == 50.0
    assert res["remaining_usd"] == 500.0
    assert res["is_over_budget"] is False
    assert res["overage_amount_usd"] == 0.0

def test_budget_pacing_warning():
    res = calculate_budget_pacing(spent_usd=850.0, limit_usd=1000.0)
    assert res["status"] == "WARNING"
    assert res["pacing_percentage"] == 85.0
    assert res["remaining_usd"] == 150.0
    assert res["is_over_budget"] is False

def test_budget_pacing_exceeded():
    res = calculate_budget_pacing(spent_usd=1200.0, limit_usd=1000.0)
    assert res["status"] == "EXCEEDED"
    assert res["pacing_percentage"] == 120.0
    assert res["remaining_usd"] == -200.0
    assert res["is_over_budget"] is True
    assert res["overage_amount_usd"] == 200.0

def test_validate_status_transition():
    # Valid normal flow
    ok, _ = validate_status_transition("DRAFT", "SUBMITTED", 500.0)
    assert ok is True

    ok, _ = validate_status_transition("SUBMITTED", "APPROVED", 500.0, approver_role="manager")
    assert ok is True

    ok, _ = validate_status_transition("APPROVED", "REIMBURSED", 500.0)
    assert ok is True

    # Invalid jump
    ok, reason = validate_status_transition("DRAFT", "REIMBURSED", 500.0)
    assert ok is False
    assert "Cannot transition from DRAFT to REIMBURSED" in reason

    # Terminal state
    ok, _ = validate_status_transition("REIMBURSED", "DRAFT", 500.0)
    assert ok is False

    # Policy limit: $1000+ requires manager/finance
    ok, reason = validate_status_transition("SUBMITTED", "APPROVED", 1500.0, approver_role="employee")
    assert ok is False
    assert "Manager or Finance" in reason
