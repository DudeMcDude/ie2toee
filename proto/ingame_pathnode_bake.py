# In-game path node bake for converted maps (Temple+ Python 2.7), run via pathnode_bake.sh / run_ingame.sh.
# For each area: teleport there (the engine loads its pathnode.pnd from ie_pathnodes.py), then
# debug.genclearance(dir) / recalc_neighbours / flush_nodes(dir) recalculate every node's links with the real pathfinder and write
# pathnodenew.pnd + pathnodedist.pnd + clearance.bin into <IE2TOEE_PNBAKE_OUT>\<area>.
#   IE2TOEE_PNBAKE="AR1000:5900:482,424;AR1001:5901:x,y;..."  IE2TOEE_PNBAKE_OUT=Z:\...\maps  [IE2TOEE_PNBAKE_MAXDIST=24]
from toee import *
import os, debug
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
OUT = os.environ['IE2TOEE_PNBAKE_OUT'].replace('/', '\\')
MAXD = float(os.environ.get('IE2TOEE_PNBAKE_MAXDIST', '24'))
JOBS = []
for j in os.environ['IE2TOEE_PNBAKE'].split(';'):
    if j:
        a, m, xy = j.split(':'); x, y = xy.split(',')
        JOBS.append((a, int(m), int(x), int(y)))

def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()

def bake(k):
    a, m, x, y = JOBS[k]
    if game.leader.map != m:
        log("PNBAKE %s FAIL not on map %d (on %d)" % (a, m, game.leader.map))
    else:
        try:
            d = OUT + '\\' + a
            # clearance first: genclearance also loads it, so recalc_neighbours links nodes with the same clearance-based
            # pathfinder the game uses (without it the legacy check walks over FlyOver/water and bakes unwalkable links)
            clr = debug.genclearance(d)
            debug.recalc_neighbours(MAXD)       # existing Temple+ hooks (feature/pathnode-bake adds the optional args)
            ok = debug.flush_nodes(d)
            log("PNBAKE %s %s flushed %d clrsectors %d" % (a, 'OK' if ok and clr else 'FAIL', ok, clr))
        except Exception, e:
            log("PNBAKE %s FAIL %r" % (a, e))
    go(k + 1); return 0

def go(k):
    if k >= len(JOBS):
        log("DONE"); return
    a, m, x, y = JOBS[k]
    game.fade_and_teleport(0, 0, 0, m, x, y)
    game.timeevent_add(bake, (k,), 8000, 1)

log("pnbake start (%d areas)" % len(JOBS))
go(0)
