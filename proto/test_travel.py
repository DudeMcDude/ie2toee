#!/usr/bin/env python3
"""Offline test of the Easthaven travel code: ie2toee.arrival_tile, ie_exits.collect and runtime/ie_travel.py against a
mock Temple+ game (no IE data, no game needed):   python3 test_travel.py"""
import json, os, sys, tempfile, types
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, 'runtime')]

# ---- mock Temple+ ---------------------------------------------------------------------------------------------
def location_from_axis(x, y): return x | (y << 32)
def location_to_axis(l): return l & 0xFFFFFFFF, l >> 32

class Obj(object):
    def __init__(self, name, x, y, mp):
        self.name, self.location, self.map, self.off_x, self.off_y = name, location_from_axis(x, y), mp, 0.0, 0.0
        self.floats = []
    def float_text_line(self, s, c=0): self.floats.append(s)

class Game(object):
    def __init__(self): self.party, self.events, self.teleports = [], [], []
    @property
    def leader(self): return self.party[0]
    def timeevent_add(self, fn, args, ms, real=0): self.events.append((fn, args))
    def fade_and_teleport(self, t, tb, mv, mp, x, y):
        self.teleports.append((mp, x, y))
        for i, o in enumerate(self.party):          # the engine spreads the party around the target; same map for all
            o.map, o.location = mp, location_from_axis(x + i % 2, y + i // 2)
game = Game()
toee = types.ModuleType('toee'); toee.game = game
toee.location_from_axis, toee.location_to_axis = location_from_axis, location_to_axis
sys.modules['toee'] = toee
clock = [1000.0]
class Time(object):
    @staticmethod
    def time(): return clock[0]

# ---- test data: exterior 5900 with exits to interior 5901 and to an unconverted area ---------------------------
data = types.ModuleType('ie_travel_data')
data.AREAS = {
 'AR1000': dict(map=5900, entrances={'FR1001': [100, 100, 0]}, regions=[
    dict(name='To1001', poly=[[110, 90], [114, 90], [114, 94], [110, 94]], dest_area='AR1001', dest_entrance='FR1000', dest_map=5901),
    dict(name='To1003', poly=[[300, 300], [302, 300], [302, 302], [300, 302]], anchor=[305, 300], dest_area='AR1001', dest_entrance='FR1000', dest_map=5901),
    dict(name='To1200', poly=[[50, 50], [54, 50]], dest_area='AR1200', dest_entrance='FR1000', dest_map=0)]),
 'AR1001': dict(map=5901, entrances={'FR1000': [200, 200, 0]}, regions=[
    dict(name='To1000', poly=[[200, 205], [204, 205], [204, 207], [200, 207]], dest_area='AR1000', dest_entrance='FR1001', dest_map=5900)])}
data.BY_MAP = dict((a['map'], n) for n, a in data.AREAS.items())
sys.modules['ie_travel_data'] = data
attached = []
doors = types.ModuleType('ie_doors'); doors.start = lambda area: attached.append(area) or 2
sys.modules['ie_doors'] = doors
sys.modules['ie_doors_ar1001'] = types.ModuleType('ie_doors_ar1001')
sys.modules['ie_bake_ar1000'] = types.ModuleType('ie_bake_ar1000')   # exterior is baked, interior is not

import ie_travel as T
T.time = Time
T.LOG[0] = None
T._log = lambda s: None

fails = []
def check(name, cond):
    print(('PASS ' if cond else 'FAIL ') + name)
    if not cond: fails.append(name)

def run_events(n=1):
    for _ in range(n):
        clock[0] += 0.25
        ev, game.events = game.events, []
        for fn, args in ev: fn(*args)

def put_party(mp, x, y):
    for i, o in enumerate(game.party): o.map, o.location = mp, location_from_axis(x + i, y)

# 1. geometry
sq = [[0, 0], [4, 0], [4, 4], [0, 4]]
check('inside polygon', T.near_region(2, 2, sq))
check('within 0.8 of polygon edge', T.near_region(4.7, 2, sq) and not T.near_region(4.9, 2, sq))
check('2-point region is a segment', T.near_region(52, 50.5, [[50, 50], [54, 50]]) and not T.near_region(52, 52, [[50, 50], [54, 50]]))

# 2. polling never moves the party (exit icons do the travel now), interiors still get their doors on arrival
game.party[:] = [Obj('pc%d' % i, 0, 0, 5900) for i in range(3)]
put_party(5900, 112, 92)
check('start() starts one poll', T.start() == 1 and len(game.events) == 1)
check('start() twice does not double-start', T.start() == 0 and len(game.events) == 1)
run_events(3); put_party(5900, 100, 100); run_events(2); put_party(5900, 111, 92); run_events(3)
put_party(5900, 305, 300); run_events(2); put_party(5900, 52, 50); run_events(2)
check('standing in / next to travel regions never teleports', not game.teleports and not game.leader.floats)
put_party(5901, 201, 206); run_events(2)
check('doors attached on arrival in the unbaked interior', attached == ['AR1001'])

# 3. exit icons (ie_exiticons): icon tile inside the polygon, jump point = destination arrival tile
import ie_exiticons as X
check('icon at the centroid when it is inside', X.icon_tile([[0, 0], [4, 0], [4, 4], [0, 4]]) == (2, 2))
L = [[0, 0], [6, 0], [6, 1], [1, 1], [1, 6], [0, 6]]          # L shape: centroid outside
u, v = X.icon_tile(L)
check('icon falls back to the nearest inside tile', X.inside(u + .5, v + .5, L))
ar = {'AR1000': dict(map=5900, entrances={'FR1001': [100, 100, 0]}, regions=[dict(name='To1001', poly=[[0, 0], [4, 0], [4, 4], [0, 4]], dest_area='AR1001', dest_entrance='FR1000', dest_map=5901),
                                                                                dict(name='To9', poly=[[0, 0], [1, 1]], dest_area='AR1200', dest_entrance='X', dest_map=0)]),
      'AR1001': dict(map=5901, entrances={'FR1000': [200, 200, 0]}, regions=[dict(name='To1000', poly=[[0, 0], [2, 0], [2, 2], [0, 2]], dest_area='AR1000', dest_entrance='FR1001', dest_map=5900)])}
icons, rows, skipped = X.build(ar)
check('jump points go to the destination arrival tiles, stable ids', rows == [(2000, 'AR1000-To1001-to-AR1001', 5901, 200, 200), (2001, 'AR1001-To1000-to-AR1000', 5900, 100, 100)])
ar['AR1001']['regions'][0]['anchor'] = [5, 6]
check('icon on the anchor tile when the region has one', X.build(ar)[0]['AR1001'] == [(5, 6, 2001)])
check('unconverted exit gets no icon', icons['AR1000'] == [(2, 2, 2000)] and len(skipped) == 1)

# 4. save/load: restored poll adopts a fresh module state; a stale second poll stops
game.events[:] = []
T._last_poll = 0.0; T._gen = 0; T._armed = True; T._map = 5900; T._noted.clear()
put_party(5900, 112, 92)                          # loaded right in a region
game.events.append((T.poll, (7,)))                # the event restored from the save (gen 7)
run_events(3)
check('restored poll adopted (gen 7), no travel', T._gen == 7 and not game.teleports)
n0 = len(game.events)
T.start()
check('start() after adopt does not add a second poll', len(game.events) == n0)
game.events.append((T.poll, (3,)))                # an older generation poll next to the live one
run_events(2)
check('stale-generation poll stops', len(game.events) == 1)

# 5. ie_exits.collect
import ie_exits
d = tempfile.mkdtemp()
def objs(entr, regs):
    return dict(entrances=[dict(name=n, toee=[x + .5, y + .5], arrival=[x, y], orient=o) for n, x, y, o in entr],
                regions=[dict(name=n, type=t, poly=[[1, 1], [2, 2]], dest_area=a, dest_entrance=e) for n, t, a, e in regs])
json.dump(objs([('FR1001', 5, 6, 2)], [('To1001', 'travel', 'AR1001', 'FR1000'), ('To9', 'travel', 'AR1200', 'FR1000'), ('i', 'info', '', '')]),
          open(os.path.join(d, 'AR1000_objects.json'), 'w'))
json.dump(objs([('FR1000', 7, 8, 0)], [('To1000', 'travel', 'AR1000', 'FR1001')]), open(os.path.join(d, 'AR1001_objects.json'), 'w'))
got, problems = ie_exits.collect(d, {'AR1000': 5900, 'AR1001': 5901})
check('ie_exits: regions + entrances collected, info regions skipped', len(got['AR1000']['regions']) == 2 and got['AR1001']['entrances']['FR1000'] == [7, 8, 0])
check('ie_exits: reports the unconverted destination, flags dest_map 0',
      problems == ['AR1000 To9 -> AR1200: destination area not converted'] and got['AR1000']['regions'][1]['dest_map'] == 0 and got['AR1000']['regions'][0]['dest_map'] == 5901)
out = os.path.join(d, 'ie_travel_data.py'); ie_exits.write(got, out)
ns = {}; exec(open(out).read(), ns)
check('ie_exits: written module imports', ns['BY_MAP'] == {5900: 'AR1000', 5901: 'AR1001'})

import ie2toee
# 5b. region_anchors
kk = np.ones((10, 10, 3, 3), np.int8); kk[0:6, 0:3] = 0      # walkable strip, tiles u 0..5, v 0..2 (bbox origin 0,0)
regs = [dict(type='travel', poly=[[8, 1], [9, 1], [9, 2], [8, 2]]), dict(type='travel', poly=[[5.2, 1.5], [5.8, 1.5]]), dict(type='info', poly=[[8, 1], [9, 1]])]
an = ie2toee.region_anchors(kk, (0, 10, 0, 10), regs, (0, 0))
check('anchors: far region gets the nearest walkable tile, near region and info region none', an == {0: [5, 1]})
check('anchors: unreachable start -> none', ie2toee.region_anchors(kk, (0, 10, 0, 10), regs, (9, 9)) == {})

# 6. ie2toee.arrival_tile
import ie2toee
kind = np.ones((12, 12, 3, 3), np.int8); kind[8, 8] = 0; kind[3, 3] = 0           # bbox origin (100, 200): walkable tiles (108,208), (103,203)
bbox = (100, 112, 200, 212)
check('arrival: walkable entrance stays', ie2toee.arrival_tile(kind, bbox, 108.5, 208.5) == (108, 208, False))
check('arrival: blocked entrance moves to the nearest walkable tile within 5', ie2toee.arrival_tile(kind, bbox, 105.5, 205.5) == (103, 203, True) or
      ie2toee.arrival_tile(kind, bbox, 105.5, 205.5) == (108, 208, True))
check('arrival: nothing within 5 tiles -> unchanged, moved=None', ie2toee.arrival_tile(kind, bbox, 111.5, 200.5)[2] is None)
check('arrival: nearer one wins', ie2toee.arrival_tile(kind, bbox, 104.5, 204.5) == (103, 203, True))

print('\n%d failed' % len(fails) if fails else '\nall passed')
sys.exit(1 if fails else 0)
