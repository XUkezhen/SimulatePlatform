from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from exata_stat_analyzer import (
    AnalysisRequest,
    analyze_stat,
    classify_cbr_businesses,
    export_cbr_classification_txt,
    export_layer_metrics_txt,
)
from exata_stat_analyzer.models import FileAccessError, ParseError
from exata_stat_analyzer.models import MetricSelector
from exata_stat_analyzer.index import RecordIndex
from exata_stat_analyzer.metrics import build_metric_results
from exata_stat_analyzer.parser import parse_stat_file
from exata_stat_analyzer.scenario import load_scenario_context

from .models import Scene


DEFAULT_CBR_REPORT_NAME = "cbr_report.txt"
DEFAULT_LAYER_REPORT_NAME = "layer_metrics_report.txt"
LAYER_REPORT_METRICS = [
    "application_throughput",
    "transport_throughput",
    "application_delay",
    "transport_delay",
    "network_delay",
    "application_jitter",
    "transport_jitter",
    "network_jitter",
    "link_utilization",
    "routing_convergence_time",
]


def _wants_json_response(payload: dict[str, Any]) -> bool:
    return str(payload.get("responseFormat") or "").strip().lower() == "json"


def _build_structured_summary_request(request: AnalysisRequest) -> AnalysisRequest:
    return AnalysisRequest(
        metrics=list(LAYER_REPORT_METRICS),
        selector=request.selector,
        rate_basis=request.rate_basis,
        loss_basis=request.loss_basis,
        config_path=request.config_path,
        app_path=request.app_path,
    )


def _numeric_values(records: list[Any], predicate) -> list[float]:
    values: list[float] = []
    for record in records:
        if not predicate(record):
            continue
        if isinstance(record.value, (int, float)):
            values.append(float(record.value))
    return values


def _mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(mean(values))


def _row_basis(parts: list[tuple[str, list[Any]]]) -> str:
    labels = [f"{label}: {records[0].metric_name}" for label, records in parts if records]
    return " | ".join(labels)


def _build_layer_groups(records: list[Any], request: AnalysisRequest) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for record in records:
        selector = request.selector
        if selector.layer and record.layer.lower() != selector.layer.lower():
            continue
        if selector.protocol and record.module.lower() != selector.protocol.lower():
            continue
        if selector.traffic_class and selector.traffic_class.lower() not in record.metric_key:
            continue
        grouped[(record.layer, record.module)].append(record)

    rows: list[dict[str, Any]] = []
    for (layer, module), group_records in sorted(grouped.items(), key=lambda item: (item[0][0].lower(), item[0][1].lower())):
        if not str(layer).strip() and not str(module).strip():
            continue
        layer_lower = layer.lower()
        if layer_lower == "application":
            throughput_records = [record for record in group_records if "received throughput" in record.metric_key]
            offered_records = [record for record in group_records if "offered load" in record.metric_key]
        elif layer_lower == "transport":
            throughput_records = [record for record in group_records if "throughput at the transport layer" in record.metric_key]
            offered_records = [record for record in group_records if "offered load" in record.metric_key]
        elif layer_lower == "network":
            throughput_records = [
                record
                for record in group_records
                if "carried load" in record.metric_key and "originated" not in record.metric_key and "forwarded" not in record.metric_key
            ]
            offered_records = [record for record in group_records if "offered load" in record.metric_key]
        else:
            throughput_records = [record for record in group_records if "throughput" in record.metric_key]
            offered_records = [record for record in group_records if "offered load" in record.metric_key]

        delay_records = [
            record
            for record in group_records
            if "delay" in record.metric_key and "delivery delay" not in record.metric_key and isinstance(record.value, (int, float))
        ]
        jitter_records = [
            record
            for record in group_records
            if "jitter" in record.metric_key and "delivery jitter" not in record.metric_key and isinstance(record.value, (int, float))
        ]
        utilization_records = [
            record
            for record in group_records
            if ("utilization (percent/100)" in record.metric_key or "link utilization" in record.metric_key)
            and isinstance(record.value, (int, float))
        ]

        rows.append(
            {
                "layer": layer,
                "module": module,
                "record_count": len(group_records),
                "throughput_bps": _mean_or_none(_numeric_values(throughput_records, lambda record: True)),
                "delay_s": _mean_or_none(_numeric_values(delay_records, lambda record: True)),
                "jitter_s": _mean_or_none(_numeric_values(jitter_records, lambda record: True)),
                "offered_load_bps": _mean_or_none(_numeric_values(offered_records, lambda record: True)),
                "link_utilization_ratio": _mean_or_none(_numeric_values(utilization_records, lambda record: True)),
                "basis": _row_basis(
                    [
                        ("throughput", throughput_records),
                        ("delay", delay_records),
                        ("jitter", jitter_records),
                        ("offered_load", offered_records),
                        ("link_utilization", utilization_records),
                    ]
                ),
            }
        )

    return rows


def _to_session_row(row: dict[str, Any]) -> dict[str, Any]:
    mapping_status = str(row.get("mapping_status") or "")
    pairing_status = "partial" if mapping_status == "partial" else "paired"
    return {
        "session_id": row.get("business_id"),
        "module_family": "UDP",
        "client_node_id": row.get("client_node_id"),
        "client_peer_ip": row.get("client_ip"),
        "server_node_id": row.get("server_node_id"),
        "server_peer_ip": row.get("server_ip"),
        "client_entity_id": row.get("client_node_id"),
        "server_entity_id": row.get("server_node_id"),
        "start_s": row.get("start_s"),
        "finish_s": row.get("end_s"),
        "status": mapping_status or "unknown",
        "messages_sent": row.get("messages_sent"),
        "messages_received": row.get("messages_received"),
        "throughput_bps": row.get("throughput_bps"),
        "delay_s": row.get("mean_delay_s"),
        "jitter_s": row.get("mean_jitter_s"),
        "pairing_status": pairing_status,
    }


def _build_structured_payload(
    stat_path: Path,
    config_path: Path | None,
    app_path: Path | None,
    request: AnalysisRequest,
) -> dict[str, Any]:
    records = parse_stat_file(stat_path)
    record_index = RecordIndex(records)
    warnings: list[str] = []
    scenario_context = None
    if config_path is not None:
        try:
            scenario_context = load_scenario_context(config_path, app_path=app_path)
        except (FileAccessError, ParseError, ValueError) as exc:
            warnings.append(f"Scenario context unavailable: {exc}")

    summary_request = _build_structured_summary_request(request)
    summary_metrics, summary_warnings = build_metric_results(record_index, summary_request, scenario_context=scenario_context)
    warnings.extend(summary_warnings)

    application_sessions: list[dict[str, Any]] = []
    if scenario_context is not None:
        session_request = AnalysisRequest(
            metrics=["cbr_sessions"],
            selector=request.selector,
            rate_basis=request.rate_basis,
            loss_basis=request.loss_basis,
            config_path=request.config_path,
            app_path=request.app_path,
        )
        session_metrics, _ = build_metric_results(record_index, session_request, scenario_context=scenario_context)
        cbr_metric = session_metrics.get("cbr_sessions")
        if cbr_metric and cbr_metric.available and isinstance(cbr_metric.value, list):
            application_sessions = [_to_session_row(row) for row in cbr_metric.value]

    return {
        "source": {
            "file": str(stat_path),
            "stat_file": stat_path.name,
            "parsed_records": len(records),
        },
        "summary_metrics": {name: metric.to_dict() for name, metric in summary_metrics.items()},
        "application_sessions": application_sessions,
        "layer_groups": _build_layer_groups(records, request),
        "warnings": warnings,
    }


def _project_root() -> Path:
    return Path(getattr(settings, "BASE_DIR", Path.cwd())).resolve()


def _scene_files_root() -> Path:
    media_root = getattr(settings, "MEDIA_ROOT", "")
    if media_root:
        return (Path(media_root) / "scene_files").resolve()
    return (_project_root() / "scene_files").resolve()


def _reports_root() -> Path:
    return (_project_root() / "tmp" / "exata_reports").resolve()


def _is_within(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _safe_resolve_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = _project_root() / candidate
    resolved = candidate.resolve(strict=False)
    if not _is_within(_project_root(), resolved):
        raise ValueError(f"路径超出项目目录: {raw_path}")
    return resolved


def _sorted_files(folder: Path, pattern: str) -> list[Path]:
    return sorted(
        [path for path in folder.glob(pattern) if path.is_file()],
        key=lambda path: (path.stat().st_mtime, path.name.lower()),
        reverse=True,
    )


def _pick_default(files: list[Path]) -> Path | None:
    return files[0] if files else None


def _resolve_scene_folder(payload: dict[str, Any]) -> tuple[str | None, int | None, Path | None]:
    scene_name = payload.get("sceneName")
    scene_id = None
    if scene_name:
        scene = Scene.objects.filter(sceneName=scene_name).first()
        scene_id = scene.id if scene else None

    if not scene_name:
        return None, None, None

    scene_folder = (_scene_files_root() / scene_name).resolve(strict=False)
    if not _is_within(_scene_files_root(), scene_folder):
        raise ValueError(f"非法场景目录: {scene_name}")
    if not scene_folder.exists() or not scene_folder.is_dir():
        raise FileNotFoundError(f"场景目录不存在: {scene_name}")
    return scene_name, scene_id, scene_folder


def _resolve_file_in_scene(scene_folder: Path, file_name: str | None, pattern: str) -> Path | None:
    if file_name:
        candidate = (scene_folder / file_name).resolve(strict=False)
        if not _is_within(scene_folder.resolve(), candidate):
            raise ValueError(f"非法文件路径: {file_name}")
        if not candidate.exists() or not candidate.is_file():
            raise FileNotFoundError(f"文件不存在: {candidate.name}")
        return candidate
    return _pick_default(_sorted_files(scene_folder, pattern))


def _resolve_unique_scene_file(scene_folder: Path, pattern: str, label: str) -> Path | None:
    matched_files = _sorted_files(scene_folder, pattern)
    if not matched_files:
        return None
    if len(matched_files) > 1:
        raise ValueError(f"场景目录下存在多个 {label} 文件，请先清理后再分析")
    return matched_files[0]


def _resolve_analysis_files(payload: dict[str, Any]) -> tuple[str | None, int | None, Path | None, Path, Path | None, Path | None]:
    if not payload.get("sceneName"):
        raise ValueError("analyze_exata_stat 必须提供 sceneName")
    if not payload.get("statFile"):
        raise ValueError("analyze_exata_stat 必须提供 statFile")

    scene_name, scene_id, scene_folder = _resolve_scene_folder(payload)
    if scene_folder is None:
        raise ValueError("场景不存在或 sceneName 缺失")

    stat_path = _resolve_file_in_scene(scene_folder, payload.get("statFile"), "*.stat")
    if stat_path is None:
        raise FileNotFoundError(f"场景 {scene_name} 下未找到 .stat 文件")

    config_path = _resolve_unique_scene_file(scene_folder, "*.config", ".config")
    app_path = _resolve_unique_scene_file(scene_folder, "*.app", ".app")
    return scene_name, scene_id, scene_folder, stat_path, config_path, app_path


def _build_selector(payload: dict[str, Any]) -> MetricSelector:
    return MetricSelector(
        layer=payload.get("layer"),
        protocol=payload.get("protocol"),
        traffic_class=payload.get("trafficClass"),
        aggregation=payload.get("aggregation", "mean"),
    )


def _build_request(payload: dict[str, Any], config_path: Path | None, app_path: Path | None) -> AnalysisRequest:
    metrics = payload.get("metrics")
    if metrics is not None and not isinstance(metrics, list):
        raise ValueError("metrics 必须是数组")

    return AnalysisRequest(
        metrics=list(metrics) if metrics else AnalysisRequest().metrics,
        selector=_build_selector(payload),
        rate_basis=payload.get("rateBasis", "auto"),
        loss_basis=payload.get("lossBasis", "application"),
        config_path=str(config_path) if config_path else None,
        app_path=str(app_path) if app_path else None,
    )


def _report_target(report_folder: Path, payload_value: Any, default_name: str) -> Path:
    name = str(payload_value or default_name)
    target = (report_folder / name).resolve(strict=False)
    if not _is_within(report_folder.resolve(), target):
        raise ValueError(f"报告输出路径不允许超出报告目录: {name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _numeric_text(value: object, unit: str | None) -> str:
    if isinstance(value, (int, float)):
        if unit == "ratio":
            return f"{float(value):.9f} ({float(value) * 100.0:.4f}%)"
        return f"{float(value):.9f}"
    return str(value)


def _build_layer_report_text(stat_path: Path, request: AnalysisRequest) -> str:
    report_request = AnalysisRequest(
        metrics=list(LAYER_REPORT_METRICS),
        selector=request.selector,
        rate_basis=request.rate_basis,
        loss_basis=request.loss_basis,
    )
    result = analyze_stat(stat_path, report_request)

    rows: list[tuple[str, str, str, str, str, str]] = []
    for metric_name in LAYER_REPORT_METRICS:
        metric = result.metrics.get(metric_name)
        if metric is None:
            rows.append((metric_name, "否", "-", "-", "-", "指标缺失"))
            continue

        if not metric.available:
            rows.append(
                (
                    metric_name,
                    "否",
                    "-",
                    metric.unit or "-",
                    metric.method,
                    metric.reason or metric.reason_code or "无可用数据",
                )
            )
            continue

        if isinstance(metric.value, list):
            value_text = f"列表结果，共 {len(metric.value)} 项"
        else:
            value_text = _numeric_text(metric.value, metric.unit)

        rows.append(
            (
                metric_name,
                "是",
                value_text,
                metric.unit or "-",
                metric.method,
                metric.basis or "-",
            )
        )

    lines = [
        "EXata 其他层分层指标结果",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"统计文件: {stat_path}",
        "说明: 本文件聚合展示非 CBR 业务明细类的分层指标结果。",
        "",
        "明细",
        "指标名 | 可用 | 数值 | 单位 | 方法 | 口径来源",
    ]
    for row in rows:
        lines.append(" | ".join(row))

    lines.extend(
        [
            "",
            "字段说明",
            "- 指标名: 分层指标名称，application/transport/network 前缀表示所属层。",
            "- 数值: 若为 ratio，会同时给出原值和百分比。",
            "- 方法: direct 表示直接读取并聚合，unavailable 表示样本无法推导。",
            "- 口径来源: 对应 stat 字段来源，便于核对计算依据。",
        ]
    )

    if result.warnings:
        lines.append("")
        lines.append("告警")
        for warning in result.warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines) + "\n"


def _build_cbr_report_text(
    stat_path: Path,
    config_path: Path,
    app_path: Path,
    request: AnalysisRequest,
) -> str:
    rows = classify_cbr_businesses(
        stat_path=stat_path,
        config_path=config_path,
        app_path=app_path,
        request=request,
    )
    total_sent = sum(float(row.get("messages_sent") or 0.0) for row in rows)
    total_received = sum(float(row.get("messages_received") or 0.0) for row in rows)
    overall_loss = None
    if total_sent > 0:
        overall_loss = max(total_sent - total_received, 0.0) / total_sent

    lines = [
        "EXata 业务分类结果",
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"统计文件: {stat_path}",
        f"配置文件: {config_path}",
        f"业务文件: {app_path}",
        "匹配模式: 业务模板聚合匹配",
        "",
        "汇总",
        f"业务模板总数: {len(rows)}",
        f"总发送消息数: {total_sent:.0f}",
        f"总接收消息数: {total_received:.0f}",
        f"整体丢包率: {'无法计算' if overall_loss is None else f'{overall_loss * 100.0:.4f}%'}",
        "",
        "明细",
        "业务ID | 客户端节点ID | 服务端节点ID | 客户端IP | 服务端IP | 启动时间(秒) | 结束时间(秒) | 持续时间(秒) | 间隔(秒) | 负载字节数 | 配置条数 | 观测条数 | 发送消息数 | 接收消息数 | 丢包率 | OfferedLoad(bps) | Throughput(bps) | 平均时延(秒) | 平均抖动(秒) | 映射状态",
    ]

    if not rows:
        lines.append("无可用业务分类结果。")
    else:
        for row in rows:
            loss_rate = row.get("packet_loss_rate")
            loss_text = "-" if not isinstance(loss_rate, (int, float)) else f"{float(loss_rate) * 100.0:.4f}%"
            delay = row.get("mean_delay_s")
            jitter = row.get("mean_jitter_s")
            end_s = row.get("end_s")
            duration_s = row.get("duration_s")
            interval_s = row.get("interval_s")

            lines.append(
                " | ".join(
                    [
                        str(row.get("business_id") or ""),
                        str(row.get("client_node_id") or ""),
                        str(row.get("server_node_id") or ""),
                        str(row.get("client_ip") or ""),
                        str(row.get("server_ip") or ""),
                        f"{float(row.get('start_s') or 0.0):.6f}",
                        "-" if end_s is None else f"{float(end_s):.6f}",
                        "-" if duration_s is None else f"{float(duration_s):.6f}",
                        "-" if interval_s is None else f"{float(interval_s):.6f}",
                        str(int(row.get("payload_bytes") or 0)),
                        str(int(row.get("configured_count") or 0)),
                        str(int(row.get("observed_count") or 0)),
                        str(int(float(row.get("messages_sent") or 0.0))),
                        str(int(float(row.get("messages_received") or 0.0))),
                        loss_text,
                        f"{float(row.get('offered_load_bps') or 0.0):.6f}",
                        f"{float(row.get('throughput_bps') or 0.0):.6f}",
                        "-" if delay is None else f"{float(delay):.9f}",
                        "-" if jitter is None else f"{float(jitter):.9f}",
                        str(row.get("mapping_status") or ""),
                    ]
                )
            )

    lines.extend(
        [
            "",
            "字段说明",
            "- 业务ID: 业务模板标识，格式为 cbr:源节点->宿节点:启动时间:负载字节数。",
            "- 配置条数: 在 .app 文件中，满足同源宿+同参数模板的配置行数量。",
            "- 观测条数: 在 .stat 中实际观测到并归入该模板的会话数量。",
            "- 持续时间(秒): 优先使用 .app 中 end-start；若缺失则用观测到的首末消息时间估算。",
            "- 间隔(秒): CBR 在 .app 中的发包间隔（ITEM-INTERVAL）。",
            "- 映射状态: exact=可稳定映射；partial=只匹配到部分会话；unmatched_template=未匹配到模板；ambiguous_template=匹配到多个候选模板。",
        ]
    )
    return "\n".join(lines) + "\n"


@require_http_methods(["GET"])
def get_exata_scene_files(request):
    root = _scene_files_root()
    if not root.exists():
        return JsonResponse({"status": "error", "message": "scene_files 目录不存在"}, status=404)

    scenes: list[dict[str, Any]] = []

    for folder in sorted([path for path in root.iterdir() if path.is_dir()], key=lambda item: item.name.lower()):
        stat_files = _sorted_files(folder, "*.stat")
        scenes.append(
            {
                "sceneName": folder.name,
                "statFiles": [path.name for path in stat_files],
            }
        )

    return JsonResponse({"status": "success", "scenes": scenes})


@require_http_methods(["POST"])
@csrf_exempt
def analyze_exata_stat(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return HttpResponse("请求体不是合法 JSON", status=400, content_type="text/plain; charset=utf-8")

    try:
        scene_name, scene_id, scene_folder, stat_path, config_path, app_path = _resolve_analysis_files(payload)
        analysis_request = _build_request(payload, config_path, app_path)
        if _wants_json_response(payload):
            structured_payload = _build_structured_payload(
                stat_path=stat_path,
                config_path=config_path,
                app_path=app_path,
                request=analysis_request,
            )
            return JsonResponse(structured_payload, json_dumps_params={"ensure_ascii": False})

        if "cbr_sessions" in analysis_request.metrics and config_path is None:
            return HttpResponse("cbr_sessions 需要提供 .config 文件", status=400, content_type="text/plain; charset=utf-8")
        if "cbr_sessions" in analysis_request.metrics and app_path is None:
            return HttpResponse("cbr_sessions 需要提供 .app 文件", status=400, content_type="text/plain; charset=utf-8")

        report_folder_name = scene_name or stat_path.stem
        report_folder = (_reports_root() / report_folder_name).resolve()
        report_folder.mkdir(parents=True, exist_ok=True)

        if "cbr_sessions" in analysis_request.metrics:
            report_text = _build_cbr_report_text(
                stat_path=stat_path,
                config_path=config_path,
                app_path=app_path,
                request=analysis_request,
            )
        else:
            report_text = _build_layer_report_text(stat_path=stat_path, request=analysis_request)

        reports: dict[str, str] = {}
        if payload.get("exportCbrTxt"):
            if config_path is None:
                return HttpResponse("导出 CBR 报告需要 .config 文件", status=400, content_type="text/plain; charset=utf-8")
            if app_path is None:
                return HttpResponse("导出 CBR 报告需要 .app 文件", status=400, content_type="text/plain; charset=utf-8")
            cbr_target = _report_target(report_folder, payload.get("cbrReportName"), DEFAULT_CBR_REPORT_NAME)
            export_cbr_classification_txt(
                stat_path=stat_path,
                config_path=config_path,
                app_path=app_path,
                output_path=cbr_target,
                request=analysis_request,
            )
            reports["cbrReport"] = str(cbr_target)

        if payload.get("exportLayerTxt"):
            layer_target = _report_target(report_folder, payload.get("layerReportName"), DEFAULT_LAYER_REPORT_NAME)
            export_layer_metrics_txt(
                stat_path=stat_path,
                output_path=layer_target,
                request=analysis_request,
            )
            reports["layerReport"] = str(layer_target)

        response = HttpResponse(report_text, content_type="text/plain; charset=utf-8")
        if reports:
            response["X-Exata-Scene-Name"] = scene_name or ""
            response["X-Exata-Scene-Id"] = str(scene_id or "")
            response["X-Exata-Stat-Path"] = str(stat_path)
            if config_path:
                response["X-Exata-Config-Path"] = str(config_path)
            if app_path:
                response["X-Exata-App-Path"] = str(app_path)
        return response
    except (FileNotFoundError, ValueError) as exc:
        return HttpResponse(str(exc), status=400, content_type="text/plain; charset=utf-8")
    except Exception as exc:
        return HttpResponse(f"EXata 分析失败: {exc}", status=500, content_type="text/plain; charset=utf-8")
