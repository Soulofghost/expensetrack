from pydantic import BaseModel, Field
from typing import Optional, List

class ExpenseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    category: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    currency: str = Field("USD", min_length=3, max_length=3)
    date: Optional[str] = None
    merchant: str = Field(..., min_length=1)
    tax_amount: float = Field(0.0, ge=0)
    notes: Optional[str] = ""
    receipt_ref: Optional[str] = ""

class StatusUpdate(BaseModel):
    status: str
    performed_by: str = "Financial Controller"
    notes: Optional[str] = ""

class BudgetSet(BaseModel):
    category: str
    monthly_limit_usd: float = Field(..., gt=0)

class CurrencyConvertRequest(BaseModel):
    amount: float = Field(..., gt=0)
    from_currency: str
    to_currency: str = "USD"
