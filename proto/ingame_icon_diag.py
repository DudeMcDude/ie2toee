# Exit-icon diagnosis probe (Temple+ Python 2.7, run via run_ingame.sh TP_AUTOEXEC): for each map in IE2TOEE_DIAG_MAPS
# (ToEE map names, e.g. I2AR1000,I2AR1004) teleport to the area start, list every exit icon (tile, offsets, flags,
# jump id), the objects on/next to its tile, and whether the leader can find a path to it from the arrival tile of
# every entrance. Optionally (IE2TOEE_DIAG_USE=<jump id>) stand next to that icon and use it by script.
from toee import *
from utilities import location_from_axis, location_to_axis
import os
import ie_travel_data as D
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
MAPS = os.environ.get('IE2TOEE_DIAG_MAPS', '').split(',')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
def icons():
    out = []
    for x in range(300, 720, 30):
        for y in range(300, 720, 30):
            for o in game.obj_list_vicinity(location_from_axis(x, y), OLC_SCENERY):
                if o.obj_get_int(obj_f_scenery_teleport_to) and o not in out: out.append(o)
    return out
def clear():
    for x in range(300, 720, 20):
        for y in range(300, 720, 20):
            for o in game.obj_list_vicinity(location_from_axis(x, y), OLC_CRITTERS):
                if o not in game.party: o.object_flag_set(OF_OFF)
def diag(a):
    try:
        clear()
        l = game.leader
        log('DIAG %s map %d leader %s' % (a, l.map, location_to_axis(l.location)))
        ents = D.AREAS[a]['entrances']
        for o in icons():
            t = location_to_axis(o.location)
            near = []
            for n in game.obj_list_vicinity(o.location, OLC_ALL):
                nt = location_to_axis(n.location)
                if n != o and max(abs(nt[0]-t[0]), abs(nt[1]-t[1])) <= 2:
                    near.append((n.name, n.type, nt))
            paths = []
            for en, e in sorted(ents.items()):
                l.move(location_from_axis(e[0], e[1]))
                paths.append('%s@%s:%s' % (en, location_to_axis(l.location), l.can_find_path_to_obj(o)))
            log('ICON jump %d tile %s off %.1f,%.1f flags %x radius %.1f near %s paths %s' % (o.obj_get_int(obj_f_scenery_teleport_to), t,
                o.obj_get_int(obj_f_offset_x), o.obj_get_int(obj_f_offset_y), o.object_flags_get(), o.radius, near, ' '.join(paths)))
    except Exception, e:
        import traceback; log('DIAG ERROR %s' % traceback.format_exc())
    return 0
def done():
    log('DONE'); return 0
t = [0]
def at(dt, fn, args=()):
    t[0] += dt; game.timeevent_add(fn, args, t[0], 1)
for a in ([] if os.environ.get('IE2TOEE_DIAG_USE') else MAPS):
    ar = D.AREAS[a]; e = ar['entrances'].values()[0]
    at(1500, lambda m=ar['map'], e=e: (game.fade_and_teleport(0, 0, 0, m, e[0], e[1]), 0)[1])
    at(6000, diag, (a,))
if not os.environ.get('IE2TOEE_DIAG_USE'): at(1000, done)

# IE2TOEE_DIAG_USE=1: for every icon of every listed map, stand next to it (out of combat) and use it by script;
# log whether the party changed map (lines "USE ...").
uq = []
def use_prep(a, k):
    try:
        clear()
        if game.combat_is_active(): log('combat active on %s, ending' % a); game.combat_end() if hasattr(game, 'combat_end') else None
        ic = sorted(icons(), key=lambda o: o.obj_get_int(obj_f_scenery_teleport_to))
        if k >= len(ic): uq.append(None); return 0
        o = ic[k]; t = location_to_axis(o.location); l = game.leader
        uq.append((a, o.obj_get_int(obj_f_scenery_teleport_to), l.map))
        for p in game.party: p.move(location_from_axis(t[0] + 1, t[1] + 1))
        log('USEPREP %s jump %d tile %s leader %s combat %s path %s' % (a, uq[-1][1], t, location_to_axis(l.location), game.combat_is_active(), l.can_find_path_to_obj(o)))
        l.anim_goal_use_object(o)
    except Exception, e:
        import traceback; log('USE ERROR %s' % traceback.format_exc())
    return 0
def use_check():
    q = uq[-1]
    if q: log('USE %s jump %d: %s (map %d -> %d at %s)' % (q[0], q[1], game.leader.map != q[2] and 'TRAVELLED' or 'NO', q[2], game.leader.map, location_to_axis(game.leader.location)))
    return 0
if os.environ.get('IE2TOEE_DIAG_USE'):
    for a in MAPS:
        ar = D.AREAS[a]; e = ar['entrances'].values()[0]; n = sum(1 for r in ar['regions'] if r.get('dest_map'))
        for k in range(n):
            at(1500, lambda m=ar['map'], e=e: (game.fade_and_teleport(0, 0, 0, m, e[0], e[1]), 0)[1])
            at(5000, use_prep, (a, k)); at(8000, use_check)
    at(1000, done)
