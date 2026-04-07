from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Layer = Literal["physical", "network", "transport", "application"]
TrafficClass = Literal["unicast", "broadcast", "multicast"]
Aggregation = Literal["sum", "mean", "max", "per_entity"]
RateBasis = Literal["auto", "throughput", "offered_load", "goodput", "carried_load"]
LossBasis = Literal["application", "network", "queue"]
Method = Literal["direct", "computed", "unavailable"]


@dataclass(frozen=True)
class Record:
    line_no: int
    entity_id: str
    address: str | None
    index: str | None
    layer: str
    module: str
    metric_name: str
    metric_key: str
    value: int | float | str
    raw_line: str


@dataclass(frozen=True)
class MetricSelector:
    layer: Layer | None = None
    protocol: str | None = None
    traffic_class: TrafficClass | None = None
    aggregation: Aggregation = "mean"


@dataclass(frozen=True)
class AnalysisRequest:
    metrics: list[str] = field(default_factory=lambda: [
        "application_throughput",
        "transport_throughput",
        "application_delay",
        "transport_delay",
        "network_delay",
        "application_jitter",
        "transport_jitter",
        "network_jitter",
        "packet_loss_rate",
        "routing_convergence_time",
        "link_utilization",
    ])
    selector: MetricSelector = field(default_factory=MetricSelector)
    rate_basis: RateBasis = "auto"
    loss_basis: LossBasis = "application"
    config_path: str | None = None
    app_path: str | None = None


@dataclass(frozen=True)
class MetricResult:
    available: bool
    value: Any
    unit: str | None
    method: Method
    basis: str | None = None
    scope: dict[str, Any] = field(default_factory=dict)
    reason_code: str | None = None
    reason: str | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisResult:
    schema_version: str
    source: dict[str, Any]
    request: dict[str, Any]
    metrics: dict[str, MetricResult]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source": self.source,
            "request": self.request,
            "metrics": {name: result.to_dict() for name, result in self.metrics.items()},
            "warnings": list(self.warnings),
        }


class ExataStatAnalyzerError(Exception):
    pass


class ParseError(ExataStatAnalyzerError):
    pass


class FileAccessError(ExataStatAnalyzerError):
    pass


def request_to_dict(request: AnalysisRequest) -> dict[str, Any]:
    return {
        "metrics": list(request.metrics),
        "selector": asdict(request.selector),
        "rate_basis": request.rate_basis,
        "loss_basis": request.loss_basis,
        "config_path": request.config_path,
        "app_path": request.app_path,
    }


def source_to_dict(path: Path, parsed_records: int) -> dict[str, Any]:
    return {"file": str(path), "parsed_records": parsed_records}
