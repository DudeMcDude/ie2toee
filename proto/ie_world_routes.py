"""Read the named arrival entrances for two-way travel from the player's world map."""
import struct

SHAENGARNE = ('AR2000', 'AR2001', 'AR2002', 'AR2100', 'AR2101', 'AR2102')
FORTRESS = ('AR3000', 'AR3001', 'AR3002', 'AR3100', 'AR3101')


def add_world_routes(data, game):
    prefix = 'I2' if 'I2AR1000' in data else ''
    if prefix:
        first, second, gate = 'AR1200', 'AR2000', 'AR2000_Revealed'
    else:
        first, second, gate = 'AR2000', 'AR2100', None
    if any(prefix + name not in data for name in (first, second)):
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

    routes = [(first, second, gate), (second, first, None)]
    if prefix and prefix + 'AR3000' in data:
        routes.extend([(first, 'AR3000', 'AR3000_Revealed'), ('AR3000', first, None)])
    for index, (src, dst, required) in enumerate(routes):
        (src_entry, _), (dst_entry, hours) = arrival(dst, src), arrival(src, dst)
        source, target = data[prefix + src], data[prefix + dst]
        anchor = source['entrances'][src_entry][:2]
        if dst_entry not in target['entrances']:
            raise ValueError('%s has no world map entrance %s' % (dst, dst_entry))
        source['regions'].append(dict(name='WorldMapTo' + dst, anchor=anchor, poly=[],
                                      dest_area=prefix + dst, dest_entrance=dst_entry,
                                      dest_map=target['map'], world_jump=1800 + index,
                                      world_icon=exits.setdefault((src, src_entry), 1800 + index), travel_hours=hours,
                                      requires_global=required))
