from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from .index import RecordIndex
from .metrics import build_metric_results
from .models import AnalysisRequest, AnalysisResult, request_to_dict, source_to_dict
from .parser import parse_stat_file
from .scenario import load_scenario_context

SCHEMA_VERSION = "1.0.0"
_LAYER_REPORT_METRICS = [
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


def _numeric_text(value: object, unit: str | None) -> str:
    if isinstance(value, (int, float)):
        if unit == "ratio":
            return f"{float(value):.9f} ({float(value) * 100.0:.4f}%)"
        return f"{float(value):.9f}"
    return str(value)


def analyze_stat(path: str | Path, request: AnalysisRequest | None = None) -> AnalysisResult:
    request = request or AnalysisRequest()
    stat_path = Path(path)
    records = parse_stat_file(stat_path)
    record_index = RecordIndex(records)
    scenario_context = None
    if request.config_path:
        scenario_context = load_scenario_context(request.config_path, app_path=request.app_path)
    metrics, warnings = build_metric_results(record_index, request, scenario_context=scenario_context)
    return AnalysisResult(
        schema_version=SCHEMA_VERSION,
        source=source_to_dict(stat_path, len(records)),
        request=request_to_dict(request),
        metrics=metrics,
        warnings=warnings,
    )


def analyze_stat_to_json(path: str | Path, request: AnalysisRequest | None = None) -> str:
    return json.dumps(analyze_stat(path, request).to_dict(), ensure_ascii=False, indent=2)


def analyze_scenario(
    stat_path: str | Path,
    config_path: str | Path,
    app_path: str | Path,
    request: AnalysisRequest | None = None,
) -> AnalysisResult:
    request = request or AnalysisRequest()
    request = AnalysisRequest(
        metrics=list(request.metrics),
        selector=request.selector,
        rate_basis=request.rate_basis,
        loss_basis=request.loss_basis,
        config_path=str(config_path),
        app_path=str(app_path),
    )
    return analyze_stat(stat_path, request)


def classify_cbr_businesses(
    stat_path: str | Path,
    config_path: str | Path,
    app_path: str | Path,
    request: AnalysisRequest | None = None,
) -> list[dict[str, object]]:
    request = request or AnalysisRequest(metrics=["cbr_sessions"])
    if "cbr_sessions" not in request.metrics:
        metrics = list(request.metrics)
        metrics.append("cbr_sessions")
        request = AnalysisRequest(
            metrics=metrics,
            selector=request.selector,
            rate_basis=request.rate_basis,
            loss_basis=request.loss_basis,
            config_path=str(config_path),
            app_path=str(app_path),
        )
    else:
        request = AnalysisRequest(
            metrics=list(request.metrics),
            selector=request.selector,
            rate_basis=request.rate_basis,
            loss_basis=request.loss_basis,
            config_path=str(config_path),
            app_path=str(app_path),
        )

    result = analyze_stat(stat_path, request)
    metric = result.metrics.get("cbr_sessions")
    if metric is None or not metric.available or not isinstance(metric.value, list):
        return []
    return metric.value


def export_cbr_classification_txt(
    stat_path: str | Path,
    config_path: str | Path,
    app_path: str | Path,
    output_path: str | Path,
    request: AnalysisRequest | None = None,
) -> Path:
    result = analyze_scenario(stat_path, config_path, app_path, request=request or AnalysisRequest(metrics=["cbr_sessions"]))
    metric = result.metrics.get("cbr_sessions")
    rows: list[dict[str, object]] = []
    if metric and metric.available and isinstance(metric.value, list):
        rows = metric.value

    output = Path(output_path)
    if output.parent and not output.parent.exists():
        output.parent.mkdir(parents=True, exist_ok=True)

    total_sent = sum(float(row.get("messages_sent") or 0.0) for row in rows)
    total_received = sum(float(row.get("messages_received") or 0.0) for row in rows)
    overall_loss = None
    if total_sent > 0:
        overall_loss = max(total_sent - total_received, 0.0) / total_sent

    lines: list[str] = []
    lines.append("EXata 业务分类结果")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"统计文件: {Path(stat_path)}")
    lines.append(f"配置文件: {Path(config_path)}")
    lines.append(f"业务文件: {Path(app_path)}")
    lines.append("匹配模式: 业务模板聚合匹配")
    lines.append("")
    lines.append("汇总")
    lines.append(f"业务模板总数: {len(rows)}")
    lines.append(f"总发送消息数: {total_sent:.0f}")
    lines.append(f"总接收消息数: {total_received:.0f}")
    if overall_loss is None:
        lines.append("整体丢包率: 无法计算")
    else:
        lines.append(f"整体丢包率: {overall_loss * 100.0:.4f}%")
    lines.append("")
    lines.append("明细")
    lines.append(
        "业务ID | 客户端节点ID | 服务端节点ID | 客户端IP | 服务端IP | 启动时间(秒) | 结束时间(秒) | 持续时间(秒) | 间隔(秒) | 负载字节数 | 配置条数 | 观测条数 | 发送消息数 | 接收消息数 | 丢包率 | OfferedLoad(bps) | Throughput(bps) | 平均时延(秒) | 平均抖动(秒) | 映射状态"
    )

    if not rows:
        lines.append("无可用业务分类结果。")
    else:
        for row in rows:
            loss_rate = row.get("packet_loss_rate")
            loss_text = "-"
            if isinstance(loss_rate, (int, float)):
                loss_text = f"{float(loss_rate) * 100.0:.4f}%"

            delay = row.get("mean_delay_s")
            jitter = row.get("mean_jitter_s")
            delay_text = "-" if delay is None else f"{float(delay):.9f}"
            jitter_text = "-" if jitter is None else f"{float(jitter):.9f}"
            end_s = row.get("end_s")
            duration_s = row.get("duration_s")
            interval_s = row.get("interval_s")
            end_text = "-" if end_s is None else f"{float(end_s):.6f}"
            duration_text = "-" if duration_s is None else f"{float(duration_s):.6f}"
            interval_text = "-" if interval_s is None else f"{float(interval_s):.6f}"

            lines.append(
                " | ".join(
                    [
                        str(row.get("business_id") or ""),
                        str(row.get("client_node_id") or ""),
                        str(row.get("server_node_id") or ""),
                        str(row.get("client_ip") or ""),
                        str(row.get("server_ip") or ""),
                        f"{float(row.get('start_s') or 0.0):.6f}",
                        end_text,
                        duration_text,
                        interval_text,
                        str(int(row.get("payload_bytes") or 0)),
                        str(int(row.get("configured_count") or 0)),
                        str(int(row.get("observed_count") or 0)),
                        str(int(float(row.get("messages_sent") or 0.0))),
                        str(int(float(row.get("messages_received") or 0.0))),
                        loss_text,
                        f"{float(row.get('offered_load_bps') or 0.0):.6f}",
                        f"{float(row.get('throughput_bps') or 0.0):.6f}",
                        delay_text,
                        jitter_text,
                        str(row.get("mapping_status") or ""),
                    ]
                )
            )

    lines.append("")
    lines.append("字段说明")
    lines.append("- 业务ID: 业务模板标识，格式为 cbr:源节点->宿节点:启动时间:负载字节数。")
    lines.append("- 配置条数: 在 .app 文件中，满足同源宿+同参数模板的配置行数量。")
    lines.append("- 观测条数: 在 .stat 中实际观测到并归入该模板的会话数量。")
    lines.append("- 持续时间(秒): 优先使用 .app 中 end-start；若缺失则用观测到的首末消息时间估算。")
    lines.append("- 间隔(秒): CBR 在 .app 中的发包间隔（ITEM-INTERVAL）。")
    lines.append("- 映射状态: exact=可稳定映射；partial=只匹配到部分会话；unmatched_template=未匹配到模板；ambiguous_template=匹配到多个候选模板。")

    if result.warnings:
        lines.append("")
        lines.append("告警")
        for warning in result.warnings:
            lines.append(f"- {warning}")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def export_layer_metrics_txt(
    stat_path: str | Path,
    output_path: str | Path,
    request: AnalysisRequest | None = None,
) -> Path:
    base_request = request or AnalysisRequest()
    report_request = AnalysisRequest(
        metrics=list(_LAYER_REPORT_METRICS),
        selector=base_request.selector,
        rate_basis=base_request.rate_basis,
        loss_basis=base_request.loss_basis,
    )
    result = analyze_stat(stat_path, report_request)

    output = Path(output_path)
    if output.parent and not output.parent.exists():
        output.parent.mkdir(parents=True, exist_ok=True)

    rows: list[tuple[str, str, str, str, str, str]] = []
    for metric_name in _LAYER_REPORT_METRICS:
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

        value_text = "-"
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

    lines: list[str] = []
    lines.append("EXata 其他层分层指标结果")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"统计文件: {Path(stat_path)}")
    lines.append("说明: 本文件聚合展示非 CBR 业务明细类的分层指标结果。")
    lines.append("")
    lines.append("明细")
    lines.append("指标名 | 可用 | 数值 | 单位 | 方法 | 口径来源")
    for row in rows:
        lines.append(" | ".join(row))

    lines.append("")
    lines.append("字段说明")
    lines.append("- 指标名: 分层指标名称，application/transport/network 前缀表示所属层。")
    lines.append("- 数值: 若为 ratio，会同时给出原值和百分比。")
    lines.append("- 方法: direct 表示直接读取并聚合，unavailable 表示样本无法推导。")
    lines.append("- 口径来源: 对应 stat 字段来源，便于核对计算依据。")

    if result.warnings:
        lines.append("")
        lines.append("告警")
        for warning in result.warnings:
            lines.append(f"- {warning}")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
