import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "expensetrack.db"))
PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
BASE_CURRENCY = "USD"
HIGH_VALUE_THRESHOLD_USD = 1000.00
