"""Export the original regional travel charts for destinations in this conversion."""
import os
import pprint
import runpy
import struct

from PIL import Image, ImageEnhance
from iefs import IEGame
from iegui import Bam, decode_mos, pvrz_loader_for
from iescript import Tlk, find_tlk


def build(ie, travel_file, module, scripts):
    areas = runpy.run_path(travel_file)['AREAS']
    hubs = {area for area, data in areas.items() if any(r.get('world_jump') for r in data['regions'])}
    game = IEGame(ie)
    tlk = Tlk.load(find_tlk(ie))
    buf = game.read('worldmap', 'wmp')
    pages, header = struct.unpack_from('<II', buf, 8)
    folder = os.path.join(module, 'art', 'interface', 'ie2toee', 'atlas')
    os.makedirs(folder, exist_ok=True)
    locations, sizes = {}, {}
    load = pvrz_loader_for(game)
    for page in range(pages):
        h = header + 184 * page
        count, entries = struct.unpack_from('<II', buf, h + 32)
        def ref(pos):
            return buf[pos:pos + 8].split(b'\0')[0].decode('ascii').upper()
        points = []
        for i in range(count):
            pos = entries + i * 240
            area = ('I2' if 'I2AR1000' in areas else '') + ref(pos)
            if area in hubs and area not in locations:
                cycle, x, y, label = struct.unpack_from('<IIIi', buf, pos + 52)
                points.append((area, cycle, x, y, tlk.get(label) or area))
        if not points:
            continue
        chart = Image.fromarray(decode_mos(game.read(ref(h), 'mos'), load))
        icons = Bam(game.read(ref(h + 48), 'bam'), load)
        # Frame the converted region on tall maps while preserving the source pixel coordinates.
        left = max(0, min(p[2] for p in points) - 160)
        top = max(0, min(p[3] for p in points) - 145)
        right = min(chart.width, max(p[2] for p in points) + 210)
        bottom = min(chart.height, max(p[3] for p in points) + 185)
        chart = chart.crop((left, top, right, bottom))
        sizes[page] = chart.size
        chart.convert('RGB').save(os.path.join(folder, 'chart%d.tga' % page))
        for area, cycle, x, y, name in points:
            frame = icons.cycles[cycle][0]
            icon = Image.fromarray(icons.frames[frame])
            cx, cy = icons.centres[frame]
            icon.save(os.path.join(folder, area + '.tga'))
            ImageEnhance.Brightness(icon).enhance(1.45).save(os.path.join(folder, area + '_hover.tga'))
            locations[area] = (page, name, x - left - cx, y - top - cy, icon.width, icon.height)
    if hubs - set(locations):
        raise ValueError('World map lacks converted hubs %r' % sorted(hubs - set(locations)))
    with open(os.path.join(scripts, 'ie_atlas_data.py'), 'w', encoding='utf8') as out:
        out.write('# -*- coding: utf-8 -*-\nSIZES = %r\nLOCATIONS = %s\n' % (sizes, pprint.pformat(locations)))
