from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Callable

from .index import RecordIndex
from .models import AnalysisRequest, MetricResult, Record
from .parser import normalize_key
from .scenario import ScenarioContext

_REASON_NOT_FOUND = "METRIC_NOT_FOUND"
_REASON_SCOPE = "INSUFFICIENT_SCOPE_SELECTION"
_REASON_DENOM = "DENOMINATOR_MISSING_OR_AMBIGUOUS"
_REASON_NOT_DERIVABLE = "NOT_DERIVABLE_FROM_SUMMARY_STAT"
_REASON_CONFIG_REQUIRED = "SCENARIO_CONFIG_REQUIRED"

_KEY_SERVER_ADDRESS = normalize_key("Server Address")
_KEY_CLIENT_ADDRESS = normalize_key("Client address")
_KEY_SESSION_START = normalize_key("Unicast Session Start (seconds)")
_KEY_FIRST_MSG_SENT = normalize_key("First Unicast Message Sent (seconds)")
_KEY_LAST_MSG_SENT = normalize_key("Last Unicast Message Sent (seconds)")
_KEY_TOTAL_MSG_SENT = normalize_key("Total Unicast Messages Sent (messages)")
_KEY_TOTAL_DATA_SENT = normalize_key("Total Unicast Data Sent (bytes)")
_KEY_OFFERED_LOAD = normalize_key("Unicast Offered Load (bits/second)")
_KEY_FIRST_MSG_RECV = normalize_key("First Unicast Message Received (seconds)")
_KEY_LAST_MSG_RECV = normalize_key("Last Unicast Message Received (seconds)")
_KEY_TOTAL_MSG_RECV = normalize_key("Total Unicast Messages Received (messages)")
_KEY_TOTAL_DATA_RECV = normalize_key("Total Unicast Data Received (bytes)")
_KEY_THROUGHPUT = normalize_key("Unicast Received Throughput (bits/second)")
_KEY_DELAY = normalize_key("Average Unicast End-to-End Delay (seconds)")
_KEY_JITTER = normalize_key("Average Unicast Jitter (seconds)")


def _matches_selector(record: Record, request: AnalysisRequest, *, include_protocol: bool = True) -> bool:
    selector = request.selector
    if selector.layer and record.layer.lower() != selector.layer.lower():
        return False
    if include_protocol and selector.protocol and record.module.lower() != selector.protocol.lower():
        return False
    if selector.traffic_class and selector.traffic_class.lower() not in record.metric_key:
        return False
    return True


def _aggregate(records: list[Record], aggregation: str) -> float | list[dict[str, object]]:
    values = [float(record.value) for record in records if isinstance(record.value, (int, float))]
    if aggregation == "per_entity":
        return [
            {
                "entity_id": record.entity_id,
                "address": record.address,
                "index": record.index,
                "value": float(record.value),
                "line_no": record.line_no,
            }
            for record in records
            if isinstance(record.value, (int, float))
        ]
    if not values:
        raise ValueError("No numeric values to aggregate")
    if aggregation == "sum":
        return sum(values)
    if aggregation == "max":
        return max(values)
    return mean(values)


def _result_from_records(records: list[Record], request: AnalysisRequest, *, unit: str, basis_label: str | None = None, diagnostics: dict[str, object] | None = None) -> MetricResult:
    aggregation = request.selector.aggregation
    value = _aggregate(records, aggregation)
    basis = basis_label or "; ".join(sorted({f"{record.layer}/{record.module}/{record.metric_name}" for record in records}))
    return MetricResult(
        available=True,
        value=value,
        unit=unit,
        method="direct",
        basis=basis,
        scope={
            "layer": request.selector.layer,
            "protocol": request.selector.protocol,
            "traffic_class": request.selector.traffic_class,
            "aggregation": aggregation,
        },
        diagnostics=diagnostics or {},
    )


def _unavailable(reason_code: str, reason: str, *, diagnostics: dict[str, object] | None = None) -> MetricResult:
    return MetricResult(
        available=False,
        value=None,
        unit=None,
        method="unavailable",
        reason_code=reason_code,
        reason=reason,
        diagnostics=diagnostics or {},
    )


def _find_contains(
    index: RecordIndex,
    request: AnalysisRequest,
    *,
    layer: str | None = None,
    module: str | None = None,
    contains: str,
    include_protocol: bool = True,
) -> list[Record]:
    return [
        record
        for record in index.filter(layer=layer, module=module, contains=contains)
        if _matches_selector(record, request, include_protocol=include_protocol)
    ]


def _validate_cbr_scope(request: AnalysisRequest) -> MetricResult | None:
    if request.selector.layer and request.selector.layer.lower() != "application":
        return _unavailable(
            _REASON_SCOPE,
            "CBR 业务指标仅支持 application 层范围选择",
            diagnostics={"selector_layer": request.selector.layer},
        )

    if request.selector.protocol and request.selector.protocol.lower() != "udp":
        return _unavailable(
            _REASON_SCOPE,
            "CBR 业务指标仅支持 protocol=UDP 或不指定协议",
            diagnostics={"selector_protocol": request.selector.protocol},
        )
    return None


def metric_cbr_throughput(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    invalid = _validate_cbr_scope(request)
    if invalid is not None:
        return invalid

    candidates = _find_contains(
        index,
        request,
        layer="application",
        module="CBR Server",
        contains="received throughput",
        include_protocol=False,
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 CBR 应用层吞吐量字段")
    return _result_from_records(candidates, request, unit="bits/second")


def metric_cbr_delay(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    invalid = _validate_cbr_scope(request)
    if invalid is not None:
        return invalid

    candidates = _find_contains(
        index,
        request,
        layer="application",
        module="CBR Server",
        contains="average unicast end to end delay",
        include_protocol=False,
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 CBR 应用层端到端时延字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_cbr_jitter(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    invalid = _validate_cbr_scope(request)
    if invalid is not None:
        return invalid

    candidates = _find_contains(
        index,
        request,
        layer="application",
        module="CBR Server",
        contains="average unicast jitter",
        include_protocol=False,
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 CBR 应用层抖动字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_cbr_offered_load(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    invalid = _validate_cbr_scope(request)
    if invalid is not None:
        return invalid

    candidates = _find_contains(
        index,
        request,
        layer="application",
        module="CBR Client",
        contains="unicast offered load",
        include_protocol=False,
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 CBR 应用层 offered load 字段")
    return _result_from_records(candidates, request, unit="bits/second")


def metric_application_throughput(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = _find_contains(
        index,
        request,
        layer="application",
        module="CBR Server",
        contains="received throughput",
        include_protocol=False,
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 application 层吞吐量字段")
    return _result_from_records(candidates, request, unit="bits/second")


def metric_transport_throughput(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = _find_contains(
        index,
        request,
        layer="transport",
        module=request.selector.protocol or None,
        contains="throughput at the transport layer",
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 transport 层吞吐量字段")
    return _result_from_records(candidates, request, unit="bits/second")


def metric_application_delay(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = _find_contains(
        index,
        request,
        layer="application",
        module="CBR Server",
        contains="end to end delay",
        include_protocol=False,
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 application 层时延字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_transport_delay(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = _find_contains(
        index,
        request,
        layer="transport",
        module=request.selector.protocol or None,
        contains="average delay at the transport layer",
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 transport 层时延字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_network_delay(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = _find_contains(
        index,
        request,
        layer="network",
        module="IP",
        contains="average delay",
    )
    candidates = [record for record in candidates if "delivery delay" not in record.metric_key]
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 network 层时延字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_application_jitter(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = _find_contains(
        index,
        request,
        layer="application",
        module="CBR Server",
        contains="average unicast jitter",
        include_protocol=False,
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 application 层抖动字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_transport_jitter(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = _find_contains(
        index,
        request,
        layer="transport",
        module=request.selector.protocol or None,
        contains="average jitter at the transport layer",
    )
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 transport 层抖动字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_network_jitter(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = _find_contains(
        index,
        request,
        layer="network",
        module="IP",
        contains="average jitter",
    )
    candidates = [record for record in candidates if "delivery jitter" not in record.metric_key]
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到 network 层抖动字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_throughput(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = []
    for layer, module, contains in [
        ("transport", request.selector.protocol or None, "throughput at the transport layer"),
        ("application", "CBR Server", "received throughput"),
    ]:
        candidates.extend(_find_contains(index, request, layer=layer, module=module, contains=contains))
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到符合当前选择范围的吞吐量字段")
    return _result_from_records(candidates, request, unit="bits/second")


def metric_delay(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = []
    for layer, module, contains in [
        ("network", "IP", "average delay"),
        ("transport", request.selector.protocol or None, "average delay at the transport layer"),
        ("application", "CBR Server", "end to end delay"),
    ]:
        candidates.extend(_find_contains(index, request, layer=layer, module=module, contains=contains))
    candidates = [record for record in candidates if "delivery delay" not in record.metric_key]
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到符合当前选择范围的时延字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_jitter(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = []
    for layer, module, contains in [
        ("network", "IP", "average jitter"),
        ("transport", request.selector.protocol or None, "average jitter at the transport layer"),
        ("application", "CBR Server", "average unicast jitter"),
    ]:
        candidates.extend(_find_contains(index, request, layer=layer, module=module, contains=contains))
    candidates = [record for record in candidates if "delivery jitter" not in record.metric_key]
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到符合当前选择范围的抖动字段")
    return _result_from_records(candidates, request, unit="seconds")


def metric_transfer_rate(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    basis = request.rate_basis
    selector_layer = request.selector.layer
    if basis == "auto":
        if selector_layer == "network":
            basis = "carried_load"
        elif selector_layer == "application":
            basis = "throughput"
        else:
            basis = "throughput"

    mapping = {
        "throughput": [("transport", request.selector.protocol or None, "throughput at the transport layer"), ("application", "CBR Server", "received throughput")],
        "offered_load": [("transport", request.selector.protocol or None, "offered load at the transport layer")],
        "goodput": [("transport", request.selector.protocol or None, "goodput at the transport layer")],
        "carried_load": [("network", "IP", "carried load")],
    }
    candidates = []
    for layer, module, contains in mapping[basis]:
        candidates.extend(_find_contains(index, request, layer=layer, module=module, contains=contains))
    if basis == "carried_load":
        candidates = [record for record in candidates if "originated" not in record.metric_key and "forwarded" not in record.metric_key]
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, f"未找到 rate_basis={basis} 对应的传输速率字段")
    return _result_from_records(candidates, request, unit="bits/second", diagnostics={"rate_basis": basis})


def metric_link_utilization(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    candidates = []
    candidates.extend(_find_contains(index, request, layer="physical", module="Abstract", contains="utilization (percent/100)"))
    candidates.extend(_find_contains(index, request, layer="mac", module="Link", contains="link utilization"))
    if not candidates:
        return _unavailable(_REASON_NOT_FOUND, "未找到符合当前选择范围的链路利用率字段")

    base_result = _result_from_records(candidates, request, unit="ratio")
    diagnostics = dict(base_result.diagnostics)
    if isinstance(base_result.value, list):
        value = [
            {**item, "percent": item["value"] * 100.0}
            for item in base_result.value
        ]
    else:
        value = base_result.value
        diagnostics["percent"] = float(base_result.value) * 100.0

    return MetricResult(
        available=base_result.available,
        value=value,
        unit=base_result.unit,
        method=base_result.method,
        basis=base_result.basis,
        scope=base_result.scope,
        diagnostics=diagnostics,
    )


def _group_application_sessions(records: list[Record]) -> dict[tuple[str, str | None], list[Record]]:
    grouped: dict[tuple[str, str | None], list[Record]] = defaultdict(list)
    current_client_by_server: dict[tuple[str, str | None], str | None] = {}
    for record in sorted(records, key=lambda item: item.line_no):
        server_key = (record.entity_id, record.index)
        if record.metric_key == normalize_key("Client address") and isinstance(record.value, str):
            current_client_by_server[server_key] = record.value.strip()
        client = current_client_by_server.get(server_key)
        grouped[(record.entity_id, client)].append(record)
    return grouped


def _safe_float(value: int | float | str) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _extract_cbr_server_sessions(records: list[Record]) -> list[dict[str, object]]:
    sessions: list[dict[str, object]] = []
    current: dict[tuple[str, str], dict[str, object]] = {}
    for record in sorted(records, key=lambda item: item.line_no):
        if record.module.lower() != "cbr server":
            continue
        if record.index is None:
            continue

        key = (record.entity_id, record.index)
        metric_key = record.metric_key
        if metric_key == _KEY_CLIENT_ADDRESS:
            client_ip = str(record.value).strip()
            session = {
                "server_entity_id": record.entity_id,
                "server_index": record.index,
                "server_ip": record.address,
                "client_ip": client_ip,
                "session_start_s": None,
                "first_message_time_s": None,
                "last_message_time_s": None,
                "messages_received": None,
                "data_received_bytes": None,
                "throughput_bps": None,
                "delay_s": None,
                "jitter_s": None,
                "line_no": record.line_no,
            }
            sessions.append(session)
            current[key] = session
            continue

        session = current.get(key)
        if session is None:
            continue

        parsed = _safe_float(record.value)
        if metric_key == _KEY_SESSION_START:
            session["session_start_s"] = parsed
        elif metric_key == _KEY_FIRST_MSG_RECV:
            session["first_message_time_s"] = parsed
        elif metric_key == _KEY_LAST_MSG_RECV:
            session["last_message_time_s"] = parsed
        elif metric_key == _KEY_TOTAL_MSG_RECV:
            session["messages_received"] = parsed
        elif metric_key == _KEY_TOTAL_DATA_RECV:
            session["data_received_bytes"] = parsed
        elif metric_key == _KEY_THROUGHPUT:
            session["throughput_bps"] = parsed
        elif metric_key == _KEY_DELAY:
            session["delay_s"] = parsed
        elif metric_key == _KEY_JITTER:
            session["jitter_s"] = parsed
    return sessions


def _extract_cbr_client_sessions(records: list[Record]) -> list[dict[str, object]]:
    sessions: list[dict[str, object]] = []
    current: dict[tuple[str, str], dict[str, object]] = {}
    for record in sorted(records, key=lambda item: item.line_no):
        if record.module.lower() != "cbr client":
            continue
        if record.index is None:
            continue

        key = (record.entity_id, record.index)
        metric_key = record.metric_key
        if metric_key == _KEY_SERVER_ADDRESS:
            server_ip = str(record.value).strip()
            session = {
                "client_entity_id": record.entity_id,
                "client_index": record.index,
                "client_ip": record.address,
                "server_ip": server_ip,
                "session_start_s": None,
                "first_message_time_s": None,
                "last_message_time_s": None,
                "messages_sent": None,
                "data_sent_bytes": None,
                "offered_load_bps": None,
                "line_no": record.line_no,
            }
            sessions.append(session)
            current[key] = session
            continue

        session = current.get(key)
        if session is None:
            continue

        parsed = _safe_float(record.value)
        if metric_key == _KEY_SESSION_START:
            session["session_start_s"] = parsed
        elif metric_key == _KEY_FIRST_MSG_SENT:
            session["first_message_time_s"] = parsed
        elif metric_key == _KEY_LAST_MSG_SENT:
            session["last_message_time_s"] = parsed
        elif metric_key == _KEY_TOTAL_MSG_SENT:
            session["messages_sent"] = parsed
        elif metric_key == _KEY_TOTAL_DATA_SENT:
            session["data_sent_bytes"] = parsed
        elif metric_key == _KEY_OFFERED_LOAD:
            session["offered_load_bps"] = parsed
    return sessions


def _build_business_templates(scenario_context: ScenarioContext) -> dict[tuple[str, str, float, int], list[dict[str, object]]]:
    templates: dict[tuple[str, str, float, int], list[dict[str, object]]] = defaultdict(list)
    for group in scenario_context.cbr_template_groups:
        key = (
            group.src_node_id,
            group.dst_node_id,
            round(float(group.start_s), 6),
            int(group.payload_bytes),
        )
        templates[key].append(
            {
                "src_node_id": group.src_node_id,
                "dst_node_id": group.dst_node_id,
                "start_s": float(group.start_s),
                "end_s": float(group.end_s),
                "duration_s": float(group.duration_s),
                "interval_s": float(group.interval_s),
                "payload_bytes": int(group.payload_bytes),
                "configured_count": int(group.configured_count),
                "line_nos": list(group.line_nos),
                "message_counts": list(group.message_counts),
            }
        )
    return templates


def _build_cbr_session_match(index: RecordIndex, request: AnalysisRequest, scenario_context: ScenarioContext) -> MetricResult:
    invalid = _validate_cbr_scope(request)
    if invalid is not None:
        return invalid

    records = [record for record in index.records if _matches_selector(record, request, include_protocol=False)]
    server_sessions = _extract_cbr_server_sessions(records)
    client_sessions = _extract_cbr_client_sessions(records)
    if not server_sessions and not client_sessions:
        return _unavailable(_REASON_NOT_FOUND, "未找到 CBR 业务会话记录")

    ip_to_node = scenario_context.ip_to_node
    server_lookup_by_node: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    server_lookup_by_ip: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for session in server_sessions:
        client_ip = str(session.get("client_ip") or "")
        server_entity = str(session.get("server_entity_id") or "")
        if client_ip and server_entity:
            client_entity = ip_to_node.get(client_ip, "")
            if client_entity:
                server_lookup_by_node[(server_entity, client_entity)].append(session)
            server_lookup_by_ip[(server_entity, client_ip)].append(session)

    templates = _build_business_templates(scenario_context)
    businesses: dict[tuple[str, str, float, int], dict[str, object]] = {}

    for client in client_sessions:
        client_entity = str(client.get("client_entity_id") or "")
        server_ip = str(client.get("server_ip") or "")
        if not client_entity or not server_ip:
            continue
        server_entity = ip_to_node.get(server_ip, "")
        start_s = float(client.get("session_start_s") or 0.0)
        payload_bytes = int((client.get("data_sent_bytes") or 0.0) / max((client.get("messages_sent") or 1.0), 1.0))
        if payload_bytes <= 0:
            payload_bytes = 0
        key = (client_entity, server_entity, round(start_s, 6), payload_bytes)

        business = businesses.get(key)
        if business is None:
            template_candidates = templates.get(key, [])
            template = template_candidates[0] if template_candidates else None
            has_ambiguous_template = len(template_candidates) > 1
            business = {
                "business_id": f"cbr:{client_entity}->{server_entity or server_ip}:{start_s:.3f}:{payload_bytes}",
                "client_node_id": client_entity,
                "server_node_id": server_entity or None,
                "client_ip": client.get("client_ip"),
                "server_ip": server_ip,
                "start_s": start_s,
                "end_s": float(template["end_s"]) if template else None,
                "duration_s": float(template["duration_s"]) if template else None,
                "interval_s": float(template["interval_s"]) if template else None,
                "payload_bytes": payload_bytes,
                "configured_count": int(template["configured_count"]) if template else 0,
                "observed_count": 0,
                "messages_sent": 0.0,
                "messages_received": 0.0,
                "data_sent_bytes": 0.0,
                "data_received_bytes": 0.0,
                "offered_load_bps": 0.0,
                "throughput_bps": 0.0,
                "delay_s": [],
                "jitter_s": [],
                "app_line_nos": list(template["line_nos"]) if template else [],
                "match_mode": "template_aggregate",
                "mapping_status": "ambiguous_template" if has_ambiguous_template else ("exact" if template else "unmatched_template"),
                "observed_first_message_s": None,
                "observed_last_message_s": None,
            }
            businesses[key] = business

        business["observed_count"] += 1
        business["messages_sent"] += float(client.get("messages_sent") or 0.0)
        business["data_sent_bytes"] += float(client.get("data_sent_bytes") or 0.0)
        business["offered_load_bps"] += float(client.get("offered_load_bps") or 0.0)
        first_sent = client.get("first_message_time_s")
        last_sent = client.get("last_message_time_s")
        if isinstance(first_sent, (int, float)):
            if business["observed_first_message_s"] is None:
                business["observed_first_message_s"] = float(first_sent)
            else:
                business["observed_first_message_s"] = min(float(business["observed_first_message_s"]), float(first_sent))
        if isinstance(last_sent, (int, float)):
            if business["observed_last_message_s"] is None:
                business["observed_last_message_s"] = float(last_sent)
            else:
                business["observed_last_message_s"] = max(float(business["observed_last_message_s"]), float(last_sent))

        matched_server = None

        candidates = server_lookup_by_node.get((server_entity, client_entity), [])
        fallback_candidates: list[dict[str, object]] = []
        client_ip = str(client.get("client_ip") or "")
        if client_ip:
            fallback_candidates = server_lookup_by_ip.get((server_entity, client_ip), [])

        for idx, candidate in enumerate(candidates):
            candidate_start = float(candidate.get("session_start_s") or 0.0)
            if abs(candidate_start - start_s) <= 1e-6:
                matched_server = candidates.pop(idx)
                break
        if matched_server is None and candidates:
            matched_server = candidates.pop(0)

        if matched_server is None:
            for idx, candidate in enumerate(fallback_candidates):
                candidate_start = float(candidate.get("session_start_s") or 0.0)
                if abs(candidate_start - start_s) <= 1e-6:
                    matched_server = fallback_candidates.pop(idx)
                    break
        if matched_server is None and fallback_candidates:
            matched_server = fallback_candidates.pop(0)

        if matched_server is not None:
            if not business.get("client_ip"):
                server_client_ip = str(matched_server.get("client_ip") or "").strip()
                if server_client_ip:
                    business["client_ip"] = server_client_ip
            business["messages_received"] += float(matched_server.get("messages_received") or 0.0)
            business["data_received_bytes"] += float(matched_server.get("data_received_bytes") or 0.0)
            business["throughput_bps"] += float(matched_server.get("throughput_bps") or 0.0)
            delay = matched_server.get("delay_s")
            jitter = matched_server.get("jitter_s")
            if isinstance(delay, (int, float)):
                business["delay_s"].append(float(delay))
            if isinstance(jitter, (int, float)):
                business["jitter_s"].append(float(jitter))
        else:
            business["mapping_status"] = "partial"

    result_rows: list[dict[str, object]] = []
    for business in sorted(businesses.values(), key=lambda item: str(item["business_id"])):
        sent = float(business["messages_sent"])
        received = float(business["messages_received"])
        loss_rate = None
        if sent > 0:
            loss_rate = max(sent - received, 0.0) / sent

        delays = list(business["delay_s"])
        jitters = list(business["jitter_s"])
        duration_s = business["duration_s"]
        if duration_s is None and business["observed_first_message_s"] is not None and business["observed_last_message_s"] is not None:
            duration_s = max(float(business["observed_last_message_s"]) - float(business["observed_first_message_s"]), 0.0)

        result_rows.append(
            {
                "business_id": business["business_id"],
                "client_node_id": business["client_node_id"],
                "server_node_id": business["server_node_id"],
                "client_ip": business["client_ip"],
                "server_ip": business["server_ip"],
                "start_s": business["start_s"],
                "end_s": business["end_s"],
                "duration_s": duration_s,
                "interval_s": business["interval_s"],
                "payload_bytes": business["payload_bytes"],
                "configured_count": business["configured_count"],
                "observed_count": business["observed_count"],
                "match_mode": business["match_mode"],
                "mapping_status": business["mapping_status"],
                "messages_sent": sent,
                "messages_received": received,
                "packet_loss_rate": loss_rate,
                "offered_load_bps": float(business["offered_load_bps"]),
                "throughput_bps": float(business["throughput_bps"]),
                "mean_delay_s": mean(delays) if delays else None,
                "mean_jitter_s": mean(jitters) if jitters else None,
                "app_line_nos": list(business["app_line_nos"]),
            }
        )

    if not result_rows:
        return _unavailable(_REASON_NOT_FOUND, "未找到可匹配的 CBR 业务会话")

    return MetricResult(
        available=True,
        value=result_rows,
        unit=None,
        method="computed",
        basis="CBR Client/Server sessions with config/app template aggregation",
        scope={
            "layer": request.selector.layer,
            "protocol": request.selector.protocol,
            "traffic_class": request.selector.traffic_class,
            "aggregation": request.selector.aggregation,
        },
        diagnostics={
            "match_mode": "template_aggregate",
            "configured_template_groups": len(scenario_context.cbr_template_groups),
            "client_sessions": len(client_sessions),
            "server_sessions": len(server_sessions),
        },
    )


def metric_cbr_packet_loss_rate(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    return metric_packet_loss_rate(index, request)


def metric_packet_loss_rate(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    if request.selector.layer and request.selector.layer.lower() != "application":
        return _unavailable(
            _REASON_SCOPE,
            "packet_loss_rate 仅支持 application 层范围选择",
            diagnostics={"selector_layer": request.selector.layer},
        )

    if request.selector.protocol and request.selector.protocol.lower() != "udp":
        return _unavailable(
            _REASON_SCOPE,
            "packet_loss_rate 仅支持 protocol=UDP 或不指定协议",
            diagnostics={"selector_protocol": request.selector.protocol},
        )

    if request.loss_basis != "application":
        return _unavailable(_REASON_DENOM, "当前样本缺少稳定的网络/队列层统一分母，无法计算可靠丢包率")

    server_records = [
        record
        for record in index.filter(layer="application", module="CBR Server")
        if _matches_selector(record, request, include_protocol=False)
    ]
    sent_records = [
        record
        for record in index.filter(layer="application", module="CBR Client", contains="total unicast messages sent")
        if _matches_selector(record, request, include_protocol=False)
    ]
    if not server_records or not sent_records:
        return _unavailable(
            _REASON_DENOM,
            "当前样本中无法同时定位应用层发送与接收消息总数",
            diagnostics={"matched_server_records": len(server_records), "matched_sent_records": len(sent_records)},
        )

    total_sent = sum(float(record.value) for record in sent_records if isinstance(record.value, (int, float)))
    total_received = sum(
        float(record.value)
        for record in server_records
        if record.metric_key == normalize_key("Total Unicast Messages Received (messages)") and isinstance(record.value, (int, float))
    )
    if total_sent <= 0:
        return _unavailable(_REASON_DENOM, "应用层发送消息总数为 0，无法计算丢包率")

    loss_rate = max(total_sent - total_received, 0.0) / total_sent
    return MetricResult(
        available=True,
        value=loss_rate,
        unit="ratio",
        method="computed",
        basis="Application/CBR Client Total Unicast Messages Sent + Application/CBR Server Total Unicast Messages Received",
        scope={
            "layer": request.selector.layer,
            "protocol": request.selector.protocol,
            "traffic_class": request.selector.traffic_class,
            "aggregation": request.selector.aggregation,
            "loss_basis": request.loss_basis,
        },
        diagnostics={
            "total_sent": total_sent,
            "total_received": total_received,
            "percent": loss_rate * 100.0,
            "matched_server_records": len(server_records),
            "matched_sent_records": len(sent_records),
        },
    )


def metric_routing_convergence_time(index: RecordIndex, request: AnalysisRequest) -> MetricResult:
    diagnostics = {}
    for contains in [
        "number of periodic updates sent",
        "number of triggered updates sent",
        "number of route timeouts",
    ]:
        matches = index.filter(layer="Application", module="Bellman-Ford", contains=contains)
        if matches:
            diagnostics[contains] = [match.value for match in matches]
    return _unavailable(
        _REASON_NOT_DERIVABLE,
        "当前 summary .stat 仅包含 Bellman-Ford 计数，不包含路由收敛时间线或事件时间戳",
        diagnostics=diagnostics,
    )


METRIC_BUILDERS: dict[str, Callable[[RecordIndex, AnalysisRequest], MetricResult]] = {
    "application_throughput": metric_application_throughput,
    "transport_throughput": metric_transport_throughput,
    "application_delay": metric_application_delay,
    "transport_delay": metric_transport_delay,
    "network_delay": metric_network_delay,
    "application_jitter": metric_application_jitter,
    "transport_jitter": metric_transport_jitter,
    "network_jitter": metric_network_jitter,
    "throughput": metric_throughput,
    "delay": metric_delay,
    "jitter": metric_jitter,
    "transfer_rate": metric_transfer_rate,
    "packet_loss_rate": metric_packet_loss_rate,
    "cbr_throughput": metric_cbr_throughput,
    "cbr_delay": metric_cbr_delay,
    "cbr_jitter": metric_cbr_jitter,
    "cbr_offered_load": metric_cbr_offered_load,
    "cbr_packet_loss_rate": metric_cbr_packet_loss_rate,
    "routing_convergence_time": metric_routing_convergence_time,
    "link_utilization": metric_link_utilization,
}


def build_metric_results(
    index: RecordIndex,
    request: AnalysisRequest,
    *,
    scenario_context: ScenarioContext | None = None,
) -> tuple[dict[str, MetricResult], list[str]]:
    metrics: dict[str, MetricResult] = {}
    warnings: list[str] = []
    for metric_name in request.metrics:
        if metric_name == "cbr_sessions":
            if scenario_context is None:
                metrics[metric_name] = _unavailable(
                    _REASON_CONFIG_REQUIRED,
                    "cbr_sessions 需要提供 config_path 以进行业务模板聚合匹配",
                )
                warnings.append("cbr_sessions skipped: missing config_path")
            else:
                metrics[metric_name] = _build_cbr_session_match(index, request, scenario_context)
            continue

        builder = METRIC_BUILDERS.get(metric_name)
        if builder is None:
            metrics[metric_name] = _unavailable(_REASON_NOT_FOUND, f"不支持的指标: {metric_name}")
            warnings.append(f"Unsupported metric requested: {metric_name}")
            continue
        metrics[metric_name] = builder(index, request)
    return metrics, warnings
