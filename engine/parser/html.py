"""HTML parser — handles table-based wholesale HTML exports."""
from __future__ import annotations
import io
from pathlib import Path
from typing import Iterator
import pandas as pd

from .base import BaseParser, ParsedRow
from ._utils import (
    NAME_COLS, PRICE_COLS, OPTION_COLS,
    normalize_colname, first_match, find_header_row, parse_price,
)


class HtmlParser(BaseParser):

    def parse(self, file_path: str, supplier_name: str) -> Iterator[ParsedRow]:
        path = Path(file_path)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            raise RuntimeError(f"Cannot read HTML: {path.name} — {exc}") from exc

        try:
            # header=0 lets pandas use the first <tr> as columns,
            # but we then scan body rows for the real Korean header.
            tables = pd.read_html(io.StringIO(text))
        except Exception:
            return

        for raw in tables:
            if raw.shape[0] < 2:
                continue
            yield from self._parse_table(raw, supplier_name, path.name)

    def _parse_table(self, raw, supplier_name: str, file_name: str) -> Iterator[ParsedRow]:
        header_row = find_header_row(raw)
        if header_row is None:
            return

        df = raw.iloc[header_row + 1:].copy()
        df.columns = [normalize_colname(c) for c in raw.iloc[header_row].tolist()]
        df = df.dropna(how="all")

        norm_cols = list(df.columns)
        name_col  = first_match(norm_cols, NAME_COLS)
        price_col = first_match(norm_cols, PRICE_COLS)
        opt_col   = first_match(norm_cols, OPTION_COLS)

        if not name_col:
            return

        for _, row in df.iterrows():
            raw_name = row.get(name_col)
            if not raw_name or str(raw_name).strip() in ("", "nan", "None", "NaN"):
                continue

            name_str = str(raw_name).strip()
            opt_str  = str(row.get(opt_col, "")).strip() if opt_col else ""
            original = f"{name_str} {opt_str}".strip() if opt_str and opt_str not in ("nan", "None", "NaN") else name_str

            price = parse_price(row.get(price_col)) if price_col else None

            yield ParsedRow(
                original_name=original,
                price=price,
                supplier=supplier_name,
                file_name=file_name,
                raw={k: v for k, v in row.items()},
            )