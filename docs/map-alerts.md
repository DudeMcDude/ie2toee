# Map ally alert distances

`proto/guidance/map_alerts.json` maps game names and IE area names to maximum
ally-alert radii in ToEE tiles. The preview builder resolves the actual converted
map ID and adds `AlertDistance: <tiles>` to that map's `rules/MapList.mes` entry.
Unlisted maps and modules keep the engine defaults. No stock ToEE map is changed.

The IWD setting is `AR1201: 12` (Orc Cave). IWD2 uses 18 for `AR1000` (Targos
docks), `AR1100` (town) and `AR1200` (palisade). Interiors keep engine defaults.
Add further areas to the appropriate game
object as needed. Integers from 0 to 1000 are accepted; zero suppresses ally
alerts but not independent enemy detection or scripted hostility.

Requires a Temple+ build with per-map `AlertDistance` support. Older executables
ignore the key. Restart after changing MapList. The cap covers both provoked
hostility and enemy-turn ally recruitment. It does not create isolated encounter
groups: nearby orcs can still relay alerts across subsequent turns.

The installed IWD2 converter explicitly selects the `IWD2` guidance key even
though it installs into the ToEE module. Its integration patch is saved beside
the other IWD2 preview patches as `iwd2-map-alerts.patch`.
