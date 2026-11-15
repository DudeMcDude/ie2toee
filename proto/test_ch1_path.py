#!/usr/bin/env python3
"""Offline test of IWD's prologue -> chapter 1 path (mock Temple+, no game needed):

  python3 test_ch1_path.py                      runtime part only (no IE data): chapter break, party jump
  python3 test_ch1_path.py <convert out>/install   + the converted scripts of YOUR convert (local data, never committed)

Runtime part: IWD's new-game prologue break (AR1006 IncrementChapter "CHPTXT1" classic / "CHPTXT0" EE, guarded by
CHAPTER_BREAK_0) shows the prologue slide after the intro and leaves CHAPTER 0; later breaks count up; a cutscene's
per-PC LeaveAreaLUA jumps the party once.
Converted part, the critical path: talk to Hrothgar until Join_Posse = 3 (Caravan_Quest 1), walk into AR1200's
caravan trigger (CARATRG1: Caravan_Quest 2, no fight), report it (Caravan_Quest 4) and get the List (Supply_Quest 1),
give it to Pomab (Supply_Quest 2), talk to Hrothgar again: state 210 -> EHHROTHM -> the party lands
on AR2000 (map 5051), whose area script plays AVALANCH (classic) on first entry; CHAPTER stays 0 (Kuldahar's ar2100
raises it). Every dialogue is walked through the generated .dlg / py scripts with the real runtime; only the item
layer (ie_itemrt) and the engine are mocked. Also checks the install has one script per id (stale-file clash) and
that Hrothgar's conversations open with each quest state."""
import os, re, sys, types, glob
HERE = os.path.dirname(os.path.abspath(__file__))
INST = sys.argv[1] if len(sys.argv) > 1 else None
SCR = DLG = None
if INST:
    core = next((d for d in glob.glob(os.path.join(INST, 'modules', '*_core')) if os.path.isdir(os.path.join(d, 'scr'))), None)
    if not core:
        sys.exit('%s: no modules/<module>_core/scr' % INST)
    SCR, DLG = os.path.join(core, 'scr'), os.path.join(core, 'dlg')
sys.path[:0] = [os.path.join(HERE, 'runtime')] + ([SCR] if SCR else [])   # the repo runtime + the generated modules

# ---- mock Temple+ ---------------------------------------------------------------------------------------------
def location_from_axis(x, y): return x | (y << 32)
def location_to_axis(l): return l & 0xFFFFFFFF, l >> 32

class Obj(object):
    _n = [0]
    def __init__(self, name, mp=5018):
        Obj._n[0] += 1
        self.id, self.name, self.map, self.location, self.inv = Obj._n[0], name, mp, location_from_axis(480, 470), {}
        self.dialog = None
    def begin_dialog(self, npc, line): self.dialog = (npc, line)
    def turn_towards(self, o): pass
    def float_text_line(self, *a): pass
    def float_line(self, *a): pass
    def distance_to(self, o): return 1.0
    def __repr__(self): return 'Obj(%s)' % self.name

class Game(object):
    def __init__(self):
        self.party, self.events, self.teleports, self.movies, self.played = [], [], [], [], []
        self.global_vars = {}
    @property
    def leader(self): return self.party[0]
    def timeevent_add(self, fn, args, ms, real=0): self.events.append((fn, args))
    def fade_and_teleport(self, t, tb, mv, mp, x, y):
        self.teleports.append((mp, x, y))
        for o in self.party:
            o.map, o.location = mp, location_from_axis(x, y)
    def fade(self, *a): pass
    def moviequeue_add(self, m): self.movies.append(m)
    def moviequeue_play(self): self.played.append(list(self.movies)); del self.movies[:]
    def obj_list_vicinity(self, *a): return []
    def scroll_to(self, *a): pass
    def get_obj_by_id(self, g): return None

class GV(dict):
    def __getitem__(self, k): return dict.get(self, k, 0)

game = Game(); game.global_vars = GV()
toee = types.ModuleType('toee')
for k, v in dict(game=game, OBJ_HANDLE_NULL=None, OLC_CRITTERS=0, OLC_NPC=0, RUN_DEFAULT=1, SKIP_DEFAULT=0,
                 location_from_axis=location_from_axis, location_to_axis=location_to_axis).items():
    setattr(toee, k, v)
sys.modules['toee'] = toee
ut = types.ModuleType('utilities'); ut.location_from_axis, ut.location_to_axis = location_from_axis, location_to_axis
sys.modules['utilities'] = ut
class _Tok(object):
    def __init__(self, holder, res): self.h, self.r = holder, res
    def destroy(self): self.h.inv.pop(self.r, None)
itemrt = types.ModuleType('ie_itemrt')                      # (py2-only engine modules: item layer mocked)
itemrt.find = lambda h, res: _Tok(h, res.lower()) if res.lower() in h.inv else None
itemrt.give = lambda res, h: h.inv.__setitem__(res.lower(), 1)
sys.modules['ie_itemrt'] = itemrt
bakert = types.ModuleType('ie_bakert'); bakert.first_heartbeat = lambda o, area: None
sys.modules['ie_bakert'] = bakert
spawn = types.ModuleType('ie_spawn'); spawn.hook_rest = spawn.area_spawns = spawn.tick = lambda *a: None
sys.modules['ie_spawn'] = spawn

import ie_runtime as rt
from ie_runtime import T, A
import ie_cutscene

fails = []
def check(name, ok, info=''):
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  [%r]' % (info,)) if info and not ok else ''))
    if not ok:
        fails.append(name)

def flush(n=50):
    """run the queued time events (IE waits / queued actions), like the game clock would"""
    for _ in range(n):
        if not game.events:
            return
        ev = list(game.events); del game.events[:]
        for fn, args in ev:
            try:
                fn(*args)
            except Exception as e:
                print('  (time event %s: %s)' % (getattr(fn, '__name__', fn), e))

def reset(maps=None):
    game.global_vars.clear(); rt._mem.clear(); game.teleports[:] = []; game.played[:] = []
    rt._leave[:] = [None, 0.0]
    if maps:
        rt.AREA_MAPS.update(maps)
    game.party[:] = [Obj('pc1'), Obj('pc2'), Obj('pc3')]

# ---- runtime part (no IE data) ---------------------------------------------------------------------------------
mv = types.ModuleType('ie_movies_data')
mv.MOVIES = {'intro': [1100, 1101, 1102], 'avalanch': [1115], 'chapter0': [1200], 'chapter1': [1201]}
sys.modules.setdefault('ie_movies_data', mv)
if not SCR:
    sys.modules['ie_movies_data'] = mv
MOV = sys.modules['ie_movies_data'].MOVIES
if not SCR:
    tvd = types.ModuleType('ie_travel_data')
    tvd.AREAS = {'AR2000': {'map': 5051, 'entrances': {'FR1000': [534, 454, 12]}, 'ie_entrances': {'FR1000': [137, 1252]}}}
    sys.modules['ie_travel_data'] = tvd
reset({'AR2000': 5051, 'AR1006': 5018})
c = rt.Ctx(game.party[0], None, 'area_AR1006', 'AR1006')
A.IncrementChapter(c, 'CHPTXT1'); A.SetGlobal(c, 'CHAPTER_BREAK_0', 'GLOBAL', 1)     # classic AR1006
check('IWD prologue break (classic CHPTXT1): CHAPTER stays 0', rt.get_var(c, 'CHAPTER', 'GLOBAL') == 0)
check('prologue screen: intro movie then the prologue slide, one queue',
      game.played and game.played[-1] == list(MOV.get('intro', [])) + list(MOV.get('chapter0', [])), game.played)
A.IncrementChapter(c, '')                                                             # classic ar2100 (Kuldahar)
check('next break (classic ar2100 ""): CHAPTER 1, slide Chapter One',
      rt.get_var(c, 'CHAPTER', 'GLOBAL') == 1 and game.played[-1] == list(MOV.get('chapter1', [])), game.played[-1:])
reset()
A.IncrementChapter(c, 'CHPTXT0'); A.SetGlobal(c, 'Chapter', 'GLOBAL', 0); A.SetGlobal(c, 'CHAPTER_BREAK_0', 'GLOBAL', 1)
A.SetGlobal(c, 'Chapter', 'GLOBAL', 0); A.IncrementChapter(c, 'CHPTXT1'); A.SetGlobal(c, 'Chapter', 'GLOBAL', 1)
check('IWD:EE prologue (CHPTXT0) then ar2100 (Chapter 0, CHPTXT1, Chapter 1): CHAPTER 1, slides 0 then 1',
      rt.get_var(c, 'CHAPTER', 'GLOBAL') == 1 and game.played[-1] == list(MOV.get('chapter1', [])), game.played)
reset(); game.global_vars[990] = 1                                                    # intro already played (heartbeat)
A.IncrementChapter(c, 'CHPTXT1')
check('prologue after the intro already played: slide only', game.played[-1:] == [list(MOV.get('chapter0', []))], game.played)
reset()
for i, pt in enumerate([(137, 1252), (137, 1242), (137, 1252)]):
    A.LeaveAreaLUA(rt.Ctx(game.party[i], None, 'cs', 'AR1000'), 'AR2000', 'LOAD2000', pt, 12)
A.LeaveAreaLUAPanic(c, 'AR2000', 'LOAD2000', (137, 1252), 12)
check('per-PC LeaveAreaLUA (EHHROTHM) -> one party jump to AR2000 (5051)', [t[0] for t in game.teleports] == [5051], game.teleports)
if not SCR:
    check('a jump onto an entrance lands on its (walkable) arrival tile', game.teleports[0] == (5051, 534, 454), game.teleports)
    reset(); A.LeaveAreaLUA(c, 'AR2000', '', (1000, 600), 0)
    check('a jump elsewhere lands on the IE point', game.teleports == [(5051,) + rt.ie_to_tile('AR2000', 1000, 600)], game.teleports)
A.LeaveAreaLUA(c, 'AR9999', '', (1, 1), 0)
check('LeaveAreaLUA to an unconverted area does nothing', len(game.teleports) == 1)

# ---- converted part: the scripts of a real convert -------------------------------------------------------------
LINE = re.compile(r'^\{(\d+)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}\{([^}]*)\}')

def load_dlg(path):
    """ToEE .dlg -> {npc line: (npc effect, [(pc line, test, next, effect)])}"""
    npc, cur = {}, None
    for l in open(path, encoding='cp1252', errors='replace'):
        m = LINE.match(l.strip())
        if not m:
            continue
        n, text, female, iq, test, nxt, eff = m.groups()
        if iq.strip():                     # PC reply (IQ column set)
            if cur is not None:
                npc[cur][1].append((int(n), test.strip(), int(nxt or 0), eff.strip()))
        else:
            cur = int(n); npc[cur] = (eff.strip(), [])
    return npc

class Actor(object):
    def __init__(self, path):
        self.path = path; self.sid = int(os.path.basename(path)[2:7])
        self.mod = __import__(os.path.basename(path)[:-3])
        self.dlg = load_dlg(os.path.join(DLG, os.path.basename(path)[2:-3] + '.dlg'))    # py01187ie_x.py -> 01187ie_x.dlg
        self.obj = Obj(self.mod.IDENT, rt.AREA_MAPS.get(self.mod.AREA, 0))
    def _ev(self, expr):
        if not expr:
            return True
        return eval(expr, vars(self.mod), {'npc': self.obj, 'pc': game.leader})
    def start(self):
        pc = game.leader; pc.dialog = None
        self.mod.san_dialog(self.obj, pc)
        return pc.dialog and pc.dialog[1]
    def talk(self, goal, maxlen=40):
        """one conversation: from the entry line, the shortest reply path to a reply whose effect source matches
        `goal` (regex on the generated ie_a<n> source); run the effects along it. -> (entry line, path) or None"""
        import inspect
        entry = self.start()
        if entry is None:
            return None
        src = lambda e: inspect.getsource(getattr(self.mod, e.split('(')[0])) if e.startswith('ie_a') else e
        prev, todo, seen, hit = {}, [entry], {entry}, None
        while todo and hit is None:
            ln = todo.pop(0)
            for r in self.dlg.get(ln, ('', []))[1]:
                pl, test, nxt, eff = r
                if not self._ev(test):
                    continue
                if eff and re.search(goal, src(eff)):
                    hit = (ln, r); break
                if nxt and nxt not in seen and nxt in self.dlg:
                    seen.add(nxt); prev[nxt] = (ln, r); todo.append(nxt)
        if hit is None:
            return entry, None
        path, ln = [hit], hit[0]
        while ln in prev:
            path.insert(0, prev[ln]); ln = prev[ln][0]
        for ln, (pl, test, nxt, eff) in path:
            if self.dlg[ln][0]:
                self._ev(self.dlg[ln][0])
            if eff:
                self._ev(eff)
        return entry, [p[1][0] for p in path]

if SCR:
    import ie_areas
    rt.AREA_MAPS.update(ie_areas.MAPS)
    try:
        rt._placement.update(dict((k.lower(), v + (1.0, 8428, -4366)) for k, v in ie_areas.PLACEMENTS.items()))
    except Exception:
        pass
    reset()
    ids = {}
    for f in os.listdir(SCR):
        m = re.match(r'py(\d{5})', f)
        if m:
            ids.setdefault(m.group(1), []).append(f)
    clash = dict((k, v) for k, v in ids.items() if len(v) > 1)
    check('one script per id in the install (no stale-file clash)', not clash, clash)
    hroths = sorted(glob.glob(os.path.join(SCR, 'py*ie_hroth*.py')))
    pomabs = sorted(glob.glob(os.path.join(SCR, 'py*ie_pomab*.py')))
    check('Hrothgar and Pomab converted', hroths and pomabs, (hroths, pomabs))
    H = [Actor(p) for p in hroths]; P = Actor(pomabs[0])
    home = next((h for h in H if h.mod.AREA == 'AR1004'), H[0])     # Hrothgar's house (the plan's quest giver)
    for h in H:
        reset()
        e = h.start()
        check('Hrothgar (%s, %s) opens a conversation at a new game' % (os.path.basename(h.path), h.mod.AREA), e is not None, e)
    # Hrothgar's quest states (the autoplayer's 2/3/4/7 failures were the stale scripts): the entry line per state
    for (jp, sq, cq), want in [((0, 0, 0), None), ((2, 0, 0), 190), ((3, 0, 0), 400), ((3, 1, 0), 200), ((3, 2, 0), 210)]:
        reset()
        rt.set_var(None, 'Join_Posse', 'GLOBAL', jp); rt.set_var(None, 'Supply_Quest', 'GLOBAL', sq)
        rt.set_var(None, 'Caravan_Quest', 'GLOBAL', cq)
        if jp == 0:
            rt.set_var(None, 'Know_Hrothgar', 'GLOBAL', 1)
        e = home.start()
        check('Hrothgar quest state Join_Posse=%d Supply_Quest=%d -> line %s' % (jp, sq, want or 'Know_Hrothgar 40'),
              e == (want or 40), e)

    # -- the critical path, from a new game
    reset()
    steps = []
    for i in range(6):                                       # Know_Hrothgar -> Join_Posse 3 (may take a few talks)
        if rt.get_var(None, 'Caravan_Quest', 'GLOBAL') == 1:
            break
        r = home.talk(r'"Caravan_Quest", "GLOBAL", 1\)|"Know_Hrothgar", "GLOBAL", 1\)')
        steps.append(('hrothgar', r))
        if r is None or r[1] is None:
            break
    check('Hrothgar: Join_Posse = 3, Caravan_Quest = 1 (find the Caer-Dinival caravan)',
          rt.get_var(None, 'Join_Posse', 'GLOBAL') == 3 and rt.get_var(None, 'Caravan_Quest', 'GLOBAL') == 1, steps)
    r = home.talk(r'GiveItemCreate\(c, "List"'); steps.append(('hrothgar, caravan not found yet', r))
    check('no List before the caravan is found (Hrothgar line 400 -> 401 "No news")', r and r[1] is None
          and rt.get_var(None, 'Supply_Quest', 'GLOBAL') == 0, r)
    # the caravan: AR1200's trigger region CARATRG1 (Caravan_Quest 2; no fight), entered as runtime/ie_travel does
    import ie_travel
    tv = __import__('ie_travel_data').AREAS
    trig = [t for a_ in tv.values() for t in a_.get('triggers', []) if t.get('module') == 'ie_bcs_caratrg1_area']
    check('AR1200 caravan trigger region converted (CARATRG1)', trig, sorted(tv))
    if trig:
        xs, ys = zip(*trig[0]['poly'])
        ie_travel._inside.clear()
        ie_travel._triggers('AR1200', trig[:1], [game.leader], [(sum(xs) / float(len(xs)), sum(ys) / float(len(ys)))])
    check('entering the caravan site: Caravan_Quest = 2', rt.get_var(None, 'Caravan_Quest', 'GLOBAL') == 2)
    r = home.talk(r'GiveItemCreate\(c, "List"'); steps.append(('hrothgar list', r))
    check('Hrothgar gives the List, Supply_Quest = 1', rt.get_var(None, 'Supply_Quest', 'GLOBAL') == 1
          and T.PartyHasItem(rt.Ctx(game.leader), 'List'), steps[-1:])
    check('the List item is converted (ie_itemmap)', 'list' in __import__('ie_itemmap').ITEMS)
    r = P.talk(r'TakePartyItem\(c, "List"'); steps.append(('pomab', r))
    check('Pomab takes the List, Supply_Quest = 2', rt.get_var(None, 'Supply_Quest', 'GLOBAL') == 2
          and not T.PartyHasItem(rt.Ctx(game.leader), 'List'), r)
    game.teleports[:] = []
    r = home.talk(r'StartCutScene\(c, "EHHrothM"'); steps.append(('hrothgar depart', r))
    check('Hrothgar state 210 -> "Let us be off" -> EHHROTHM', r is not None and r[0] == 210 and r[1], r)
    flush()
    tp = [t for t in game.teleports]
    check('EHHROTHM lands the party on AR2000 (map %s), once' % rt.AREA_MAPS.get('AR2000'),
          [t[0] for t in tp] == [rt.AREA_MAPS.get('AR2000')], tp)
    check('cutscene mode ended after the jump', not ie_cutscene.active())
    # arrival: AR2000's area script (first map tick on the new map)
    game.played[:] = []
    ie_cutscene.STATE['hook'] = 1; ie_cutscene._area.clear()
    ie_cutscene.map_tick(rt.AREA_MAPS.get('AR2000'), 1000); flush()
    first = list(game.played)
    ie_cutscene.map_tick(rt.AREA_MAPS.get('AR2000'), 1000); flush()
    av = MOV.get('avalanch')
    if 'ie_bcs_ar2000_area' in ie_areas.SCRIPTS.values():
        src = open(os.path.join(SCR, 'ie_bcs_ar2000_area.py'), encoding='cp1252').read()
        if 'AVALANCH' in src:      # classic IWD (IWD:EE plays it in EHHROTHM before the jump)
            check('AR2000 first entry plays AVALANCH once', av and first == [av] and game.played == first, game.played)
        check('AR2000_INIT / AR2000_visited set by the area script', rt.get_var(None, 'AR2000_INIT', 'GLOBAL') == 1
              or rt.get_var(None, 'AR2000_visited', 'GLOBAL') == 1)
    else:
        check('AR2000 area script converted', False)
    check('CHAPTER still 0 on AR2000 (Kuldahar raises it)', rt.get_var(None, 'CHAPTER', 'GLOBAL') == 0)
    if tp:
        try:      # the landing tile must be walkable ground (sector Block/FlyOver bits of the converted map)
            import toee_sectors
            K, _ = toee_sectors.load_map_subtiles(os.path.join(core[:-len('_core')], 'maps', 'AR2000'))   # modules/<module>
            u, v = tp[0][1], tp[0][2]
            check('AR2000 landing tile (%d, %d) is walkable' % (u, v), (K[3 * u:3 * u + 3, 3 * v:3 * v + 3] == 0).all())
        except ImportError:
            pass
    for s in steps:
        print('  step %s: entry %s replies %s' % (s[0], s[1] and s[1][0], s[1] and s[1][1]))

print('\nall passed' if not fails else '\n%d FAILED' % len(fails))
sys.exit(1 if fails else 0)
