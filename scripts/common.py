"""Shared helpers for parsing supplier price files of mixed type."""
import re
import json
import unicodedata

NAME_COLS = ["상품명", "품목", "품목명", "제품명", "대표품목명", "대표상품명"]
ORDER_NAME_COLS = ["발주상품명", "주문명", "관리코드명"]
OPTION_COLS = ["옵션명", "규격", "옵션", "규격/옵션", "단위", "단위값"]
PRICE_COLS = ["공급가", "공급단가()", "공급단가", "도매가", "단가"]
ORIGIN_COLS = ["원산지", "출고지", "산지"]
SHIPPING_COLS = ["택배비", "배송비", "배송정책"]
STATUS_COLS = ["품절여부", "판매상태", "상태"]
DEADLINE_COLS = ["발주마감시간", "마감시간"]
MEMO_COLS = ["특이사항", "비고", "상품간략설명", "상품상세설명"]

HEADER_HINT_WORDS = set(NAME_COLS) | {"공급가", "공급단가", "단가", "옵션명", "규격"}


def first_match(row_values, candidates):
    for c in candidates:
        if c in row_values:
            return c
    return None


def find_header_row(raw_df, max_scan=15):
    """Scan the first N rows of a headerless dataframe for the row that looks
    like a column header (contains a product-name-ish keyword)."""
    for i in range(min(max_scan, len(raw_df))):
        values = [normalize_colname(v) for v in raw_df.iloc[i].tolist()]
        if any(v in HEADER_HINT_WORDS for v in values):
            return i
    return None


def normalize_colname(c):
    if c is None:
        return ""
    s = str(c).strip()
    s = re.sub(r"\s+", "", s)
    return s


def extract_jeju_island_fee(text):
    """Pull 제주/도서산간 extra fee + availability out of a free-text shipping note."""
    if not text or not isinstance(text, str):
        return ("UNKNOWN", None, "UNKNOWN", None)
    t = text.replace(" ", "")
    jeju_avail, jeju_fee = "UNKNOWN", None
    island_avail, island_fee = "UNKNOWN", None

    jeju_m = re.search(r"제주(?:도)?[:\s]*([0-9,]+)\s*원", t)
    if jeju_m:
        jeju_avail = "Y"
        jeju_fee = int(jeju_m.group(1).replace(",", ""))
    elif re.search(r"제주.*?(불가|발송불가|배송불가)", t):
        jeju_avail = "N"
    elif "제주" in t:
        jeju_avail = "Y"

    island_m = re.search(r"도서산간[:\s]*([0-9,]+)\s*원", t)
    if island_m:
        island_avail = "Y"
        island_fee = int(island_m.group(1).replace(",", ""))
    elif re.search(r"도서산간.*?(불가|발송불가|배송불가)", t):
        island_avail = "N"
    elif "도서산간" in t:
        island_avail = "Y"

    return (jeju_avail, jeju_fee, island_avail, island_fee)


def guess_supplier_from_text(*texts):
    """Look for a '<name> 위탁/공급/단가표' style title embedded in early rows."""
    for t in texts:
        if not t or not isinstance(t, str):
            continue
        m = re.search(r"([가-힣A-Za-z0-9]{2,20})\s+(위탁|단가표)", t)
        if m and m.group(1) not in HEADER_HINT_WORDS:
            return m.group(1)
    return None


def clean_filename_supplier(filename):
    base = filename
    for ext in (".xlsx", ".xls", ".html", ".htm"):
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
    base = re.sub(r"\(\d+\)$", "", base).strip()
    base = re.sub(r"_\d{10,}$", "", base).strip()
    base = re.sub(r"_\d{8}.*$", "", base).strip()
    base = unicodedata.normalize("NFC", base)
    base = re.sub(r"^[^\w가-힣]+|[^\w가-힣]+$", "", base)
    return base or filename


def to_json_safe(d):
    out = {}
    for k, v in d.items():
        try:
            json.dumps(v)
            out[k] = v
        except TypeError:
            out[k] = str(v)
    return out
