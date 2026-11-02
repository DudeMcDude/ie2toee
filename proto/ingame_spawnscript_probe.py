# Probe: runtime spawns run their own IE scripts/dialogue (script ids from ie_spawnables), per-instance idents,
# IE summon spells (ie_spawn.summon), INI keys (difficulty / visibility / spec counts), script-name noise.
from toee import *
from utilities import location_from_axis, location_to_axis
import os, __main__
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
def start():
    try:
        import ie_movies_rt; ie_movies_rt.play = lambda *a, **k: None
    except Exception, e:
        log('nomovie %s' % e)
    log("start map %d" % game.leader.map); log("KEY Escape"); log("KEY Escape")
    game.fade_and_teleport(0, 0, 0, 5950, 450, 490)
    game.timeevent_add(step1, (), 6000, 1)
def step1():
    try:
        __main__.cheats.kos = 0
    except Exception, e:
        log('kos %s' % e)
    import ie_runtime as rt, ie_spawn, ie_spawnables as d
    rt.IN_GAME = 1
    scripted = sorted([k for k, s in d.SPECS.items() if s.get('script_id')])
    log('SPECS %d scripted %d e.g. %s' % (len(d.SPECS), len(scripted), scripted[:8]))
    c = rt.Ctx(game.leader, None, 'probe', 'AR1000', {})
    out = []
    pick = [r for r in ('11veira', '41sorc', '41sfrgnt') if r in d.SPECS] + scripted[:2]
    for r in pick + pick[:1]:
        o = ie_spawn.create(c, r, (-1, -1), 4)
        if o:
            out.append((r, o))
            log('SPAWNED %s sid=%s dialog_script=%d heartbeat=%d bound=%r' % (r, d.SPECS[r].get('script_id'),
                o.scripts[san_dialog], o.scripts[san_heartbeat], rt._bound.get(rt._key(o))))
    __main__._probe_objs = out
    log('SHOT spawned')
    log('map now %d' % game.leader.map); game.timeevent_add(step2, (), 15000, 1)
def step2():
    import ie_runtime as rt, ie_spawn
    for r, o in getattr(__main__, '_probe_objs', []):
        b = rt._bound.get(rt._key(o))
        log('TICKED %s ident=%r first=%s last_tick=%s events=%s' % (r, b, b and b[0] in rt._first,
            b and rt._last_tick.get(b[0]), b and b[0] in rt._events))
    log('combat %d; mob idents ticked: %d' % (game.combat_is_active(), len(rt._first)))
    # summons: party caster (friendly) and a hostile NPC caster
    for res in ('sppr150', 'sppr150', 'sppr150', 'sppr150', 'spwi514', 'spwi520', 'spwi622', 'spwi716', 'spwi626', 'sppr402', 'effsf'):
        n = ie_spawn.summon(game.leader, res)
        log('SUMMON_PARTY %s -> %s followers=%d' % (res, n, len(list(game.leader.group_list() if hasattr(game.leader, 'group_list') else []))))
    objs = getattr(__main__, '_probe_objs', [])
    if objs:
        foe = objs[0][1]
        foe.npc_flag_set(ONF_KOS)
        n = ie_spawn.summon(foe, 'spwi124')
        log('SUMMON_HOSTILE spwi124 by %s -> %s' % (foe, n))
    log('SUMMON_NONE %r' % ie_spawn.summon(game.leader, 'spwi112'))
    import ie_spellrt
    log('CAST_VIA_SPELLRT %r' % ie_spellrt.cast(game.leader, 'spwi515', None, 'force'))
    log('SHOT summoned')
    game.timeevent_add(step3, (), 2000, 1)
def step3():
    import ie_runtime as rt, ie_spawn
    loc = game.leader.location
    log('SEEN leader spot %d; area diff AR1000 %d' % (ie_spawn._seen(loc), ie_spawn._area_diff('AR1000')))
    log('DONE')
start()
