from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend.app.database import init_db
from backend.app.routers.expenses import router as expenses_router

app = FastAPI(
    title="ExpenseTrack API",
    description="Multi-Currency Business & Personal Expense Management with Budget Pacing & Audit Trails",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(expenses_router)

# Serve static frontend if directory exists
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists() and (frontend_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
