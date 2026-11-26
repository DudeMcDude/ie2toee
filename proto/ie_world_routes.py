"""Read the named arrival entrances for two-way travel from the player's world map."""
import struct


def add_world_routes(data, game):
    prefix = 'I2' if 'I2AR1000' in data else ''
    if prefix:
        routes = [('AR1200', 'AR2000', 'AR2000_Revealed', 1800)]
    else:
        routes = [('AR2000', 'AR2100', None, 1800), ('AR2100', 'AR3000', 'Vale_Quest', 1802),
                  ('AR2100', 'AR3600', '#ar3600_reveal', 1804),
                  ('AR2100', 'AR4000', '#ar4000_reveal', 1806)]
    routes = [r for r in routes if prefix + r[0] in data and prefix + r[1] in data]
    if not routes:
        return
    buf = game.read('worldmap', 'wmp')
    header, = struct.unpack_from('<I', buf, 12)
    count, areas, links = struct.unpack_from('<III', buf, header + 32)

    def resref(offset, length):
        return buf[offset:offset + length].split(b'\0')[0].decode('ascii').upper()

    names = [resref(areas + i * 240, 8) for i in range(count)]
    exits = {}

    def arrival(src, dst):
        offset = areas + names.index(src) * 240 + 80
        for direction in range(4):
            start, size = struct.unpack_from('<II', buf, offset + direction * 8)
            for i in range(start, start + size):
                pos = links + i * 216
                target, = struct.unpack_from('<I', buf, pos)
                if names[target] == dst:
                    return resref(pos + 4, 32), 4 * struct.unpack_from('<I', buf, pos + 36)[0]
        raise ValueError('Missing world map link from %s to %s' % (src, dst))

    def connect(src, dst, gate, jump):
        (src_entry, _), (dst_entry, hours) = arrival(dst, src), arrival(src, dst)
        source, target = data[prefix + src], data[prefix + dst]
        anchor = source['entrances'][src_entry][:2]
        if dst_entry not in target['entrances']:
            raise ValueError('%s has no world map entrance %s' % (dst, dst_entry))
        source['regions'].append(dict(name='WorldMapTo' + dst, anchor=anchor, poly=[],
                                      dest_area=prefix + dst, dest_entrance=dst_entry,
                                      dest_map=target['map'], world_jump=jump,
                                      world_icon=exits.setdefault((src, src_entry), jump), travel_hours=hours, requires_global=gate))

    for first, second, gate, jump in routes:
        connect(first, second, gate, jump)
        connect(second, first, None, jump + 1)
