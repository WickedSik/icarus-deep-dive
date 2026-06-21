#!/usr/bin/env python3
"""Find the closest ore deposits to a given grid square in an Icarus prospect save.

Every ore deposit the in-game map tracks (each carries a world transform and a
ResourceDTKey) is a *deep mining* deposit — the kind you drill with a Deep Mining
Drill. They come in two breeds:
    surface  (BP_Deep_Mining_Ore_Deposit_C)       drillable in the open world
    cave     (BP_Deep_Mining_Ore_Deposit_Cave_C)  buried inside a cave system

Given a save, an ore type, and an origin grid square (e.g. H10), this tool ranks
those deposits by horizontal distance from the *centre* of that square and lists
the nearest. Distance therefore carries roughly half-a-cell (~265 m) uncertainty,
depending on where within the square your base actually sits.

Usage:
    python icarus_closest.py <save> <ore> <grid> [--breed surface|cave|any]
                             [--limit N] [--csv]

Examples:
    python icarus_closest.py "The Garden.json" iron H10
    python icarus_closest.py "The Garden.json" iron H10 --breed surface
    python icarus_closest.py "The Garden.json" titanium C7 --limit 5
    python icarus_closest.py "The Garden.json" uranium H10 --csv > nearest.csv

Reuses the parser and calibration from icarus_map.py / icarus_deposits.py.
"""

import argparse
import math
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from icarus_map import Reader, read_props, load_blobs, location_of  # noqa: E402
from icarus_deposits import (  # noqa: E402
    MAP_CALIBRATION, MAP_DEADZONES, GRID_COLS, GRID_ROWS,
    grid_ref, detect_terrain,
)

# Friendly names for the less-obvious multi-word ResourceDTKeys. Plain ore names
# (Iron, Titanium, Copper, ...) match case-insensitively without an alias.
ORE_ALIASES = {
    "uranium": "Exotic_Raw_Uranium",
    "red": "Exotic_Red_Raw",
    "red exotic": "Exotic_Red_Raw",
    "ice": "Super_Cooled_Ice",
}


def resource_types(blobs):
    """Return a Counter of every ResourceDTKey present in the save."""
    counts = Counter()
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
        if dt:
            counts[dt] += 1
    return counts


def resolve_ore(query, available):
    """Map a user ore query to an exact ResourceDTKey present in the save.

    Returns (key, None) on success, or (None, message) describing the failure
    with the available types so the player can correct course.
    """
    q = query.strip().lower()
    by_lower = {k.lower(): k for k in available}

    # 1) explicit alias, 2) exact (case-insensitive), 3) unique substring match.
    if q in ORE_ALIASES and ORE_ALIASES[q] in available:
        return ORE_ALIASES[q], None
    if q in by_lower:
        return by_lower[q], None
    hits = [k for k in available if q in k.lower()]
    if len(hits) == 1:
        return hits[0], None

    listing = ", ".join(f"{k} ({c})" for k, c in available.most_common())
    if len(hits) > 1:
        return None, (f"Ore '{query}' is ambiguous — matches: {', '.join(hits)}.\n"
                      f"Available types: {listing}")
    return None, (f"Ore '{query}' not found. Available types: {listing}")


def parse_grid(text):
    """Parse a grid square like 'H10' into (col_index, row). Raises ValueError."""
    m = re.fullmatch(r"\s*([A-Pa-p])\s*(\d{1,2})\s*", text or "")
    if not m:
        raise ValueError(f"Bad grid square '{text}'. Expect a letter A-P + row 1-16, e.g. H10.")
    col_i = GRID_COLS.index(m.group(1).upper())
    row = int(m.group(2))
    if not 1 <= row <= GRID_ROWS:
        raise ValueError(f"Row {row} out of range — the grid runs 1-{GRID_ROWS}.")
    return col_i, row


def cell_center(col_i, row, cal):
    """World-space (metres) centre of grid cell (col_i, row)."""
    xm = cal["x0"] + (col_i + 0.5) * cal["cell_x"]
    ym = cal["y0"] + (row - 1 + 0.5) * cal["cell_y"]
    return xm, ym


def harvest_ore(blobs, want_key):
    """Collect every deposit whose ResourceDTKey equals want_key, with breed."""
    out = []
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
        if rec.get("ResourceDTKey") != want_key:
            continue
        xyz = location_of(rec)
        if not xyz:
            continue
        cls = str(rec.get("ActorClassName") or "")
        out.append({
            "xyz": xyz,
            "breed": "cave" if "Cave" in cls else "surface",
            "remaining": rec.get("ResourceRemaining"),
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Find the closest ore deposits to a grid square in an Icarus save.")
    ap.add_argument("save", help="Path to a prospect .json save file")
    ap.add_argument("ore", help="Ore type (e.g. iron, titanium, gold, uranium)")
    ap.add_argument("grid", help="Origin grid square (e.g. H10)")
    ap.add_argument("--breed", choices=["surface", "cave", "any"], default="any",
                    help="Filter by deep-deposit breed (default: any)")
    ap.add_argument("--limit", type=int, default=10,
                    help="How many of the nearest to list (default: 10)")
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

    available = resource_types(blobs)
    key, err = resolve_ore(args.ore, available)
    if err:
        print(err, file=sys.stderr)
        return 2

    try:
        col_i, row = parse_grid(args.grid)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    bx, by = cell_center(col_i, row, cal)
    origin_ref = f"{GRID_COLS[col_i]}{row}"

    deadzones = MAP_DEADZONES.get(terrain, set())
    rows = []
    for d in harvest_ore(blobs, key):
        if args.breed != "any" and d["breed"] != args.breed:
            continue
        ref, in_bounds = grid_ref(d["xyz"], cal)
        if ref in deadzones:
            continue
        xm, ym = d["xyz"][0] / 100.0, d["xyz"][1] / 100.0
        dist = math.hypot(xm - bx, ym - by)
        rows.append({
            "dist": dist, "ref": ref + ("" if in_bounds else "*"),
            "breed": d["breed"], "xm": xm, "ym": ym, "remaining": d["remaining"],
        })
    rows.sort(key=lambda r: r["dist"])
    if args.limit and args.limit > 0:
        rows = rows[:args.limit]

    if args.csv:
        print("ore,grid,breed,dist_m,world_x_m,world_y_m,remaining")
        for r in rows:
            rem = "" if r["remaining"] is None else str(r["remaining"])
            print(f"{key},{r['ref']},{r['breed']},{r['dist']:.0f},"
                  f"{r['xm']:.0f},{r['ym']:.0f},{rem}")
        return 0

    name = info.get("ProspectID", args.save)
    print(f"Closest '{key}' deposits to {origin_ref} in {name}  ({terrain})")
    print(f"Origin: centre of {origin_ref} = world ({bx:.0f}, {by:.0f}) m   "
          f"breed filter: {args.breed}")
    print(f"Distances are horizontal (XY) from the cell centre — "
          f"~{cal['cell_x']/2:.0f} m uncertainty within the square.\n")
    if not rows:
        print("  (no matching deposits found)")
        return 0
    print(f"  {'GRID':5} {'BREED':8} {'DIST':>7}   {'WORLD XY (m)':22} {'REMAINING'}")
    print(f"  {'-'*5} {'-'*8} {'-'*7}   {'-'*22} {'-'*9}")
    for r in rows:
        rem = "" if r["remaining"] is None else str(r["remaining"])
        world = f"({r['xm']:.0f}, {r['ym']:.0f})"
        print(f"  {r['ref']:5} {r['breed']:8} {r['dist']:6.0f}m   {world:22} {rem}")
    by_breed = Counter(r["breed"] for r in rows)
    breakdown = ", ".join(f"{n} {b}" for b, n in sorted(by_breed.items()))
    print(f"\n  showing {len(rows)} nearest  ({breakdown})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
