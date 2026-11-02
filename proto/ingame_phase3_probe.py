# Probe: INI spawns (enter + timed event, spec_var/spec_qty, spread), rest encounter hooks, cutscene letterbox.
from toee import *
from utilities import location_from_axis, location_to_axis
import os, __main__
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
def ie_pt(area, u, v):
    import ie_runtime as rt
    cx, cy, s, calx, caly = rt._placement.get(area.lower(), (0, 0, 1.0, 8428, -4366))
    a = v - u; b = u + v
    return int(round((calx + 20 * a - cx) / s)), int(round((caly + 14 * b - cy) / s))
def near(nid):
    r = []
    for o in game.obj_list_vicinity(game.leader.location, OLC_NPC):
        if o.obj_get_int(__import__('ie_critters')._c('obj_f_description')) == nid:
            r.append(location_to_axis(o.location))
    return r
def dump():
    r = []
    for o in game.obj_list_vicinity(game.leader.location, OLC_NPC):
        try:
            r.append((str(o.description), o.obj_get_int(__import__('ie_critters')._c('obj_f_description')), location_to_axis(o.location)))
        except Exception, e:
            r.append(str(e))
    log('NPCS %r' % r[:12])
def start():
    try:
        import ie_movies_rt; ie_movies_rt.play = lambda *a, **k: None
    except Exception, e:
        log('nomovie %s' % e)
    log("KEY Escape"); log("KEY Escape")
    game.fade_and_teleport(0, 0, 0, 5950, 450, 490)
    game.timeevent_add(step1, (), 6000, 1)
def step1():
    try:
        __main__.cheats.kos = 0
    except Exception, e:
        pass
    import ie_runtime as rt, ie_spawn, ie_spawnables as d
    rt.IN_GAME = 1
    u, v = location_to_axis(game.leader.location)
    x, y = ie_pt('AR1000', u + 6, v)
    x2, y2 = ie_pt('AR1000', u - 6, v + 2)
    log('leader tile %d,%d -> ie %d,%d (roundtrip %r)' % (u, v, x, y, rt.ie_to_tile('AR1000', x, y)))
    keg = dict(d.INI_SPAWNS['AR1200']['enter'][0]['critters'][0])
    keg.update(points=[(x, y, 0)], var='PROBE_STOP', qty=3, spec_qty=2, inc=0)
    wolf = {'name': 'WOLVES', 'cre': '40rwolfw', 'points': [(x2, y2, 4)], 'select': 'r', 'qty': 2, 'spec_qty': 4}
    d.INI_SPAWNS['AR1000'] = {'enter': [{'name': 'ENTERSPAWN', 'interval': 1, 'critters': [keg]}],
                              'events': [{'name': 'WOLFTIMER', 'interval': 30, 'critters': [wolf]}]}
    kn = d.SPECS['12kegarc']['name_id']; __main__._kn = kn; __main__._wn = d.SPECS['40rwolfw']['name_id']
    log('ENTER1 %d' % ie_spawn.area_spawns('AR1000'))
    log('ENTER2 (spec_qty cap) %d' % ie_spawn.area_spawns('AR1000'))
    rt.set_var(None, 'PROBE_STOP', 'GLOBAL', 1)
    log('ENTER3 (spec_var 1 != 0) %d' % ie_spawn.area_spawns('AR1000'))
    log('KEG tiles %r named %s' % (near(kn), rt.N(rt.Ctx(game.leader, None, 'probe', 'AR1000', {}), '12KegArc')))
    dump()
    game.timeevent_add(step2, (), 7000, 1)
def step2():
    import ie_spawn
    log('TICK now %r EV %r' % (ie_spawn._gsecs(), ie_spawn._EV))
    log('WOLF tiles after timer %r' % near(__main__._wn))
    log('SHOT ini_spawns')
    game.timeevent_add(step3, (), 1500, 1)
class Enc:
    id = 0; map = 0; enemies = (); dc = 0
def step3():
    import ie_runtime as rt, ie_spawn, ie_spawnables as d, random_encounter as re_
    log('HOOK %r' % ie_spawn.hook_rest())
    d.REST['AR1000'] = d.REST['AR2000']
    log('CAN_SLEEP %r (SAFE %d DANGEROUS %d)' % (re_.can_sleep(), SLEEP_SAFE, SLEEP_DANGEROUS))
    e = Enc(); ie_spawn.FORCE[0] = 1
    log('CHECK forced %r id %d' % (re_.check_sleep_encounter(None, e), e.id))
    o1 = len(near(d.SPECS['20rndorw']['name_id']) + near(d.SPECS['20rndora']['name_id']))
    log('CREATE %r' % re_.encounter_create(e))
    log('REST orcs near party %d -> %d' % (o1, len(near(d.SPECS['20rndorw']['name_id']) + near(d.SPECS['20rndora']['name_id']))))
    e2 = Enc(); r = [re_.check_sleep_encounter(None, e2) for i in range(40)]
    log('CHECK x40 hits %d (chance %d/%d)' % (len([h for h in r if h]), d.REST['AR1000']['day'], d.REST['AR1000']['night']))
    del d.REST['AR1000']
    log('CAN_SLEEP no table %r' % re_.can_sleep())
    sv = rt.AREA_MAPS; rt.AREA_MAPS = {}
    try:
        log('VANILLA hooks None: %r %r; Co8 can_sleep -> %r' % (ie_spawn.rest_can_sleep(), ie_spawn.rest_check(Enc()), re_.can_sleep()))
    finally:
        rt.AREA_MAPS = sv
    log('SHOT rest')
    game.timeevent_add(step4, (), 1500, 1)
def step4():
    import ie_cutscene
    ie_cutscene.mode(1)
    log('SHOT letterbox')
    game.timeevent_add(step5, (), 1500, 1)
def step5():
    import ie_cutscene
    ie_cutscene.mode(0)
    log('SHOT after'); log('DONE')
try:
    start()
except:
    import traceback, sys
    f = open(LOG, 'a'); traceback.print_exc(file=f); f.close()
