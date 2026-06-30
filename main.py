"""
PaldoDamdA OS - FastAPI Backend
Sprint 1: Product search endpoint only.

Run:
    uvicorn main:app --reload --port 8000

Docs:
    http://localhost:8000/docs
"""
from pathlib import Path
import sqlite3
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = Path(__file__).parent / "data" / "paldodamda.db"

app = FastAPI(
    title="PaldoDamdA OS API",
    description="Agricultural consignment ERP - Core API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────

@app.get("/api/health")
def health():
    conn = get_conn()
    try:
        row = conn.execute("SELECT COUNT(*) as n FROM standard_products").fetchone()
        return {"status": "ok", "standard_products": row["n"]}
    finally:
        conn.close()


# ─────────────────────────────────────────────
# GET /api/products?q=
# ─────────────────────────────────────────────

@app.get("/api/products")
def search_products(
    q: str = Query(default="", description="Search term (product name or alias)"),
):
    """
    Search standard_products by name or alias.
    Returns product list with offer count and price range.
    """
    conn = get_conn()
    try:
        like = f"%{q}%"

        if q:
            rows = conn.execute(
                """
                SELECT
                    sp.id,
                    sp.standard_name,
                    sp.category,
                    COUNT(po.id)    AS offer_count,
                    MIN(po.price)   AS min_price,
                    MAX(po.price)   AS max_price
                FROM standard_products sp
                LEFT JOIN product_offers po
                    ON po.standard_product_id = sp.id
                    AND po.needs_review = 0
                    AND po.price IS NOT NULL
                WHERE
                    sp.standard_name LIKE ?
                    OR sp.id IN (
                        SELECT standard_product_id
                        FROM product_aliases
                        WHERE alias LIKE ?
                    )
                GROUP BY sp.id
                ORDER BY offer_count DESC, sp.standard_name
                """,
                (like, like),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    sp.id,
                    sp.standard_name,
                    sp.category,
                    COUNT(po.id)    AS offer_count,
                    MIN(po.price)   AS min_price,
                    MAX(po.price)   AS max_price
                FROM standard_products sp
                LEFT JOIN product_offers po
                    ON po.standard_product_id = sp.id
                    AND po.needs_review = 0
                    AND po.price IS NOT NULL
                GROUP BY sp.id
                ORDER BY offer_count DESC, sp.standard_name
                """
            ).fetchall()

        return {
            "q": q,
            "count": len(rows),
            "products": [dict(r) for r in rows],
        }
    finally:
        conn.close()