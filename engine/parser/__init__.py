from .base import ParsedRow
from .xlsx import XlsxParser
from .html import HtmlParser
from .csv import CsvParser

def get_parser(file_path):
    """Return the appropriate parser for the given file path."""
    from pathlib import Path
    import io

    ext = Path(file_path).suffix.lower()
    if ext in (".xlsx", ".xls"):
        # Some .xls files are actually HTML exports
        try:
            with open(file_path, "rb") as f:
                head = f.read(512)
            if b"<html" in head.lower() or b"<!doctype" in head.lower() or b"<table" in head.lower():
                return HtmlParser()
        except Exception:
            pass
        return XlsxParser()
    elif ext in (".html", ".htm"):
        return HtmlParser()
    elif ext == ".csv":
        return CsvParser()
    else:
        raise ValueError(f"Unsupported file type: {ext}")

__all__ = ["ParsedRow", "XlsxParser", "HtmlParser", "CsvParser", "get_parser"]