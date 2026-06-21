# Character Tier: Characters.json and Loadouts

## Scope & Location

Character-tier data is per-character progression. Each character has XP, cosmetics (head shape, hair color, body color, tattoos, scars), learned talents, status (alive, dead, abandoned), and equipment loadout configuration.

**Location**: `%LocalAppData%\Icarus\Saved\PlayerData\<SteamID64>\Characters.json`

**Related file**: `Loadout/Loadouts.json` — equipment configurations per loadout slot

## Characters.json: The Double-Encoding Trap

### Critical Gotcha

Characters.json contains an **array of JSON strings**, not an array of objects. Each character is a string that must be decoded *twice*.

**Why this matters**: When reading, you must:
1. Decode the outer JSON to get the array of strings
2. Decode each string to get the actual character object

When writing, you must:
1. Encode each character object to a JSON string
2. Encode the array of strings as JSON
3. Write with SystemEncoding (not UTF-8; the editor uses `const SystemEncoding()`)

Failure to re-encode properly will corrupt the file or lose character data.

### File Structure

```json
{
  "Characters.json": [
    "{\"CharacterName\":\"LUGHIR\",\"XP\":5060100,\"XP_Debt\":0,\"IsDead\":false,\"IsAbandoned\":false,...}",
    "{\"CharacterName\":\"LYTHIA\",\"XP\":600000,\"XP_Debt\":0,\"IsDead\":false,\"IsAbandoned\":false,...}",
    "{\"CharacterName\":\"CYNTHIA\",\"XP\":5017656,\"XP_Debt\":0,\"IsDead\":false,\"IsAbandoned\":false,...}",
    null
  ]
}
```

The outer key is literally `"Characters.json"` (the filename as a string key). The value is an array of strings. Empty slots are `null`.

### Decoding Example (Dart)

From icarus_save.dart (line 39–46):

```dart
var charactersContent = await _charactersFile.readAsString(encoding: _encoding);
var rawCharacters = json.decode(charactersContent)[_charactersKey];  // _charactersKey = "Characters.json"
for (var rawCharacter in rawCharacters) {
  var decoded = json.decode(rawCharacter);  // Second decode: string -> object
  characters.add(IcarusCharacter(character: decoded, save: this));
}
```

**First decode**: Outer JSON → gets the "Characters.json" array of strings  
**Second decode**: Each string → character object

### Encoding Example (Dart)

From icarus_save.dart (line 65–73):

```dart
Future _saveCharacters() async {
  var content = {
    'Characters.json': [
      for (var character in characters) character.serialize()  // Re-encode each to JSON string
    ]
  };

  await _charactersFile.writeAsString(json.encode(content), encoding: _encoding);
}
```

**Step 1**: `character.serialize()` returns each character as a JSON string  
**Step 2**: Create a map with key "Characters.json" and the array of strings  
**Step 3**: `json.encode(content)` encodes the outer map and array  
**Step 4**: Write with `SystemEncoding` (not UTF-8)

### SystemEncoding vs UTF-8

The editor uses `const SystemEncoding()` instead of UTF-8. On Windows, this defaults to the system code page (often CP-1252). On macOS/Linux, it's UTF-8. Always use SystemEncoding to match the game's behavior.

## Per-Character Fields

Once decoded, each character object has these fields:

```json
{
  "CharacterName": "LUGHIR",
  "XP": 5060100,
  "XP_Debt": 0,
  "IsDead": false,
  "IsAbandoned": false
}
```

### Common Fields

| Field | Type | Notes |
|-------|------|-------|
| `CharacterName` | string | Display name (max length varies, typically 20–32 chars) |
| `XP` | int | Experience points toward next level |
| `XP_Debt` | int | Penalty XP; subtracted when respawning after death |
| `IsDead` | bool | Whether character is currently dead |
| `IsAbandoned` | bool | Whether character was abandoned (permanent state) |

Additional fields may be present depending on schema version. The editor (icarus_character.dart) only surfaces the above; others are preserved as-is in the raw map.

### Cosmetics (Not Yet Parsed)

The full character schema includes cosmetic fields (head, hair color, body color, tattoos, scars, etc.), but the editor does not currently expose these for editing. They exist in the raw character object and are preserved when serializing.

### Learned Talents

Characters may have a `LearnedTalents` array (not shown in the basic editor UI). This tracks which account talents the character has invested skill points into.

### Location & Last Prospect

Characters retain references to their last known location and prospect. These fields are not typically edited and are managed by the game engine.

## Loadout/Loadouts.json

Equipment loadout configurations, stored separately from character state. Each loadout is associated with a character slot and a prospect.

### Structure

```json
{
  "Loadouts": [
    {
      "EnviroSuit": {
        "ItemStaticData": {"RowName": "Envirosuit_Tier6", "DataTableName": "D_ItemsStatic"},
        "ItemDynamicData": [{"PropertyType": "ItemableStack", "Value": 1}],
        "ItemCustomStats": [],
        "CustomProperties": {...},
        "DatabaseGUID": "6CC7E5A848BE5694DF761EA2BDD5C8DB",
        "ItemOwnerLookupId": -1,
        "RuntimeTags": {"GameplayTags": []}
      },
      "Dropship": {
        "Name": "",
        "Type": "DropshipType_UndefinedID",
        "DropshipID": 0,
        "InUse": false,
        "TOP_Part": {"ItemStaticRow": "", "Properties": [], "Stats": [], "ID": ""},
        "MID_Part": {"ItemStaticRow": "", "Properties": [], "Stats": [], "ID": ""},
        "BTM_Part": {"ItemStaticRow": "", "Properties": [], "Stats": [], "ID": ""}
      },
      "MetaItems": [
        {
          "ItemStaticData": {"RowName": "Meta_Backpack_Larkwell_Beta", "DataTableName": "D_ItemsStatic"},
          "ItemDynamicData": [
            {"PropertyType": "ItemableStack", "Value": 1},
            {"PropertyType": "Durability", "Value": 5500}
          ],
          "ItemCustomStats": [],
          "CustomProperties": {...},
          "DatabaseGUID": "2C1BAD30463FA230E1D831990092C65E",
          "ItemOwnerLookupId": -1,
          "RuntimeTags": {"GameplayTags": []}
        }
      ],
      "AssociatedProspect": {
        "ProspectID": "Welcome to Hell",
        "ClaimedAccountID": "76561198009434211",
        "ClaimedAccountCharacter": 2,
        "ProspectDTKey": "OpenWorld_Prometheus",
        "ProspectState": "Active",
        "AssociatedMembers": [
          {
            "AccountName": "LYTHIA",
            "CharacterName": "LYTHIA",
            "UserID": "76561198009434211",
            "ChrSlot": 2,
            "Experience": 600000,
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
        "ElapsedTime": 0,
        "SelectedDropPoint": 0,
        "CustomSettings": []
      },
      "HostedBy": {
        "LastHostType": "LocalHost",
        "SteamP2PHostId": "",
        "DedicatedServerIP": "",
        "CachedServerName": ""
      },
      "bInsured": false,
      "bSettled": false,
      "LoadoutClaimTime": 1756586308,
      "ChrSlot": 2,
      "Guid": "72E5CF054B18FDF72B421798131412DF"
    }
  ]
}
```

### Loadout Object Fields

| Field | Type | Notes |
|-------|------|-------|
| `EnviroSuit` | object | Current envirosuit (item structure) |
| `Dropship` | object | Drop pod configuration (usually empty) |
| `MetaItems` | array | Equipment items brought into prospect (backpacks, tools, armor) |
| `AssociatedProspect` | object | Prospect this loadout is used in; contains multiplayer metadata |
| `HostedBy` | object | Steam P2P or dedicated server hosting info |
| `bInsured` | bool | Whether loadout is insured (cost refund on death) |
| `bSettled` | bool | Whether character has settled an outpost here |
| `LoadoutClaimTime` | int | Unix timestamp when loadout was claimed |
| `ChrSlot` | int | Character slot (0–3) |
| `Guid` | string | Unique loadout ID |

### MetaItems

Items brought into the prospect. Each is a standard item object with `ItemStaticData`, `ItemDynamicData`, `DatabaseGUID`, etc. (same structure as MetaInventory.json).

### AssociatedProspect

Metadata about the prospect this loadout is for. Includes:
- Prospect ID and state (Active, Completed, etc.)
- Claim history (who claimed it, when)
- Multiplayer members (if co-op)
- Custom difficulty settings (Arachnophobia, PrebuiltCleanup, etc.)

For single-player outposts, `HostedBy.LastHostType` is `"LocalHost"`. For multiplayer, it's `"SteamP2P"` and includes the host's Steam ID.

## Editing Hazards

### Re-Serialization Rules

When editing character data in code:

1. **Preserve the outer structure**: The "Characters.json" key must remain
2. **Keep empty slots as `null`**: Don't remove or replace with empty strings
3. **Re-encode strings**: After modifying a character, call `.serialize()` (JSON-encode the object)
4. **Use SystemEncoding**: Write with `SystemEncoding`, not UTF-8
5. **Null slots stay null**: If a character is deleted, set the slot to `null` and re-encode the whole array

### Corruption Prevention

A common mistake is editing the character object without re-serializing:

**Wrong**:
```dart
characters[0]['CharacterName'] = 'NewName';
// Characters.json now contains an object, not a string!
```

**Right**:
```dart
characters[0].character['CharacterName'] = 'NewName';
// Behind the scenes, IcarusCharacter.serialize() is called on write
```

The editor wraps raw character maps in an `IcarusCharacter` class to enforce this contract. If you edit the raw map, you must manually re-JSON-encode it.

### Character Slot Limits

`NextChrSlot` in Profile.json indicates the next available slot. Slots 0–3 are the game's character limit. Don't create slot 4 or higher; the game won't read them.

## Worked Example: Decoded Character

From the raw Characters.json string (after two decodes):

```json
{
  "CharacterName": "LUGHIR",
  "XP": 5060100,
  "XP_Debt": 0,
  "IsDead": false,
  "IsAbandoned": false
}
```

**Interpretation**:
- **CharacterName**: "LUGHIR" (the player's avatar name)
- **XP**: 5,060,100 experience points (high-level character)
- **XP_Debt**: 0 (no death penalty active)
- **IsDead**: false (character is alive)
- **IsAbandoned**: false (character hasn't been permanently deleted)

When editing this character's XP, the editor:
1. Reads Characters.json, decodes twice, gets this object
2. Modifies `XP` value
3. Encodes the object back to JSON string
4. Wraps it in the "Characters.json" array structure
5. Encodes the outer map to JSON
6. Writes to disk with SystemEncoding

If any step is skipped or wrong, the file becomes unreadable by the game.
