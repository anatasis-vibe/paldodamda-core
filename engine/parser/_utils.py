"""
Column detection utilities — engine-internal copy, tuned for Korean wholesale files.
Keyword lists are derived from scripts/common.py analysis of real supplier files.
"""
import re
from typing import Optional, List

# Column name keywords (exact Korean terms from real wholesale files, longest-first within each group)
NAME_COLS  = ["대표품목명", "대표상품명", "발주상품명", "품목명", "상품명", "제품명", "주문명", "품목", "품명"]
PRICE_COLS = ["공급단가", "공급가", "도매가", "판매가", "단가"]
OPTION_COLS = ["규격/옵션", "옵션명", "단위값", "규격", "옵션", "단위"]
ORIGIN_COLS = ["원산지", "출고지", "산지"]
SHIPPING_COLS = ["배송정책", "택배비", "배송비"]
STATUS_COLS = ["판매상태", "품절여부", "상태"]
MEMO_COLS  = ["상품간략설명", "특이사항", "비고"]

# Presence of any of these in a cell → row is likely the header
HEADER_HINTS = set(NAME_COLS) | {"공급가", "공급단가", "단가", "옵션명", "규격"}


def normalize_colname(col) -> str:
    """Strip whitespace only — preserve Korean characters and punctuation."""
    if col is None:
        return ""
    return re.sub(r"\s+", "", str(col)).strip()


def first_match(norm_cols: List[str], keywords: List[str]) -> Optional[str]:
    """Return the first norm_col that equals any keyword (exact match after normalize)."""
    kw_set = {normalize_colname(k) for k in keywords}
    for col in norm_cols:
        if col in kw_set:
            return col
    return None


def find_header_row(df, max_scan: int = 15) -> Optional[int]:
    """
    Scan first max_scan rows for a row containing any HEADER_HINTS keyword.
    Returns row index or None.
    """
    for i in range(min(max_scan, len(df))):
        row_vals = {normalize_colname(v) for v in df.iloc[i].tolist()}
        if row_vals & HEADER_HINTS:
            return i
    return None


def parse_price(raw) -> Optional[int]:
    """Extract integer price from strings like '12,000원' or '12000'."""
    if raw is None:
        return None
    cleaned = re.sub(r"[^\d]", "", str(raw))
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None