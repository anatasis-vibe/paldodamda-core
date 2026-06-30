"""CSV parser — auto-detects encoding (utf-8-sig / euc-kr / cp949)."""
from __future__ import annotations
from pathlib import Path
from typing import Iterator
import pandas as pd

from .base import BaseParser, ParsedRow
from ._utils import (
    NAME_COLS, PRICE_COLS, OPTION_COLS,
    normalize_colname, first_match, parse_price,
)

_ENCODINGS = ["utf-8-sig", "utf-8", "euc-kr", "cp949"]


class CsvParser(BaseParser):

    def parse(self, file_path: str, supplier_name: str) -> Iterator[ParsedRow]:
        path = Path(file_path)
        df = None
        for enc in _ENCODINGS:
            try:
                df = pd.read_csv(path, encoding=enc, dtype=str)
                break
            except (UnicodeDecodeError, Exception):
                continue

        if df is None or df.empty:
            return

        norm_cols = [normalize_colname(c) for c in df.columns]
        name_col  = first_match(norm_cols, NAME_COLS)
        price_col = first_match(norm_cols, PRICE_COLS)
        opt_col   = first_match(norm_cols, OPTION_COLS)

        if not name_col:
            return

        df.columns = norm_cols
        df = df.dropna(how="all")

        for _, row in df.iterrows():
            raw_name = row.get(name_col)
            if not raw_name or str(raw_name).strip() in ("", "nan", "None"):
                continue

            name_str = str(raw_name).strip()
            opt_str  = str(row.get(opt_col, "")).strip() if opt_col else ""
            original = f"{name_str} {opt_str}".strip() if opt_str and opt_str != "nan" else name_str

            price = parse_price(row.get(price_col)) if price_col else None

            yield ParsedRow(
                original_name=original,
                price=price,
                supplier=supplier_name,
                file_name=path.name,
                raw={k: v for k, v in row.items()},
            )