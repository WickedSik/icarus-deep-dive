#!/usr/bin/env python3
"""List the exotic and exotic-uranium deposits in an Icarus prospect save,
each with its in-game map grid reference (e.g. C7, N5).

The in-game map overlays a fixed 16x16 grid (columns A-P, rows 1-16). That grid
is a property of the map (terrain), not the save, so converting a deposit's
world coordinate to a grid cell needs a per-map calibration: the world position
of the grid's top-left corner plus the cell size. Those constants live in
MAP_CALIBRATION below and are the only map-specific values; the grid dimensions
themselves never change.

Usage:
    python icarus_deposits.py <path/to/Prospect.json> [--type exotic|uranium|all] [--csv]

Examples:
    python icarus_deposits.py "The Garden.json"
    python icarus_deposits.py "The Garden.json" --type uranium
    python icarus_deposits.py "The Garden.json" --csv > deposits.csv

Reuses the UE4 property parser from icarus_map.py (same directory).
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icarus_map import Reader, read_props, load_blobs, location_of  # noqa: E402


# --------------------------------------------------------------------------
# Per-map grid calibration.
#
# The game draws a fixed 16x16 grid (cols A-P, rows 1-16) over each map. To map
# a world coordinate (metres) to a cell we need, per terrain:
#   x0, y0     world position (m) of the grid's top-left corner (col A / row 1 edge)
#   cell_x/y   cell width/height in metres
#
# Terrain_021 (OpenWorld_Elysium / "The Garden") values were calibrated from two
# in-game-verified deposits — uranium at N5 and B8 — and cross-checked against the
# biome cave distribution. Accurate mid-map; if an exact in-game cell ever
# disagrees near the edges, adjust these four numbers (they are fixed per map).
# --------------------------------------------------------------------------
MAP_CALIBRATION = {
    "Terrain_021": {"x0": -4187.0, "y0": -3897.0, "cell_x": 487.75, "cell_y": 470.6},
}

GRID_COLS = "ABCDEFGHIJKLMNOP"   # 16 columns
GRID_ROWS = 16

DEPOSIT_LABELS = {
    "Exotic": "Exotic",
    "Exotic_Raw_Uranium": "Uranium",
}


def detect_terrain(blobs):
    """Find the terrain id (e.g. 'Terrain_021') from any actor's path name."""
    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        bd = blob.get("BinaryData")
        if not isinstance(bd, list):
            continue
        try:
            rec = read_props(Reader(bytes(bd)))
        except Exception:
            continue
        path = str(rec.get("ActorPathName") or "")
        m = re.search(r"(Terrain_\d+)", path)
        if m:
            return m.group(1)
    return None


def grid_ref(xyz_cm, cal):
    """Convert a world position (centimetres) to a grid ref like 'C7'.

    Returns (ref, in_bounds). Out-of-grid positions are clamped and flagged.
    """
    xm = xyz_cm[0] / 100.0
    ym = xyz_cm[1] / 100.0
    col_i = int((xm - cal["x0"]) // cal["cell_x"])   # 0-based column
    row_n = int((ym - cal["y0"]) // cal["cell_y"]) + 1  # 1-based row
    in_bounds = 0 <= col_i < GRID_COLS.__len__() and 1 <= row_n <= GRID_ROWS
    col_i = max(0, min(len(GRID_COLS) - 1, col_i))
    row_n = max(1, min(GRID_ROWS, row_n))
    return f"{GRID_COLS[col_i]}{row_n}", in_bounds


def harvest_deposits(blobs):
    """Return exotic and uranium deposit records with location and remaining amount."""
    deposits = []
    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        bd = blob.get("BinaryData")
        if not isinstance(bd, list):
            continue
        try:
            rec = read_props(Reader(bytes(bd)))
        except Exception:
            continue
        dt = rec.get("ResourceDTKey")
        if dt not in DEPOSIT_LABELS:
            continue
        xyz = location_of(rec)
        if not xyz:
            continue
        deposits.append({
            "type": DEPOSIT_LABELS[dt],
            "dtkey": dt,
            "xyz": xyz,
            "remaining": rec.get("ResourceRemaining"),
        })
    # Sort by type then grid-friendly position (north-west first).
    deposits.sort(key=lambda d: (d["type"], d["xyz"][1], d["xyz"][0]))
    return deposits


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="List exotic/uranium deposits with in-game grid references.")
    ap.add_argument("save", help="Path to a prospect .json save file")
    ap.add_argument("--type", choices=["exotic", "uranium", "all"], default="all",
                    help="Which deposits to list (default: all)")
    ap.add_argument("--csv", action="store_true", help="Output CSV instead of a table")
    args = ap.parse_args(argv)

    try:
        blobs, info = load_blobs(args.save)
    except FileNotFoundError:
        print(f"File not found: {args.save}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to load prospect: {exc}", file=sys.stderr)
        return 1

    terrain = detect_terrain(blobs)
    cal = MAP_CALIBRATION.get(terrain)
    if cal is None:
        print(f"No grid calibration for map '{terrain}'. Known maps: "
              f"{', '.join(MAP_CALIBRATION)}.", file=sys.stderr)
        return 2

    deposits = harvest_deposits(blobs)
    if args.type != "all":
        want = "Uranium" if args.type == "uranium" else "Exotic"
        deposits = [d for d in deposits if d["type"] == want]

    rows = []
    for d in deposits:
        ref, in_bounds = grid_ref(d["xyz"], cal)
        x, y, z = (d["xyz"][0] / 100, d["xyz"][1] / 100, d["xyz"][2] / 100)
        rows.append((d["type"], ref + ("" if in_bounds else "*"),
                     f"{x:.0f}", f"{y:.0f}", f"{z:.0f}",
                     "" if d["remaining"] is None else str(d["remaining"])))

    if args.csv:
        print("type,grid,world_x_m,world_y_m,world_z_m,remaining")
        for r in rows:
            print(",".join(r))
        return 0

    name = info.get("ProspectID", args.save)
    dtkey = info.get("ProspectDTKey", "?")
    print(f"Deposits in {name}  ({dtkey} / {terrain})")
    print(f"Grid: 16x16 (A-P x 1-16), calibration '{terrain}'   "
          f"(* = outside grid bounds)\n")
    print(f"  {'TYPE':8} {'GRID':5} {'WORLD (m)':24} {'REMAINING'}")
    print(f"  {'-'*7} {'-'*5} {'-'*24} {'-'*9}")
    for typ, ref, x, y, z, rem in rows:
        world = f"({x}, {y}, {z})"
        print(f"  {typ:8} {ref:5} {world:24} {rem}")
    if not rows:
        print("  (none found)")
    else:
        n_exo = sum(1 for r in rows if r[0] == "Exotic")
        n_ura = sum(1 for r in rows if r[0] == "Uranium")
        print(f"\n  total: {len(rows)} deposits  ({n_exo} exotic, {n_ura} uranium)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
