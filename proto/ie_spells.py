"""Spells: IE SPL -> ToEE / Temple+ spells.

  survey    count every spell of an install by type / level / school, record where each one is used (creature spell
            lists, scripts, dialogs, items, scrolls, other spells) and tabulate effect opcodes
  coverage  apply the authored guidance table (proto/guidance/spells_iwd.json) and report mapping coverage
  convert   write the runtime spell map module (ie_spellmap.py: IE resref -> Temple+ spell enum + caster level rules)

Reads the player's own IE and ToEE/Temple+ installs. Reports and generated modules stay on the player's machine
(they contain names from both games); the repository ships code and the id-only guidance table. See docs/spells.md.

usage:
  python3 ie_spells.py survey <IWD dir> [<IWD:EE dir>] --toee <ToEE dir> [--tp <Temple+ dir>] --md out.md --json out.json
  python3 ie_spells.py coverage <IE dir>... --toee <ToEE dir> [--tp <Temple+ dir>]
  python3 ie_spells.py convert <IE dir> <out dir> --toee <ToEE dir> [--tp <Temple+ dir>]
"""
import os, re, sys, json, struct, argparse, collections
import iefs, iecre, iespl, iescript as S

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDANCE = os.path.join(HERE, 'guidance', 'spells_iwd.json')
OPNAMES = os.path.join(HERE, '..', 'out', 'iesdp_effect_opcodes.json')   # local copy of IESDP opcode titles

# script actions / triggers that name a spell (SPELL.IDS number or, EE, a resref in the string slot)
CAST_ACTIONS = {'spell', 'spellnodec', 'spellpoint', 'spellpointnodec', 'forcespell', 'forcespellpoint',
                'forcespellrange', 'forcespellpointrange', 'reallyforcespell', 'reallyforcespellpoint',
                'reallyforcespelldead', 'applyspell', 'spellres', 'forcespellres', 'reallyforcespellres',
                'applyspellres', 'spellpointres', 'forcespellpointres', 'reallyforcespellpointres', 'spellnodecres'}
GRANT_ACTIONS = {'addspecialability', 'givespell', 'removespell', 'removespellres'}
SPELL_TRIGGERS = {'havespell', 'havespellres', 'haveknownspell', 'havespellparty', 'spellcast', 'spellcastinnate',
                  'spellcastonme', 'spellcastpriest', 'havespellRES'.lower()}


def flavor(game):
    return 'ee' if iefs._ci_find(game.root, 'lang') else 'classic'


def opnames():
    try:
        return json.load(open(OPNAMES))
    except Exception:
        return {}


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


# --------------------------------------------------------------------------------------------- Temple+ side
class TPSpells(object):
    """Spell enum ids, names, schools and class levels from the player's ToEE install (+ Temple+ tpdata)."""

    def __init__(self, toee_root, tp_root=None):
        import toeedata
        td = toeedata.ToEEData(toee_root)
        arcs = [s for s in td.sources]
        if tp_root:
            for n in ('tpgamefiles.dat', 'co8infra.dat'):
                p = os.path.join(tp_root, 'tpdata', n)
                if os.path.isfile(p):
                    arcs.append(toeedata.DatArchive(p))
        names = {}
        se = td.mes('rules/spell_enum.mes')
        for k, v in se.items():
            if 5000 <= k < 6000:
                names[k - 5000] = v
        for a in arcs:
            for f in a.files:
                if f.startswith('rules/spell_enums/') and f.endswith('.mes'):
                    for m in re.finditer(r'\{(\d+)\}\s*\{([^}]*)\}', a.read(f).decode('latin-1')):
                        names.setdefault(int(m.group(1)), m.group(2).strip())
        self.rules = {}
        for a in arcs:
            for f in a.files:
                m = re.match(r'rules/spells/(\d+) - (.*)\.txt$', f)
                if m:
                    self.rules[int(m.group(1))] = (a, f, m.group(2))
        self.spells = {}
        for sid, (a, f, fname) in self.rules.items():
            txt = a.read(f).decode('latin-1')
            school = re.search(r'^School:\s*(\w+)', txt, re.M)
            lv = {m.group(1).lower(): int(m.group(2)) for m in re.finditer(r'^Level:\s*(\w+)\s+(\d+)', txt, re.M)}
            ai = re.search(r'^ai_type:\s*(\w+)', txt, re.M)
            rng = re.search(r'^Range:\s*(\w+)', txt, re.M)
            self.spells[sid] = dict(id=sid, name=names.get(sid, fname), school=(school.group(1).lower() if school else ''),
                                    levels=lv, ai=(ai.group(1) if ai else ''), range=(rng.group(1).lower() if rng else ''),
                                    source=os.path.basename(getattr(a, 'path', '')))
        self.names = names
        self.by_name = {}
        for sid, n in names.items():
            if n.strip():
                self.by_name.setdefault(_norm(n), sid)

    def implemented(self, sid):
        return sid in self.spells

    def label(self, sid):
        s = self.spells.get(sid)
        return s['name'] if s else self.names.get(sid, '?')


# --------------------------------------------------------------------------------------------- adjudication
# 2e -> 3.5 judgement calls for spells (docs/spells.md, SPL-ADJ-n). Every one is a switch; the value here is the
# recommended default. Override per run with --option key=value.
SPELL_OPTIONS = {
    'mapped_rules': '35',          # SPL-ADJ-1  mapped spells run the Temple+ (3.5) spell as-is | 'ie_numbers'
    'match': 'guidance',           # SPL-ADJ-2  authored guidance table, then name match | 'name' only
    'slot_level': 'toee',          # SPL-ADJ-3  memorise at the 3.5 level of the mapped spell | 'ie'
    'summons': 'by_level',         # SPL-ADJ-4  Monster/Animal Summoning N -> Summon Monster/Nature's Ally by spell level | 'by_name' (CM)
    'npc_spells': 'cap_level',     # SPL-ADJ-5  keep the IE memorised list, drop spells above the NPC's 3.5 max level | 'keep_ie' | 'fit_slots'
    'caster_level': 'class',       # SPL-ADJ-6  3.5 class level (CM-converted); monsters/innate: hit dice | 'ie'
    'innate': 'domain_special',    # SPL-ADJ-7  innate/creature abilities as Temple+ spell-like abilities, IE count per day | 'skip'
    'protection_strippers': 'dispel',  # SPL-ADJ-8  spells that strip magical protections -> Dispel Magic / Greater Dispelling | 'new'
    'saves': 'by_effect',          # SPL-ADJ-9  new spells: Fort/Ref/Will from the effect, 2e category as fallback | 'by_category'
    'save_dc': '35',               # SPL-ADJ-10 new spells: DC 10 + level + ability; IE save bonus ignored | 'ie_bonus'
    'durations': 'rounds',         # SPL-ADJ-11 new spells: IE seconds / 6 = rounds (2e turn = 3.5 minute) | 'hours_kept'
    'dice_cap': '35_by_level',     # SPL-ADJ-12 new spells: damage dice capped like 3.5 spells of that level | 'ie'
    'spell_resistance': 'from_ie_flags',  # SPL-ADJ-13 new spells: SR yes when the IE effects can be resisted | 'always'
    'unique_level': 'ie',          # SPL-ADJ-14 IWD-unique spells keep the IE level and list | 'review'
    'schools': 'renamed',          # SPL-ADJ-15 alteration -> transmutation, invocation -> evocation, healing -> conjuration | 'ie'
    'casting_time': 'standard',    # SPL-ADJ-16 standard action; IE casting time 10 (1 round) -> full round | 'ie_speed'
    'script_cast': 'force_known',  # SPL-ADJ-17 ForceSpell/ApplySpell by a caster who lacks the spell: grant it for the cast | 'fail'
    'npc_ai': 'script_first',      # SPL-ADJ-18 a creature whose own IE script casts spells drops the spell entries of its Temple+
                                   #            AI strategy (the script decides; Temple+ AI melees/drinks) | 'strategy' (both)
}
# priest/wizard casting classes in Temple+ spell files (Level: <key> N), in preference order per IE spell type
CLASS_KEYS = {'wizard': ('wiz', 'sor', 'brd'), 'priest': ('clr', 'drd', 'pal', 'rgr')}
DICE_CAP = {1: 5, 2: 5, 3: 10, 4: 10, 5: 15, 6: 15, 7: 20, 8: 20, 9: 20}   # SPL-ADJ-12 (dice, by spell level)
SUMMON_BY_LEVEL = {'wizard': {3: 469, 4: 470, 5: 471, 6: 472, 7: 473, 8: 474, 9: 475},       # Summon Monster III..IX
                   'priest': {1: 476, 2: 477, 3: 478, 4: 479, 5: 480, 6: 481, 7: 482}}       # Summon Nature's Ally I..VII


class SpellMapper(object):
    """IE spell resref -> Temple+ spell, using the authored guidance table for the install's flavour (classic/ee),
    then (SPL-ADJ-2) the player's spell names + the Conversion Manual renames, restricted to implemented spells."""

    def __init__(self, game, tp, options=None, guidance=GUIDANCE):
        self.game, self.tp = game, tp
        self.opt = dict(SPELL_OPTIONS); self.opt.update(options or {})
        self.fl = flavor(game)
        try:
            self.gd = json.load(open(guidance))['flavors'].get(self.fl, {})
        except Exception:
            self.gd = {}
        self.text = _tlk(game)
        self._cache = {}

    def spl(self, ref):
        if ref not in self._cache:
            try:
                self._cache[ref] = iespl.Spl(self.game.read(ref, 'spl'), ref)
            except Exception:
                self._cache[ref] = None
        return self._cache[ref]

    def name(self, ref):
        s = self.spl(ref)
        return self.text(s.name_strref) if s and s.name_strref >= 0 else ''

    def lookup(self, ref):
        ref = ref.lower()
        s = self.spl(ref)
        e = dict(self.gd.get(ref, {})) if self.opt['match'] == 'guidance' else {}
        if not e:
            from ie_creatures import CM_SPELL_RENAMES
            n = self.name(ref).lower().strip()
            sid = self.tp.by_name.get(_norm(CM_SPELL_RENAMES.get(n, n))) if n else None
            if sid is not None and self.tp.implemented(sid):
                e = {'c': 'close', 'toee': sid, 'by': 'name'}
            else:
                e = {'c': 'unmapped'}
        sid = e.get('toee')
        if sid is not None and not self.tp.implemented(sid):
            e = {'c': 'new_srd', 'toee_missing': sid}; sid = None
        ie_type = s.type if s else '?'
        ie_level = s.level if s else 0
        if sid in set(SUMMON_BY_LEVEL['wizard'].values()) | set(SUMMON_BY_LEVEL['priest'].values()) \
                and self.opt['summons'] == 'by_level' and ie_type in SUMMON_BY_LEVEL:
            sid = SUMMON_BY_LEVEL[ie_type].get(ie_level, sid); e['toee'] = sid
        if e.get('c') == 'close' and self.opt['protection_strippers'] == 'new' and sid in (133, 202) \
                and not (s and s.summary()['opcodes'] and 58 in s.summary()['opcodes']):
            e = {'c': 'new_unique'}; sid = None
        lv = dict(self.tp.spells[sid]['levels']) if sid is not None else {}
        return dict(resref=ref, cls=e.get('c'), toee=sid, ie_type=ie_type, ie_level=ie_level, lv=lv,
                    school=s.school if s else '', ai=(self.tp.spells[sid]['ai'] if sid is not None else ''),
                    label=(self.tp.label(sid) if sid is not None else ''))

    def slot_level(self, m, class_key):
        """SPL-ADJ-3: the level a mapped spell is memorised at for a Temple+ class key ('clr', 'wiz', ...)."""
        if self.opt['slot_level'] == 'toee' and class_key in m['lv']:
            return m['lv'][class_key]
        return max(1, min(9, m['ie_level'] or 1))


# --------------------------------------------------------------------------------------------- survey
def _tlk(game):
    p = S.find_tlk(game.root)
    return S.StrrefText(S.Tlk.load(p) if p else None)


def load_spells(game):
    out, bad = {}, []
    for r in game.list('spl'):
        try:
            out[r] = iespl.Spl(game.read(r, 'spl'), r)
        except Exception as e:
            bad.append((r, str(e)[:80]))
    return out, bad


def spell_uses(game, ids, spells, log=print):
    """resref -> Counter(kind -> count). Kinds: creature (known/memorised by a placed/spawned creature, weighted by
    placements), creature_unplaced, creature_innate, script, dialog, item, scroll, subspell, cre_effect."""
    import ie_creatures
    fl = flavor(game)
    refops = iespl.SPELL_REF_OPS['ee' if fl == 'ee' else 'iwd1']
    effops = iespl.EFF_REF_OPS['ee' if fl == 'ee' else 'iwd1']
    uses = collections.defaultdict(collections.Counter)
    where = collections.defaultdict(set)
    sp_ids = ids['spell']
    effcache = {}

    def eff_spell(ref, depth=0):
        if ref in effcache:
            return effcache[ref]
        effcache[ref] = None
        try:
            e = iespl.Eff(game.read(ref, 'eff'), ref).effect
        except Exception:
            return None
        r = None
        if e.opcode in refops and e.resource:
            r = e.resource.lower()
        effcache[ref] = r
        return r

    def from_effects(effs, kind, src):
        for e in effs:
            r = None
            if e.opcode in refops and e.resource:
                r = e.resource.lower()
                k = 'scroll' if (kind == 'item' and e.opcode == 147) else kind
            elif e.opcode in effops and e.resource:
                r = eff_spell(e.resource.lower()); k = kind
            if r and r in spells:
                uses[r][k] += 1; where[r].add(src)

    # creatures
    refs, cwhere, careas, nbcs = ie_creatures.creature_refs(game, ids)
    ncre = 0
    for cr in game.list('cre'):
        try:
            c = iecre.Cre(game.read(cr, 'cre'), cr)
        except Exception:
            continue
        ncre += 1
        placed = refs.get(cr, 0)
        seen = set()
        for m in c.memorized + c.known_spells:
            r = m['resref']
            if r in seen:
                continue
            seen.add(r)
            if m['type'] == 'innate':
                k = 'creature_innate' if placed else 'creature_unplaced'
            else:
                k = 'creature' if placed else 'creature_unplaced'
            uses[r][k] += max(placed, 1); where[r].add(cr + '.cre')
        from_effects(c.effects, 'cre_effect', cr + '.cre')
    # scripts
    def script_calls(calls, kind, src):
        for c in S.walk_calls(calls):
            n = c.name.lower()
            if n in CAST_ACTIONS or n in GRANT_ACTIONS or n in SPELL_TRIGGERS:
                for a in c.args:
                    if isinstance(a, (int, str, S.Sym)) and not isinstance(a, bool):
                        r = S.spell_resref(a, sp_ids)
                        if r and r in spells:
                            uses[r][kind] += 1; where[r].add(src)
                            uses[r]['%s:%s' % (kind, n)] += 1
                            break
    for ref in game.list('bcs'):
        try:
            b = S.Bcs(game.read(ref, 'bcs'), ids, ref)
        except Exception:
            continue
        for trig, resp in b.blocks:
            script_calls(trig, 'script', ref + '.bcs')
            for _, acts in resp:
                script_calls(acts, 'script', ref + '.bcs')
    objn = list(ids['object'].by_name)
    for ref in game.list('dlg'):
        try:
            d = S.Dlg(game.read(ref, 'dlg'), ref)
        except Exception:
            continue
        for s in d.state_triggers + d.trans_triggers + d.actions:
            try:
                script_calls(S.parse_script_text(s, objn), 'dialog', ref + '.dlg')
            except Exception:
                pass
    # items
    nitm = 0
    for ref in game.list('itm'):
        try:
            data = game.read(ref, 'itm')
            if data[:4] != b'ITM ':
                continue
            abil = iespl.itm_abilities(data)
        except Exception:
            continue
        nitm += 1
        for a in abil:
            from_effects(a['effects'], 'item', ref + '.itm')
    # spells referencing spells
    for ref, s in spells.items():
        from_effects([e for _, e in s.all_effects()], 'subspell', ref + '.spl')
    return uses, where, dict(cre=ncre, itm=nitm, bcs=nbcs)


PLAYER_RE = re.compile(r'^(spwi|sppr)([1-9])(\d\d)$')
USE_KINDS = ('creature', 'creature_innate', 'script', 'dialog', 'item', 'scroll')


def hidden_spells(game):
    try:
        t = game.read('hidespl', '2da').decode('latin-1').split()
        return {w.lower() for w in t if re.match(r'^(spwi|sppr)\d{3}$', w, re.I)}
    except Exception:
        return set()


def survey(game, log=print):
    ids = S.IdsSet(game)
    fl = flavor(game)
    text = _tlk(game)
    ops = opnames().get('ee' if fl == 'ee' else 'iwd1', {})
    spells, bad = load_spells(game)
    uses, where, nfiles = spell_uses(game, ids, spells, log)
    hidden = hidden_spells(game)
    # direct use + player-castable; then the closure over sub-spells of used spells
    used = {r for r in spells if any(uses[r].get(k) for k in USE_KINDS)}
    player = set()
    for r, s in spells.items():
        m = PLAYER_RE.match(r)
        if m and r not in hidden and s.type in ('wizard', 'priest') and 1 <= s.level <= 9:
            if s.type == 'priest' or uses[r].get('scroll'):   # priests get every listed spell, wizards need a scroll
                player.add(r)
    top = used | player
    sub = set()
    frontier = list(top)
    refops = iespl.SPELL_REF_OPS['ee' if fl == 'ee' else 'iwd1']
    while frontier:
        r = frontier.pop()
        for _, e in spells[r].all_effects():
            x = e.resource.lower() if e.opcode in refops and e.resource else None
            if x and x in spells and x not in top and x not in sub:
                sub.add(x); frontier.append(x)
    rows = []
    for r, s in sorted(spells.items()):
        sm = s.summary()
        rows.append(dict(resref=r, name=text(s.name_strref) if s.name_strref >= 0 else '', **sm,
                         uses=dict(uses[r]), used=r in used, player=r in player, subspell_of_used=r in sub,
                         hidden=r in hidden))
    by = lambda keyf, filt=lambda x: True: dict(collections.Counter(keyf(x) for x in rows if filt(x)).most_common())
    opc_all, opc_used, opc_sp = collections.Counter(), collections.Counter(), collections.Counter()
    for r, s in spells.items():
        seen = set()
        for _, e in s.all_effects():
            opc_all[e.opcode] += 1
            if r in top or r in sub:
                opc_used[e.opcode] += 1
                seen.add(e.opcode)
        for o in seen:
            opc_sp[o] += 1
    opcodes = [dict(opcode=o, name=ops.get(str(o), ops.get(o, '?')), effects=opc_all[o], effects_used=opc_used[o],
                    spells_used=opc_sp[o]) for o in sorted(opc_all, key=lambda o: (-opc_used[o], -opc_all[o]))]
    std = lambda x: x['type'] in ('wizard', 'priest') and bool(PLAYER_RE.match(x['resref']))
    return dict(
        flavor=fl, spl_files=len(spells), unreadable=bad, files_scanned=nfiles,
        by_type=by(lambda x: x['type']),
        by_type_level=by(lambda x: '%s %d' % (x['type'], x['level'])),
        standard_by_type_level=by(lambda x: '%s %d' % (x['type'], x['level']), std),
        standard_by_school=by(lambda x: x['school'], std),
        by_school=by(lambda x: x['school'], lambda x: x['type'] in ('wizard', 'priest')),
        priest_class=by(lambda x: x['priest_class'], lambda x: x['type'] == 'priest' and std(x)),
        used=len(used), player=len(player), used_or_player=len(top), subspells_of_used=len(sub),
        used_by_kind={k: sum(1 for r in spells if uses[r].get(k)) for k in USE_KINDS + ('creature_unplaced', 'subspell', 'cre_effect')},
        used_by_type=by(lambda x: x['type'], lambda x: x['used'] or x['player']),
        script_action_uses=dict(sum((collections.Counter({k.split(':', 1)[1]: v for k, v in uses[r].items()
                                                          if k.startswith('script:')}) for r in spells),
                                    collections.Counter()).most_common()),
        opcodes=opcodes, spells=rows)


def survey_md(reps):
    L = ['# IE spell survey (local, do not distribute)', '']
    for r in reps:
        L += ['## %s: %d SPL files' % (r['flavor'], r['spl_files']), '',
              'Scanned: %(cre)d CRE, %(itm)d ITM, %(bcs)d BCS.' % r['files_scanned'], '',
              '* by type: %s' % r['by_type'],
              '* standard player spells (SPWI/SPPR) by type and level: %s' % r['standard_by_type_level'],
              '* standard player spells by school: %s' % r['standard_by_school'],
              '* priest spells, class restriction: %s' % r['priest_class'],
              '* **used** (creature lists, scripts, dialogs, items, scrolls): %d; player-castable: %d; union: %d; '
              'sub-spells reached from them: %d' % (r['used'], r['player'], r['used_or_player'], r['subspells_of_used']),
              '* spells used per source: %s' % r['used_by_kind'],
              '* used/player by type: %s' % r['used_by_type'],
              '* script spell actions/triggers (calls): %s' % r['script_action_uses'], '',
              '### Effect opcodes (top 60 by use in used/player spells)', '',
              '| opcode | IESDP name | effects (all) | effects (used) | used spells containing |', '|---|---|---|---|---|']
        for o in r['opcodes'][:60]:
            L.append('| %(opcode)d | %(name)s | %(effects)d | %(effects_used)d | %(spells_used)d |' % o)
        L += ['', '### Most used spells', '', '| resref | name | type | lvl | school | uses |', '|---|---|---|---|---|---|']
        score = lambda x: sum(v for k, v in x['uses'].items() if ':' not in k and k in USE_KINDS)
        for x in sorted(r['spells'], key=lambda x: -score(x))[:80]:
            if score(x):
                L.append('| %s | %s | %s | %d | %s | %s |' % (x['resref'], x['name'], x['type'], x['level'], x['school'],
                         {k: v for k, v in x['uses'].items() if ':' not in k}))
        L.append('')
    return '\n'.join(L) + '\n'


# --------------------------------------------------------------------------------------------- coverage / convert
CLASSES = ('direct', 'close', 'new_srd', 'new_unique', 'innate', 'meta', 'sub', 'unmapped')


def coverage(rep, mapper):
    """Mapping coverage for one survey report: by class for player spells, used spells, and use instances."""
    def cnt(rows, weight=lambda x: 1):
        c = collections.Counter()
        for x in rows:
            m = mapper.lookup(x['resref'])
            k = m['cls'] or 'unmapped'
            if k == 'innate' and m['toee'] is not None:
                k = 'innate_mapped'
            c[k] += weight(x)
        return dict(c.most_common())
    w = lambda x: sum(v for k, v in x['uses'].items() if ':' not in k and k in USE_KINDS)
    std = [x for x in rep['spells'] if x['player']]
    used = [x for x in rep['spells'] if x['used']]
    cre = [x for x in rep['spells'] if x['uses'].get('creature') or x['uses'].get('creature_innate')]
    scr = [x for x in rep['spells'] if x['uses'].get('script') or x['uses'].get('dialog')]
    return dict(flavor=rep['flavor'], player=cnt(std), used=cnt(used), used_weighted=cnt(used, w),
                creature_lists=cnt(cre), scripts=cnt(scr, lambda x: x['uses'].get('script', 0) + x['uses'].get('dialog', 0)))


def pct(c, keys=('direct', 'close')):
    tot = sum(v for k, v in c.items() if k not in ('sub', 'meta'))
    return round(100.0 * sum(c.get(k, 0) for k in keys) / tot, 1) if tot else 0.0


def convert(game, tp, out, options=None):
    """Write <out>/ie_spellmap.py for the runtime: every spell the install has -> Temple+ spell + levels."""
    mp = SpellMapper(game, tp, options)
    rows = {}
    for r in game.list('spl'):
        m = mp.lookup(r)
        if m['ie_type'] == '?':
            continue
        rows[r] = dict(t=m['toee'], c=m['cls'], ty=m['ie_type'], l=m['ie_level'], lv=m['lv'], ai=m['ai'],
                       n=m['label'])
    os.makedirs(out, exist_ok=True)
    py = ["# Generated by ie2toee ie_spells.py from the player's own IE + Temple+ installs. Do not distribute.",
          'FLAVOR = %r' % mp.fl, 'OPTIONS = %r' % mp.opt, 'MAP = {']
    for r in sorted(rows):
        py.append('    %r: %r,' % (r, rows[r]))
    py.append('}')
    open(os.path.join(out, 'ie_spellmap.py'), 'w').write('\n'.join(py) + '\n')
    return rows


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    s1 = sub.add_parser('survey'); s1.add_argument('games', nargs='+'); s1.add_argument('--md', required=True)
    s1.add_argument('--json')
    s2 = sub.add_parser('coverage'); s2.add_argument('--survey', required=True); s2.add_argument('--games', nargs='+', required=True)
    s2.add_argument('--toee', required=True); s2.add_argument('--tp'); s2.add_argument('--json')
    s2.add_argument('--option', action='append', default=[])
    s3 = sub.add_parser('convert'); s3.add_argument('game'); s3.add_argument('out'); s3.add_argument('--toee', required=True)
    s3.add_argument('--tp'); s3.add_argument('--option', action='append', default=[])
    a = ap.parse_args()
    if a.cmd in ('coverage', 'convert'):
        tp = TPSpells(a.toee, a.tp)
        opts = dict(kv.split('=', 1) for kv in a.option)
    if a.cmd == 'coverage':
        reps = json.load(open(a.survey)); res = []
        for g in a.games:
            game = iefs.IEGame(g); fl = flavor(game)
            rep = next(r for r in reps if r['flavor'] == fl)
            cv = coverage(rep, SpellMapper(game, tp, opts)); res.append(cv)
            print(fl)
            for k in ('player', 'used', 'used_weighted', 'creature_lists', 'scripts'):
                print('  %-15s direct+close %5.1f%%  (+innate mapped %5.1f%%)  %s' % (
                    k, pct(cv[k]), pct(cv[k], ('direct', 'close', 'innate_mapped')), cv[k]))
        if a.json:
            json.dump(res, open(a.json, 'w'), indent=1)
    elif a.cmd == 'convert':
        rows = convert(iefs.IEGame(a.game), tp, a.out, opts)
        print(len(rows), dict(collections.Counter(r['c'] for r in rows.values())))
    elif a.cmd == 'survey':
        reps = [survey(iefs.IEGame(g)) for g in a.games]
        open(a.md, 'w').write(survey_md(reps))
        if a.json:
            json.dump(reps, open(a.json, 'w'), indent=1, default=list)
        for r in reps:
            print(r['flavor'], {k: r[k] for k in ('spl_files', 'by_type', 'used', 'player', 'used_or_player',
                                                  'subspells_of_used', 'used_by_kind')})
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
