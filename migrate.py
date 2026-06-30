"""
PaldoDamdA OS - Migration Script
Run once to add new tables to existing paldodamda.db.
Existing data is never touched. All statements use CREATE TABLE IF NOT EXISTS.

Usage:
    python migrate.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "paldodamda.db"

MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS attribute_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword     TEXT    NOT NULL,
    attribute   TEXT    NOT NULL,
    value       TEXT    NOT NULL,
    priority    INTEGER NOT NULL DEFAULT 10,
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_attr_rules_kw_attr
    ON attribute_rules(keyword, attribute);

CREATE TABLE IF NOT EXISTS import_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id     INTEGER,
    file_name       TEXT,
    imported_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    total_rows      INTEGER NOT NULL DEFAULT 0,
    success_rows    INTEGER NOT NULL DEFAULT 0,
    failed_rows     INTEGER NOT NULL DEFAULT 0,
    new_products    INTEGER NOT NULL DEFAULT 0,
    updated_prices  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS price_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id    INTEGER,
    supplier_id INTEGER,
    product_id  INTEGER,
    price       INTEGER,
    captured_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    import_id   INTEGER,
    FOREIGN KEY (offer_id)    REFERENCES product_offers(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
    FOREIGN KEY (product_id)  REFERENCES standard_products(id),
    FOREIGN KEY (import_id)   REFERENCES import_history(id)
);

CREATE TABLE IF NOT EXISTS review_queue (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id         INTEGER,
    supplier_id       INTEGER,
    supplier_name     TEXT,
    original_name     TEXT NOT NULL,
    normalized_attrs  TEXT,
    price             INTEGER,
    file_name         TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',
    created_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    reviewed_at       TEXT,
    FOREIGN KEY (import_id)   REFERENCES import_history(id),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);
"""

ATTRIBUTE_SEEDS = [
    ("grade", "grade", "grade", 10),
]

ATTRIBUTE_SEEDS = [
    # grade
    ("왕특",   "grade", "왕특",   10),
    ("특품",   "grade", "특품",   10),
    ("특대",   "grade", "특대",   10),
    ("상품",   "grade", "상품",   10),
    ("중품",   "grade", "중품",   10),
    ("하품",   "grade", "하품",   10),
    ("프리미엄","grade","프리미엄",20),
    ("로얄",   "grade", "로얄",   20),
    ("실속",   "grade", "실속",   10),
    ("못난이", "grade", "못난이", 10),
    ("가정용", "grade", "가정용", 10),
    ("선물용", "grade", "선물용", 20),
    ("대과",   "grade", "대과",   10),
    ("중과",   "grade", "중과",   10),
    ("소과",   "grade", "소과",   10),
    # cultivation_type
    ("노지",   "cultivation_type", "노지",   10),
    ("하우스", "cultivation_type", "하우스", 10),
    ("시설",   "cultivation_type", "시설",   10),
    # tag
    ("고당도", "tag", "고당도", 10),
    ("GAP",    "tag", "GAP",    10),
    ("무농약", "tag", "무농약", 20),
    ("유기농", "tag", "유기농", 30),
    # package_type
    ("아이스박스","package_type","아이스박스",10),
    ("선물세트",  "package_type","선물세트",  10),
    ("박스포함",  "package_type","박스포함",  10),
    ("실중량",    "package_type","실중량",    10),
    # weight_unit (exact values handled by regex in code)
    ("kg", "weight_unit", "kg", 10),
    ("g",  "weight_unit", "g",  10),
]


def run():
    if not DB_PATH.exists():
        print(f"[ERROR] DB not found: {DB_PATH}")
        print("  Run ingest_all.py first to create paldodamda.db")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(MIGRATION_SQL)
        conn.commit()
        print("[OK] Tables created: attribute_rules / import_history / price_history")

        inserted = 0
        for keyword, attribute, value, priority in ATTRIBUTE_SEEDS:
            cur = conn.execute(
                "INSERT OR IGNORE INTO attribute_rules (keyword, attribute, value, priority) VALUES (?, ?, ?, ?)",
                (keyword, attribute, value, priority),
            )
            inserted += cur.rowcount
        conn.commit()
        print(f"[OK] attribute_rules seed: {inserted} rows added (duplicates ignored)")

        for t in ["attribute_rules", "import_history", "price_history"]:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"     {t}: {n} rows")

        # Sprint 5: product_url column on product_offers
        try:
            conn.execute("ALTER TABLE product_offers ADD COLUMN product_url TEXT")
            conn.commit()
            print("[OK] product_offers.product_url column added")
        except Exception:
            print("[SKIP] product_offers.product_url already exists")

        # Sprint 5 (UX): 도매처 표준화 — supplier_master / supplier_alias
        conn.executescript("""
CREATE TABLE IF NOT EXISTS supplier_master (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    display_name TEXT NOT NULL UNIQUE,
    memo         TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS supplier_alias (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name           TEXT NOT NULL UNIQUE,
    supplier_master_id INTEGER NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (supplier_master_id) REFERENCES supplier_master(id)
);
        """)
        conn.commit()
        for t in ["supplier_master", "supplier_alias"]:
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"[OK] {t}: {n} rows")

    finally:
        conn.close()


if __name__ == "__main__":
    run()