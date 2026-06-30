"""
PaldoDamdA OS - FastAPI Backend  v0.3.0

Endpoints:
    GET  /api/health
    GET  /api/products?q=&category=
    GET  /api/compare/{product_id}
    GET  /api/review?status=&supplier_id=&limit=&offset=
    POST /api/review/{id}/approve
    POST /api/import   (dev / local use only)

Run:
    python -m uvicorn main:app --reload --port 8000
    http://localhost:8000/docs
"""
from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DB_PATH = Path(__file__).parent / "data" / "paldodamda.db"

app = FastAPI(
    title="PaldoDamdA OS API",
    description="Agricultural consignment ERP — Core API",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# DB helper
# ─────────────────────────────────────────────

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────

class ApproveRequest(BaseModel):
    standard_product_id: int
    alias: Optional[str] = None  # if None, uses normalized product_name


class ImportRequest(BaseModel):
    file_path: str
    supplier_name: str


# ─────────────────────────────────────────────
# GET /api/health
# ─────────────────────────────────────────────

@app.get("/api/health", tags=["system"])
def health():
    """DB 연결 상태 및 핵심 테이블 row 수 반환."""
    conn = get_conn()
    try:
        def count(table: str) -> int:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        return {
            "status": "ok",
            "standard_products": count("standard_products"),
            "product_aliases":   count("product_aliases"),
            "product_offers":    count("product_offers"),
            "review_queue_pending": conn.execute(
                "SELECT COUNT(*) FROM review_queue WHERE status='pending'"
            ).fetchone()[0],
            "import_history_count": count("import_history"),
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────
# GET /api/products
# ─────────────────────────────────────────────

@app.get("/api/products", tags=["products"])
def search_products(
    q:        str = Query(default="", description="상품명 또는 alias 검색어"),
    category: str = Query(default="", description="카테고리 필터 (예: 과일, 농산물)"),
):
    """
    standard_products 검색.
    상품명 직접 검색 + alias 검색 모두 지원.
    offer_count(도매처 수), 가격 범위 포함 반환.
    """
    conn = get_conn()
    try:
        conditions = []
        params: list = []

        if q:
            conditions.append(
                "(sp.standard_name LIKE ? OR sp.id IN "
                "(SELECT standard_product_id FROM product_aliases WHERE alias LIKE ?))"
            )
            like = f"%{q}%"
            params += [like, like]

        if category:
            conditions.append("sp.category = ?")
            params.append(category)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        rows = conn.execute(
            f"""
            SELECT
                sp.id,
                sp.standard_name,
                sp.category,
                COUNT(po.id)   AS offer_count,
                MIN(po.price)  AS min_price,
                MAX(po.price)  AS max_price,
                GROUP_CONCAT(DISTINCT s.name) AS suppliers
            FROM standard_products sp
            LEFT JOIN product_offers po
                ON po.standard_product_id = sp.id
                AND po.needs_review = 0
                AND po.price IS NOT NULL
                AND po.price > 0
            LEFT JOIN suppliers s ON s.id = po.supplier_id
            {where}
            GROUP BY sp.id
            ORDER BY offer_count DESC, sp.standard_name
            """,
            params,
        ).fetchall()

        return {
            "q":        q,
            "category": category,
            "count":    len(rows),
            "products": [dict(r) for r in rows],
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────
# GET /api/compare/{product_id}
# ─────────────────────────────────────────────

@app.get("/api/compare/{product_id}", tags=["products"])
def compare_suppliers(product_id: int):
    """
    특정 standard_product에 대한 도매처별 가격 비교.
    가장 낮은 가격 순 정렬.
    """
    conn = get_conn()
    try:
        product = conn.execute(
            "SELECT id, standard_name, category FROM standard_products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail=f"product_id {product_id} not found")

        offers = conn.execute(
            """
            SELECT
                po.id          AS offer_id,
                s.name         AS supplier_name,
                po.price,
                po.quality_grade AS grade,
                po.weight_value,
                po.weight_unit,
                po.quantity_value AS count,
                po.quantity_unit  AS count_unit,
                po.cultivation_type,
                po.package_type,
                po.match_confidence
            FROM product_offers po
            JOIN suppliers s ON s.id = po.supplier_id
            WHERE po.standard_product_id = ?
              AND po.needs_review = 0
              AND po.price IS NOT NULL
              AND po.price > 0
            ORDER BY po.price ASC
            """,
            (product_id,),
        ).fetchall()

        return {
            "product_id":    product["id"],
            "standard_name": product["standard_name"],
            "category":      product["category"],
            "offer_count":   len(offers),
            "offers":        [dict(o) for o in offers],
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────
# GET /api/review
# ─────────────────────────────────────────────

@app.get("/api/review", tags=["review"])
def list_review_queue(
    status:      str = Query(default="pending", description="pending | approved | rejected"),
    supplier_id: Optional[int] = Query(default=None, description="도매처 ID 필터"),
    limit:       int = Query(default=50,  ge=1, le=500),
    offset:      int = Query(default=0,   ge=0),
):
    """
    Review Queue 목록.
    기본값: status=pending (미매칭 항목).
    검토 후 POST /api/review/{id}/approve 로 승인.
    """
    conn = get_conn()
    try:
        conditions = ["rq.status = ?"]
        params: list = [status]

        if supplier_id is not None:
            conditions.append("rq.supplier_id = ?")
            params.append(supplier_id)

        where = "WHERE " + " AND ".join(conditions)

        total = conn.execute(
            f"SELECT COUNT(*) FROM review_queue rq {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT
                rq.id,
                rq.original_name,
                rq.normalized_attrs,
                rq.price,
                rq.supplier_name,
                rq.file_name,
                rq.status,
                rq.created_at,
                rq.reviewed_at,
                rq.import_id,
                s.name AS supplier_display_name
            FROM review_queue rq
            LEFT JOIN suppliers s ON s.id = rq.supplier_id
            {where}
            ORDER BY rq.created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

        items = []
        for r in rows:
            item = dict(r)
            if item.get("normalized_attrs"):
                try:
                    item["normalized_attrs"] = json.loads(item["normalized_attrs"])
                except Exception:
                    pass
            items.append(item)

        return {
            "status":  status,
            "total":   total,
            "limit":   limit,
            "offset":  offset,
            "items":   items,
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────
# POST /api/review/{id}/approve
# ─────────────────────────────────────────────

@app.post("/api/review/{review_id}/approve", tags=["review"])
def approve_review(review_id: int, body: ApproveRequest):
    """
    Review Queue 항목 승인.

    1. review_queue 항목 확인 (status=pending 이어야 함)
    2. standard_product_id 유효성 확인
    3. product_aliases에 alias 추가 (INSERT OR IGNORE)
    4. review_queue status → approved, reviewed_at = now()

    RULE: standard_products는 절대 자동 수정하지 않음.
    alias는 이 API를 통해서만 추가됨.
    """
    conn = get_conn()
    try:
        # 1. 항목 확인
        rq = conn.execute(
            "SELECT * FROM review_queue WHERE id = ?", (review_id,)
        ).fetchone()
        if not rq:
            raise HTTPException(status_code=404, detail=f"review_queue id {review_id} not found")
        if rq["status"] != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Already processed: status={rq['status']}"
            )

        # 2. standard_product 유효성 확인
        sp = conn.execute(
            "SELECT id, standard_name FROM standard_products WHERE id = ?",
            (body.standard_product_id,),
        ).fetchone()
        if not sp:
            raise HTTPException(
                status_code=404,
                detail=f"standard_product id {body.standard_product_id} not found"
            )

        # 3. alias 결정
        alias_to_add = body.alias
        if not alias_to_add:
            try:
                attrs = json.loads(rq["normalized_attrs"] or "{}")
                alias_to_add = attrs.get("product_name") or rq["original_name"]
            except Exception:
                alias_to_add = rq["original_name"]
        alias_to_add = alias_to_add.strip()

        # 4. alias 추가
        conn.execute("BEGIN")
        conn.execute(
            """INSERT OR IGNORE INTO product_aliases
               (alias, standard_product_id, standard_name, attributes_hint)
               VALUES (?, ?, ?, NULL)""",
            (alias_to_add, sp["id"], sp["standard_name"]),
        )

        # 5. review_queue 상태 업데이트
        conn.execute(
            """UPDATE review_queue
               SET status='approved', reviewed_at=datetime('now','localtime')
               WHERE id=?""",
            (review_id,),
        )
        conn.execute("COMMIT")

        return {
            "review_id":          review_id,
            "alias_added":        alias_to_add,
            "standard_product_id": sp["id"],
            "standard_name":      sp["standard_name"],
            "status":             "approved",
        }
    except HTTPException:
        conn.execute("ROLLBACK")
        raise
    except Exception as e:
        conn.execute("ROLLBACK")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ─────────────────────────────────────────────
# POST /api/import  (dev only)
# ─────────────────────────────────────────────

@app.post("/api/import", tags=["import"])
def run_import(body: ImportRequest):
    """
    Import Engine 트리거 (로컬 개발 전용).
    file_path는 서버 기준 절대경로 또는 data/raw/ 기준 상대경로.
    """
    from engine.importer import ImportEngine

    file_path = Path(body.file_path)
    if not file_path.is_absolute():
        file_path = Path(__file__).parent / "data" / "raw" / body.file_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    engine = ImportEngine()
    try:
        stats = engine.run(str(file_path), body.supplier_name)
        return {
            "file":           file_path.name,
            "supplier_name":  body.supplier_name,
            "total_rows":     stats.total_rows,
            "success_rows":   stats.success_rows,
            "new_products":   stats.new_products,
            "failed_rows":    stats.failed_rows,
            "updated_prices": stats.updated_prices,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))