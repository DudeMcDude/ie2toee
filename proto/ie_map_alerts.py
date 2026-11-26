"""Apply opt-in Temple+ ally alert caps using IE area names, not fixed map IDs."""
import re


def apply_map_alert_distances(maplist, area_ids, distances):
    for area, distance in distances.items():
        if type(distance) is not int or not 0 <= distance <= 1000:
            raise ValueError('invalid alert distance for %s: %r' % (area, distance))
        if area not in area_ids:
            continue  # this area was not included in the conversion
        pattern = r'(^\{%d\}\{)([^}\r\n]*)(\})' % area_ids[area]

        def update(match):
            fields = re.sub(r',\s*AlertDistance\s*:[^,}]*', '', match.group(2))
            return '%s%s, AlertDistance: %d%s' % (match.group(1), fields, distance, match.group(3))

        maplist, count = re.subn(pattern, update, maplist, flags=re.M)
        if count != 1:
            raise ValueError('expected one MapList entry for %s (map %d), found %d' %
                             (area, area_ids[area], count))
    return maplist
