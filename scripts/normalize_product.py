"""Seed standard_products/product_aliases and match raw_items -> product_offers."""
import re
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import extract_jeju_island_fee

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "paldodamda.db"

# standard_name -> category
STANDARD_PRODUCTS = {
    "감귤": "과일", "천혜향": "과일", "레드향": "과일", "카라향": "과일",
    "한라봉": "과일", "애플망고": "과일", "신비복숭아": "과일",
    "대극천복숭아": "과일", "백도복숭아": "과일", "황도복숭아": "과일",
    "납작복숭아": "과일", "조치원복숭아": "과일", "샤인머스켓": "과일",
    "거봉": "과일", "캠벨포도": "과일", "초당옥수수": "농산물",
    "감자": "농산물", "고구마": "농산물", "참외": "과일", "수박": "과일",
    "씨없는수박": "과일", "대저토마토": "농산물", "부사사과": "과일",
    "홍옥사과": "과일", "방울토마토": "농산물", "매실": "과일",
    "자두": "과일", "추희자두": "과일",
}

# alias -> (standard_name, attributes_hint)
ALIAS_SEED = [
    # direct self-aliases generated below; this list is for known spelling
    # variants / shorthand that differ from the standard name itself.
    ("귤", "감귤", None),
    ("제주감귤", "감귤", "제주"),
    ("애망", "애플망고", None),
    ("신비", "신비복숭아", None),
    ("대극천", "대극천복숭아", None),
    ("백도", "백도복숭아", None),
    ("황도", "황도복숭아", None),
    ("샤인", "샤인머스켓", None),
    ("스테비아 방울토마토", "방울토마토", "스테비아"),
    ("씨없는 수박", "씨없는수박", None),
]

ATTRIBUTE_KEYWORDS = {
    "cultivation_type": ["노지", "하우스", "시설"],
    "quality_grade": ["특품", "상품", "중품", "하품", "프리미엄", "로얄", "실속", "못난이", "가정용", "선물용"],
    "package_type": ["아이스박스", "선물세트", "박스포함", "실중량"],
}
QUALITY_KEYWORDS = ["고당도", "GAP", "무농약", "유기농"] + ATTRIBUTE_KEYWORDS["quality_grade"]
SIZE_KEYWORDS = ["왕특", "특대", "대과", "중과", "소과", "특", "대", "중", "소"]

WEIGHT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|KG|G)")
QTY_RE = re.compile(r"(\d+)\s*(과|입|개|수|구)\b")
PRICE_RE = re.compile(r"[\d,]+")


def parse_price(raw_price):
    if not raw_price:
        return None
    m = PRICE_RE.search(str(raw_price).replace("₩", ""))
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def parse_weight(text):
    m = WEIGHT_RE.search(text)
    if not m:
        return None, None
    return float(m.group(1)), m.group(2).lower()


def parse_quantity(text):
    m = QTY_RE.search(text)
    if not m:
        return None, None
    return int(m.group(1)), m.group(2)


def find_attribute(text, keywords):
    for k in keywords:
        if k in text:
            return k
    return None


def build_alias_index(conn):
    """Returns list of (alias, standard_name, standard_product_id) sorted by alias length desc."""
    cur = conn.execute("SELECT id, standard_name FROM standard_products")
    name_to_id = {name: pid for pid, name in cur.fetchall()}

    aliases = []
    for name in STANDARD_PRODUCTS:
        aliases.append((name, name, name_to_id[name]))
    for alias, std_name, hint in ALIAS_SEED:
        if std_name in name_to_id:
            aliases.append((alias, std_name, name_to_id[std_name]))
            conn.execute(
                "INSERT INTO product_aliases (alias, standard_product_id, standard_name, attributes_hint) VALUES (?,?,?,?)",
                (alias, name_to_id[std_name], std_name, hint),
            )
    conn.commit()
    aliases.sort(key=lambda x: -len(x[0]))
    return aliases


def match_standard_product(name_text, aliases):
    for alias, std_name, pid in aliases:
        if alias in name_text:
            confidence = 1.0 if len(alias) >= 3 else 0.7
            return std_name, pid, confidence
    return None, None, 0.0


def seed_standard_products(conn):
    for name, category in STANDARD_PRODUCTS.items():
        conn.execute(
            "INSERT OR IGNORE INTO standard_products (standard_name, category) VALUES (?, ?)",
            (name, category),
        )
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM product_offers")
    conn.execute("DELETE FROM product_aliases")
    conn.execute("DELETE FROM standard_products")
    conn.commit()

    seed_standard_products(conn)
    aliases = build_alias_index(conn)

    cur = conn.execute(
        """SELECT id, supplier_id, raw_product_name, raw_option, raw_price,
                  raw_origin, raw_memo, raw_status, raw_shipping
           FROM raw_items"""
    )
    rows = cur.fetchall()

    matched, review = 0, 0
    for (rid, supplier_id, raw_name, raw_option, raw_price, raw_origin,
         raw_memo, raw_status, raw_shipping) in rows:
        full_text = " ".join(str(x) for x in [raw_name, raw_option] if x)
        std_name, std_id, confidence = match_standard_product(full_text, aliases)
        needs_review = 1 if confidence < 0.7 else 0
        if std_name:
            matched += 1
        if needs_review:
            review += 1

        cultivation = find_attribute(full_text, ATTRIBUTE_KEYWORDS["cultivation_type"])
        quality = find_attribute(full_text, QUALITY_KEYWORDS)
        package = find_attribute(full_text, ATTRIBUTE_KEYWORDS["package_type"])
        weight_value, weight_unit = parse_weight(full_text)
        qty_value, qty_unit = parse_quantity(full_text)
        price = parse_price(raw_price)

        shipping_text = " ".join(str(x) for x in [raw_shipping, raw_memo] if x)
        jeju_avail, jeju_fee, island_avail, island_fee = extract_jeju_island_fee(shipping_text)

        conn.execute(
            """INSERT INTO product_offers
               (raw_item_id, supplier_id, standard_product_id, standard_name,
                attributes, cultivation_type, quality_grade, package_type,
                weight_value, weight_unit, quantity_value, quantity_unit,
                option_text, origin, price, jeju_available, jeju_extra_fee,
                island_available, island_extra_fee, status, match_confidence,
                needs_review)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid, supplier_id, std_id, std_name or raw_name,
                quality, cultivation, quality, package,
                weight_value, weight_unit, qty_value, qty_unit,
                raw_option, raw_origin, price, jeju_avail, jeju_fee,
                island_avail, island_fee, raw_status, confidence, needs_review,
            ),
        )

    conn.commit()
    print(f"Total offers: {len(rows)}")
    print(f"Matched to standard product: {matched}")
    print(f"Needs review (low confidence): {review}")
    conn.close()


if __name__ == "__main__":
    main()
