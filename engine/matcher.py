"""
Matcher — resolves a NormalizedRow to a standard_products entry.

Search order:
  1. standard_products.standard_name == product_name  (direct, confidence 1.0)
  2. product_aliases.alias == product_name            (alias,  confidence 0.9)
  3. No match → MatchResult(matched=False)            → goes to review_queue

Matcher is the ONLY layer that queries the Product Master / Alias Master.
"""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from typing import Optional

from .normalizer import NormalizedRow


@dataclass
class MatchResult:
    matched: bool
    product_id: Optional[int]
    standard_name: Optional[str]
    confidence: float
    method: str   # 'direct' | 'alias' | 'unmatched'


class Matcher:
    """Stateless — takes a live DB connection per call."""

    def match(self, normalized: NormalizedRow, conn: sqlite3.Connection) -> MatchResult:
        name = normalized.product_name

        # 1. Direct match
        row = conn.execute(
            "SELECT id, standard_name FROM standard_products WHERE standard_name = ?",
            (name,),
        ).fetchone()
        if row:
            return MatchResult(
                matched=True,
                product_id=row[0],
                standard_name=row[1],
                confidence=1.0,
                method="direct",
            )

        # 2. Alias lookup
        row = conn.execute(
            """SELECT sp.id, sp.standard_name
               FROM product_aliases pa
               JOIN standard_products sp ON sp.id = pa.standard_product_id
               WHERE pa.alias = ?""",
            (name,),
        ).fetchone()
        if row:
            return MatchResult(
                matched=True,
                product_id=row[0],
                standard_name=row[1],
                confidence=0.9,
                method="alias",
            )

        # 3. No match
        return MatchResult(
            matched=False,
            product_id=None,
            standard_name=None,
            confidence=0.0,
            method="unmatched",
        )