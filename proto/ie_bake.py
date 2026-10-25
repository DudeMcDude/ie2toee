"""Bake converted IE area objects into ToEE map files (docs/mapfiles.md, "Baking").

Instead of spawning the converted creatures, items and doors from Python at run time (dynamic objects, stored in
full in every save and re-created by the probe on each load), the converter writes them the way vanilla maps ship
their objects:
  * creatures, their items, containers and their contents -> one prefab .mob per object (permanent GUID, loaded
    from the map directory on every visit; saves only store differences),
  * doors -> portal objects appended to the .sec sector object lists (static objects, null id).
GUIDs are uuid5 of flavour / area / object key, so a re-bake keeps the same ids and existing saves stay valid.
The few things a .mob cannot express offline are finalized once in game by runtime/ie_bakert.py.

  ie_bake.py bake --area AR1000 --specs out/cre/ie_creatures_ar1000.py --items out/items/ie_itemmap.py \
      --doors out/ie_doors_ar1000.py --maps out/maps/AR1000 --map-id 5900 --placement 6528,7648 \
      --toee <ToEE> --ie <IE install> --out out/bake/IWD --flavour IWD

The runtime spawner (runtime/ie_critters.spawn_area + ie_doors.start) stays the fallback: install the plain
out/maps sectors and no .mob files (proto/ie_bake.py install --mode runtime prints the layout).
"""
import argparse, json, math, os, shutil, struct, sys, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toeemob as T

NS = uuid.UUID('6f1c1d1e-2b9a-5e2e-8a6f-1e2b70ee0000')     # ie2toee bake namespace (uuid5 seeds)

# engine enums (Temple+ temple_enums.h / OpenTemple GameObjects/*Flag.cs)
OF = {n: 1 << i for i, n in enumerate(
    'DESTROYED OFF FLAT TEXT SEE_THROUGH SHOOT_THROUGH TRANSLUCENT SHRUNK DONTDRAW INVISIBLE NO_BLOCK CLICK_THROUGH '
    'INVENTORY DYNAMIC PROVIDES_COVER RANDOM_SIZE NOHEIGHT WADING UNUSED_40000 STONED DONTLIGHT TEXT_FLOATER '
    'INVULNERABLE EXTINCT TRAP_PC TRAP_SPOTTED DISALLOW_WADING UNUSED_08000000 HEIGHT_SET ANIMATED_DEAD TELEPORTED '
    'RADIUS_SET'.split())}
OIF = {n: 1 << i for i, n in enumerate(
    'IDENTIFIED WONT_SELL IS_MAGICAL NO_PICKPOCKET NO_DISPLAY NO_DROP NEEDS_SPELL CAN_USE_BOX NEEDS_TARGET LIGHT_SMALL '
    'LIGHT_MEDIUM LIGHT_LARGE LIGHT_XLARGE PERSISTENT MT_TRIGGERED STOLEN USE_IS_THROW NO_DECAY UBER NO_NPC_PICKUP '
    'NO_RANGED_USE VALID_AI_ACTION DRAW_WHEN_PARENTED EXPIRES_AFTER_USE NO_LOOT USES_WAND_ANIM NO_TRANSFER '
    'NO_TRANSFER_SPECIAL'.split())}
ONF = {n: 1 << i for i, n in enumerate(
    'EX_FOLLOWER WAYPOINTS_DAY WAYPOINTS_NIGHT AI_WAIT_HERE AI_SPREAD_OUT JILTED LOGBOOK_IGNORES UNUSED_00000080 KOS '
    'USE_ALERTPOINTS FORCED_FOLLOWER KOS_OVERRIDE WANDERS WANDERS_IN_DARK FENCE FAMILIAR CHECK_LEADER NO_EQUIP '
    'CAST_HIGHEST GENERATOR GENERATED GENERATED_RATE BACKING_OFF BOSS_MONSTER EXTRAPLANAR DEMAINTAIN_SPELLS '
    'BUSTED_IN_CONVERSATION NO_ATTACK'.split())}
OPF_LOCKED, OPF_OPEN = 0x1, 0x200
OCOF_LOCKED = 0x1      # ContainerFlag.LOCKED
CLASS_STAT = {'barbarian': 7, 'bard': 8, 'cleric': 9, 'druid': 10, 'fighter': 11, 'monk': 12, 'paladin': 13,
              'ranger': 14, 'rogue': 15, 'sorcerer': 16, 'wizard': 17}
WEAR_SLOT = {'helmet': 0, 'amulet': 1, 'gloves': 2, 'weapon1': 3, 'shield': 11, 'armor': 5, 'lring': 6, 'rring': 7,
             'boots': 8, 'quiver1': 9, 'cloak': 10}
SAN = {'san_dialog': 9, 'san_first_heartbeat': 10, 'san_dying': 12, 'san_enter_combat': 13, 'san_start_combat': 15,
       'san_heartbeat': 19}
ITEM_OF = OF['FLAT'] | OF['SEE_THROUGH'] | OF['SHOOT_THROUGH'] | OF['NO_BLOCK'] | OF['INVENTORY']   # vanilla 0x1434
CRITTER_OF = OF['PROVIDES_COVER'] | OF['SEE_THROUGH'] | OF['SHOOT_THROUGH']                       # vanilla 0x4030
PORTAL_OF = OF['PROVIDES_COVER']                                                                  # vanilla 0x4000
QTY_FIELD = {'ammo': 'ammo_quantity', 'money': 'money_quantity'}


def _flags(cell, table, prefix):
    v = 0
    for n in (cell or '').replace(',', ' ').replace('|', ' ').split():
        n = n.strip()
        if n.startswith(prefix) and n[len(prefix):] in table:
            v |= table[n[len(prefix):]]
    return v


def load_py(path):
    g = {}
    exec(compile(open(path, encoding='latin-1').read(), path, 'exec'), g)
    return g


def ie_to_tile(placement, x, y, calx=8428, caly=-4366):
    """runtime/ie_runtime.ie_to_tile (scale 1)."""
    X = placement[0] + x; Y = placement[1] + y
    a = (X - calx) / 20.0; b = (Y - caly) / 14.0
    return int(round((b - a) / 2.0)), int(round((b + a) / 2.0))


def ie_rotation(orient):
    return (5.0 * math.pi / 4.0 + int(orient) * math.pi / 8.0) % (2 * math.pi)


def standpoints(map_id, x, y):
    """npc_standpoints: day (indices 0-3) and night (10-13); StandPoint = mapId u32, pad, loc, offx, offy, jump, pad."""
    sp = struct.pack('<IIqffiI', map_id, 0, T.location(x, y), 0.0, 0.0, -1, 0)
    items = {}
    for base in (0, 10):
        for i in range(10):
            items[base + i] = sp[8 * i:8 * i + 8] if i < 4 else b'\0' * 8
    return T.Array(8, items)


def waypoints(points, delay_ms):
    """npc_waypoints_idx: [0] count, [1] unused, then 8 int64 per waypoint (OpenTemple WaypointSystem.GetWaypoint)."""
    items = {0: struct.pack('<q', len(points)), 1: b'\0' * 8}
    for n, (x, y) in enumerate(points):
        flags = 2 if delay_ms else 0
        # ints: 0 flags, 1-2 tile x/y, 3-4 offsets, 5 rotation, 6-7 eight anim bytes, 8 delay ms, 9-15 unused
        w = struct.pack('<Iiiff', flags, x, y, 0.0, 0.0) + struct.pack('<f', 0.0) + b'\0' * 8 + \
            struct.pack('<I', delay_ms) + b'\0' * 28
        for i in range(8):
            items[2 + 8 * n + i] = w[8 * i:8 * i + 8]
    return T.Array(8, items)


class Baker(object):
    def __init__(self, a):
        self.a = a
        self.area = a.area.upper()
        self.flavour = a.flavour
        self.placement = tuple(int(v) for v in a.placement.split(','))
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import toeedata
        self.protos = toeedata.ToEEData(a.toee).protos()
        self.items = load_py(a.items)['ITEMS'] if a.items else {}
        self.containers = (load_py(a.items).get('CONTAINERS') or {}).get(self.area, []) if a.items else []
        self.specs = load_py(a.specs)['CREATURES'] if a.specs else []
        self.stores = (load_py(a.items).get('STORES') or {}) if a.items else {}
        self.shops = json.load(open(a.shops)) if getattr(a, 'shops', None) else {}    # actor ident -> IE store resref
        self.doors = load_py(a.doors)['DOORS'] if a.doors else []
        self.mobs = []          # GameObjects
        self.sec_objs = {}      # sector id -> [GameObject]
        self.runtime = {}       # guid name -> finalize data
        self.report = {'npcs': 0, 'items': 0, 'containers': 0, 'doors': 0, 'patrols': [], 'unbaked': []}

    def gid(self, *key):
        return T.permanent_id(uuid.uuid5(NS, 'ie2toee/%s/%s/' % (self.flavour, self.area) + '/'.join(map(str, key))))

    def proto_flags(self, pid, col, table, prefix):
        r = self.protos.get(int(pid))
        return _flags(r[col], table, prefix) if r else 0

    # ---------------------------------------------------------------- items
    def item(self, key, pid, res, parent, inv_loc, x, y, qty=None):
        r = self.protos.get(int(pid))
        if not r:
            self.report['unbaked'].append('item %s: proto %s missing' % (res, pid)); return None
        otype = int(r[1]) if r[1].strip().isdigit() else T.OBJ_TYPES.index(r[1].strip().replace('obj_t_', ''))
        o = T.GameObject(otype, int(pid), self.gid('item', *key))
        o.set('location', T.location(x, y))
        o.set('flags', ITEM_OF | self.proto_flags(pid, 20, OF, 'OF_'))
        o.set('item_parent', parent.id)
        o.set('item_inv_location', inv_loc)
        e = self.items.get((res or '').lower()) if res else None
        if e:
            if e.get('n'):
                o.set('description', e['n']); o.set('item_description_unknown', e['n'] + 1)
            if e.get('i'):
                o.set('item_inv_aid', e['i'])
            if e.get('w'):
                o.set('item_worth', e['w'])
            q = qty or e.get('q')
            t = T.OBJ_TYPES[otype]
            if q and t in QTY_FIELD:
                o.set(QTY_FIELD[t], int(q))
            f = self.proto_flags(pid, 50, OIF, 'OIF_')
            if e.get('m'):
                f |= OIF['IS_MAGICAL']
            if e.get('id'):
                f |= OIF['IDENTIFIED']
            else:
                f &= ~OIF['IDENTIFIED']
            o.set('item_flags', f)
            if e.get('c'):
                self.runtime[T.guid_name(o.id)] = {'k': 'item', 'res': res.lower()}
        self.mobs.append(o)
        self.report['items'] += 1
        return o

    # ---------------------------------------------------------------- critters
    def critter(self, i, s, patrol=None):
        u, v = ie_to_tile(self.placement, s['x'], s['y'])
        o = T.GameObject(14, int(s['proto']), self.gid('npc', i, s.get('resref', '')))
        o.set('location', T.location(u, v)).set('offset_x', 0.0).set('offset_y', 0.0)
        flags = CRITTER_OF | self.proto_flags(s['proto'], 20, OF, 'OF_')
        if s.get('invulnerable'):
            flags |= OF['INVULNERABLE']
        o.set('flags', flags)
        if s.get('orient') is not None:
            o.set('rotation', ie_rotation(s['orient']))
        o.set('critter_teleport_dest', T.location(u, v))
        o.set('npc_standpoints', standpoints(self.a.map_id, u, v))
        npc_flags = self.proto_flags(s['proto'], 152, ONF, 'ONF_')
        if s.get('hostility') == 'hostile':
            npc_flags |= ONF['KOS']
        else:
            npc_flags &= ~ONF['KOS']
        if patrol:
            pts = [ie_to_tile(self.placement, x, y) for x, y in patrol]
            o.set('npc_waypoints_idx', waypoints(pts, self.a.waypoint_delay))
            npc_flags |= ONF['WAYPOINTS_DAY'] | ONF['WAYPOINTS_NIGHT']
            self.report['patrols'].append({'actor': i, 'resref': s.get('resref'), 'waypoints': len(pts)})
        o.set('npc_flags', npc_flags)
        # converted stat block (runtime/ie_critters.apply, as fields)
        o.set('critter_inventory_source', 0)
        ab = s.get('abilities')
        if ab:
            o.set('critter_abilities_idx', T.int_array([int(x) for x in ab]))
        levels = s.get('levels') or []
        hd = s.get('monster_hd')
        if levels:
            lv = []
            for cls, n in levels:
                lv += [CLASS_STAT.get(cls, CLASS_STAT['fighter'])] * int(n)
            o.set('critter_level_idx', T.int_array(lv))
            o.set('npc_hitdice_idx', T.int_array([0, 0, 0]))
            total = len(lv)
        elif hd:
            o.set('npc_hitdice_idx', T.int_array([int(x) for x in hd[:3]]))
            total = int(hd[0])
        else:
            total = 1
        con = int(ab[2]) if ab else 10
        if s.get('hp'):
            o.set('hp_pts', max(1, int(s['hp']) - ((con - 10) // 2) * total))
            o.set('hp_damage', 0)
        if s.get('natural_ac') is not None:
            o.set('npc_ac_bonus', int(s['natural_ac']))
        for f, b in zip(('npc_save_fortitude_bonus', 'npc_save_reflexes_bonus', 'npc_save_willpower_bonus'),
                        s.get('save_bonus') or ()):
            if b:
                o.set(f, int(b))
        if s.get('alignment') is not None:
            o.set('critter_alignment', int(s['alignment']))
        if s.get('gender'):
            o.set('critter_gender', 0 if s['gender'] == 'female' else 1)
        if s.get('scale') and int(s['scale']) != 100:
            o.set('model_scale', int(s['scale']))
        if s.get('portrait'):
            o.set('critter_portrait', int(s['portrait']))
        if s.get('name_id'):
            o.set('description', int(s['name_id'])); o.set('critter_description_unknown', int(s['name_id']))
        sid = s.get('script_id') or self.a.generic_script
        if sid:
            events = SAN if s.get('script_id') else {'san_first_heartbeat': 10}
            o.set('scripts_idx', T.script_array({slot: (0, 0, int(sid)) for slot in events.values()}))
        # gear: worn into its natural slot (200 + slot), the rest in the pack
        inv, used, pack = [], set(), 0
        for k, it in enumerate(s.get('items') or ()):
            slot = WEAR_SLOT.get(it.get('slot'))
            if slot is not None and slot not in used:
                used.add(slot); loc = 200 + slot
            else:
                loc = pack; pack += 1
            io = self.item((i, k), it['proto'], it.get('res'), o, loc, u, v)
            if io is not None:
                inv.append(io.id)
        if inv:
            o.set('critter_inventory_num', len(inv))
            o.set('critter_inventory_list_idx', T.obj_array(inv))
        st = self.shops.get(s.get('ident') or '')
        if st:
            box = self.store_box(i, st, u, v)
            if box is not None:
                o.set('npc_substitute_inventory', box.id)
        self.mobs.append(o)
        keep = ('ident', 'resref', 'hp', 'conditions', 'spells', 'ai_strategy', 'to_hit_bonus')
        self.runtime[T.guid_name(o.id)] = {'k': 'npc', 'spec': {k: s[k] for k in keep if s.get(k) not in (None, [], '')}}
        self.report['npcs'] += 1
        return o

    # ---------------------------------------------------------------- stores (the merchant's barter stock)
    def store_box(self, i, store, x, y):
        """IE store -> a hidden container MOB on the merchant's tile, set as his npc_substitute_inventory (ToEE's
        barter screen sells from it, like vanilla merchants). Infinite IE stock -> 5 of each (ie_items)."""
        sd = self.stores.get(store.lower())
        if not sd:
            self.report['unbaked'].append('store %s: not converted' % store); return None
        pid = int(sd.get('container') or 1001)
        o = T.GameObject(1, pid, self.gid('store', i, store.lower()))
        o.set('location', T.location(x, y))
        o.set('flags', CRITTER_OF | OF['DONTDRAW'] | OF['CLICK_THROUGH'] | OF['NO_BLOCK'] | self.proto_flags(pid, 20, OF, 'OF_'))
        inv = []
        for k, (res, q) in enumerate(sd.get('items') or ()):
            e = self.items.get(res.lower())
            if not e:
                self.report['unbaked'].append('store %s item %s: unmapped' % (store, res)); continue
            for n in range(1 if e.get('q') else int(q)):          # stackables: one stack of q
                io = self.item(('s', i, store.lower(), k, n), e['p'], res, o, len(inv), x, y,
                               int(q) if e.get('q') and q > 1 else None)
                if io is not None:
                    inv.append(io.id)
        if inv:
            o.set('container_inventory_num', len(inv)); o.set('container_inventory_list_idx', T.obj_array(inv))
        self.mobs.append(o)
        self.report.setdefault('stores', {})[store.lower()] = len(inv)
        return o

    # ---------------------------------------------------------------- containers (MOBs, like vanilla)
    def container(self, i, c):
        if not c.get('toee'):
            self.report['unbaked'].append('container %s: no position' % c['name']); return None
        x, y = int(c['toee'][0]), int(c['toee'][1])
        o = T.GameObject(1, int(c['proto']), self.gid('container', i, c['name']))
        o.set('location', T.location(x, y)).set('flags', CRITTER_OF | self.proto_flags(c['proto'], 20, OF, 'OF_'))
        if c.get('lock'):
            o.set('container_flags', self.proto_flags(c['proto'], 41, {}, '') | OCOF_LOCKED)
            o.set('container_lock_dc', min(40, 10 + int(c['lock']) // 5))
        inv = []
        for k, (res, q) in enumerate(c.get('items') or ()):
            e = self.items.get(res.lower())
            if not e:
                self.report['unbaked'].append('container item %s: unmapped' % res); continue
            io = self.item(('c', i, k), e['p'], res, o, k, x, y, q if q > 1 else None)
            if io is not None:
                inv.append(io.id)
        if inv:
            o.set('container_inventory_num', len(inv)); o.set('container_inventory_list_idx', T.obj_array(inv))
        self.mobs.append(o)
        self.report['containers'] += 1

    # ---------------------------------------------------------------- doors (sector objects)
    def door(self, d):
        x, y, ox, oy = d['loc']
        o = T.GameObject(0, self.a.portal_proto)
        o.set('location', T.location(int(x), int(y))).set('offset_x', float(ox)).set('offset_y', float(oy))
        o.set('flags', PORTAL_OF | self.proto_flags(self.a.portal_proto, 20, OF, 'OF_'))
        o.set('model_scale', self.a.portal_scale)
        pf = self.proto_flags(self.a.portal_proto, 37, {}, '')
        if d.get('locked'):
            pf |= OPF_LOCKED
        if d.get('open'):
            pf |= OPF_OPEN
        if pf:
            o.set('portal_flags', pf)
        if d.get('locked') and d.get('lock_difficulty'):
            o.set('portal_lock_dc', min(40, 10 + int(d['lock_difficulty']) // 5))
        self.sec_objs.setdefault(T.sector_of(int(x), int(y)), []).append(o)
        self.report['doors'] += 1

    # ---------------------------------------------------------------- patrols
    def patrol_routes(self):
        if not self.a.ie:
            return {}
        import iefs, ie_patrol
        rows = ie_patrol.Survey(iefs.IEGame(self.a.ie)).run({self.area})
        return {(r['cre'], r['x'], r['y']): r['route'] for r in rows if r['bucket'] == 'fixed_loop'}

    # ---------------------------------------------------------------- output
    def run(self):
        routes = self.patrol_routes()
        for i, s in enumerate(self.specs):
            self.critter(i, s, routes.get(((s.get('resref') or '').lower(), s['x'], s['y'])))
        for i, c in enumerate(self.containers):
            self.container(i, c)
        for d in self.doors:
            self.door(d)
        mapd = os.path.join(self.a.out, 'modules', 'ToEE', 'maps', self.a.map_dir or self.area)
        if os.path.isdir(mapd):
            shutil.rmtree(mapd)
        shutil.copytree(self.a.maps, mapd)
        for f in os.listdir(mapd):
            if f.lower().endswith('.mob'):
                os.remove(os.path.join(mapd, f))
        for sid, objs in sorted(self.sec_objs.items()):
            p = os.path.join(mapd, '%d.sec' % sid)
            if not os.path.exists(p):
                self.report['unbaked'].append('sector %d missing: %d objects dropped' % (sid, len(objs))); continue
            sec = T.Sector.read(open(p, 'rb').read())
            sec.objects += objs
            open(p, 'wb').write(sec.write())
        for o in self.mobs:
            open(os.path.join(mapd, T.mob_filename(o).lower()), 'wb').write(T.write_mob(o))
        # round-trip self check of everything written
        for f in os.listdir(mapd):
            b = open(os.path.join(mapd, f), 'rb').read()
            if f.endswith('.mob'):
                assert T.write_mob(T.read_mob(b)) == b, f
            elif f.endswith('.sec'):
                assert T.Sector.read(b).write() == b, f
        F = {n: T.FIELD_INDEX[n] for n in ('npc_pad_i_3', 'item_pad_i_1')}
        rt = os.path.join(self.a.out, 'ie_bake_%s.py' % self.area.lower())
        with open(rt, 'w') as f:
            f.write("# generated by proto/ie_bake.py (local only: converted from the player's own IE install)\n")
            f.write('AREA = %r\nFIELDS = %r\nOBJS = {\n' % (self.area, F))
            for g, d in sorted(self.runtime.items()):
                f.write('    %r: %r,\n' % (g, d))
            f.write('}\n')
        if self.a.generic_script:
            sd = os.path.join(self.a.out, 'modules', 'ToEE', 'scr'); os.makedirs(sd, exist_ok=True)
            with open(os.path.join(sd, 'py%05die_baked.py' % self.a.generic_script), 'w') as f:
                f.write(GENERIC_SCRIPT % {'area': self.area})
        self.report['mob_files'] = len(self.mobs)
        self.report['sector_objects'] = {str(k): len(v) for k, v in self.sec_objs.items()}
        self.report['finalize_entries'] = len(self.runtime)
        json.dump(self.report, open(os.path.join(self.a.out, 'bake_%s.json' % self.area.lower()), 'w'), indent=1)
        return self.report


GENERIC_SCRIPT = '''# generated by proto/ie_bake.py: baked critters without an IE script/dialog get this one, so the map's
# baked objects are finalized (runtime/ie_bakert.py) on the first heartbeat after the map loads.
from toee import *

def san_first_heartbeat(attachee, triggerer):
    try:
        import ie_bakert
        ie_bakert.first_heartbeat(attachee, %(area)r)
    except ImportError:
        pass
    return RUN_DEFAULT
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd')
    b = sub.add_parser('bake')
    b.add_argument('--area', required=True); b.add_argument('--flavour', required=True)
    b.add_argument('--specs'); b.add_argument('--items'); b.add_argument('--doors')
    b.add_argument('--shops', help='json {actor ident: IE store resref}: bake the store stock as the merchant\'s barter inventory')
    b.add_argument('--maps', required=True, help='converted map dir (ie2toee.py output, the .sec files)')
    b.add_argument('--map-dir', help='ToEE map directory name (default: the area)')
    b.add_argument('--map-id', type=int, required=True); b.add_argument('--placement', default='0,0')
    b.add_argument('--toee', required=True); b.add_argument('--ie', help='IE install, for the patrol routes')
    b.add_argument('--out', required=True)
    b.add_argument('--portal-proto', type=int, default=39); b.add_argument('--portal-scale', type=int, default=30)
    b.add_argument('--generic-script', type=int, default=1099)
    b.add_argument('--waypoint-delay', type=int, default=3000, help='ms at each waypoint')
    d = sub.add_parser('dump', help='print the objects of .mob / .sec files')
    d.add_argument('files', nargs='+')
    a = ap.parse_args()
    if a.cmd == 'bake':
        r = Baker(a).run()
        print(json.dumps({k: (v if not isinstance(v, list) or len(v) < 8 else len(v)) for k, v in r.items()}))
    elif a.cmd == 'dump':
        for f in a.files:
            b_ = open(f, 'rb').read()
            objs = [T.read_mob(b_)] if f.endswith('.mob') else T.Sector.read(b_).objects
            for o in objs:
                print(f, o)
                for k, v in o.names().items():
                    print('   %-28s %s' % (k, T.id_str(v) if isinstance(v, bytes) else v))
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
