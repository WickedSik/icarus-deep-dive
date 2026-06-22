# Account Tier: Profile, Inventory, and Metadata

## Scope & Location

Account-tier data is shared across all character slots in a save. It includes user identity, currency, technology unlocks, achievement records, and the *meta* inventory (items that persist when a character dies).

**Root directory**: `%LocalAppData%\Icarus\Saved\PlayerData\<SteamID64>\`

**Key files**:
- `Profile.json` — Account identity, currency, account-wide talents
- `MetaInventory.json` — Persistent inventory
- `Accolades.json` — Achievement records with timestamps
- `BestiaryData.json` — Creature encounter/kill records (largely unexplored)
- `Mounts.json` — Tamed mount roster
- `flags_<SteamID>.dat` — Binary flag state

## Profile.json

The top-level account document. Contains user ID, currency pools, unlocked flags, account-wide talent tree progress, and metadata about character slots.

### Structure

```json
{
  "UserID": "<STEAMID64>",
  "MetaResources": [
    {"MetaRow": "Refund", "Count": 10},
    {"MetaRow": "Credits", "Count": 41},
    {"MetaRow": "Exotic1", "Count": 453},
    {"MetaRow": "Exotic_Red", "Count": 57}
  ],
  "UnlockedFlags": [5, 4, 1, 26, 86, 7, 60, 20, 93],
  "Talents": [
    {"RowName": "Workshop_Envirosuit", "Rank": 1},
    {"RowName": "Workshop_Envirosuit_1", "Rank": 1}
  ],
  "NextChrSlot": 4,
  "DataVersion": 4
}
```

### Key Fields

| Field | Type | Notes |
|-------|------|-------|
| `UserID` | string | Steam ID (64-bit) as string |
| `MetaResources` | array | Currency/resource pools; see table below |
| `UnlockedFlags` | `array<int>` | Bit indices for unlocked tech/content |
| `Talents` | `array<object>` | Account-wide tech tree entries; each has `RowName` and `Rank` |
| `NextChrSlot` | int | Next available character slot (0–3) |
| `DataVersion` | int | Schema version (observed: 4) |

### MetaResources

Known `MetaRow` keys and their meanings:

| MetaRow | Meaning |
|---------|---------|
| `Credits` | Currency for crafting |
| `Exotic1` | Standard exotics — purple |
| `Exotic_Red` | Red exotics — red |
| `Biomass` | Organic material for crafting |
| `Exotic_Uranium` | Exotic uranium — yellow |
| `Refund` | Refund tokens (reset talent points) |

New entries can be added dynamically if missing; the editor code (icarus_profile.dart line 62–73) auto-creates them.

### Talents

Talents are account-wide tech tree unlocks. Examples include envirosuit tiers, workshop recipes, creature domestication, and prospect-specific challenges.

```json
{"RowName": "Workshop_Seed_Wheat", "Rank": 1}
```

Each entry has a `RowName` (the data table key) and `Rank` (progression level, typically 1 for unlocked).

### UnlockedFlags

A sparse array of bit indices representing unlocked features. Reading them requires knowing the bit-to-feature mapping, which is internal to the game.

## MetaInventory.json

Items that persist across all characters and survive character death. Used for storing extra gear, backup tools, and crafted items.

### Structure

```json
{
  "InventoryID": "MetaInventoryID_Main",
  "Items": [
    {
      "ItemStaticData": {
        "RowName": "Envirosuit_Tier3",
        "DataTableName": "D_ItemsStatic"
      },
      "ItemDynamicData": [
        {"PropertyType": "ItemableStack", "Value": 1}
      ],
      "ItemCustomStats": [],
      "CustomProperties": {
        "StaticWorldStats": [],
        "StaticWorldHeldStats": [],
        "Stats": [],
        "Alterations": [],
        "LivingItemSlots": []
      },
      "DatabaseGUID": "F450B30C4C194998FC1CEF8C4FF35570",
      "ItemOwnerLookupId": -1,
      "RuntimeTags": {"GameplayTags": []}
    },
    {
      "ItemStaticData": {
        "RowName": "Meta_Carbon_Head_Beta",
        "DataTableName": "D_ItemsStatic"
      },
      "ItemDynamicData": [
        {"PropertyType": "ItemableStack", "Value": 1},
        {"PropertyType": "Durability", "Value": 5500}
      ],
      "ItemCustomStats": [],
      "CustomProperties": {...},
      "DatabaseGUID": "A795257A4BA79D264929188E62BF887F",
      "ItemOwnerLookupId": -1,
      "RuntimeTags": {"GameplayTags": []}
    }
  ]
}
```

### Item Object Fields

| Field | Type | Notes |
|-------|------|-------|
| `ItemStaticData.RowName` | string | The item ID (looked up in D_ItemsStatic) |
| `ItemStaticData.DataTableName` | string | Always `"D_ItemsStatic"` |
| `ItemDynamicData` | array | Item state properties (stack size, durability, etc.) |
| `ItemCustomStats` | array | Custom stat overrides (usually empty) |
| `CustomProperties` | object | Additional traits (alterations, living item slots, etc.) |
| `DatabaseGUID` | string | Unique instance ID (hex UUID) |
| `ItemOwnerLookupId` | int | Inventory owner reference; `-1` for meta inventory |
| `RuntimeTags` | object | Gameplay tag runtime data |

### ItemDynamicData

Properties stored per item instance. Common types:

| PropertyType | Value | Meaning |
|--------------|-------|---------|
| `ItemableStack` | int | Stack count (1 for most items) |
| `Durability` | int | Current durability (resolved against D_Durable max) |
| (others) | — | Varying by item type |

### Durability Resolution

To find max durability for an item, look up its `RowName` in the `D_Durable.g.dart` generated file (or the extracted `D_Durable.json`). The editor's `IcarusInventoryItem.maxDurability` property does this lookup.

**Example**: Item `Meta_Carbon_Head_Beta` has `Durability: 5500` in `ItemDynamicData`. Its max is found in the D_Durable table, and durability percentage is `(5500 / max) * 100`.

## Accolades.json

Records achievements/accolades completed by the player, including timestamps and which prospect they were earned in.

### Structure

```json
{
  "CompletedAccolades": [
    {
      "Accolade": {
        "RowName": "PickupBasicResource",
        "DataTableName": "D_Accolades"
      },
      "TimeCompleted": "2024.08.18-16.07.39",
      "ProspectID": "Cradle of the Gods"
    },
    {
      "Accolade": {
        "RowName": "ReachMaxLevel",
        "DataTableName": "D_Accolades"
      },
      "TimeCompleted": "2025.04.08-18.16.05",
      "ProspectID": "Welcome to Hell"
    }
  ]
}
```

### Fields

| Field | Type | Notes |
|-------|------|-------|
| `Accolade.RowName` | string | Accolade ID from D_Accolades |
| `Accolade.DataTableName` | string | Always `"D_Accolades"` |
| `TimeCompleted` | string | ISO-like timestamp: `YYYY.MM.DD-HH.MM.SS` |
| `ProspectID` | string | Prospect name or GUID where accolade was earned |

The timestamp format is unusual (`YYYY.MM.DD-HH.MM.SS` with dots, not dashes). Store/compare as strings unless you have a reason to parse.

## BestiaryData.json

Creature encounter and kill records. Schema is not fully documented; treat as supplementary data.

**Observed**: Array of creature encounter objects with counts, kill records, and species identifiers.

## Mounts.json

Tamed mount roster. Typically ~643 KB of roster data. Each mount entry includes taming status, health, abilities, and cosmetic state.

**Note**: Full schema reverse-engineering is incomplete. Known to exist and persist mounts across prospects.

## flags_<SteamID>.dat

Small binary file holding account progression flags. Its precise purpose is *unproven* — we have not mapped the values to specific features.

### Format (observed)

The byte layout is read directly from the file:

| Bytes | Meaning |
|-------|---------|
| `int32` | Length prefix for the following string (includes the trailing null) |
| ASCII | SteamID64, null-terminated |
| `int32` | Count of flag entries that follow |
| `int32 × count` | Flag index values |

**Example breakdown** (from a real 62-byte save, `flags_<STEAMID64>.dat`):

```
12 00 00 00                                       # length = 18 (17 digits + null)
<17 ASCII bytes: SteamID64 digits>           00   # "<STEAMID64>\0"
09 00 00 00                                       # count = 9
01.. 02.. 03.. 04.. 15.. 16.. 17.. 19.. 1b..      # values (int32): 1, 2, 3, 4, 21, 22, 23, 25, 27
```

### Unknown / unproven

- **What the integers mean** — *unknown*. The indices are not mapped to features.
- **Relationship to `Profile.json` `UnlockedFlags`** — *unproven*. In the single snapshot examined, the value sets differ (`flags.dat` = `[1, 2, 3, 4, 21, 22, 23, 25, 27]` vs `UnlockedFlags` = `[5, 4, 1, 26, 86, 7, 60, 20, 93]`). This may indicate two separate flag spaces, **or** simply a stale snapshot (see [Data Provenance](00-overview.md#data-provenance--confidence)); we cannot tell from the data alone.
- **Whether the layout is always an int32 list** — based on a single sample; not generalised.

## Metadata Data Tables

Item display names and durability limits are stored in extracted game data tables.

### Extraction Process

1. **Source**: Game `.pak` archive at `<IcarusRoot>/Icarus/Content/Data/data.pak`
2. **Tool**: UnrealPakTool (git submodule in `src/UnrealPakTool/`)
3. **Script**: `scripts/Extract-Packs.ps1` (PowerShell)
   - Filters for `D_ItemsStatic.json`, `D_Itemable.json`, `D_Durable.json`
   - Extracts to `icarus_editor_core/lib/src/generated/`
   - Runs `flutter pub run build_runner build` to generate Dart code

**Extract-Packs.ps1 snippet**:

```powershell
Add-Type -AssemblyName System.Windows.Forms
$FileBrowser = New-Object System.Windows.Forms.FolderBrowserDialog
$FileBrowser.ShowDialog()
$icarus = $FileBrowser.SelectedPath
$packFile = Join-Path $icarus "Icarus\Content\Data\data.pak"

if (Test-Path -Path $packFile -PathType Leaf) {
    ..\src\UnrealPakTool\UnrealPak.exe -Filter="*D_ItemsStatic.json" -Extract $packFile ../icarus_editor_core/lib/src/generated
    ..\src\UnrealPakTool\UnrealPak.exe -Filter="*D_Itemable.json" -Extract $packFile ../icarus_editor_core/lib/src/generated
    ..\src\UnrealPakTool\UnrealPak.exe -Filter="*D_Durable.json" -Extract $packFile ../icarus_editor_core/lib/src/generated
    cd ../src/icarus_editor_core
    flutter pub run build_runner build
} else {
    Write-Error "Failed to find data.pak file, please select the Icarus root folder"
}
```

### Generated Dart Constants

After extraction and code generation, the editor uses:

- `itemsStatic` (Map<String, ItemStaticEntry>) — RowName → display name
- `durable` (Map<String, int>) — RowName → max durability

**Usage** (icarus_inventory.dart line 28–30):

```dart
if (itemsStatic.containsKey(item['ItemStaticData']['RowName'])) {
  _entry = itemsStatic[item['ItemStaticData']['RowName']];
}
```

When an item is added in a game update before the editor is rebuilt, it won't be in the map; the editor falls back to displaying the `RowName` as-is.

## Backup Rotation

All account-tier files follow the same rotation scheme:

```
Profile.json          (current)
Profile.json.backup   (previous save)
Profile.json.backup_1
Profile.json.backup_2
...
Profile.json.backup_10 (oldest, then discarded)
```

Same for `MetaInventory.json`, `Accolades.json`, `BestiaryData.json`, `Mounts.json`.

When writing a new save, backups roll forward and the oldest is deleted.

## Worked Example: Profile.json

From `%LocalAppData%\Icarus\Saved\PlayerData\<STEAMID64>\Profile.json`:

```json
{
  "UserID": "<STEAMID64>",
  "MetaResources": [
    {"MetaRow": "Refund", "Count": 10},
    {"MetaRow": "Credits", "Count": 41},
    {"MetaRow": "Exotic1", "Count": 453},
    {"MetaRow": "Exotic_Red", "Count": 57}
  ],
  "UnlockedFlags": [5, 4, 1, 26, 86, 7, 60, 20, 93],
  "Talents": [
    {"RowName": "Workshop_Envirosuit", "Rank": 1},
    {"RowName": "Workshop_Envirosuit_1", "Rank": 1},
    {"RowName": "Workshop_Survival_Backpack", "Rank": 1},
    {"RowName": "Prospect_OLY_Forest_Recon", "Rank": 1},
    {"RowName": "Prospect_OLY_Forest_Exploration", "Rank": 1},
    {"RowName": "Workshop_Seed_Wheat", "Rank": 1},
    {"RowName": "Workshop_Creature_Chicken", "Rank": 1}
  ],
  "NextChrSlot": 4,
  "DataVersion": 4
}
```

**Interpretation**:
- **UserID**: Steam account <STEAMID64>
- **MetaResources**: 10 refund tokens, 41 credits, 453 standard (purple) exotics, 57 red exotics
- **UnlockedFlags**: Bits 5, 4, 1, 26, 86, etc. are set (feature flags not reverse-engineered)
- **Talents**: 7 techs unlocked (envirosuit variants, backpack, farm seeds, chicken taming, forest exploration)
- **NextChrSlot**: Next available slot is 4 (means slots 0–3 are full)
- **DataVersion**: Schema version 4

This player has 4 character slots filled and 41 credits to spend on a new prospect drop.
