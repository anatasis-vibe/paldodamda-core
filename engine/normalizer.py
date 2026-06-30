"""
Normalizer — extracts structured attributes from a raw product name.

Rules are loaded from attribute_rules table at construction time (cached in-memory).
Weight and count are extracted via regex (not attribute_rules).
Does NOT query Product Master or Alias Master.
"""
from __future__ import annotations
import re
import sqlite3
import json
from dataclasses import dataclass, field
from typing import Optional
from .parser.base import ParsedRow

# Regex: weight like 2kg / 500g / 1.5KG
_WEIGHT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g)", re.IGNORECASE)
# Regex: count like 8과 / 10입 / 5개
_COUNT_RE  = re.compile(r"(\d+)\s*(과|입|개|수|구)\b")


@dataclass
class NormalizedRow:
    # ── passthrough from ParsedRow ──────────────────────
    original_name: str
    price: Optional[int]
    supplier: str
    file_name: str
    raw: dict = field(default_factory=dict)
    # ── extracted attributes ────────────────────────────
    product_name: str = ""
    grade: Optional[str] = None
    weight: Optional[str] = None          # "2kg"
    weight_value: Optional[float] = None
    weight_unit: Optional[str] = None
    count: Optional[int] = None
    count_unit: Optional[str] = None
    size: Optional[str] = None
    cultivation_type: Optional[str] = None
    package_type: Optional[str] = None
    tags: list = field(default_factory=list)


class Normalizer:
    """
    Load attribute_rules once from DB and use them to parse product names.
    Instance is created once per ImportEngine run (not per row).
    """

    def __init__(self, db_path: str):
        self._rules: dict[str, list[tuple[str, str]]] = {}
        self._load_rules(db_path)

    def _load_rules(self, db_path: str) -> None:
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                """SELECT keyword, attribute, value
                   FROM attribute_rules
                   WHERE enabled = 1
                   ORDER BY priority DESC, LENGTH(keyword) DESC"""
            ).fetchall()
        finally:
            conn.close()

        for keyword, attribute, value in rows:
            self._rules.setdefault(attribute, []).append((keyword, value))

    def normalize(self, parsed: ParsedRow) -> NormalizedRow:
        text   = parsed.original_name
        result = NormalizedRow(
            original_name=text,
            price=parsed.price,
            supplier=parsed.supplier,
            file_name=parsed.file_name,
            raw=parsed.raw,
        )
        removed: list[str] = []

        # 1. Weight (regex — highest specificity)
        m = _WEIGHT_RE.search(text)
        if m:
            result.weight_value = float(m.group(1))
            result.weight_unit  = m.group(2).lower()
            result.weight       = f"{m.group(1)}{result.weight_unit}"
            removed.append(m.group(0))

        # 2. Count (regex)
        m = _COUNT_RE.search(text)
        if m:
            result.count      = int(m.group(1))
            result.count_unit = m.group(2)
            removed.append(m.group(0))

        # 3. Keyword-based attributes from attribute_rules
        #    Keywords are already sorted: priority DESC, length DESC
        ATTR_MAP = {
            "grade":            "_set_grade",
            "cultivation_type": "_set_cultivation",
            "package_type":     "_set_package",
            "tag":              "_add_tag",
        }

        for attribute, kw_pairs in self._rules.items():
            if attribute == "weight_unit":
                continue
            for keyword, value in kw_pairs:
                if keyword not in text:
                    continue
                if attribute == "grade" and result.grade is None:
                    result.grade = value
                    removed.append(keyword)
                    break
                elif attribute == "cultivation_type" and result.cultivation_type is None:
                    result.cultivation_type = value
                    removed.append(keyword)
                    break
                elif attribute == "package_type" and result.package_type is None:
                    result.package_type = value
                    removed.append(keyword)
                    break
                elif attribute == "tag":
                    if value not in result.tags:
                        result.tags.append(value)
                        removed.append(keyword)
                    # continue — multiple tags allowed

        # 4. Build clean product_name by removing matched tokens
        product_name = text
        # Remove longest tokens first to avoid partial re-removal
        for token in sorted(removed, key=len, reverse=True):
            product_name = product_name.replace(token, " ")
        result.product_name = " ".join(product_name.split()).strip()

        return result