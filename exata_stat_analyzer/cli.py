from __future__ import annotations

import argparse
from pathlib import Path

from .api import analyze_stat_to_json, export_cbr_classification_txt, export_layer_metrics_txt
from .models import AnalysisRequest, MetricSelector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="exata-stat-analyzer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("stat_path")
    analyze.add_argument("--layer", choices=["physical", "network", "transport", "application"])
    analyze.add_argument("--protocol")
    analyze.add_argument("--traffic-class", choices=["unicast", "broadcast", "multicast"])
    analyze.add_argument("--aggregation", choices=["sum", "mean", "max", "per_entity"], default="mean")
    analyze.add_argument("--rate-basis", choices=["auto", "throughput", "offered_load", "goodput", "carried_load"], default="auto")
    analyze.add_argument("--loss-basis", choices=["application", "network", "queue"], default="application")
    analyze.add_argument("--config-path")
    analyze.add_argument("--app-path")
    analyze.add_argument("--output-txt")
    analyze.add_argument("--output-layer-txt")
    analyze.add_argument("--metric", action="append", dest="metrics")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    request = AnalysisRequest(
        metrics=args.metrics or AnalysisRequest().metrics,
        selector=MetricSelector(
            layer=args.layer,
            protocol=args.protocol,
            traffic_class=args.traffic_class,
            aggregation=args.aggregation,
        ),
        rate_basis=args.rate_basis,
        loss_basis=args.loss_basis,
        config_path=args.config_path,
        app_path=args.app_path,
    )

    if args.output_txt:
        if not args.config_path or not args.app_path:
            parser.error("--output-txt 需要同时提供 --config-path 和 --app-path")
        export_cbr_classification_txt(
            stat_path=args.stat_path,
            config_path=args.config_path,
            app_path=args.app_path,
            output_path=Path(args.output_txt),
            request=request,
        )

    if args.output_layer_txt:
        export_layer_metrics_txt(
            stat_path=args.stat_path,
            output_path=Path(args.output_layer_txt),
            request=request,
        )

    if not args.output_txt and not args.output_layer_txt:
        print(analyze_stat_to_json(args.stat_path, request))


if __name__ == "__main__":
    main()
