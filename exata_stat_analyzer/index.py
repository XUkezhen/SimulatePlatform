from __future__ import annotations

from collections import defaultdict

from .models import Record
from .parser import normalize_key


class RecordIndex:
    def __init__(self, records: list[Record]) -> None:
        self.records = records
        self.by_metric: dict[str, list[Record]] = defaultdict(list)
        for record in records:
            self.by_metric[record.metric_key].append(record)

    def find(self, metric_name: str) -> list[Record]:
        return list(self.by_metric.get(normalize_key(metric_name), []))

    def filter(
        self,
        *,
        layer: str | None = None,
        module: str | None = None,
        metric_name: str | None = None,
        contains: str | None = None,
    ) -> list[Record]:
        if metric_name is not None:
            candidates = self.find(metric_name)
        else:
            candidates = list(self.records)

        results: list[Record] = []
        needle = normalize_key(contains) if contains else None
        for record in candidates:
            if layer and record.layer.lower() != layer.lower():
                continue
            if module and record.module.lower() != module.lower():
                continue
            if needle and needle not in record.metric_key:
                continue
            results.append(record)
        return results
