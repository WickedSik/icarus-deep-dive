#!/usr/bin/env python3
"""Render an ASCII top-down map of an Icarus prospect (world) save.

The prospect save stores world state inside ``ProspectBlob.BinaryBlob`` as a
base64-encoded, zlib-compressed Unreal Engine 4 tagged-property stream. This
tool decodes that stream, harvests the recorded deposits and cave entrances
(each carries a world-space transform), and plots them on an ASCII grid.

Usage:
    python icarus_map.py <path/to/Prospect.json> [options]

Examples:
    python icarus_map.py "The Garden.json"
    python icarus_map.py "The Garden.json" --ore --ice
    python icarus_map.py "The Garden.json" --no-caves --width 100 --height 44
    python icarus_map.py "The Garden.json" --resources      # list resource types only

Markers:
    E = Exotic deposit          U = Exotic-Uranium deposit
    o = ore deposit (--ore)     ~ = ice deposit (--ice)
    biome caves: a=Arctic i=Ice d=Desert l=Lava/Volcanic s=Swamp ?=unknown

No third-party dependencies; standard library only.
"""

import argparse
import base64
import collections
import json
import re
import struct
import sys
import zlib


# --------------------------------------------------------------------------
# UE4 tagged-property (FPropertyTag) parser
# --------------------------------------------------------------------------
class Reader:
    """Cursor over a byte buffer with the primitive reads UE4 serialization uses."""

    def __init__(self, buf, pos=0):
        self.b = buf
        self.p = pos
        self.n = len(buf)

    def i32(self):
        v = struct.unpack_from("<i", self.b, self.p)[0]
        self.p += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.b, self.p)[0]
        self.p += 4
        return v

    def i64(self):
        v = struct.unpack_from("<q", self.b, self.p)[0]
        self.p += 8
        return v

    def f32(self):
        v = struct.unpack_from("<f", self.b, self.p)[0]
        self.p += 4
        return v

    def f64(self):
        v = struct.unpack_from("<d", self.b, self.p)[0]
        self.p += 8
        return v

    def byte(self):
        v = self.b[self.p]
        self.p += 1
        return v

    def fstr(self):
        """Read an UE4 FString: int32 length prefix (incl. trailing null), then bytes."""
        ln = self.i32()
        if ln == 0:
            return ""
        if ln > 0:
            raw = self.b[self.p:self.p + ln]
            self.p += ln
            return raw[:-1].decode("latin-1", "replace")
        ln = -ln
        raw = self.b[self.p:self.p + ln * 2]
        self.p += ln * 2
        return raw[:-2].decode("utf-16-le", "replace")


# Structs UE4 serializes natively (raw values, not nested tagged properties).
def read_struct_value(r, stype, size):
    if stype in ("Vector", "Rotator"):
        return [r.f32(), r.f32(), r.f32()]
    if stype == "Quat":
        return [r.f32(), r.f32(), r.f32(), r.f32()]
    if stype == "Vector2D":
        return [r.f32(), r.f32()]
    if stype == "LinearColor":
        return [r.f32(), r.f32(), r.f32(), r.f32()]
    if stype == "Color":
        v = r.b[r.p:r.p + 4]
        r.p += 4
        return list(v)
    if stype == "Guid":
        v = r.b[r.p:r.p + 16]
        r.p += 16
        return v.hex()
    if stype == "IntPoint":
        return [r.i32(), r.i32()]
    if stype == "DateTime":
        return r.i64()
    # General struct: nested tagged properties terminated by a "None" property.
    return read_props(r)


def read_value(r, ptype, size, structtype=None, innertype=None):
    if ptype == "StructProperty":
        return read_struct_value(r, structtype, size)
    if ptype in ("IntProperty", "Int32Property"):
        return r.i32()
    if ptype == "Int64Property":
        return r.i64()
    if ptype == "UInt32Property":
        return r.u32()
    if ptype == "FloatProperty":
        return r.f32()
    if ptype == "DoubleProperty":
        return r.f64()
    if ptype in ("StrProperty", "NameProperty"):
        return r.fstr()
    if ptype == "BoolProperty":
        return None  # value lives in the tag, not the body
    if ptype == "ByteProperty":
        return r.byte() if size == 1 else r.fstr()
    if ptype == "EnumProperty":
        return r.fstr()
    if ptype == "ArrayProperty":
        end = r.p + size
        count = r.i32()
        out = []
        if innertype == "StructProperty":
            # array-of-struct header: a single element property tag, then `count` structs
            r.fstr()              # element name
            r.fstr()              # element type ("StructProperty")
            r.i32()               # element data size
            r.i32()               # array index
            r.fstr()              # struct type
            r.p += 16             # struct guid
            r.byte()              # terminator
            for _ in range(count):
                out.append(read_props(r))
            r.p = end
            return out
        for _ in range(count):
            if innertype in ("IntProperty",):
                out.append(r.i32())
            elif innertype == "FloatProperty":
                out.append(r.f32())
            elif innertype == "ByteProperty":
                out.append(r.byte())
            elif innertype in ("StrProperty", "NameProperty"):
                out.append(r.fstr())
            elif innertype == "BoolProperty":
                out.append(r.byte())
            else:
                break
        r.p = end
        return out
    # Unknown property type: skip its body.
    r.p += size
    return None


def read_props(r, limit=None):
    """Read a list of tagged properties until a 'None' name or buffer end."""
    props = {}
    while r.p < r.n:
        if limit is not None and r.p >= limit:
            break
        name = r.fstr()
        if name == "None":
            break
        ptype = r.fstr()
        size = r.i32()
        r.i32()  # array index
        structtype = innertype = boolval = None
        if ptype == "StructProperty":
            structtype = r.fstr()
            r.p += 16   # struct guid
            r.byte()    # terminator
        elif ptype == "ArrayProperty":
            innertype = r.fstr()
            r.byte()
        elif ptype == "BoolProperty":
            boolval = r.byte()
            r.byte()
        elif ptype in ("ByteProperty", "EnumProperty"):
            r.fstr()    # enum name
            r.byte()
        elif ptype == "MapProperty":
            r.fstr()    # key type
            r.fstr()    # value type
            r.byte()
        else:
            r.byte()
        start = r.p
        try:
            if ptype == "BoolProperty":
                val = boolval
            else:
                val = read_value(r, ptype, size, structtype, innertype)
        except Exception:
            val = None
        if ptype not in ("ArrayProperty", "StructProperty"):
            r.p = start + size  # realign defensively for fixed-size bodies
        props[name] = val
    return props


# --------------------------------------------------------------------------
# Prospect loading and actor harvesting
# --------------------------------------------------------------------------
def load_blobs(path):
    """Load a prospect save, decompress its ProspectBlob, return StateRecorderBlobs."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    blob = data.get("ProspectBlob")
    if not blob or "BinaryBlob" not in blob:
        raise ValueError("No ProspectBlob.BinaryBlob found — is this an open-world prospect save?")
    raw = zlib.decompress(base64.b64decode(blob["BinaryBlob"]))
    top = read_props(Reader(raw))
    info = data.get("ProspectInfo", {})
    return top.get("StateRecorderBlobs", []), info


def location_of(rec):
    t = rec.get("ActorTransform")
    if isinstance(t, dict) and isinstance(t.get("Translation"), list):
        return t["Translation"]
    return None


CAVE_CODE_LETTER = {"AC": "a", "DC": "d", "LC": "l", "IC": "i", "SW": "s"}


def harvest(blobs):
    """Categorise recorded actors into deposits and cave entrances with locations."""
    out = {"exotic": [], "uranium": [], "ore": [], "ice": [], "caves": []}
    resource_counts = collections.Counter()
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
        name = str(rec.get("ActorClassName") or rec.get("ObjectFName") or "")
        if "CaveEntrance" in name:
            m = re.search(r"CaveEntrance_([A-Z]{2})_", name)
            xyz = location_of(rec)
            if m and xyz:
                out["caves"].append((m.group(1), xyz))
            continue
        dt = rec.get("ResourceDTKey")
        xyz = location_of(rec)
        if not dt or not xyz:
            continue
        resource_counts[dt] += 1
        if dt == "Exotic":
            out["exotic"].append(xyz)
        elif dt == "Exotic_Raw_Uranium":
            out["uranium"].append(xyz)
        elif "Ice" in dt:
            out["ice"].append(xyz)
        else:
            out["ore"].append(xyz)
    return out, resource_counts


# --------------------------------------------------------------------------
# ASCII rendering
# --------------------------------------------------------------------------
def render(data, info, args):
    cells = []  # (priority, marker, xyz)
    if args.show_caves:
        for code, xyz in data["caves"]:
            cells.append((0, CAVE_CODE_LETTER.get(code, code[0].lower()), xyz))
    if args.show_ore:
        for xyz in data["ore"]:
            cells.append((1, "o", xyz))
    if args.show_ice:
        for xyz in data["ice"]:
            cells.append((1, "~", xyz))
    if args.show_exotic:
        for xyz in data["exotic"]:
            cells.append((2, "E", xyz))
    if args.show_uranium:
        for xyz in data["uranium"]:
            cells.append((2, "U", xyz))

    if not cells:
        print("Nothing to plot with the current flags.", file=sys.stderr)
        return

    xs = [c[2][0] for c in cells]
    ys = [c[2][1] for c in cells]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    spanx = (maxx - minx) or 1.0
    spany = (maxy - miny) or 1.0
    W, H = args.width, args.height

    # Each grid cell keeps the highest-priority marker that lands in it.
    grid = [[" "] * W for _ in range(H)]
    prio = [[-1] * W for _ in range(H)]
    for p, marker, xyz in cells:
        cx = int((xyz[0] - minx) / spanx * (W - 1))
        cy = int((xyz[1] - miny) / spany * (H - 1))
        if p >= prio[cy][cx]:
            prio[cy][cx] = p
            grid[cy][cx] = marker

    name = info.get("ProspectID", "?")
    dtkey = info.get("ProspectDTKey", "?")
    print(f"  {name}  ({dtkey})  — top-down, world XY")
    print(f"  X(left->right): {minx/100:.0f}m .. {maxx/100:.0f}m"
          f"   Y(top->bottom): {miny/100:.0f}m .. {maxy/100:.0f}m")
    print("  +" + "-" * W + "+")
    for row in grid:
        print("  |" + "".join(row) + "|")
    print("  +" + "-" * W + "+")

    if not args.no_legend:
        print()
        parts = []
        if args.show_exotic:
            parts.append("E=Exotic")
        if args.show_uranium:
            parts.append("U=Uranium")
        if args.show_ore:
            parts.append("o=ore")
        if args.show_ice:
            parts.append("~=ice")
        print("  LEGEND  " + "   ".join(parts))
        if args.show_caves:
            print("  caves:  a=Arctic  i=Ice  d=Desert  l=Lava/Volcanic  s=Swamp"
                  "  (other=first letter of code)")

    if not args.no_table:
        def fmt(pts):
            return ", ".join(f"({p[0]/100:.0f},{p[1]/100:.0f})" for p in pts) or "none"
        print()
        if args.show_exotic:
            print(f"  EXOTIC  ({len(data['exotic'])}): {fmt(data['exotic'])}")
        if args.show_uranium:
            print(f"  URANIUM ({len(data['uranium'])}): {fmt(data['uranium'])}")
        if args.show_ore:
            print(f"  ORE     ({len(data['ore'])} deposits)")
        if args.show_ice:
            print(f"  ICE     ({len(data['ice'])} deposits)")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Render an ASCII top-down map of an Icarus prospect save.")
    ap.add_argument("save", help="Path to a prospect .json save file")
    ap.add_argument("--width", type=int, default=68, help="Grid width (default 68)")
    ap.add_argument("--height", type=int, default=30, help="Grid height (default 30)")
    # Layer toggles. Exotic/uranium/caves on by default; ore/ice off by default.
    ap.add_argument("--no-caves", dest="show_caves", action="store_false",
                    help="Hide biome cave entrances")
    ap.add_argument("--no-exotic", dest="show_exotic", action="store_false",
                    help="Hide exotic deposits")
    ap.add_argument("--no-uranium", dest="show_uranium", action="store_false",
                    help="Hide exotic-uranium deposits")
    ap.add_argument("--ore", dest="show_ore", action="store_true",
                    help="Also plot ore deposits (Titanium, Iron, ...)")
    ap.add_argument("--ice", dest="show_ice", action="store_true",
                    help="Also plot ice deposits")
    ap.add_argument("--no-legend", action="store_true", help="Omit the legend")
    ap.add_argument("--no-table", action="store_true", help="Omit the coordinate table")
    ap.add_argument("--resources", action="store_true",
                    help="List resource types found in the save and exit")
    args = ap.parse_args(argv)

    try:
        blobs, info = load_blobs(args.save)
    except FileNotFoundError:
        print(f"File not found: {args.save}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Failed to load prospect: {exc}", file=sys.stderr)
        return 1

    data, resource_counts = harvest(blobs)

    if args.resources:
        print(f"Resource deposit types in {info.get('ProspectID', args.save)}:")
        for k, c in resource_counts.most_common():
            print(f"  {c:4}  {k}")
        return 0

    render(data, info, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
