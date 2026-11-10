from toee import *
import os, time, traceback
T = {'n': 0, 'log': 1}
def _log(s):
    f = open(os.environ['IE2TOEE_PROBE_LOG'], 'a'); f.write((s.split(' ')[0] in ('SHOT','KEY','DONE') and s or '%.2f %s' % (time.time(), s)) + '\n'); f.close()
import ie_cutscene
_orig = ie_cutscene.map_tick
def _wrapped(map_id, el):
    T['n'] += 1
    if T['log']:
        _log('TICK %d map %d elapsed %d areas %r' % (T['n'], map_id, el, sorted(ie_cutscene._area.keys())))
    return _orig(map_id, el)
ie_cutscene.map_tick = _wrapped
def _at(fn, ms):
    game.timeevent_add(fn, (), ms, 1)      # probe steps on the real-time clock (they run while paused)
def s0(*a):
    game.global_vars[990] = 1
    _log('START map %s ticks %d' % (game.leader.map, T['n'])); _log('SHOT running'); _at(s1, 5000)
def s1(*a):
    _log('PAUSE esc ticks %d' % T['n']); _log('KEY Escape'); _at(s2, 6000)
def s2(*a):
    _log('SHOT escmenu'); _log('PAUSED esc ticks %d' % T['n']); _log('KEY Escape'); _at(s3, 4000)
def s3(*a):
    _log('RESUMED ticks %d' % T['n']); _log('KEY i'); _at(s4, 6000)
def s4(*a):
    _log('SHOT inventory'); _log('PAUSED inv ticks %d' % T['n']); _log('KEY Escape'); _at(s5, 4000)
def s5(*a):
    _log('RESUMED2 ticks %d' % T['n'])
    _at(s7, 9000)       # saved with the game: continues after the load
    _log('SAVE -> %s' % game.savegame('slot0777', 'maptick test')); _at(s6, 2000)
def s6(*a):
    T['pre_load'] = T['n']; _log('LOADGAME ticks %d' % T['n'])
    _log('LOAD -> %s' % game.loadgame('slot0777'))
def s7(*a):
    _log('AFTERLOAD map %s ticks %d' % (game.leader.map, T['n'])); _log('SHOT afterload')
    import ie_runtime as rt
    u, v = rt.ie_to_tile('AR1000', 2400, 1000)
    game.fade_and_teleport(0, 0, 0, 5031, u, v); _at(s8, 12000)
def s8(*a):
    _log('AR1000 map %s ticks %d' % (game.leader.map, T['n'])); _log('SHOT ar1000'); _log('DONE')
_at(s0, 4000)
