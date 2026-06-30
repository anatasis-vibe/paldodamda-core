"""
XLSX / XLS parser.
Streams ParsedRow objects from each sheet. Never modifies original_name.
Supports up to 100MB+ files via chunked sheet reading (pandas per-sheet, not all-at-once).
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterator, Optional
import pandas as pd

from .base import BaseParser, ParsedRow
from ._utils import (
    NAME_COLS, PRICE_COLS, OPTION_COLS,
    normalize_colname, first_match, find_header_row, parse_price,
)


class XlsxParser(BaseParser):

    def parse(self, file_path: str, supplier_name: str) -> Iterator[ParsedRow]:
        path = Path(file_path)
        try:
            xl = pd.ExcelFile(path)
        except Exception as exc:
            raise RuntimeError(f"Cannot open XLSX: {path.name} — {exc}") from exc

        for sheet_name in xl.sheet_names:
            yield from self._parse_sheet(xl, sheet_name, supplier_name, path.name)

    def _parse_sheet(self, xl, sheet_name: str, supplier_name: str, file_name: str) -> Iterator[ParsedRow]:
        try:
            raw = pd.read_excel(xl, sheet_name=sheet_name, header=None, dtype=str)
        except Exception:
            return

        header_row = find_header_row(raw)
        if header_row is None:
            # Fall back: treat row 0 as header
            df = pd.read_excel(xl, sheet_name=sheet_name, header=0, dtype=str)
        else:
            df = raw.iloc[header_row + 1:].copy()
            df.columns = raw.iloc[header_row].tolist()
            df = df.dropna(how="all")

        norm_cols = [normalize_colname(c) for c in df.columns]
        name_col  = first_match(norm_cols, NAME_COLS)
        price_col = first_match(norm_cols, PRICE_COLS)
        opt_col   = first_match(norm_cols, OPTION_COLS)

        if not name_col:
            return

        # Remap to normalized column names for safe access
        df.columns = norm_cols

        for _, row in df.iterrows():
            raw_name = row.get(name_col)
            if not raw_name or str(raw_name).strip() in ("", "nan", "None"):
                continue

            # Combine name + option as original_name (common in Korean wholesale sheets)
            name_str  = str(raw_name).strip()
            opt_str   = str(row.get(opt_col, "")).strip() if opt_col else ""
            original  = f"{name_str} {opt_str}".strip() if opt_str and opt_str != "nan" else name_str

            price = parse_price(row.get(price_col)) if price_col else None

            yield ParsedRow(
                original_name=original,
                price=price,
                supplier=supplier_name,
                file_name=file_name,
                raw={k: v for k, v in row.items()},
            )