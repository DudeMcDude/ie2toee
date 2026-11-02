# Probe: CreateCreature spawns (+portraits), cutscene input lock, PlaySequence, cutscene queue.
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
    import ie_runtime as rt
    rt.IN_GAME = 1
    c = rt.Ctx(game.leader, None, 'probe', 'AR1000', {})
    out = []
    for r in ['41sfrgnt', '41sdfgnt', '40rwolfw', '40rwolfw', '41sorc', '11veira']:
        try:
            import ie_spawn
            o = ie_spawn.create(c, r, (-1, -1), 4)
            if o:
                out.append(o)
                log('SPAWNED %s portrait=%d name=%s proto=%d' % (r, o.obj_get_int(obj_f_critter_portrait), o.description, o.proto))
            else:
                log('SPAWNED %s -> None' % r)
        except Exception, e:
            log('ERR spawn %s %s' % (r, e))
    log('N(Veira) -> %s' % rt.N(c, 'Veira'))
    __main__._probe_objs = out
    log('SHOT spawned')
    game.timeevent_add(step2, (), 2500, 1)
def step2():
    import ie_cutscene, ie_runtime as rt
    ie_cutscene.mode(1)
    __main__._p0 = location_to_axis(game.leader.location)
    log('lock on, leader at %r' % (__main__._p0,))
    log('CLICK 300 250')
    game.timeevent_add(step3, (), 2500, 1)
def step3():
    import ie_cutscene, ie_runtime as rt
    p = location_to_axis(game.leader.location)
    log('LOCKTEST leader %r -> %r clicks eaten %d' % (__main__._p0, p, ie_cutscene._LOCK['clicks']))
    objs = getattr(__main__, '_probe_objs', [])
    if objs:
        for seq in (3,):
            rt.play_sequence(objs[0], seq)
        if len(objs) > 2:
            rt.play_sequence(objs[2], 4)
    log('SHOT sequence')
    game.timeevent_add(step4, (), 1500, 1)
def step4():
    import ie_cutscene, ie_runtime as rt
    c = rt.Ctx(game.leader, None, 'probe', 'AR1000', {})
    ie_cutscene.start('10cbarf1', c)
    ie_cutscene.mode(0)
    log('lock off')
    __main__._p0 = location_to_axis(game.leader.location)
    log('CLICK 640 300')
    game.timeevent_add(step5, (), 3000, 1)
def step5():
    import ie_cutscene
    p = location_to_axis(game.leader.location)
    log('UNLOCKTEST leader %r -> %r clicks eaten %d' % (__main__._p0, p, ie_cutscene._LOCK['clicks']))
    log('SHOT after'); log('DONE')
start()
