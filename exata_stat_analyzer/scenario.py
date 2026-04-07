from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .models import FileAccessError, ParseError

_APP_FILE_RE = re.compile(r"^\s*APP-CONFIG-FILE\s+(\S+)\s*$", re.IGNORECASE)
_SIM_TIME_RE = re.compile(r"^\s*SIMULATION-TIME\s+([0-9]+(?:\.[0-9]+)?)S\s*$", re.IGNORECASE)
_IP_MAP_RE = re.compile(r"^\s*\[[^\]]+/(\d+)/\d+\]\s+IP-ADDRESS\s+([0-9]+(?:\.[0-9]+){3})\s*$", re.IGNORECASE)
_CBR_LINE_RE = re.compile(
    r"^\s*CBR\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([0-9]+(?:\.[0-9]+)?)S\s+([0-9]+(?:\.[0-9]+)?)S\s+([0-9]+(?:\.[0-9]+)?)S(?:\s+\S+)?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CbrTemplate:
    src_node_id: str
    dst_node_id: str
    messages_to_send: int
    payload_bytes: int
    interval_s: float
    start_s: float
    end_s: float
    line_no: int


@dataclass(frozen=True)
class CbrTemplateGroup:
    src_node_id: str
    dst_node_id: str
    payload_bytes: int
    interval_s: float
    start_s: float
    end_s: float
    duration_s: float
    configured_count: int
    message_counts: list[int] = field(default_factory=list)
    line_nos: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class ScenarioContext:
    config_path: Path
    app_path: Path | None
    simulation_time_s: float | None
    ip_to_node: dict[str, str]
    cbr_template_groups: list[CbrTemplateGroup]


def _round_key(value: float) -> float:
    return round(float(value), 6)


def _build_template_groups(templates: list[CbrTemplate]) -> list[CbrTemplateGroup]:
    grouped: dict[tuple[str, str, int, float, float, float], dict[str, object]] = {}
    for template in templates:
        key = (
            template.src_node_id,
            template.dst_node_id,
            template.payload_bytes,
            _round_key(template.interval_s),
            _round_key(template.start_s),
            _round_key(template.end_s),
        )
        entry = grouped.get(key)
        if entry is None:
            grouped[key] = {
                "configured_count": 1,
                "message_counts": [template.messages_to_send],
                "line_nos": [template.line_no],
            }
            continue
        entry["configured_count"] = int(entry["configured_count"]) + 1
        entry["message_counts"].append(template.messages_to_send)
        entry["line_nos"].append(template.line_no)

    groups: list[CbrTemplateGroup] = []
    for (src, dst, payload, interval_s, start_s, end_s), meta in sorted(grouped.items()):
        groups.append(
            CbrTemplateGroup(
                src_node_id=src,
                dst_node_id=dst,
                payload_bytes=payload,
                interval_s=interval_s,
                start_s=start_s,
                end_s=end_s,
                duration_s=max(end_s - start_s, 0.0),
                configured_count=int(meta["configured_count"]),
                message_counts=sorted(set(int(value) for value in meta["message_counts"])),
                line_nos=sorted(int(value) for value in meta["line_nos"]),
            )
        )
    return groups


def _parse_app_file(app_path: Path) -> list[CbrTemplate]:
    if not app_path.exists() or not app_path.is_file():
        raise FileAccessError(f"App file not found: {app_path}")

    templates: list[CbrTemplate] = []
    with app_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = _CBR_LINE_RE.match(stripped)
            if not match:
                continue

            src, dst, count, payload, interval_s, start_s, end_s = match.groups()
            templates.append(
                CbrTemplate(
                    src_node_id=src,
                    dst_node_id=dst,
                    messages_to_send=int(count),
                    payload_bytes=int(payload),
                    interval_s=float(interval_s),
                    start_s=float(start_s),
                    end_s=float(end_s),
                    line_no=line_no,
                )
            )
    return templates


def load_scenario_context(config_path: str | Path, app_path: str | Path | None = None) -> ScenarioContext:
    resolved = Path(config_path)
    if not resolved.exists() or not resolved.is_file():
        raise FileAccessError(f"Config file not found: {resolved}")

    app_file_name: str | None = None
    simulation_time_s: float | None = None
    ip_to_node: dict[str, str] = {}

    with resolved.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            app_match = _APP_FILE_RE.match(line)
            if app_match:
                app_file_name = app_match.group(1)
                continue

            sim_match = _SIM_TIME_RE.match(line)
            if sim_match:
                simulation_time_s = float(sim_match.group(1))
                continue

            ip_match = _IP_MAP_RE.match(line)
            if ip_match:
                node_id, ip = ip_match.groups()
                ip_to_node[ip] = node_id
                continue

            if line.upper().startswith("APP-CONFIG-FILE") and app_file_name is None:
                raise ParseError(f"Line {line_no} has malformed APP-CONFIG-FILE entry")

    resolved_app_path: Path | None = None
    templates: list[CbrTemplate] = []

    if app_path is not None:
        resolved_app_path = Path(app_path)
        if not resolved_app_path.is_absolute():
            resolved_app_path = resolved.parent / resolved_app_path
        templates = _parse_app_file(resolved_app_path)
    elif app_file_name:
        resolved_app_path = resolved.parent / app_file_name
        templates = _parse_app_file(resolved_app_path)

    return ScenarioContext(
        config_path=resolved,
        app_path=resolved_app_path,
        simulation_time_s=simulation_time_s,
        ip_to_node=ip_to_node,
        cbr_template_groups=_build_template_groups(templates),
    )
