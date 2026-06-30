"""Scan data/raw, parse every xlsx/xls/html file regardless of extension,
and load everything into raw_items (SQLite). Original files are never modified.
"""
import io
import sys
import json
import sqlite3
import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    NAME_COLS, OPTION_COLS, PRICE_COLS, ORIGIN_COLS, SHIPPING_COLS,
    STATUS_COLS, DEADLINE_COLS, MEMO_COLS,
    first_match, find_header_row, normalize_colname,
    guess_supplier_from_text, clean_filename_supplier, to_json_safe,
)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "paldodamda.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".pdf"}
NOTICE_KEYWORDS = ["안내사항", "공지사항", "필독", "당근마켓추천"]


def init_db(conn):
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def get_or_create_supplier(conn, name, memo=None):
    cur = conn.execute("SELECT id FROM suppliers WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO suppliers (name, memo) VALUES (?, ?)", (name, memo)
    )
    conn.commit()
    return cur.lastrowid


def create_source_file(conn, supplier_id, file_name, file_path, file_type,
                        sheet_name, table_index, parsed_status, row_count, memo=None):
    cur = conn.execute(
        """INSERT INTO source_files
           (supplier_id, file_name, file_path, file_type, sheet_name,
            table_index, parsed_status, row_count, memo, received_date)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (supplier_id, file_name, file_path, file_type, sheet_name,
         table_index, parsed_status, row_count, memo,
         datetime.date.today().isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def map_header(columns):
    """Map a raw header row (list of strings) to canonical field -> column name."""
    norm = [normalize_colname(c) for c in columns]
    mapping = {}
    mapping["name"] = first_match(norm, NAME_COLS)
    mapping["option"] = first_match(norm, OPTION_COLS)
    mapping["price"] = first_match(norm, PRICE_COLS)
    mapping["origin"] = first_match(norm, ORIGIN_COLS)
    mapping["shipping"] = first_match(norm, SHIPPING_COLS)
    mapping["status"] = first_match(norm, STATUS_COLS)
    mapping["deadline"] = first_match(norm, DEADLINE_COLS)
    memo_cols = [c for c in norm if c in MEMO_COLS]
    mapping["memo_cols"] = memo_cols
    return mapping, norm


def df_to_raw_items(conn, df, supplier_id, source_file_id, default_shipping_text=None):
    if df.empty:
        return 0
    df.columns = [normalize_colname(c) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    mapping, norm_cols = map_header(list(df.columns))
    if not mapping["name"]:
        return 0  # no recognizable product-name column; nothing to ingest as items

    count = 0
    for _, row in df.iterrows():
        name = row.get(mapping["name"])
        if pd.isna(name) or not str(name).strip():
            continue
        option = row.get(mapping["option"]) if mapping["option"] else None
        price = row.get(mapping["price"]) if mapping["price"] else None
        origin = row.get(mapping["origin"]) if mapping["origin"] else None
        shipping = row.get(mapping["shipping"]) if mapping["shipping"] else None
        if (shipping is None or (isinstance(shipping, float) and pd.isna(shipping))) and default_shipping_text:
            shipping = default_shipping_text
        status = row.get(mapping["status"]) if mapping["status"] else None
        memo_parts = []
        for mc in mapping["memo_cols"]:
            v = row.get(mc)
            if pd.notna(v) and str(v).strip():
                memo_parts.append(str(v).strip())
        memo = " | ".join(memo_parts) if memo_parts else None

        raw_json = to_json_safe({k: (None if pd.isna(v) else v) for k, v in row.items()})

        conn.execute(
            """INSERT INTO raw_items
               (supplier_id, source_file_id, raw_product_name, raw_option,
                raw_price, raw_origin, raw_memo, raw_status, raw_shipping, raw_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                supplier_id, source_file_id, str(name).strip(),
                None if option is None or pd.isna(option) else str(option).strip(),
                None if price is None or pd.isna(price) else str(price).strip(),
                None if origin is None or pd.isna(origin) else str(origin).strip(),
                memo,
                None if status is None or pd.isna(status) else str(status).strip(),
                None if shipping is None or pd.isna(shipping) else str(shipping).strip(),
                json.dumps(raw_json, ensure_ascii=False),
            ),
        )
        count += 1
    conn.commit()
    return count


def parse_xlsx_file(conn, path):
    supplier_guess = clean_filename_supplier(path.name)
    try:
        xl = pd.ExcelFile(path)
    except Exception as e:
        sid = get_or_create_supplier(conn, supplier_guess)
        create_source_file(conn, sid, path.name, str(path), "xlsx", None, None,
                            "error", 0, memo=str(e))
        print(f"[xlsx] {path.name}: ERROR {e}")
        return

    total_rows = 0
    for sheet_idx, sheet_name in enumerate(xl.sheet_names):
        raw = pd.read_excel(xl, sheet_name=sheet_name, header=None)
        header_row = find_header_row(raw)
        pre_header = raw.head(header_row) if header_row else raw.head(4)
        title_text = " ".join(str(v) for v in pre_header.values.flatten() if pd.notna(v))
        supplier_name = guess_supplier_from_text(title_text) or supplier_guess
        sid = get_or_create_supplier(conn, supplier_name, memo=f"file:{path.name}")

        banner_text = None
        if header_row is not None:
            for i in range(header_row):
                for v in raw.iloc[i].tolist():
                    if isinstance(v, str) and ("제주" in v or "도서산간" in v) and "원" in v:
                        banner_text = v
                        break
                if banner_text:
                    break

        if header_row is None:
            # fall back to default header=0 read
            try:
                df = pd.read_excel(xl, sheet_name=sheet_name, header=0)
            except Exception:
                df = pd.DataFrame()
            status = "no-header-detected"
        else:
            df = raw.iloc[header_row + 1:].copy()
            df.columns = raw.iloc[header_row].tolist()
            df = df.dropna(how="all")
            status = "ok"

        sfid = create_source_file(conn, sid, path.name, str(path), "xlsx",
                                   sheet_name, sheet_idx, status, len(df))
        n = df_to_raw_items(conn, df, sid, sfid, default_shipping_text=banner_text)
        total_rows += n
    print(f"[xlsx] {path.name}: {total_rows} rows")


def parse_html_file(conn, path):
    base = clean_filename_supplier(path.name)
    is_notice = any(k in path.name for k in NOTICE_KEYWORDS)
    supplier_id = get_or_create_supplier(conn, f"미확인-{base}")

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        create_source_file(conn, supplier_id, path.name, str(path), "html", None, None,
                            "error", 0, memo=str(e))
        return

    try:
        tables = pd.read_html(io.StringIO(text))
    except Exception as e:
        create_source_file(conn, supplier_id, path.name, str(path), "html", None, None,
                            "no-tables" if is_notice else "error", 0, memo=str(e))
        print(f"[html] {path.name}: 0 rows (no tables)")
        return

    total_rows = 0
    for idx, raw in enumerate(tables):
        if raw.shape[0] < 2:
            continue
        header_row = find_header_row(raw)
        if header_row is None:
            sfid = create_source_file(conn, supplier_id, path.name, str(path), "html",
                                       None, idx, "no-header-detected", len(raw))
            continue

        banner_text = None
        for i in range(header_row):
            for v in raw.iloc[i].tolist():
                if isinstance(v, str) and ("제주" in v or "도서산간" in v) and "원" in v:
                    banner_text = v
                    break
            if banner_text:
                break

        df = raw.iloc[header_row + 1:].copy()
        df.columns = raw.iloc[header_row].tolist()
        df = df.dropna(how="all")
        sfid = create_source_file(conn, supplier_id, path.name, str(path), "html",
                                   None, idx, "ok", len(df))
        n = df_to_raw_items(conn, df, supplier_id, sfid, default_shipping_text=banner_text)
        total_rows += n
    print(f"[html] {path.name}: {total_rows} rows")


def is_actually_html(path):
    try:
        with open(path, "rb") as f:
            head = f.read(512)
        return b"<html" in head.lower() or b"<!doctype" in head.lower() or b"<table" in head.lower()
    except Exception:
        return False


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    files = sorted(RAW_DIR.iterdir())
    for path in files:
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext in SKIP_EXT:
            continue
        if ext in (".html", ".htm"):
            parse_html_file(conn, path)
        elif ext == ".xls":
            if is_actually_html(path):
                parse_html_file(conn, path)
            else:
                parse_xlsx_file(conn, path)
        elif ext == ".xlsx":
            parse_xlsx_file(conn, path)
        else:
            print(f"[skip] {path.name}: unsupported extension")

    cur = conn.execute("SELECT COUNT(*) FROM raw_items")
    print(f"\nTotal raw_items: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT COUNT(*) FROM source_files")
    print(f"Total source_files: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT COUNT(*) FROM suppliers")
    print(f"Total suppliers: {cur.fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    main()
