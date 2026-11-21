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
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
INST = sys.argv[1] if len(sys.argv) > 1 else None
SCR = DLG = None
if INST:
    cores = [d for d in glob.glob(os.path.join(INST, 'modules', '*_core'))
             if os.path.isfile(os.path.join(d, 'scr', 'ie_areas.py'))]
    iwd = os.path.join(INST, 'modules', 'IWD_core')
    if iwd in cores:
        core = iwd
    elif len(cores) == 1:
        core = cores[0]
    else:
        sys.exit('%s: could not identify the converted IWD module among %r' % (INST, cores))
    SCR, DLG = os.path.join(core, 'scr'), os.path.join(core, 'dlg')
sys.path[:0] = [os.path.join(HERE, 'runtime')] + ([SCR] if SCR else [])   # the repo runtime + the generated modules

# ---- mock Temple+ ---------------------------------------------------------------------------------------------
from offline_game import install, location_from_axis, location_to_axis

game = install()
import ie_runtime as rt
from ie_runtime import T, A
import ie_cutscene
rt._real = lambda: game.t

fails = []
def check(name, ok, info=''):
    print('%s %s%s' % ('PASS' if ok else 'FAIL', name, ('  [%r]' % (info,)) if info and not ok else ''))
    if not ok:
        fails.append(name)

def flush(n=500):
    """Advance simulated time until the script queue empties or the tick budget is spent."""
    for _ in range(n):
        if not game.events:
            return
        game.tick()

def reset(maps=None):
    game.reset()
    if maps:
        rt.AREA_MAPS.update(maps)
    game.party.extend(game.spawn(name) for name in ('pc1', 'pc2', 'pc3'))

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
from unittest.mock import patch
from ie_dialogue import xplist_rewards
class QuestXPTable:
    def read(self, name, ext):
        assert (name, ext) == ('xplist', '2da')
        return b'2DA V1.0\n0\nCOMMENT 0 1 2\nexample cmt P_300 P_600 350\nfixed cmt P_900 P_900 P_900'

with patch.dict(rt.XP2DA, xplist_rewards(QuestXPTable()), clear=True):
    game.party[1].abilities['level_fighter'] = 2
    A.AddXP2DA(c, 'example')
    A.AddXP2DA(c, 'FIXED')
    A.AddXP2DA(c, 'missing')
    check('shared and personal XP by level, including fixed rows and unknown labels',
          [pc.experience for pc in game.party] == [500, 650, 500])
    rt.XP2DA['LEGACY'] = 60
    A.AddXP2DA(c, 'legacy')
    check('existing scalar XP tables remain readable', game.party[0].experience == 520)
giver = game.spawn('reward giver')
giver.money_adj(700)
reward_context = rt.Ctx(giver, game.party[0])
A.GivePartyGold(reward_context, 5)
A.GivePartyGold(reward_context, 5)
check('quest giver pays from available gold once', (giver.money_get(), game.party[0].money_get()) == (0, 700))
A.GivePartyGold(rt.Ctx(game.party[0]), 2)
A.GivePartyGold(rt.Ctx(None, None, 'area_AR1000'), 3)
check('area rewards and party-owned gold use the party purse once', game.party[0].money_get() == 1000)
for difficulty in range(1, 6):
    with patch.dict(os.environ, IE2TOEE_DIFFICULTY=str(difficulty)):
        check('difficulty %d, Normal and Hard encounter gates' % difficulty,
              T.Difficulty(c, difficulty) and T.DifficultyLT(c, 4) == (difficulty < 4)
              and T.DifficultyGT(c, 2) == (difficulty > 2))
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
        self.obj = game.spawn(self.mod.IDENT, rt.AREA_MAPS.get(self.mod.AREA, 0))
        self.obj.script_mod = self.mod
    def _ev(self, expr):
        if not expr:
            return True
        return eval(expr, vars(self.mod), {'npc': self.obj, 'pc': game.leader})
    def start(self):
        game.objects[self.obj.id] = self.obj
        if game.area_scripts and self.obj.map and self.obj.map != game.leader.map:
            game.fade_and_teleport(0, 0, 0, self.obj.map, *location_to_axis(self.obj.location))
            game.tick()
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
    reset()
    ambiguous = False
    for directory, pattern, kind in ((SCR, r'py(\d{5}).*\.py', 'script'), (DLG, r'(\d{5}).*\.dlg', 'dialogue')):
        ids = {}
        for filename in sorted(os.listdir(directory)):
            match = re.fullmatch(pattern, filename, re.I)
            if match and os.path.isfile(os.path.join(directory, filename)):
                ids.setdefault(match[1], []).append(filename)
        clashes = {key: names for key, names in ids.items() if len(names) > 1}
        check('one %s per id in %s' % (kind, directory), not clashes, clashes)
        if clashes:
            ambiguous = True
    if ambiguous:
        sys.exit('Chapter path requires unambiguous numbered scripts and dialogues.')
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

    # -- the new-game opening in Winter's Cradle (AR1006): the prologue screen (after the intro), then Hrothgar
    #    greets the party: IWD:EE through AR1006's area script (CDOpeningCut -> cutscene EHHROTHT), classic through
    #    Hrothgar's own script EHHROTHT (cutscene inline, ends in his dialogue)
    reset()
    cradle = next((h for h in H if h.mod.AREA == 'AR1006'), None)
    for o in game.party:
        o.map = rt.AREA_MAPS.get('AR1006')
    if cradle:
        game.objects[cradle.obj.id] = cradle.obj
        rt.bind(cradle.obj, cradle.mod.IDENT, 'AR1006')
    game.enable_area_scripts()
    for i in range(8):
        game.tick(); flush()
        if cradle and hasattr(cradle.mod, 'san_heartbeat') and not game.leader.dialog:
            try:
                cradle.mod.san_heartbeat(cradle.obj, None); flush()
            except Exception as e:
                print('  (Hrothgar heartbeat: %r)' % e)
        for _ in range(10):
            game.tick()
    check('new game: AR1006 area script ran the prologue break (CHAPTER_BREAK_0 = 1, CHAPTER 0)',
          rt.get_var(None, 'CHAPTER_BREAK_0', 'GLOBAL') == 1 and rt.get_var(None, 'CHAPTER', 'GLOBAL') == 0)
    check('new game: intro movie + prologue slide played first (skippable: Temple+ movie player)',
          game.played and game.played[0] == list(MOV.get('intro', [])) + list(MOV.get('chapter0', [])), game.played)
    d = game.leader.dialog
    check("new game: Hrothgar greets the party (%s)" % ('IWD:EE cutscene EHHROTHT' if os.path.isfile(
          os.path.join(SCR, 'ie_bcs_ehhrotht_area.py')) else 'his script EHHROTHT'),
          cradle is not None and d is not None and d[0] is cradle.obj, d)
    check('new game: cutscene mode over after the greeting', not ie_cutscene.active())

    # -- the critical path, from a new game
    reset()
    game.enable_area_scripts()
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
    tv = __import__('ie_travel_data').AREAS
    trig = [t for a_ in tv.values() for t in a_.get('triggers', []) if t.get('module') == 'ie_bcs_caratrg1_area']
    check('AR1200 caravan trigger region converted (CARATRG1)', trig, sorted(tv))
    if trig:
        xs, ys = zip(*trig[0]['poly'])
        start = (int(min(xs)) - 5, int(min(ys)) - 5)
        dest = (round(sum(xs) / len(xs)), round(sum(ys) / len(ys)))
        game.fade_and_teleport(0, 0, 0, rt.AREA_MAPS['AR1200'], *start)
        game.tick()
        check('caravan stays undiscovered outside the trigger', rt.get_var(None, 'Caravan_Quest', 'GLOBAL') == 1)
        game.leader.run_to(location_from_axis(*dest))
        for _ in range(max(abs(dest[0] - start[0]), abs(dest[1] - start[1]))):
            game.tick()
    check('entering the caravan site: Caravan_Quest = 2', rt.get_var(None, 'Caravan_Quest', 'GLOBAL') == 2)
    r = home.talk(r'GiveItemCreate\(c, "List"'); steps.append(('hrothgar list', r))
    check('Hrothgar gives the List, Supply_Quest = 1', rt.get_var(None, 'Supply_Quest', 'GLOBAL') == 1
          and T.PartyHasItem(rt.Ctx(game.leader), 'List'), steps[-1:])
    check('the List item is converted (ie_itemmap)', 'list' in __import__('ie_itemmap').ITEMS)
    r = P.talk(r'TakePartyItem\(c, "List"'); steps.append(('pomab', r))
    check('Pomab takes the List, Supply_Quest = 2', rt.get_var(None, 'Supply_Quest', 'GLOBAL') == 2
          and not T.PartyHasItem(rt.Ctx(game.leader), 'List'), r)
    # Stage the journey from Pomab's shop back to Hrothgar's house.
    game.fade_and_teleport(0, 0, 0, home.obj.map, *location_to_axis(home.obj.location))
    game.tick()
    game.teleports[:] = []
    game.played[:] = []
    r = home.talk(r'StartCutScene\(c, "EHHrothM"'); steps.append(('hrothgar depart', r))
    check('Hrothgar state 210 -> "Let us be off" -> EHHROTHM', r is not None and r[0] == 210 and r[1], r)
    flush()
    tp = [t for t in game.teleports]
    check('EHHROTHM lands the party on AR2000 (map %s), once' % rt.AREA_MAPS.get('AR2000'),
          [t[0] for t in tp] == [rt.AREA_MAPS.get('AR2000')], tp)
    check('cutscene mode ended after the jump', not ie_cutscene.active())
    # arrival: AR2000's area script (first map tick on the new map)
    game.tick(); flush()
    first = list(game.played)
    game.tick(); flush()
    av = MOV.get('avalanch')
    if 'ie_bcs_ar2000_area' in ie_areas.SCRIPTS.values():
        src = open(os.path.join(SCR, 'ie_bcs_ar2000_area.py'), encoding='cp1252').read()
        if 'AVALANCH' in src:      # classic IWD (IWD:EE plays it in EHHROTHM before the jump)
            check('AR2000 first entry plays AVALANCH once', av and first.count(av) == 1 and game.played == first, game.played)
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
