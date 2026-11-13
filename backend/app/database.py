import sqlite3
import datetime
import uuid
from typing import Optional
from backend.app.config import DB_PATH

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    if not path.startswith(":memory:") and "mode=memory" not in path:
        conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Optional[str] = None):
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL,
        amount_usd REAL NOT NULL,
        date TEXT NOT NULL,
        merchant TEXT NOT NULL,
        tax_amount REAL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'DRAFT',
        notes TEXT DEFAULT '',
        receipt_ref TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id TEXT PRIMARY KEY,
        category TEXT UNIQUE NOT NULL,
        monthly_limit_usd REAL NOT NULL,
        period TEXT DEFAULT 'MONTHLY',
        updated_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        expense_id TEXT NOT NULL,
        action TEXT NOT NULL,
        performed_by TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        notes TEXT DEFAULT ''
    );
    """)

    # Seed default category budgets if table is empty
    cursor.execute("SELECT COUNT(*) FROM budgets;")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        default_budgets = [
            (str(uuid.uuid4()), "Software & SaaS", 2500.0, "MONTHLY", now),
            (str(uuid.uuid4()), "Travel & Transit", 1800.0, "MONTHLY", now),
            (str(uuid.uuid4()), "Client Meals", 800.0, "MONTHLY", now),
            (str(uuid.uuid4()), "Equipment & Hardware", 3000.0, "MONTHLY", now),
            (str(uuid.uuid4()), "Marketing & Ads", 1500.0, "MONTHLY", now),
            (str(uuid.uuid4()), "Office Supplies", 500.0, "MONTHLY", now),
        ]
        cursor.executemany(
            "INSERT INTO budgets (id, category, monthly_limit_usd, period, updated_at) VALUES (?, ?, ?, ?, ?);",
            default_budgets
        )

    conn.commit()
    return conn
