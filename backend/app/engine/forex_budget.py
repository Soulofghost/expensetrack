"""
Forex Conversion & Budget Pacing Engine
Institutional multi-currency ledger math, FX conversions, and state machine transitions.
"""

from typing import Dict, Tuple

# Institutional pegged exchange rates against USD base (1 unit of currency = X USD)
FX_TO_USD: Dict[str, float] = {
    "USD": 1.0000,
    "EUR": 1.0850,
    "GBP": 1.2820,
    "CAD": 0.7420,
    "AUD": 0.6580,
    "JPY": 0.00667,
    "CHF": 1.1240,
    "INR": 0.01205,
    "SGD": 0.7510,
}

VALID_STATUSES = {"DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "REIMBURSED"}

ALLOWED_TRANSITIONS: Dict[str, set] = {
    "DRAFT": {"SUBMITTED", "REJECTED"},
    "SUBMITTED": {"APPROVED", "REJECTED", "DRAFT"},
    "APPROVED": {"REIMBURSED", "REJECTED"},
    "REJECTED": {"DRAFT"},
    "REIMBURSED": set(),  # Terminal state
}


def convert_currency(amount: float, from_curr: str, to_curr: str = "USD") -> float:
    """
    Converts amount from from_curr to to_curr using standard USD peg cross-rate.
    """
    from_curr = from_curr.upper()
    to_curr = to_curr.upper()

    if from_curr not in FX_TO_USD:
        raise ValueError(f"Unsupported source currency: {from_curr}")
    if to_curr not in FX_TO_USD:
        raise ValueError(f"Unsupported target currency: {to_curr}")

    if amount < 0:
        raise ValueError("Expense amount cannot be negative")

    # Step 1: Convert to USD
    usd_val = amount * FX_TO_USD[from_curr]

    # Step 2: Convert USD to target
    target_val = usd_val / FX_TO_USD[to_curr]
    return round(target_val, 2)


def calculate_budget_pacing(spent_usd: float, limit_usd: float) -> dict:
    """
    Calculates monthly pacing percentage, overage amount, and alert status.
    """
    spent_usd = max(0.0, spent_usd)
    limit_usd = max(0.0, limit_usd)

    if limit_usd == 0:
        pacing_pct = 100.0 if spent_usd > 0 else 0.0
        status = "EXCEEDED" if spent_usd > 0 else "ON_TRACK"
        remaining = 0.0
    else:
        pacing_pct = round((spent_usd / limit_usd) * 100.0, 1)
        remaining = round(limit_usd - spent_usd, 2)
        if spent_usd > limit_usd:
            status = "EXCEEDED"
        elif spent_usd >= (0.80 * limit_usd):
            status = "WARNING"
        else:
            status = "ON_TRACK"

    return {
        "spent_usd": round(spent_usd, 2),
        "limit_usd": round(limit_usd, 2),
        "pacing_percentage": pacing_pct,
        "remaining_usd": remaining,
        "status": status,
        "is_over_budget": spent_usd > limit_usd,
        "overage_amount_usd": round(max(0.0, spent_usd - limit_usd), 2),
    }


def validate_status_transition(
    current_status: str,
    new_status: str,
    amount_usd: float,
    approver_role: str = "manager"
) -> Tuple[bool, str]:
    """
    Validates expense approval workflow rules and policy restrictions.
    """
    current_status = current_status.upper()
    new_status = new_status.upper()

    if current_status not in VALID_STATUSES:
        return False, f"Invalid current status: {current_status}"
    if new_status not in VALID_STATUSES:
        return False, f"Invalid target status: {new_status}"

    if current_status == new_status:
        return True, "No status change requested"

    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        return False, f"Cannot transition from {current_status} to {new_status}"

    # Policy rule: approvals over $1,000 USD require manager or finance role
    if new_status == "APPROVED" and amount_usd >= 1000.0:
        if approver_role.lower() not in {"manager", "finance", "admin"}:
            return False, "Expenses >= $1,000.00 USD require Manager or Finance role approval"

    # Reimbursement can only happen for approved expenses
    if new_status == "REIMBURSED" and current_status != "APPROVED":
        return False, "Only APPROVED expenses can be marked REIMBURSED"

    return True, "Transition authorized"
