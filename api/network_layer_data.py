import re
from pathlib import Path


SIM_TIME_PREFIX = "simTime:"
_NODE_FILE_PATTERN = re.compile(r"bellmanford_node_(\d+)\.txt$", re.IGNORECASE)


def extract_node_id_from_path(file_path):
    match = _NODE_FILE_PATTERN.search(Path(file_path).name)
    if not match:
        return None
    return int(match.group(1))


def find_bellmanford_files(scene_folder):
    files = []
    for path in scene_folder.glob("bellmanford_node_*.txt"):
        if not path.is_file():
            continue
        node_id = extract_node_id_from_path(path)
        if node_id is None:
            continue
        files.append((node_id, path.resolve(strict=False)))
    return sorted(files, key=lambda item: item[0])


def parse_bellmanford_file(file_path):
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="replace")

    node_id = extract_node_id_from_path(path)
    blocks = []
    current_block = None

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith(SIM_TIME_PREFIX):
            if current_block:
                blocks.append(_finalize_block(current_block))
            current_block = {
                "simTime": line[len(SIM_TIME_PREFIX):].strip(),
                "lines": [line],
            }
            continue

        if current_block is None:
            continue

        current_block["lines"].append(line)

    if current_block:
        blocks.append(_finalize_block(current_block))

    return {
        "nodeId": node_id,
        "nodeLabel": f"节点{node_id}" if node_id is not None else path.stem,
        "fileName": path.name,
        "blocks": blocks,
    }


def build_network_layer_overview(parsed_nodes):
    columns = []
    max_row_count = 0

    for parsed in parsed_nodes:
        items = [
            _build_time_item(
                block=block,
                row_index=index,
                node_id=parsed["nodeId"],
                node_name=parsed["nodeLabel"],
            )
            for index, block in enumerate(parsed["blocks"])
        ]
        max_row_count = max(max_row_count, len(items))
        columns.append({
            "nodeId": parsed["nodeId"],
            "nodeName": parsed["nodeLabel"],
            "fileName": parsed["fileName"],
            "items": items,
        })

    table_rows = []
    for row_index in range(max_row_count):
        cells = []
        for column in columns:
            if row_index < len(column["items"]):
                cells.append(column["items"][row_index])
            else:
                cells.append(None)
        table_rows.append({
            "rowIndex": row_index,
            "cells": cells,
        })

    return {
        "columns": columns,
        "tableRows": table_rows,
        "maxRowCount": max_row_count,
    }


def get_block_by_sim_time(file_path, sim_time):
    parsed = parse_bellmanford_file(file_path)
    target = str(sim_time).strip()
    for block in parsed["blocks"]:
        if block["simTime"] == target:
            return {
                "nodeId": parsed["nodeId"],
                "nodeLabel": parsed["nodeLabel"],
                "fileName": parsed["fileName"],
                "block": block,
            }
    return None


def _finalize_block(block):
    lines = list(block["lines"])
    header_line = lines[1] if len(lines) > 1 else ""
    rows = lines[2:] if len(lines) > 2 else []
    return {
        "simTime": block["simTime"],
        "displayTime": f'{block["simTime"]}秒',
        "headerLine": header_line,
        "rows": rows,
        "rawBlock": "\n".join(lines),
    }


def _build_time_item(block, row_index, node_id, node_name):
    return {
        "rowIndex": row_index,
        "nodeId": node_id,
        "nodeName": node_name,
        "simTime": block["simTime"],
        "displayTime": block["displayTime"],
        "blockTitle": block["headerLine"],
        "lineCount": len(block["rows"]),
    }
