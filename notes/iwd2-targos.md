# IWD2 first experiment: AR1000 (Targos docks)

- Source: player's own GOG installer (v2.01_fixes), extracted with innoextract to a local dir outside the repo.
- `ie2toee.py --game <iwd2> --area AR1000 --map-id 5950 --ground-id 950 --guidance guidance/iwd2.example.json --preview`
  converted with no code changes: 25 sectors, 35462 walkable subtiles, 182 wall polygons -> clipping, 6 doors with
  patches, 32 path nodes, start tile (489,425). Objects: 7 entrances, 56 actors, 25 containers, 17 regions, 9 anims.
- Map ids 5950+ / ground 950+ reserved for IWD2 (IWD uses 5900-5918).
- Not done yet: creature/item bake (CRE V2.2 untested), exit icons, in-game load test in a separate overlay.
