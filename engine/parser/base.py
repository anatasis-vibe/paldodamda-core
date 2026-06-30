"""
Parser base: ParsedRow dataclass and abstract parser interface.
Parsers never modify original_name — raw data only.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Iterator


@dataclass
class ParsedRow:
    """One product row as read from a source file. Immutable — no normalization applied."""
    original_name: str
    price: Optional[int]
    supplier: str
    file_name: str
    raw: dict = field(default_factory=dict)


class BaseParser:
    """All parsers must implement parse() returning an iterator of ParsedRow."""

    def parse(self, file_path: str, supplier_name: str) -> Iterator[ParsedRow]:
        raise NotImplementedError