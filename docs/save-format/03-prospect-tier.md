# Prospect Tier: World Save State and Multiplayer Metadata

## Scope & Location

Prospect-tier data is per-world state. Each prospect (world instance) stores building placements, NPC state, creature spawns, voxel terrain deformation, fog-of-war visibility, and other world-time-series data. Saves are large (50 KB–1.3 MB compressed) because they contain full world snapshots.

**Primary location**: `%LocalAppData%\Icarus\Saved\PlayerData\<SteamID64>\Prospects\<ProspectName>.json`

**Multiplayer metadata**: `AssociatedProspects_Slot_*.json` (one per equipped loadout slot)

**Terrain masks**: `MapData/Terrain_*.fog` (binary fog-of-war per terrain chunk)

## Prospect File Structure

### Top-Level JSON

```json
{
  "ProspectInfo": {
    "ProspectID": "The Garden",
    "ProspectDTKey": "OpenWorld_Elysium",
    "FactionMissionDTKey": "",
    "ProspectState": "Active",
    "...": "..."
  },
  "ProspectBlob": {
    "Key": "actors",
    "Hash": "7fc6fabba9c81265f27effec57446349b6f78162",
    "TotalLength": 245084,
    "DataLength": 245084,
    "UncompressedLength": 2470000,
    "BinaryBlob": "H4sIAAABBQC/...[base64-encoded compressed data]..."
  }
}
```

### ProspectInfo

Metadata about the prospect and its current state.

| Field | Type | Notes |
|-------|------|-------|
| `ProspectID` | string | Display name (e.g., "The Garden", "Welcome to Hell") or GUID |
| `ProspectDTKey` | string | Data table reference (e.g., "OpenWorld_Elysium") |
| `FactionMissionDTKey` | string | Faction mission type, or empty for open worlds |
| `ProspectState` | string | "Active", "Completed", "Failed", etc. |
| (others) | — | Additional metadata (creation time, difficulty, rewards, etc.) |

The `ProspectID` can be either a human-readable name (for named prospects like "Arcpost") or a 32-character hex GUID (for procedurally-named or dynamically-created worlds).

## ProspectBlob: Compressed World State

The `ProspectBlob` object contains the world state data in an envelope format: base64-encoded, zlib-compressed binary.

### Blob Fields

| Field | Type | Notes |
|-------|------|-------|
| `Key` | string | Usually `"actors"` (meaning actor/object state) |
| `Hash` | string | SHA1 hex digest of the uncompressed data (integrity check) |
| `TotalLength` | int | Compressed byte length (size on disk after zlib) |
| `DataLength` | int | Same as TotalLength in practice; redundant field |
| `UncompressedLength` | int | Decompressed size (in bytes) |
| `BinaryBlob` | string | Base64-encoded zlib-compressed binary |

### Decompression Workflow

1. **Decode Base64**: Convert `BinaryBlob` from base64 string to bytes
   - Zlib-compressed data typically starts with base64 prefix `eJz` (decoded: 0x78 0x9C)
2. **Inflate zlib**: Decompress the bytes using standard zlib/DEFLATE
3. **Verify hash**: Compute SHA1 of decompressed data; should match `Hash` field
4. **Parse inner payload**: Parse the decompressed bytes as a UE4 tagged-property serialization stream (see below)

**Compression ratio example** (from real save `EF3EA80F45D6AE51185B8686EC1C71FA`):
- `TotalLength`: 35,187 bytes (compressed)
- `UncompressedLength`: 856,886 bytes (decompressed)
- Ratio: ~24:1 compression
- `Hash`: f5f8504262b8c5b6c5748263310f34ec8e033418 (verified match)

### Inner Payload: StateRecorder Format

The decompressed binary is an Unreal Engine 4 **tagged-property serialization stream**. This is the same FPropertyTag binary format used internally in UE4 GVAS `.sav` files, but without the outer GVAS magic header—it's a raw property stream.

#### Property Serialization Format

The stream contains a series of typed properties, each prefixed with metadata:

- **Property name**: UE4 FString (int32 little-endian length including null, then ASCII bytes, then 0x00 terminator)
- **Property type**: UE4 FString (e.g., "StructProperty", "ArrayProperty", "IntProperty")
- **Property tag**: Binary header with size and metadata
- **Property value**: Bytes matching the declared type

#### Top-Level Structure: StateRecorder System

The root property is named `StateRecorderBlobs` and is an ArrayProperty. Each element in the array is a StructProperty named `StateRecorderBlob`, containing:

| Field | Type | Content |
|-------|------|---------|
| `ComponentClassName` | StrProperty | Fully-qualified class name (e.g., `/Script/Icarus.EnzymeGeyserRecorderComponent`) |
| `BinaryData` | ArrayProperty<ByteProperty> | Raw byte array (component-specific serialized state) |

Each `StateRecorderBlob.BinaryData` is itself a UE4 tagged-property stream (recursive structure). This nested stream contains the component's world state (buildings, inventories, transforms, etc.).

#### Observed Property Types

The stream uses the following UE4 property types (frequencies from sample save):

| Type | Count | Content |
|------|-------|---------|
| StructProperty | ~5946 | Nested structures (Vector, Transform, Rotation, etc.) |
| ArrayProperty | ~2454 | Variable-length arrays |
| IntProperty | ~2432 | 32-bit signed integers |
| BoolProperty | ~1235 | Boolean flags |
| NameProperty | ~974 | FName references (e.g., enum values) |
| FloatProperty | ~501 | 32-bit floats |
| StrProperty | ~399 | Strings (UTF-8) |
| EnumProperty | ~171 | Enum values |
| ByteProperty | ~167 | Single bytes or byte arrays |
| UInt32Property | ~144 | 32-bit unsigned integers |
| MapProperty | ~2 | Key-value maps |
| Int64Property | ~1 | 64-bit signed integers |

#### Recorder Component Types

The world state is decomposed into ~23 distinct recorder component types. Each persists one slice of world state:

| Component Type | Persists |
|---|---|
| ResourceDepositRecorderComponent | Resource/ore node depletion state |
| SpawnedVoxelRecorderComponent | Voxel deformation (player-dug/mined areas) |
| VoxelRecorderComponent | Voxel metadata and terrain modifications |
| DeployableRecorderComponent | Player-built structures and deployables |
| EnzymeGeyserRecorderComponent | Enzyme geyser state and health |
| CaveAIRecorderComponent | Cave creature spawns and behavior |
| CaveEntranceRecorderComponent | Cave entrance state and accessibility |
| IcarusContainerManagerRecorderComponent | Storage container inventories (SavedInventories) |
| IcarusQuestManagerRecorderComponent | Quest/mission progress and completion |
| PlayerRecorderComponent | Individual player position and state |
| PlayerStateRecorderComponent | Player health, resources, status effects |
| PlayerHistoryRecorderComponent | Player action history and death logs |
| GameModeStateRecorderComponent | Overall prospect/game-mode state and timers |
| WeatherForecastRecorderComponent | Weather forecast data |
| WeatherControllerRecorderComponent | Current weather state and transitions |
| WorldBossManagerRecorderComponent | World boss spawns and health |
| RocketRecorderComponent | Evacuation rocket state |
| DynamicRocketSpawnRecorderComponent | Dynamic rocket spawn points |
| BedRecorderComponent | Beds and respawn points |
| BuildingGridRecorderComponent | Building grid and placement snap points |
| MapManagerRecorderComponent | Map markers and discovery state |
| FLODRecorderComponent | Foliage LOD and rendering state |
| FLODTileRecorderComponent | Per-tile harvested foliage records |

**Note**: The list above captures ~23 types observed in one sample save. Other prospects may contain additional recorder types depending on prospect type and progression.

#### Common Nested Structural Keys

Inside the recursive BinaryData streams, you'll encounter:

- **Spatial data**: Vector, Transform, Quat, Rotation, Translation, Scale3D
- **Object tracking**: Instances, DynamicInstances, RecordIndex, DestroyedInstanceIndices
- **Inventories**: SavedInventories, Modifiers
- **Trait records**: EnergyTraitRecord, WaterTraitRecord, GeneratorTraitRecord, ResourceComponentRecord
- **State variables**: IntVariables, BoolVariables, NameVariables, TextVariables, LinearColorVariables
- **Component metadata**: bActive, Location, Radius, RecorderName, Value

### Editing Implications

To safely edit prospect world state, follow this round-trip workflow:

1. **Decompress**: Base64-decode `BinaryBlob` → zlib-inflate to get decompressed bytes
2. **Parse**: Read the decompressed bytes as a UE4 tagged-property stream (requires parsing the recursive BinaryData nesting)
3. **Modify**: Edit properties as needed (e.g., adjust inventory contents, teleport a player, remove a building)
4. **Re-serialize**: Write the modified property stream back to bytes (byte order matters; must match UE4's binary format exactly)
5. **Recompute hash**: Calculate SHA1 of the new decompressed bytes; update `Hash` field
6. **Recompress**: Compress the new bytes with zlib; update `TotalLength`/`UncompressedLength`
7. **Re-base64**: Base64-encode the compressed bytes; update `BinaryBlob`

Any error in re-serialization (wrong byte order, mismatched sizes, incorrect property tags) risks the game rejecting or corrupting the save file. The layout is deterministic and decodable, but not forgiving.

**Note**: No encryption is used. The data is compressible and structurally sound once decompressed.

## Worked Example: Decompression + Verification

Python snippet to decode, verify, and inspect the envelope:

```python
import base64
import zlib
import hashlib

blob_dict = {
    "Key": "actors",
    "Hash": "f5f8504262b8c5b6c5748263310f34ec8e033418",
    "TotalLength": 35187,
    "DataLength": 35187,
    "UncompressedLength": 856886,
    "BinaryBlob": "eJz..."  # truncated for brevity
}

# Step 1: Decode Base64
compressed_bytes = base64.b64decode(blob_dict["BinaryBlob"])
print(f"Compressed size: {len(compressed_bytes)} bytes (expected: {blob_dict['TotalLength']})")

# Step 2: Inflate zlib
decompressed_bytes = zlib.decompress(compressed_bytes)
print(f"Decompressed size: {len(decompressed_bytes)} bytes (expected: {blob_dict['UncompressedLength']})")

# Step 3: Verify hash
computed_hash = hashlib.sha1(decompressed_bytes).hexdigest()
print(f"Hash match: {computed_hash == blob_dict['Hash']} (computed: {computed_hash})")

# Step 4: Parse inner format (pseudocode)
# The decompressed bytes now contain a UE4 tagged-property stream starting with
# the root property "StateRecorderBlobs" : ArrayProperty<StateRecorderBlob>
```

Expected output for a valid blob:
```
Compressed size: 35187 bytes (expected: 35187)
Decompressed size: 856886 bytes (expected: 856886)
Hash match: True (computed: f5f8504262b8c5b6c5748263310f34ec8e033418)
```

## Multiplayer Linkage: AssociatedProspects_Slot_*.json

For multiplayer prospects, the player also stores metadata about co-op sessions and hosting.

### File Naming

- `AssociatedProspects_Slot_0.json` — Loadout slot 0 prospect metadata
- `AssociatedProspects_Slot_2.json` — Loadout slot 2 prospect metadata
- `AssociatedProspects_Slot_3.json` — Loadout slot 3 prospect metadata

(Slot 1 is typically absent or unused.)

### Structure

```json
{
  "AssociatedProspects_Slot_0.json": [
    "{\"AssociatedProspect\":{\"ProspectID\":\"Eden Oasis\",\"ClaimedAccountID\":\"<STEAMID64_2>\",\"ClaimedAccountCharacter\":2,\"ProspectDTKey\":\"OpenWorld_Elysium\",\"ProspectState\":\"Active\",\"AssociatedMembers\":[{\"AccountName\":\"Player4\",\"CharacterName\":\"Player4\",\"UserID\":\"<STEAMID64_2>\",\"ChrSlot\":2,\"Experience\":1400000,\"Status\":\"Prospect_Conifer\",\"Settled\":false,\"IsCurrentlyPlaying\":true},{\"AccountName\":\"Player1\",\"CharacterName\":\"Player1\",\"UserID\":\"<STEAMID64>\",\"ChrSlot\":0,\"Experience\":5060100,\"Status\":\"Prospect_Conifer\",\"Settled\":false,\"IsCurrentlyPlaying\":false}],\"Cost\":0,\"Reward\":0,\"Difficulty\":\"Medium\",\"Insurance\":false,\"NoRespawns\":false,\"ElapsedTime\":201146,\"SelectedDropPoint\":0,\"CustomSettings\":[]},\"HostedBy\":{\"LastHostType\":\"SteamP2P\",\"SteamP2PHostId\":\"<STEAMID64_2>\",\"DedicatedServerIP\":\"<STEAMID64_2>:17777\",\"CachedServerName\":\"Player4\"}}"
  ]
}
```

**Note**: Like Characters.json, this is a **double-encoded JSON structure**. The outer key is the filename, the value is an array of JSON strings, and each string must be decoded to get the actual object.

### AssociatedProspect Object

| Field | Type | Notes |
|-------|------|-------|
| `ProspectID` | string | Prospect name (e.g., "Eden Oasis") |
| `ClaimedAccountID` | string | Steam ID of the player who claimed/owns the prospect |
| `ClaimedAccountCharacter` | int | Character slot of the owner |
| `ProspectDTKey` | string | Data table key |
| `ProspectState` | string | "Active", "Completed", etc. |
| `AssociatedMembers` | array | Co-op players in this prospect |
| `Cost` | int | Entry cost (exotics, typically 0 for open worlds) |
| `Reward` | int | Completion reward |
| `Difficulty` | string | "Easy", "Medium", "Hard", "Insane", etc. |
| `Insurance` | bool | Whether loadout is insured |
| `NoRespawns` | bool | Hardcore mode (no respawns) |
| `ElapsedTime` | int | Time spent in prospect (seconds) |
| `SelectedDropPoint` | int | Drop zone index |
| `CustomSettings` | array | Difficulty modifiers (Arachnophobia, NoCreatures, etc.) |

### AssociatedMembers

Each co-op player in the prospect.

| Field | Type | Notes |
|-------|------|-------|
| `AccountName` | string | Player's Steam account name |
| `CharacterName` | string | Character's in-game name |
| `UserID` | string | Steam ID (64-bit) |
| `ChrSlot` | int | Character slot (0–3) |
| `Experience` | int | XP gained in this prospect |
| `Status` | string | Current status code (e.g., "Prospect_Conifer") |
| `Settled` | bool | Whether character has settled an outpost here |
| `IsCurrentlyPlaying` | bool | True if this player is currently in the prospect |

### HostedBy

Hosting information for the prospect.

| Field | Type | Notes |
|-------|------|-------|
| `LastHostType` | string | "LocalHost", "SteamP2P", or "DedicatedServer" |
| `SteamP2PHostId` | string | Steam ID of the hosting player (P2P only) |
| `DedicatedServerIP` | string | Server address (dedicated server only) |
| `CachedServerName` | string | Cached name of the host player or server |

For single-player prospects, `LastHostType` is `"LocalHost"` and other fields are empty.

For multiplayer, `LastHostType` is typically `"SteamP2P"` and `SteamP2PHostId` identifies the host.

## MapData/Terrain_*.fog

Binary fog-of-war masks. One file per terrain chunk, storing which areas of the map have been revealed to the player.

### Format

**Observed**: Binary file with a small header followed by bit-packed revelation state per terrain grid cell.

**Header pattern** (not fully reverse-engineered):
- May include chunk coordinates or size info
- Followed by byte array representing visibility (1 bit per cell typically)

**Usage**: Regenerate fog-of-war by reading these files and reconstructing the player's map knowledge.

**Note**: Full schema is incomplete. Treat as supplementary data for now.

## Backup Rotation

Prospect files follow the same backup rotation as account-tier files:

```
Prospects/The Garden.json          (current)
Prospects/The Garden.json.backup   (previous)
Prospects/The Garden.json.backup_1
...
Prospects/The Garden.json.backup_10 (oldest, then discarded)
```

## Worked Example: AssociatedProspects_Slot_0.json (Decoded String)

From `%LocalAppData%\Icarus\Saved\PlayerData\<STEAMID64>\AssociatedProspects_Slot_0.json`:

After decoding the outer JSON and the inner JSON string, the object looks like:

```json
{
  "AssociatedProspect": {
    "ProspectID": "Eden Oasis",
    "ClaimedAccountID": "<STEAMID64_2>",
    "ClaimedAccountCharacter": 2,
    "ProspectDTKey": "OpenWorld_Elysium",
    "ProspectState": "Active",
    "AssociatedMembers": [
      {
        "AccountName": "Player4",
        "CharacterName": "Player4",
        "UserID": "<STEAMID64_2>",
        "ChrSlot": 2,
        "Experience": 1400000,
        "Status": "Prospect_Conifer",
        "Settled": false,
        "IsCurrentlyPlaying": true
      },
      {
        "AccountName": "Player1",
        "CharacterName": "Player1",
        "UserID": "<STEAMID64>",
        "ChrSlot": 0,
        "Experience": 5060100,
        "Status": "Prospect_Conifer",
        "Settled": false,
        "IsCurrentlyPlaying": false
      }
    ],
    "Cost": 0,
    "Reward": 0,
    "Difficulty": "Medium",
    "Insurance": false,
    "NoRespawns": false,
    "ElapsedTime": 201146,
    "SelectedDropPoint": 0,
    "CustomSettings": []
  },
  "HostedBy": {
    "LastHostType": "SteamP2P",
    "SteamP2PHostId": "<STEAMID64_2>",
    "DedicatedServerIP": "<STEAMID64_2>:17777",
    "CachedServerName": "Player4"
  }
}
```

**Interpretation**:
- **ProspectID**: "Eden Oasis" (named world)
- **Owner**: Player `<STEAMID64_2>` (Player4), character slot 2
- **Co-op Members**: Player4 + Player1, 2 players
- **Player4**: Currently playing (IsCurrentlyPlaying: true), 1.4M XP earned
- **Player1**: Offline (IsCurrentlyPlaying: false), 5.06M XP earned
- **ElapsedTime**: ~55 hours in this prospect (201146 seconds)
- **Hosting**: Steam P2P, hosted by Player4 (`<STEAMID64_2>`)

This indicates an active co-op session with Player4 as host and Player1 as guest.
