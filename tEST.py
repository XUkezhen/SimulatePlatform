from __future__ import annotations
from pathlib import Path
import json

# ------------------------------------------------------------
#  A minimal stand‑alone module to read "node.txt", decide which
#  lines are active at the current simulation time, write a
#  static config file ("config_no_move.txt"), and return the
#  chosen nodes as JSON‑serialisable data.
# ------------------------------------------------------------

class SocketView:
    """Mimics the original environment that stores simulation state."""

    # Current simulation time (seconds). The caller should update this
    # before invoking ``read_node_file``.
    now_time: int = 0

    # List that will hold the filtered node dictionaries
    normal_node: list[dict] = []


def read_node_file(node_path: str | Path = "1.txt") -> dict:
    """Read *node_path* and apply the selection rules described below.

    Rules
    -----
    * Keep **exactly one** line for each *node id*.
      * If there exists any line with ``time > SocketView.now_time`` for this
        id, choose the one with **largest** ``time``.
      * Otherwise keep the line whose ``time == 0``.
    * Write every chosen line to *config_no_move.txt* in the required
      CREATEPLATFORM format.
    * Store the same dictionaries in ``SocketView.normal_node`` and return
      them wrapped in ``{"node": ...}``.
    """

    # Make sure it's empty each call
    SocketView.normal_node = []

    zero_rows: dict[str, dict] = {}
    future_rows: dict[str, dict] = {}

    node_path = Path(node_path)
    if not node_path.exists():
        raise FileNotFoundError(node_path)

    with node_path.open("r", encoding="utf-8") as f:
        for raw in f:
            if not raw.strip():
                continue

            parts = raw.split()
            node_id = parts[0]
            t = int(parts[1])
            lat, lon, alt = map(float, parts[2:5])
            node_type = parts[5]
            name = " ".join(parts[6:])  # allow spaces in name

            info = {
                "satellite_id": f"satellite_{node_id}",
                "time": t,
                "lat": str(lat),  # keep original precision as str
                "lon": str(lon),
                "alt": str(alt),
                "type": node_type,
                "name": name,
            }

            if t == 0:
                zero_rows.setdefault(node_id, info)
            elif t < SocketView.now_time:
                if t > future_rows.get(node_id, {}).get("time", -1):
                    future_rows[node_id] = info

    # Combine: future_rows overrides zero_rows when id duplicates
    final_nodes: dict[str, dict] = zero_rows.copy()
    final_nodes.update(future_rows)

    # Prepare output directory (same as node.txt)
    cfg_path = node_path.with_name("config_no_move.txt")
    with cfg_path.open("w", encoding="utf-8") as cfg:
        for info in sorted(final_nodes.values(),
                           key=lambda x: int(x["satellite_id"].split("_")[1])):
            cfg.write(
                f"CREATEPLATFORM {info['satellite_id'].split('_')[1]} 0 "
                f"LAT {int(float(info['lat']))} "
                f"LON {int(float(info['lon']))} "
                f"ALT {int(float(info['alt']))} "
                f"DAMAGESTATE 0 Type 1\n"
            )
            SocketView.normal_node.append(info)

    return {"node": SocketView.normal_node}


# -------------------------------------------------------------------------
#  Example usage
# -------------------------------------------------------------------------

def main() -> None:
    """Simple CLI demo."""

    try:
        SocketView.now_time = int(input("Enter current simulation time (seconds): "))
    except ValueError:
        print("Invalid input – using 0 as default time.")
        SocketView.now_time = 0

    try:
        result = read_node_file("1.txt")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    print("\nSelected nodes (JSON pretty‑printed):")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("\nWrote config_no_move.txt with", len(result["node"]), "platform(s).")


if __name__ == "__main__":
    main()
