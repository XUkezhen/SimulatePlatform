from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

from .models import FileAccessError, ParseError, Record

_WS_RE = re.compile(r"\s+")


def normalize_key(value: str) -> str:
    normalized = _WS_RE.sub(" ", value.strip().lower())
    return normalized.replace("-", " ")


def parse_value(raw_value: str) -> int | float | str:
    text = raw_value.strip()
    if not text:
        return ""
    try:
        if any(ch in text for ch in ".eE"):
            return float(text)
        return int(text)
    except ValueError:
        return text


def parse_line(line_no: int, raw_line: str) -> Record | None:
    stripped = raw_line.strip()
    if not stripped:
        return None

    parts = raw_line.rstrip("\n").split(",", 5)
    if len(parts) != 6:
        raise ParseError(f"Line {line_no} does not match EXata stat format")

    entity_id, address, index, layer, module, metric_expr = [part.strip() for part in parts]
    metric_name, sep, raw_value = metric_expr.rpartition("=")
    if not sep:
        raise ParseError(f"Line {line_no} does not contain a metric assignment")

    metric_name = metric_name.strip()
    return Record(
        line_no=line_no,
        entity_id=entity_id,
        address=address or None,
        index=index or None,
        layer=layer,
        module=module,
        metric_name=metric_name,
        metric_key=normalize_key(metric_name),
        value=parse_value(raw_value),
        raw_line=raw_line.rstrip("\n"),
    )


def iter_records(path: str | Path) -> Iterator[Record]:
    stat_path = Path(path)
    if not stat_path.exists() or not stat_path.is_file():
        raise FileAccessError(f"Stat file not found: {stat_path}")

    with stat_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            record = parse_line(line_no, raw_line)
            if record is not None:
                yield record


def parse_stat_file(path: str | Path) -> list[Record]:
    return list(iter_records(path))
