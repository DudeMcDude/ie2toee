"""Patrol survey and conversion: IE creature movement scripts -> ToEE NPC waypoints (docs/mapfiles.md, "Patrols").

Buckets (per placed creature, over all its scripts in IE evaluation order):
  fixed_loop   two or more MoveToPoint-family targets, reached in a cycle that depends only on the creature's own
               state (no trigger, True(), its own timers / LOCALS counters / arrival checks). -> ToEE waypoints.
  wander       RandomWalk / RandomWalkContinuous / RandomFly / Wander, no fixed targets. -> ONF_WANDERS (engine wander)
               is the closest; left to the script runtime by default.
  conditional  movement that depends on the world (See, globals, area, party, time of day, dialog, ...) or a single
               target ("go there and stay"). Left to the script runtime.
  reactive     only reactive movement (MoveToObject, RunAwayFrom, EscapeArea, ...): no patrol, script runtime.
  none         no movement actions.
"""
import argparse, collections, json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iefs, iescript as S, ieformats as F, iecre

MOVE_POINT = re.compile(r'^(MoveToPoint|MoveToPointNoInterrupt|MoveToPointNoRecticle|RunToPoint|RunToPointNoRecticle|'
                        r'MoveToPointNoInterruptRun|WalkToPoint|MoveToOffset)$', re.I)
WANDER = re.compile(r'^(RandomWalk|RandomWalkContinuous|RandomFly|RandomRun|Wander|RandomWalkTime)$', re.I)
OTHER_MOVE = re.compile(r'^(MoveToObject\w*|MoveToSavedLocation\w*|ReturnToSavedLocation\w*|EscapeArea\w*|'
                        r'MoveToCampaign|MoveBetweenAreas\w*|MoveGlobal\w*|JumpToPoint\w*)$', re.I)
# triggers that only look at the creature's own state: a cycle built from them is a fixed loop
SELF_TRIGGERS = re.compile(r'^(True|False|TimerExpired|TimerActive|GlobalTimerExpired|GlobalTimerNotExpired|'
                           r'Global|GlobalGT|GlobalLT|GlobalLTGlobal|GlobalGTGlobal|NumTimesTalkedTo|'
                           r'AtLocation|NearLocation|NearSavedLocation|Delay|OnCreation|ActionListEmpty|IsActive|HPGT|InActiveArea|'
                           r'ActuallyInCombat|CombatCounter|Detect|See|NumCreature\w*)$', re.I)
WORLD_SENSITIVE = re.compile(r'^(See|Detect|ActuallyInCombat|CombatCounter|NumCreature\w*|InActiveArea|HPGT)$', re.I)


def _point(c):
    for a in c.args:
        if isinstance(a, S.Point):
            return (a.x, a.y)
    return None


def _self_only(trig):
    """Triggers reference only the creature's own timers/LOCALS (or nothing)."""
    for t in trig:
        if not SELF_TRIGGERS.match(t.name) or WORLD_SENSITIVE.match(t.name):
            return False
        if t.name.lower().startswith('global') and not any(isinstance(a, str) and a.upper() == 'LOCALS'
                                                            for a in t.args):
            return False
    return True


def classify(blocks_by_script):
    """blocks_by_script: [(resref, Bcs.blocks)]. Returns (bucket, info)."""
    points, wander, other, cond_points = [], 0, 0, 0
    loop_blocks = 0
    for ref, blocks in blocks_by_script:
        for trig, resp in blocks:
            for _w, acts in resp:
                pts_here = []
                for c in S.walk_calls(acts):
                    if MOVE_POINT.match(c.name):
                        p = _point(c)
                        if p:
                            pts_here.append(p)
                    elif WANDER.match(c.name):
                        wander += 1
                    elif OTHER_MOVE.match(c.name):
                        other += 1
                if pts_here:
                    if _self_only(trig):
                        points.extend(pts_here); loop_blocks += 1
                    else:
                        cond_points += len(pts_here)
    distinct = []
    for p in points:
        if p not in distinct:
            distinct.append(p)
    info = {'points': distinct, 'route': points, 'wander': wander, 'other_moves': other,
            'conditional_points': cond_points}
    if len(distinct) >= 2 and not cond_points:
        return 'fixed_loop', info
    if wander and not distinct and not cond_points:
        return 'wander', info
    if distinct or cond_points or (wander and (distinct or cond_points)):
        return 'conditional', info
    if wander:
        return 'wander', info
    # MoveToObject / RunAwayFrom / EscapeArea only: reactive movement, not a patrol
    return ('reactive' if other else 'none'), info


class Survey(object):
    def __init__(self, game):
        self.game = game
        self.ids = S.IdsSet(game)
        self._bcs = {}

    def bcs(self, ref):
        ref = ref.lower()
        if ref not in self._bcs:
            try:
                self._bcs[ref] = S.Bcs(self.game.read(ref, 'bcs'), self.ids, ref).blocks
            except Exception:
                self._bcs[ref] = None
        return self._bcs[ref]

    def actor_scripts(self, act):
        ok = lambda r: r and r.strip() and r.strip().lower() != 'none'
        order = ('override', 'specific', 'class', 'race', 'general', 'default')
        src = act.get('scripts') or {}
        if not any(ok(v) for v in src.values()) and act.get('cre'):
            try:
                src = iecre.Cre(self.game.read(act['cre'], 'cre')).scripts
            except Exception:
                src = {}
        return [src[k].lower() for k in order if ok(src.get(k))]

    def run(self, areas=None):
        out = []
        for ar in self.game.list('are'):
            if areas and ar.upper() not in areas:
                continue
            try:
                a = F.Are(self.game.read(ar, 'are'))
            except Exception:
                continue
            for i, act in enumerate(a.actors):
                refs = self.actor_scripts(act)
                blocks = [(r, self.bcs(r)) for r in refs if self.bcs(r)]
                bucket, info = classify(blocks)
                out.append({'area': ar.upper(), 'actor': i, 'cre': (act.get('cre') or '').lower(),
                            'x': act.get('x'), 'y': act.get('y'), 'scripts': refs, 'bucket': bucket, **info})
        return out


def waypoints(points, to_tile, delay_ms=3000):
    """IE area points -> ToEE waypoint dicts for toeemob / ie_bake (tile, offsets, delay, fixed rotation off)."""
    wps = []
    for x, y in points:
        u, v = to_tile(x, y)
        wps.append({'x': int(u), 'y': int(v), 'ox': 0.0, 'oy': 0.0, 'delay': delay_ms})
    return wps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('games', nargs='+')
    ap.add_argument('--json'); ap.add_argument('--md')
    a = ap.parse_args()
    md = ['# Patrol survey (local only: contains resrefs of the player\'s installs)', '']
    allj = {}
    for gp in a.games:
        g = iefs.IEGame(gp)
        rows = Survey(g).run()
        c = collections.Counter(r['bucket'] for r in rows)
        moving = [r for r in rows if r['bucket'] not in ('none', 'reactive')]
        md += ['## %s' % gp, '', '- placed creatures: %d; with movement: %d' % (len(rows), len(moving)),
               '- buckets: ' + ', '.join('%s %d' % (k, c[k]) for k in ('fixed_loop', 'wander', 'conditional', 'reactive', 'none')),
               '', '| area | actor | cre | bucket | points | wander | conditional points | scripts |',
               '|---|---|---|---|---|---|---|---|']
        for r in moving:
            md.append('| %s | %d | %s | %s | %d | %d | %d | %s |' % (r['area'], r['actor'], r['cre'], r['bucket'],
                      len(r['points']), r['wander'], r['conditional_points'], ' '.join(r['scripts'])))
        md.append('')
        allj[gp] = {'counts': dict(c), 'rows': rows}
        print('%s: %d placed, buckets %s' % (gp, len(rows), dict(c)))
    if a.md:
        open(a.md, 'w').write('\n'.join(md) + '\n')
    if a.json:
        json.dump(allj, open(a.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
