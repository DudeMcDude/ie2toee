"""Map-local loot presentation. Container GUIDs still identify their original inventories in saves."""
import json
from pathlib import Path


def container_art(container, area):
    items = container.get('items') or []
    kind = container.get('type')
    poly = container.get('poly') or []
    # One point-sized spear on the docks is tagged as a bag in the ARE.
    spear_pile = area == 'I2AR1000' and container['name'] == 'Soldier Spear' and not poly and kind == 1
    if ((kind == 4 or spear_pile) and len(items) <= 2 and container.get('toee')
            and not any(container.get(k) for k in ('locked', 'key', 'trapped', 'script', 'flags'))):
        return {'pile': container['toee']}
    if kind != 4 and len({tuple(p) for p in poly}) >= 3:
        return {'poly': poly}
    return None


def write_container_art(map_dir, containers, guid):
    path = Path(map_dir)
    entries = {}
    for index, c in enumerate(containers):
        art = container_art(c, path.name.upper())
        if art:
            entries[guid(index, c['name'])] = art
    metadata = path / 'container_art.json'
    if entries:
        metadata.write_text(json.dumps(entries, separators=(',', ':')), encoding='ascii')
    elif metadata.exists():
        metadata.unlink()
