# Icarus Save Game Tools

This repository documents the Icarus (video game) save game format and provides Python tools to read and visualize prospect (world) saves. Most of the save data is plain JSON, but the prospect world state is stored as a base64-encoded, zlib-compressed Unreal Engine 4 tagged-property stream — and we can decode it.

## Documentation

The `docs/save-format/` directory contains detailed breakdowns of the Icarus save structure across three hierarchical tiers. Start with the overview, then dive into the tier that interests you.

| File | Covers |
|------|--------|
| [`00-overview.md`](docs/save-format/00-overview.md) | Three-tier model (account / character / prospect), file locations, the JSON-vs-binary reality, and an index |
| [`01-account-tier.md`](docs/save-format/01-account-tier.md) | Account-shared data: Profile.json, MetaInventory.json, Accolades, flags.dat, and the item data-table metadata system |
| [`02-character-tier.md`](docs/save-format/02-character-tier.md) | Per-character progression: Characters.json (with its double-encoding trap) and Loadouts |
| [`03-prospect-tier.md`](docs/save-format/03-prospect-tier.md) | Per-world saves: the ProspectBlob (base64 + zlib + UE4 StateRecorder format), deposits, and multiplayer linkage |

## Tools

Both tools are Python 3 (3.8+) with no third-party dependencies — they use only the standard library.

Prospect save files are located at:
```
%LocalAppData%\Icarus\Saved\PlayerData\<SteamID64>\Prospects\<Name>.json
```

Note: only open-world prospect saves contain a ProspectBlob to decode. Instance missions and dropship runs store data differently.

### `icarus_map.py`

Renders an ASCII top-down map of a prospect, plotting resource deposits and biome cave entrances over a grid.

**Usage:**
```bash
python3 tools/icarus_map.py <path/to/Prospect.json> [options]
```

**Options:**

| Flag | Effect |
|------|--------|
| `--width N` | Grid width in characters (default: 68) |
| `--height N` | Grid height in characters (default: 30) |
| `--no-caves` | Hide biome cave entrances |
| `--no-exotic` | Hide exotic deposits |
| `--no-uranium` | Hide exotic-uranium deposits |
| `--ore` | Also plot ore deposits (Titanium, Iron, etc.) |
| `--ice` | Also plot ice deposits |
| `--no-legend` | Omit the legend |
| `--no-table` | Omit the coordinate table |
| `--resources` | List resource deposit types found, then exit |

**Markers:**
- `E` = exotic deposit
- `U` = exotic-uranium deposit
- `o` = ore deposit (with `--ore`)
- `~` = ice deposit (with `--ice`)
- Biome caves: `a`=Arctic, `i`=Ice, `d`=Desert, `l`=Lava/Volcanic, `s`=Swamp, `?`=unknown

**Example:**
```bash
python3 tools/icarus_map.py "The Garden.json" --height 16 --no-table
```

Sample output:
```
  The Garden  (OpenWorld_Elysium)  — top-down, world XY
  X(left->right): -3455m .. 2857m   Y(top->bottom): -2954m .. 3023m
  +--------------------------------------------------------------------+
  |                                 l    l l    l                      |
  |                            l            ll     aa        i         |
  |                l            d  d            a a     a     ii U     |
  |                    d  d              d       d       a   a a a   a |
  |         l                            d           d              i a|
  |     l EE            d   d   d  d d     d   d        d  dd      a   |
  |U    E         d                   d      d        d  d d           |
  |                      a a       d          d    d  dd       d       |
  |         a      a a        a      d  d  d    d d   d    d    l      |
  |       i i           a  a a     a      a                        l   |
  |      a   i              a aa      a      l               l         |
  |                 a            a a          l  l ll    ls l          |
  |     a          a   a a  a         l    l  l                        |
  |                       a     a a                                    |
  |                     a     a                                        |
  |                           a                                        |
  +--------------------------------------------------------------------+

  LEGEND  E=Exotic   U=Uranium
  caves:  a=Arctic  i=Ice  d=Desert  l=Lava/Volcanic  s=Swamp  (other=first letter of code)
```

### `icarus_deposits.py`

Lists exotic and exotic-uranium deposits with their in-game map grid reference (e.g., C7, N5).

**Usage:**
```bash
python3 tools/icarus_deposits.py <path/to/Prospect.json> [options]
```

**Options:**

| Flag | Effect |
|------|--------|
| `--type exotic\|uranium\|all` | Which deposits to list (default: all) |
| `--csv` | Output CSV instead of a formatted table |

**Grid System:**

The game overlays a fixed 16×16 grid (columns A–P, rows 1–16) on each map. This grid is a property of the map itself, not the save file. The tool converts world coordinates (in metres) to grid cells using per-map calibration constants: the world position of the grid's top-left corner and the cell size. Grid references are fixed in-game — a deposit at C7 is always at C7 for that map.

Currently calibrated for `Terrain_021` (OpenWorld_Elysium / "The Garden"). Other maps need their own four-value calibration entry in the `MAP_CALIBRATION` dictionary.

A `*` after a grid reference means the position fell outside the 16×16 grid bounds.

**Example:**
```bash
python3 tools/icarus_deposits.py "The Garden.json"
```

Sample output:
```
Deposits in The Garden  (OpenWorld_Elysium / Terrain_021)
Grid: 16x16 (A-P x 1-16), calibration 'Terrain_021'   (* = outside grid bounds)

  TYPE     GRID  WORLD (m)                REMAINING
  ------- ----- ------------------------ ---------
  Exotic   D7    (-2640, -799, -10)       297
  Exotic   C7    (-2727, -783, -11)       231
  Exotic   C7    (-2787, -755, -11)       267
  Exotic   C7    (-2785, -720, -8)        202
  Exotic   C8    (-2935, -419, 98)        211
  Uranium  N5    (2398, -1780, 90)        282
  Uranium  B8    (-3455, -368, 30)        257

  total: 7 deposits  (5 exotic, 2 uranium)
```

CSV output:
```bash
python3 tools/icarus_deposits.py "The Garden.json" --csv
```

```csv
type,grid,world_x_m,world_y_m,world_z_m,remaining
Exotic,D7,-2640,-799,-10,297
Exotic,C7,-2727,-783,-11,231
Exotic,C7,-2787,-755,-11,267
Exotic,C7,-2785,-720,-8,202
Exotic,C8,-2935,-419,98,211
Uranium,N5,2398,-1780,90,282
Uranium,B8,-3455,-368,30,257
```

## Requirements

- Python 3.8 or later
- Standard library only (no external packages)
