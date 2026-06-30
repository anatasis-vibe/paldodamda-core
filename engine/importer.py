"""
ImportEngine — the main orchestrator for the 4-layer pipeline.

Pipeline:
    file -> Parser -> [ParsedRow] -> Normalizer -> [NormalizedRow] -> Matcher -> DB / ReviewQueue

Design rules:
  - Every import runs inside a single SQLite transaction (all-or-nothing).
  - On any unhandled exception: ROLLBACK.
  - Price history is recorded only when price changes.
  - Import history is always written at the end.
  - failed_rows  = actual row-level exceptions (parse/normalize/match error).
  - new_products = unmatched rows saved to review_queue (not a failure).
  - review_queue deduplication: if a pending entry exists for the same
    supplier + original_name, skip re-insert (update price if changed).
  - Logging: logs/{date}.log + stdout.
"""
from __future__ import annotations
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from .parser import get_parser
from .normalizer import Normalizer, NormalizedRow
from .matcher import Matcher, MatchResult

ROOT     = Path(__file__).parent.parent
DB_PATH  = ROOT / "data" / "paldodamda.db"
LOGS_DIR = ROOT / "logs"


# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

def _get_logger(name: str = "paldodamda.importer") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    LOGS_DIR.mkdir(exist_ok=True)
    log_file = LOGS_DIR / f"{date.today().isoformat()}.log"

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.INFO)

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ─────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────

@dataclass
class ImportStats:
    total_rows:     int = 0
    success_rows:   int = 0
    failed_rows:    int = 0   # actual exceptions — NOT review_queue entries
    new_products:   int = 0   # unmatched rows sent to review_queue
    updated_prices: int = 0


# ─────────────────────────────────────────────
# ImportEngine
# ─────────────────────────────────────────────

class ImportEngine:
    """
    Usage:
        engine = ImportEngine()
        stats  = engine.run("path/to/file.xlsx", supplier_name="업체명")
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path    = str(db_path or DB_PATH)
        self.normalizer = Normalizer(self.db_path)
        self.matcher    = Matcher()
        self.log        = _get_logger()

    # ── public ──────────────────────────────────────────

    def run(self, file_path: str, supplier_name: str) -> ImportStats:
        path = Path(file_path)
        self.log.info(f"=== Import START: {path.name} / supplier={supplier_name} ===")
        stats = ImportStats()
        conn  = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        try:
            supplier_id = self._get_or_create_supplier(conn, supplier_name)

            conn.execute("BEGIN")
            import_id = self._create_import_history(conn, supplier_id, path.name)
            self.log.info(f"import_history id={import_id}")

            parser = get_parser(str(path))

            for parsed in parser.parse(str(path), supplier_name):
                stats.total_rows += 1
                try:
                    normalized = self.normalizer.normalize(parsed)
                    match      = self.matcher.match(normalized, conn)

                    if match.matched:
                        offer_id, price_changed = self._save_offer(
                            conn, normalized, match, supplier_id, import_id
                        )
                        if price_changed:
                            self._record_price_history(
                                conn, offer_id, supplier_id,
                                match.product_id, normalized.price, import_id
                            )
                            stats.updated_prices += 1
                        stats.success_rows += 1
                        self.log.debug(
                            f"  [OK] {parsed.original_name!r} -> {match.standard_name}"
                        )
                    else:
                        added = self._upsert_review_queue(
                            conn, parsed, normalized, supplier_id, import_id
                        )
                        if added:
                            stats.new_products += 1
                        self.log.debug(
                            f"  [REVIEW] {parsed.original_name!r} "
                            f"-> product_name={normalized.product_name!r}"
                            f"{'' if added else ' (dedup skip)'}"
                        )

                except Exception as row_err:
                    stats.failed_rows += 1
                    self.log.warning(
                        f"  [ROW ERROR] {parsed.original_name!r}: {row_err}"
                    )

            self._update_import_history(conn, import_id, stats)
            conn.execute("COMMIT")
            self.log.info(
                f"=== Import DONE: total={stats.total_rows} "
                f"ok={stats.success_rows} review={stats.new_products} "
                f"err={stats.failed_rows} price_changes={stats.updated_prices} ==="
            )

        except Exception as fatal:
            conn.execute("ROLLBACK")
            self.log.error(f"=== Import FAILED (rollback): {fatal} ===")
            raise

        finally:
            conn.close()

        return stats

    # ── private helpers ──────────────────────────────────

    def _get_or_create_supplier(self, conn: sqlite3.Connection, name: str) -> int:
        row = conn.execute(
            "SELECT id FROM suppliers WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row[0]
        cur = conn.execute("INSERT INTO suppliers (name) VALUES (?)", (name,))
        conn.commit()
        return cur.lastrowid

    def _create_import_history(
        self, conn: sqlite3.Connection, supplier_id: int, file_name: str
    ) -> int:
        cur = conn.execute(
            "INSERT INTO import_history (supplier_id, file_name, total_rows) VALUES (?, ?, 0)",
            (supplier_id, file_name),
        )
        return cur.lastrowid

    def _update_import_history(
        self, conn: sqlite3.Connection, import_id: int, stats: ImportStats
    ) -> None:
        conn.execute(
            """UPDATE import_history
               SET total_rows=?, success_rows=?, failed_rows=?,
                   new_products=?, updated_prices=?
               WHERE id=?""",
            (
                stats.total_rows, stats.success_rows, stats.failed_rows,
                stats.new_products, stats.updated_prices, import_id,
            ),
        )

    def _save_offer(
        self,
        conn: sqlite3.Connection,
        normalized: NormalizedRow,
        match: MatchResult,
        supplier_id: int,
        import_id: int,
    ) -> tuple[int, bool]:
        """INSERT product_offer. Returns (offer_id, price_changed)."""
        existing = conn.execute(
            """SELECT id, price FROM product_offers
               WHERE supplier_id = ? AND standard_product_id = ? AND standard_name = ?""",
            (supplier_id, match.product_id, match.standard_name),
        ).fetchone()

        price_changed = (
            existing is not None
            and existing[1] != normalized.price
            and normalized.price is not None
        )

        cur = conn.execute(
            """INSERT INTO product_offers
               (supplier_id, standard_product_id, standard_name,
                attributes, cultivation_type, quality_grade, package_type,
                weight_value, weight_unit, quantity_value, quantity_unit,
                price, match_confidence, needs_review)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (
                supplier_id, match.product_id, match.standard_name,
                normalized.grade, normalized.cultivation_type, normalized.grade,
                normalized.package_type, normalized.weight_value, normalized.weight_unit,
                normalized.count, normalized.count_unit,
                normalized.price, match.confidence,
            ),
        )
        offer_id = existing[0] if existing else cur.lastrowid
        return offer_id, price_changed

    def _record_price_history(
        self,
        conn: sqlite3.Connection,
        offer_id: int,
        supplier_id: int,
        product_id: Optional[int],
        price: Optional[int],
        import_id: int,
    ) -> None:
        conn.execute(
            """INSERT INTO price_history
               (offer_id, supplier_id, product_id, price, import_id)
               VALUES (?,?,?,?,?)""",
            (offer_id, supplier_id, product_id, price, import_id),
        )

    def _upsert_review_queue(
        self,
        conn: sqlite3.Connection,
        parsed,
        normalized: NormalizedRow,
        supplier_id: int,
        import_id: int,
    ) -> bool:
        """
        Insert into review_queue.
        Deduplication: if a 'pending' entry already exists for the same
        supplier + original_name, skip insert and return False.
        Returns True if a new row was inserted, False if deduped.
        """
        existing = conn.execute(
            """SELECT id FROM review_queue
               WHERE supplier_id = ? AND original_name = ? AND status = 'pending'""",
            (supplier_id, parsed.original_name),
        ).fetchone()

        if existing:
            return False

        attrs = json.dumps(
            {
                "product_name":     normalized.product_name,
                "grade":            normalized.grade,
                "weight":           normalized.weight,
                "count":            normalized.count,
                "cultivation_type": normalized.cultivation_type,
                "tags":             normalized.tags,
            },
            ensure_ascii=False,
        )
        conn.execute(
            """INSERT INTO review_queue
               (import_id, supplier_id, supplier_name, original_name,
                normalized_attrs, price, file_name, status)
               VALUES (?,?,?,?,?,?,?,'pending')""",
            (
                import_id, supplier_id, parsed.supplier,
                parsed.original_name, attrs, parsed.price, parsed.file_name,
            ),
        )
        return True