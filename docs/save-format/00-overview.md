# Icarus Save Game Format

## Overview

Icarus saves player progress and world state across three hierarchical tiers of data. This documentation describes how the game stores data on disk, the file structures involved, and the tool limitations in reading them.

Saves are stored in `%LocalAppData%\Icarus\Saved\PlayerData\<SteamID64>\`. The data is mostly UTF-8 JSON, with binary files for fog-of-war masks and within-JSON base64-encoded+zlib-compressed world state blobs.

## Data Provenance & Confidence

These files are a **cloud-synced snapshot, not a live view**. While the game is running, in-game state can run ahead of what has been flushed to disk, and a later sync may overwrite the local files. Treat any specific **values** in this documentation as a point-in-time sample that may be stale — the **structures** are stable, the **contents** are not.

This documentation distinguishes what is proven from what is not:

- **Proven** — file structures, field names, and byte layouts read directly from real saves.
- **Inferred** — field *meanings* deduced from names, values, or the editor source. Reasonable, but not confirmed.
- **Unknown / unproven** — explicitly flagged. We do not guess; if a meaning or relationship cannot be shown from the data, it is marked as such (e.g. *unproven*, *inferred*, *unknown*).

## Three Tiers of Data

Icarus organizes save data in three tiers, each representing a scope of player progression:

### Account Tier

Shared across all character slots. Includes credentials, currency (credits, exotics), account-wide technology unlocks (talents), and global inventory (the *meta* inventory, which persists across character deaths).

**Location**: `PlayerData/<SteamID64>/` root directory  
**Key files**: `Profile.json`, `MetaInventory.json`, `Accolades.json`, `BestiaryData.json`, `Mounts.json`, `flags_<SteamID>.dat`

See [Account Tier](01-account-tier.md) for details.

### Character Tier

Per-character progression. Each character has an XP level, cosmetic settings (head, hair, body color, tattoos, scars), personal inventory state, and status (alive, dead, abandoned).

**Location**: `PlayerData/<SteamID64>/Characters.json`  
**Key field**: Characters are stored as JSON strings *inside* a JSON array, requiring double-decoding.

See [Character Tier](02-character-tier.md) for details.

### Prospect Tier

Per-world (prospect) state. Includes local building placements, NPC state, creature spawns, voxel deformation, and fog-of-war visibility. World saves are large (50 KB–1.3 MB) and compress a binary blob inside JSON using base64 encoding and zlib.

**Location**: `PlayerData/<SteamID64>/Prospects/` and multiplayer metadata files  
**Key files**: `Prospects/<Name>.json`, `AssociatedProspects_Slot_*.json`, `MapData/Terrain_*.fog`

See [Prospect Tier](03-prospect-tier.md) for details.

## Data Format Reality

The `icarus_editor` project (a separate, third-party repository — see [Acknowledgements](#acknowledgements)) presents itself as a "pure JSON" save tool, but this is incomplete:

- **Handles**: Profile.json, Characters.json, MetaInventory.json (account tier + character tier data)
- **Ignores**: Prospect/world layer (Prospects/*.json), binary fog files (MapData/*.fog), binary flag files (flags_*.dat), and any data-table metadata

The reason: reading prospect saves requires decompressing a zlib blob and parsing the inner schema, which uses Unreal Engine 4's binary property serialization format (tagged-property stream). The editor focuses on character-level edits (XP, credits, gear durability) rather than world state. The ProspectBlob format is now fully documented and decodable; see [Prospect Tier § Inner Payload](03-prospect-tier.md#inner-payload-staterecorder-format) for details on the UE4 property stream and StateRecorder component structure.

## Backup Rotation

All save files use a rotating backup scheme:

- `<filename>` — current save
- `<filename>.backup` — previous save
- `<filename>.backup_1` — older
- `<filename>.backup_2` .. `<filename>.backup_10` — up to 10 snapshots

When a new save is written, the oldest backup is discarded and the others roll forward.

## Metadata Data Tables

Item display names and durability limits come from data tables extracted from the game's `.pak` archives:

- `D_ItemsStatic.json` — maps item RowName to display name
- `D_Itemable.json` — item property traits
- `D_Durable.json` — maps item RowName to max durability

These are extracted at build time via the UnrealPakTool (a git submodule) and the `Extract-Packs.ps1` script, then code-generated into Dart constants.

See [Account Tier § Metadata System](01-account-tier.md#metadata-data-tables) for the extraction process.

## File Structure Summary

| Tier | File | Scope | Notes |
|------|------|-------|-------|
| Account | `Profile.json` | User ID, credits, exotics, account-wide talents, unlocked flags | Top-level metadata |
| Account | `MetaInventory.json` | Items that persist across character death | Account-wide backpack |
| Account | `Accolades.json` | Achievement records | Linked to ProspectID |
| Account | `BestiaryData.json` | Creature kill/encounter records | (mostly unexplored) |
| Account | `Mounts.json` | Tamed mount roster | ~643 KB of data |
| Account | `flags_<SteamID>.dat` | Binary flags (SteamID + int32 flag list) | Flag meanings *unproven* |
| Character | `Characters.json` | All character slots; **double-encoded JSON strings** | Critical gotcha |
| Character | `Loadout/Loadouts.json` | Equipment loadouts per character | Prospect-associated |
| Prospect | `Prospects/<Name>.json` | World state (buildings, creatures, voxels) | ProspectBlob uses zlib + StateRecorder format |
| Prospect | `AssociatedProspects_Slot_*.json` | Multiplayer metadata | Steam P2P host info |
| Prospect | `MapData/Terrain_*.fog` | Binary fog-of-war masks | Per-terrain-chunk visibility |

## Cross-References

- [Account Tier Documentation](01-account-tier.md) — Profile, inventory, talents, metadata tables
- [Character Tier Documentation](02-character-tier.md) — Characters.json, double-encoding trap, loadouts
- [Prospect Tier Documentation](03-prospect-tier.md) — World saves, compression, StateRecorder format, multiplayer

## Acknowledgements

The `icarus_editor` project is a **separate, third-party repository** — not part of this project. It is referenced throughout this documentation as a source of insight into the account- and character-tier save files (Profile.json, Characters.json, MetaInventory.json). Its source provided valuable reference for understanding how those data files are read, written, and encoded. Credit and thanks to its author for that groundwork.

- **Repository**: <https://github.com/dealloc/icarus_editor>
- **Author**: [dealloc](https://github.com/dealloc)
