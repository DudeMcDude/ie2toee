# Probe: AR1200 (Targos palisade) - hidden goblin waves, Caballus' spawn cutscene (12cSpn1a/1b), travel AR1100 <-> AR1200.
from toee import *
from utilities import location_from_axis, location_to_axis
import os, time, __main__
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
def start():
    try:
        import ie_movies_rt; ie_movies_rt.play = lambda *a, **k: None
    except Exception, e:
        log('nomovie %s' % e)
    log("start map %d" % game.leader.map); log("KEY Escape"); log("KEY Escape")
    try:
        __main__.cheats.kos = 0
    except Exception:
        pass
    game.fade_and_teleport(0, 0, 0, 5958, 513, 536)     # (travel AR1100 <-> AR1200 <-> AR1201: ingame_exiticon_probe)
    game.timeevent_add(step2, (), 9000, 1)
def step0():
    import ie_travel_data as td
    r = [x for x in td.AREAS['I2AR1100']['regions'] if x.get('dest_area') == 'I2AR1200']
    log('AR1100 -> AR1200 regions %r' % [(x['name'], x['anchor'], x['dest_map']) for x in r])
    try:
        import ie_travel
        log('travel fns %s' % [n for n in dir(ie_travel) if not n.startswith('_')])
    except Exception, e:
        log('ie_travel %s' % e)
    if r:
        u, v = r[0]['anchor']
        game.leader.move(location_from_axis(u, v), 0.0, 0.0)
        for p in game.party:
            p.move(location_from_axis(u, v), 0.0, 0.0)
    game.timeevent_add(step1, (), 8000, 1)
def step1():
    log('after exit walk: map %d tile %s' % (game.leader.map, location_to_axis(game.leader.location)))
    if game.leader.map != 5958:
        log('TRAVEL_FALLBACK teleport'); game.fade_and_teleport(0, 0, 0, 5958, 513, 536)
    game.timeevent_add(step2, (), 8000, 1)
def step2():
    import ie_runtime as rt
    log('map %d tile %s' % (game.leader.map, location_to_axis(game.leader.location)))
    log('SHOT ar1200_arrive')
    ids = sorted(set(i for i, a in rt._bound.values() if a == 'AR1200'))
    log('bound AR1200 %d: %s' % (len(ids), ids[:60]))
    off = 0; tot = 0
    for o in game.obj_list_vicinity(game.leader.location, OLC_NPC):
        tot += 1
    log('npcs near leader %d' % tot)
    import ie_doors, ie_bakert
    log('bakert %s members %s gen %s LOG %s' % (ie_bakert.__file__, ie_bakert._members.keys(), ie_bakert._hidden_gen, ie_bakert.LOG))
    try:
        offs = [o for o in game.obj_list_range(game.leader.location, 300, OLC_NPC) if o.object_flags_get() & OF_OFF]
        log('off npcs %d: %s' % (len(offs), [(str(o), o.scripts[san_heartbeat], o.scripts[san_first_heartbeat]) for o in offs[:8]]))
        log('hb mods %s' % ie_bakert._hb_mods)
    except Exception, e:
        log('off ERR %s' % e)
    try:
        log('range n=%d' % len(game.obj_list_range(game.leader.location, 300, OLC_NPC)))
    except Exception, e:
        log('range ERR %s' % e)
    log('doors area %s n=%d' % (ie_doors._area, len(ie_doors._doors)))
    for nm in ('12caball_103', '12ghotra', '12gob_69', '12caball'):
        log('IDENT %s bound=%s' % (nm, nm in ids))
    c = rt.Ctx(game.leader, None, 'probe', 'AR1200', {})
    for k in ('05_Caballus', '05_Ghotrag', 'AR1200_Door4_WallNE'):
        o = rt.N(c, k)
        log('N %s -> %s off=%s' % (k, o, o and (o.object_flags_get() & OF_OFF) != 0))
    try:
        __main__.cheats.kos = 0
    except Exception:
        pass
    rt.set_var(c, 'Goblins_Attack_Palisade', 'GLOBAL', 1)
    for t in (1, 2, 3):
        rt.set_var(c, 'GOBLIN_TEAM_%d_STATE' % t, 'MYAREA', 2)
    log('REC 58 goblin_attack')
    game.timeevent_add(step3, (), 7000, 1)
def step3():
    import ie_cutscene, ie_runtime as rt
    if ie_cutscene.active():
        log('cutscene started by 12caba05 itself')
    else:
        log('FORCE 12cSpn1a'); c = rt.Ctx(rt.N(rt.Ctx(game.leader, None, 'p', 'AR1200', {}), '05_Caballus') or game.leader, None, '12caball_103', 'AR1200', {})
        ie_cutscene.start('12cSpn1a', c)
    __main__._n = 0
    game.timeevent_add(shots, (), 2000, 1)
def shots():
    import ie_cutscene, ie_runtime as rt
    __main__._n += 1
    log('SHOT spn_%02d' % __main__._n)
    log('t=%d active=%s leader %s' % (__main__._n, ie_cutscene.active(), location_to_axis(game.leader.location)))
    if __main__._n < 27:
        game.timeevent_add(shots, (), 2000, 1)
    else:
        c = rt.Ctx(game.leader, None, 'probe', 'AR1200', {})
        for k in ('05_Ghotrag', '05_Goblin_01', '05_Caballus'):
            o = rt.N(c, k)
            log('AFTER %s -> off=%s' % (k, o and (o.object_flags_get() & OF_OFF) != 0))
        log('REC_END %f' % time.time())
        log('DONE')
start()
