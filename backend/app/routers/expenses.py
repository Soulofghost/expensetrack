import uuid
import datetime
from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional, List

from backend.app.database import get_connection
from backend.app.schemas import ExpenseCreate, StatusUpdate, BudgetSet, CurrencyConvertRequest
from backend.app.engine.forex_budget import (
    convert_currency,
    calculate_budget_pacing,
    validate_status_transition,
    FX_TO_USD
)

router = APIRouter(prefix="/api", tags=["expenses"])

@router.get("/health")
def healthcheck():
    return {"status": "ok", "service": "ExpenseTrack", "version": "1.0.0"}

@router.get("/forex/rates")
def get_forex_rates():
    """Returns supported institutional FX rates against USD base."""
    return {
        "base_currency": "USD",
        "rates": FX_TO_USD,
        "last_synced": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

@router.post("/forex/convert")
def convert_forex(payload: CurrencyConvertRequest):
    """Converts an amount between two supported currencies."""
    try:
        converted = convert_currency(payload.amount, payload.from_currency, payload.to_currency)
        return {
            "amount": payload.amount,
            "from_currency": payload.from_currency.upper(),
            "to_currency": payload.to_currency.upper(),
            "converted_amount": converted
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(expense: ExpenseCreate):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        amount_usd = convert_currency(expense.amount, expense.currency, "USD")
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))

    expense_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    expense_date = expense.date or now[:10]

    cursor.execute("""
    INSERT INTO expenses (
        id, title, category, amount, currency, amount_usd, date,
        merchant, tax_amount, status, notes, receipt_ref, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?);
    """, (
        expense_id, expense.title, expense.category, expense.amount,
        expense.currency.upper(), amount_usd, expense_date,
        expense.merchant, expense.tax_amount, expense.notes or "",
        expense.receipt_ref or "", now, now
    ))

    # Add audit log
    audit_id = str(uuid.uuid4())
    cursor.execute("""
    INSERT INTO audit_logs (id, expense_id, action, performed_by, timestamp, notes)
    VALUES (?, ?, 'CREATED', 'Submitter', ?, 'Initial draft created');
    """, (audit_id, expense_id, now))

    conn.commit()

    # Check budget alert
    cursor.execute("SELECT monthly_limit_usd FROM budgets WHERE category = ?;", (expense.category,))
    budget_row = cursor.fetchone()
    conn.close()

    budget_warning = None
    if budget_row:
        limit = budget_row[0]
        # fetch total spent
        chk_conn = get_connection()
        chk_cur = chk_conn.cursor()
        chk_cur.execute(
            "SELECT COALESCE(SUM(amount_usd), 0.0) FROM expenses WHERE category = ? AND status != 'REJECTED';",
            (expense.category,)
        )
        total_spent = chk_cur.fetchone()[0]
        chk_conn.close()
        pacing = calculate_budget_pacing(total_spent, limit)
        if pacing["status"] in ("WARNING", "EXCEEDED"):
            budget_warning = pacing

    return {
        "id": expense_id,
        "title": expense.title,
        "category": expense.category,
        "amount": expense.amount,
        "currency": expense.currency.upper(),
        "amount_usd": amount_usd,
        "date": expense_date,
        "merchant": expense.merchant,
        "tax_amount": expense.tax_amount,
        "status": "DRAFT",
        "notes": expense.notes,
        "receipt_ref": expense.receipt_ref,
        "budget_pacing": budget_warning
    }

@router.get("/expenses")
def list_expenses(
    category: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    currency: Optional[str] = None,
    search: Optional[str] = None
):
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM expenses WHERE 1=1"
    params = []

    if category:
        query += " AND category = ?"
        params.append(category)
    if status_filter:
        query += " AND status = ?"
        params.append(status_filter.upper())
    if currency:
        query += " AND currency = ?"
        params.append(currency.upper())
    if search:
        query += " AND (title LIKE ? OR merchant LIKE ? OR notes LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY date DESC, created_at DESC;"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "amount": r["amount"],
            "currency": r["currency"],
            "amount_usd": r["amount_usd"],
            "date": r["date"],
            "merchant": r["merchant"],
            "tax_amount": r["tax_amount"],
            "status": r["status"],
            "notes": r["notes"],
            "receipt_ref": r["receipt_ref"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        })
    return {"total": len(results), "expenses": results}

@router.get("/expenses/{expense_id}")
def get_expense_details(expense_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM expenses WHERE id = ?;", (expense_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    cursor.execute("SELECT * FROM audit_logs WHERE expense_id = ? ORDER BY timestamp ASC;", (expense_id,))
    audit_rows = cursor.fetchall()
    conn.close()

    logs = []
    for a in audit_rows:
        logs.append({
            "id": a["id"],
            "action": a["action"],
            "performed_by": a["performed_by"],
            "timestamp": a["timestamp"],
            "notes": a["notes"]
        })

    return {
        "id": row["id"],
        "title": row["title"],
        "category": row["category"],
        "amount": row["amount"],
        "currency": row["currency"],
        "amount_usd": row["amount_usd"],
        "date": row["date"],
        "merchant": row["merchant"],
        "tax_amount": row["tax_amount"],
        "status": row["status"],
        "notes": row["notes"],
        "receipt_ref": row["receipt_ref"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "audit_logs": logs
    }

@router.patch("/expenses/{expense_id}/status")
def update_expense_status(expense_id: str, payload: StatusUpdate):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM expenses WHERE id = ?;", (expense_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    current_status = row["status"]
    amount_usd = row["amount_usd"]

    valid, reason = validate_status_transition(
        current_status=current_status,
        new_status=payload.status,
        amount_usd=amount_usd,
        approver_role="finance"
    )

    if not valid:
        conn.close()
        raise HTTPException(status_code=400, detail=reason)

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cursor.execute(
        "UPDATE expenses SET status = ?, updated_at = ? WHERE id = ?;",
        (payload.status.upper(), now, expense_id)
    )

    audit_id = str(uuid.uuid4())
    cursor.execute("""
    INSERT INTO audit_logs (id, expense_id, action, performed_by, timestamp, notes)
    VALUES (?, ?, ?, ?, ?, ?);
    """, (
        audit_id, expense_id, f"STATUS_CHANGE_TO_{payload.status.upper()}",
        payload.performed_by, now, payload.notes or f"Transitioned from {current_status} to {payload.status.upper()}"
    ))

    conn.commit()
    conn.close()

    return {
        "id": expense_id,
        "previous_status": current_status,
        "new_status": payload.status.upper(),
        "updated_at": now,
        "detail": reason
    }

@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM expenses WHERE id = ?;", (expense_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Expense not found")

    if row["status"] in ("APPROVED", "REIMBURSED"):
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot delete an approved or reimbursed expense")

    cursor.execute("DELETE FROM audit_logs WHERE expense_id = ?;", (expense_id,))
    cursor.execute("DELETE FROM expenses WHERE id = ?;", (expense_id,))
    conn.commit()
    conn.close()
    return None

@router.get("/budgets")
def list_budgets():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM budgets ORDER BY category ASC;")
    budget_rows = cursor.fetchall()

    results = []
    for b in budget_rows:
        cat = b["category"]
        limit = b["monthly_limit_usd"]

        cursor.execute(
            "SELECT COALESCE(SUM(amount_usd), 0.0) FROM expenses WHERE category = ? AND status != 'REJECTED';",
            (cat,)
        )
        spent = cursor.fetchone()[0]
        pacing = calculate_budget_pacing(spent, limit)

        results.append({
            "id": b["id"],
            "category": cat,
            "period": b["period"],
            "monthly_limit_usd": limit,
            "spent_usd": pacing["spent_usd"],
            "remaining_usd": pacing["remaining_usd"],
            "pacing_percentage": pacing["pacing_percentage"],
            "status": pacing["status"],
            "is_over_budget": pacing["is_over_budget"],
            "overage_amount_usd": pacing["overage_amount_usd"]
        })

    conn.close()
    return {"total": len(results), "budgets": results}

@router.post("/budgets")
def set_budget(payload: BudgetSet):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cursor.execute("SELECT id FROM budgets WHERE category = ?;", (payload.category,))
    row = cursor.fetchone()

    if row:
        cursor.execute(
            "UPDATE budgets SET monthly_limit_usd = ?, updated_at = ? WHERE category = ?;",
            (payload.monthly_limit_usd, now, payload.category)
        )
        budget_id = row[0]
    else:
        budget_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO budgets (id, category, monthly_limit_usd, period, updated_at) VALUES (?, ?, ?, 'MONTHLY', ?);",
            (budget_id, payload.category, payload.monthly_limit_usd, now)
        )

    conn.commit()
    conn.close()

    return {
        "id": budget_id,
        "category": payload.category,
        "monthly_limit_usd": payload.monthly_limit_usd,
        "updated_at": now
    }

@router.get("/analytics/summary")
def get_analytics_summary():
    conn = get_connection()
    cursor = conn.cursor()

    # Total spend in USD (non-rejected)
    cursor.execute("SELECT COALESCE(SUM(amount_usd), 0.0), COUNT(*) FROM expenses WHERE status != 'REJECTED';")
    tot_row = cursor.fetchone()
    total_spend_usd = round(tot_row[0], 2)
    total_active_count = tot_row[1]

    # Category breakdown
    cursor.execute("""
    SELECT category, COALESCE(SUM(amount_usd), 0.0) as cat_spend, COUNT(*) as cnt
    FROM expenses WHERE status != 'REJECTED'
    GROUP BY category ORDER BY cat_spend DESC;
    """)
    cat_rows = cursor.fetchall()
    by_category = [{"category": r["category"], "total_usd": round(r["cat_spend"], 2), "count": r["cnt"]} for r in cat_rows]

    # Status breakdown
    cursor.execute("SELECT status, COUNT(*), COALESCE(SUM(amount_usd), 0.0) FROM expenses GROUP BY status;")
    status_rows = cursor.fetchall()
    by_status = {r[0]: {"count": r[1], "amount_usd": round(r[2], 2)} for r in status_rows}

    # Currency breakdown
    cursor.execute("SELECT currency, COUNT(*), COALESCE(SUM(amount), 0.0) FROM expenses GROUP BY currency;")
    curr_rows = cursor.fetchall()
    by_currency = [{"currency": r[0], "count": r[1], "original_amount": round(r[2], 2)} for r in curr_rows]

    conn.close()

    return {
        "total_spend_usd": total_spend_usd,
        "total_expense_records": total_active_count,
        "breakdown_by_category": by_category,
        "breakdown_by_status": by_status,
        "breakdown_by_currency": by_currency
    }
