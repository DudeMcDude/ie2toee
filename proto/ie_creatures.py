"""IE creatures (CRE) -> ToEE/Temple+ critters: survey + converter (prototype).

Runs on the player's machine against their own IE and ToEE installs. Everything it writes (names, stats, reports) is
derived from the games and stays local; the only shipped inputs are this code, ie_rules.py and the authored guidance
table proto/guidance/creatures_iwd.json.

  python3 ie_creatures.py survey  <IE dir> <out.md> [--json out.json]
  python3 ie_creatures.py convert <IE dir> <ToEE dir> <out dir> --area AR1000 [--name-base 27000] [--dialogue DIR]

convert writes  <out>/ie_creatures_<area>.py  (spawn specs for runtime/ie_critters.py)
                <out>/modules/ToEE/mes/description/ie2toee_<area>.mes  (creature names from the player's TLK)
                <out>/<area>_creatures.json  (full conversion report incl. every judgement applied)
"""
import os, re, sys, json, argparse, collections
import iefs, iecre, iescript as S, ieformats as F, ie_rules as R

HERE = os.path.dirname(os.path.abspath(__file__))
GUIDANCE = os.path.join(HERE, 'guidance', 'creatures_iwd.json')


def flavor(game):
    """'ee' for Enhanced Edition installs (lang/ folder, CRE V1.0), else 'classic'."""
    return 'ee' if iefs._ci_find(game.root, 'lang') else 'classic'


def anim_names(game):
    """ANIMATE.IDS with full names (names may contain spaces in classic IWD). Local display only."""
    out = {}
    try:
        txt = game.read('animate', 'ids').decode('latin-1')
    except Exception:
        return out
    for line in txt.splitlines():
        m = re.match(r'\s*(0x[0-9A-Fa-f]+|\d+)\s+(.+?)\s*$', line)
        if m:
            out.setdefault(int(m.group(1), 0), m.group(2))
    return out


class Guidance(object):
    def __init__(self, path=GUIDANCE):
        self.g = json.load(open(path))
        self.by_anim = {'classic': {}, 'ee': {}}
        for f in self.g['families']:
            for fl in ('classic', 'ee'):
                for h in f.get(fl, []):
                    self.by_anim[fl].setdefault(int(h, 16), f)
        cb = self.g['class_based']
        self.class_ranges = [(int(a, 16), int(b, 16)) for a, b in cb['anim_ranges']]
        self.cb = cb

    def family(self, fl, anim):
        f = self.by_anim[fl].get(anim)
        if f:
            return f
        if any(a <= anim <= b for a, b in self.class_ranges):
            return {'id': 'class_based', 'label': 'Class-based humanoid', 'track': 'class', 'status': 'match'}
        return None


# ----------------------------------------------------------------------------------------------------- survey
CREATE_ACTIONS = re.compile(r'^CreateCreature', re.I)


def creature_refs(game, ids):
    """Every creature an install uses: ARE actors, spawn points, rest spawns, CreateCreature* in BCS and DLG.
    Returns (refs: Counter cre -> placements, where: cre -> Counter of source kinds, areas: cre -> set, nbcs)."""
    refs = collections.Counter()          # cre resref -> placements
    where = collections.defaultdict(collections.Counter)   # cre -> source kind counts
    areas = collections.defaultdict(set)
    for ar in game.list('are'):
        try:
            a = F.Are(game.read(ar, 'are'))
        except Exception:
            continue
        for act in a.actors:
            if act['cre']:
                r = act['cre'].lower(); refs[r] += 1; where[r]['area actor'] += 1; areas[r].add(ar.upper())
        for sp in a.spawn_points:
            for c in sp['creatures']:
                refs[c.lower()] += 1; where[c.lower()]['spawn point'] += 1; areas[c.lower()].add(ar.upper())
        for c in a.rest_spawns:
            refs[c.lower()] += 1; where[c.lower()]['rest spawn'] += 1; areas[c.lower()].add(ar.upper())
    nbcs = 0
    for ref in game.list('bcs'):
        try:
            b = S.Bcs(game.read(ref, 'bcs'), ids, ref)
        except Exception:
            continue
        nbcs += 1
        for _, resp in b.blocks:
            for _, acts in resp:
                for c in S.walk_calls(acts):
                    if CREATE_ACTIONS.match(c.name):
                        s = next((x for x in c.args if isinstance(x, str) and x), None)
                        if s:
                            refs[s.lower()] += 1; where[s.lower()]['script CreateCreature'] += 1
                            if ref.upper().startswith('AR'):
                                areas[s.lower()].add(ref.upper()[:6])
    for ref in game.list('dlg'):
        try:
            d = S.Dlg(game.read(ref, 'dlg'), ref)
        except Exception:
            continue
        for s in d.actions:
            try:
                calls = S.parse_script_text(s)
            except Exception:
                continue
            for c in S.walk_calls(calls):
                if CREATE_ACTIONS.match(c.name):
                    a0 = next((x for x in c.args if isinstance(x, str) and x), None)
                    if a0:
                        refs[a0.lower()] += 1; where[a0.lower()]['dialog CreateCreature'] += 1
    return refs, where, areas, nbcs


def survey(game, log=print):
    ids = S.IdsSet(game)
    fl = flavor(game)
    gd = Guidance()
    names = anim_names(game)
    refs, where, areas, nbcs = creature_refs(game, ids)
    all_cre = set(game.list('cre'))
    fams = collections.defaultdict(lambda: {'placements': 0, 'cres': set(), 'anims': collections.Counter()})
    anims = collections.defaultdict(lambda: {'placements': 0, 'cres': set()})
    missing_cre, rows = [], []
    for r, n in refs.items():
        if r not in all_cre:
            missing_cre.append(r); continue
        try:
            c = iecre.Cre(game.read(r, 'cre'), r)
        except Exception as e:
            missing_cre.append(r); continue
        f = gd.family(fl, c.animation)
        fid = f['id'] if f else 'unmapped:%04x' % c.animation
        fams[fid]['placements'] += n; fams[fid]['cres'].add(r); fams[fid]['anims'][c.animation] += n
        fams[fid]['status'] = f['status'] if f else 'unmapped'
        fams[fid]['label'] = f['label'] if f else names.get(c.animation, '?')
        anims[c.animation]['placements'] += n; anims[c.animation]['cres'].add(r)
        rows.append((r, n, c))
    unused = sorted(all_cre - set(refs))
    rep = {'flavor': fl, 'cre_files': len(all_cre), 'referenced_cres': len(rows), 'placements': sum(n for _, n, _ in rows),
           'unreferenced_cres': len(unused), 'missing_refs': sorted(missing_cre), 'bcs_parsed': nbcs,
           'by_source': dict(sum((where[r] for r, _, _ in rows), collections.Counter())),
           'families': {k: {'label': v['label'], 'status': v['status'], 'placements': v['placements'],
                            'cres': len(v['cres']),
                            'anims': ['%04x %s x%d' % (a, names.get(a, '?'), m) for a, m in v['anims'].most_common()]}
                        for k, v in sorted(fams.items(), key=lambda kv: -kv[1]['placements'])},
           'anims': len(anims)}
    # coverage by status (placements and distinct CREs)
    cov = collections.Counter(); covc = collections.Counter()
    for k, v in fams.items():
        st = v['status']
        if k == 'class_based':
            st = 'class-based'
        cov[st] += v['placements']; covc[st] += len(v['cres'])
    rep['coverage_placements'] = dict(cov); rep['coverage_cres'] = dict(covc)
    # track B class mix
    tb = collections.Counter()
    for r, n, c in rows:
        f = gd.family(fl, c.animation)
        if f and f.get('track') == 'class':
            tb[ids['class'].name(c.cls, str(c.cls))] += n
    rep['class_based_classes'] = dict(tb.most_common())
    xs = collections.Counter()
    for r, n, c in rows:
        if c.str == 18 and c.str_bonus > 0 or c.str > 18:
            xs['%d/%02d' % (c.str, c.str_bonus % 100) if c.str == 18 else str(c.str)] += 1
    rep['exceptional_strength_cres'] = dict(xs.most_common())
    rep['magic_resistance_cres'] = sum(1 for _, _, c in rows if c.resist['magic'] > 0)
    rep['spellcaster_cres'] = sum(1 for _, _, c in rows if c.memorized or c.known_spells)
    rep['multiclass_cres'] = sum(1 for _, _, c in rows if '_' in (ids['class'].name(c.cls) or '') and
                                 len(R.split_class(ids['class'].name(c.cls))) > 1)
    return rep


def survey_md(reps):
    L = ['# IWD creature survey (local, derived from the player\'s installs: do not commit)\n']
    for rep in reps:
        L.append('## %s install\n' % rep['flavor'])
        L.append('- CRE files: %d; referenced by areas/scripts/dialogs: %d (%d placements/call sites); unreferenced: %d; '
                 'dangling refs: %d' % (rep['cre_files'], rep['referenced_cres'], rep['placements'],
                                        rep['unreferenced_cres'], len(rep['missing_refs'])))
        L.append('- sources: %s' % ', '.join('%s %d' % kv for kv in sorted(rep['by_source'].items())))
        L.append('- model coverage by placements: %s' % ', '.join('%s %d' % kv for kv in sorted(rep['coverage_placements'].items())))
        L.append('- model coverage by distinct CREs: %s' % ', '.join('%s %d' % kv for kv in sorted(rep['coverage_cres'].items())))
        L.append('- class-based (track B) placements by IE class: %s' % ', '.join('%s %d' % kv for kv in rep['class_based_classes'].items()))
        L.append('- exceptional strength CREs: %s; magic resistance: %d; spellcasters: %d; multiclass: %d\n' % (
            rep['exceptional_strength_cres'], rep['magic_resistance_cres'], rep['spellcaster_cres'], rep['multiclass_cres']))
        L.append('| family | label | model status | placements | CREs | animation ids |')
        L.append('|---|---|---|---:|---:|---|')
        for k, v in rep['families'].items():
            L.append('| %s | %s | %s | %d | %d | %s |' % (k, v['label'], v['status'], v['placements'], v['cres'],
                                                         '; '.join(v['anims'][:6])))
        L.append('')
    return '\n'.join(L) + '\n'


# ----------------------------------------------------------------------------------------------------- convert
class ToEEIndex(object):
    def __init__(self, td):
        import toeedata
        self.td = td
        self.protos = td.protos()
        self.meshes = td.mes('art/meshes/meshes.mes')
        self.by_model = collections.defaultdict(list)
        for pid, r in sorted(self.protos.items()):
            if r[1] == 'obj_t_npc' and r[34].strip().isdigit():
                self.by_model[int(r[34])].append(pid)
        se = td.mes('rules/spell_enum.mes')
        self.spells = {}
        for k, v in se.items():
            if 5000 <= k < 6000:
                self.spells[_norm(v)] = k - 5000

    def resolve(self, fam, co8=True):
        model = fam.get('model')
        if co8 and fam.get('co8_model') and fam['co8_model'] in self.meshes and self.by_model.get(fam['co8_model']):
            model = fam['co8_model']
            return self.by_model[model][0], model, 'co8'
        p = fam.get('proto')
        if p and p in self.protos and (model is None or self.protos[p][34].strip() == str(model)):
            return p, int(self.protos[p][34]), 'proto'
        if model and self.by_model.get(model):
            return self.by_model[model][0], model, 'by-model'
        return None, None, 'missing'

    def col(self, pid, c):
        return self.protos[pid][c] if pid in self.protos else ''


def _norm(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


# CM p.15 "Renamed Spells" (old 2e name -> 3e name), the subset relevant to IE spell lists
CM_SPELL_RENAMES = {
    'animal summoning i': "summon nature's ally i", 'animal summoning ii': "summon nature's ally ii",
    'animal summoning iii': "summon nature's ally iii", 'armor': 'mage armor', 'blindness': 'blindness/deafness',
    'cause light wounds': 'inflict light wounds', 'cause serious wounds': 'inflict serious wounds',
    'cause critical wounds': 'inflict critical wounds', 'cure disease': 'remove disease', 'detect invisibility': 'see invisibility',
    'domination': 'dominate person', 'free action': 'freedom of movement', 'hold undead': 'halt undead',
    'magic resistance': 'spell resistance', 'monster summoning i': 'summon monster i', 'monster summoning ii': 'summon monster ii',
    'monster summoning iii': 'summon monster iii', 'monster summoning iv': 'summon monster iv',
    'monster summoning v': 'summon monster v', 'monster summoning vi': 'summon monster vi', 'monster summoning vii': 'summon monster vii',
    'protection from evil 10 radius': 'magic circle against evil', 'resist fire/resist cold': 'resist energy',
    'slow poison': 'delay poison', 'spiritual hammer': 'spiritual weapon', 'strength': "bull's strength",
    'chant': 'prayer', 'fog cloud': 'obscuring mist', 'infravision': 'darkvision', 'death fog': 'acid fog',
    'remove fear': 'remove fear', 'resist fire': 'resist energy', 'resist cold': 'resist energy',
}


# SRD 3.5 racial ability adjustments (STR DEX CON INT WIS CHA) as Temple+ applies them
RACE_ABILITY_ADJ = {'ELF': (0, 2, -2, 0, 0, 0), 'HALF_ELF': (0,) * 6, 'DWARF': (0, 0, 2, 0, 0, -2),
                    'GNOME': (-2, 0, 2, 0, 0, 0), 'HALFLING': (-2, 2, 0, 0, 0, 0), 'HALF_ORC': (2, 0, 0, -2, 0, -2)}


class Converter(object):
    def __init__(self, game, toee, options=None, guidance=None, tp_root=None):
        self.game, self.toee = game, toee
        self.tp_root = tp_root
        self._spells = None
        self.fl = flavor(game)
        self.ids = S.IdsSet(game)
        self.gd = guidance or Guidance()
        self.opt = dict(R.DEFAULT_OPTIONS, **(options or {}))
        p = S.find_tlk(game.root)
        self.text = S.StrrefText(S.Tlk.load(p) if p else None)
        self._itm = {}

    # IE difficulty levels (DIFFLEV.IDS): 1 easiest, 2 easy, 3 normal, 4 hard, 5 hardest/insane. IWD:EE gates extra
    # actors with tiny scripts (EFDELNOR/EFDELHRD/EFDELINS/EFDELEAS/EFDELDEF) of the form
    #   IF DifficultyLT(4) !See([PC]) THEN DestroySelf()   -> the actor only exists at difficulty >= 4 (docs/creatures.md)
    def difficulty_gate(self, refs):
        """{'levels': [allowed difficulty levels], 'script': resref, 'cond': trigger text} for an actor whose scripts
        destroy it at some difficulty levels; None when it exists at every level. Heart of Fury is a separate game mode
        (stat boost), not an actor gate."""
        if not hasattr(self, '_dg'):
            self._dg = {}
        best = None
        for ref in refs:
            ref = ref.lower()
            if ref not in self._dg:
                self._dg[ref] = None
                try:
                    b = S.Bcs(self.game.read(ref, 'bcs'), self.ids, ref) if self.game.find(ref, 'bcs') else None
                except Exception:
                    b = None
                for trig, resp in (b.blocks if b else []):
                    if not any(c.name.lower() == 'destroyself' for _, acts in resp for c in S.walk_calls(acts)):
                        continue
                    lv = set(range(1, 6)); hit = False
                    for t in trig:
                        n = t.name.lower(); v = next((a for a in t.args if isinstance(a, int)), None)
                        if not n.startswith('difficulty') or v is None:
                            continue
                        f = {'difficulty': lambda x: x == v, 'difficultylt': lambda x: x < v,
                             'difficultygt': lambda x: x > v}.get(n)
                        if f is None:
                            continue
                        hit = True; m = {x for x in lv if f(x)}
                        lv = (lv - m) if t.neg else m        # levels at which the destroy condition holds
                    if hit:
                        self._dg[ref] = {'levels': sorted(set(range(1, 6)) - lv), 'script': ref,
                                         'cond': ' '.join(map(repr, trig))}
                        break
            g = self._dg[ref]
            if g and (best is None or len(g['levels']) < len(best['levels'])):
                best = g
        return best

    def itm(self, ref):
        if ref not in self._itm:
            try:
                self._itm[ref] = iecre.Itm(self.game.read(ref, 'itm'), ref)
            except Exception:
                self._itm[ref] = None
        return self._itm[ref]

    def idsname(self, f, v):
        return self.ids[f].name(v) or ''

    def effects(self, cre):
        """Permanent effects: the CRE's own plus equip effects of non-droppable (creature-only) items."""
        effs, gear = list(cre.effects), []
        eq = cre.equipped
        for slot, ref in sorted(cre.slots.items()):
            it = self.itm(ref)
            if not it:
                continue
            if it.flags & 4:            # droppable: real gear (worn, quiver, inventory)
                gear.append((slot, ref, it))
            elif slot in eq:            # creature-only item: its equip effects are the creature's abilities
                effs.extend(it.equip_effects)
        return effs, gear

    def convert(self, cre, actor=None):
        o, notes = self.opt, []
        fam = self.gd.family(self.fl, cre.animation)
        track = 'class' if (fam and fam.get('track') == 'class') else ('monster' if fam else 'unmapped')
        cls_name = self.idsname('class', cre.cls); race_name = self.idsname('race', cre.race)
        effs, gear = self.effects(cre)
        res = dict(cre.resist)
        mr, weapon_imm, regen, base_ac_set, invuln = res['magic'], None, None, None, False
        for e in effs:
            op, p1, p2 = e.opcode, e.param1, e.param2
            tgt = {30: 'fire', 28: 'cold', 29: 'electricity', 27: 'acid', 84: 'magic_fire', 85: 'magic_cold',
                   86: 'slashing', 87: 'crushing', 88: 'piercing', 89: 'missile'}.get(op)
            if tgt:
                res[tgt] = p1 if p2 == 1 else res[tgt] + p1
            elif op == 166:
                mr = p1 if p2 == 1 else mr + p1
            elif op == 120:
                weapon_imm = {0: 'magic', 1: 'magic', 3: 'silver', 10: 'cold_iron'}.get(p2, weapon_imm)
            elif op == 98:
                regen = max(regen or 0, p1 if p2 in (0, 1, 2) else 1)
            elif op == 208:
                invuln = True
            elif op == 0 and p2 == 16:
                base_ac_set = p1 - (1 if self.fl == 'classic' else 0)   # IESDP: IWD1 sets field-1
        res['fire'] = max(res['fire'], res['magic_fire']); res['cold'] = max(res['cold'], res['magic_cold'])
        ie_ac = min(cre.ac_natural, base_ac_set) if base_ac_set is not None else cre.ac_natural
        gender = 'female' if self.idsname('gender', cre.gender).upper().startswith('FEMALE') else 'male'
        # ---- abilities (CM p.3-4)
        st = R.strength_3e(cre.str, cre.str_bonus, o['strength_table'])
        abil = [st, cre.dex, cre.con, cre.int, cre.wis, cre.cha]
        if st != cre.str:
            notes.append('STR %d/%02d -> %d (%s table)' % (cre.str, cre.str_bonus % 100, st, o['strength_table']))
        # ---- levels / classes
        classes = R.split_class(cls_name)
        levels = R.class_levels(classes, cre.levels, o['multiclass']) if track == 'class' else []
        commoner = False
        if track == 'class' and (not classes or (o['commoners'] == 'monster_hd' and classes == ['fighter'] and
                                                 cre.levels[0] <= 1 and cre.max_hp <= 8 and
                                                 R.hostility(cre.ea) != 'hostile')):
            commoner, levels = True, []
            notes.append('commoner: %s L%d -> 1 HD humanoid, no PC class (ADJ-12)' % (cls_name or '?', cre.levels[0]))
        if len(classes) > 1 and levels:
            notes.append('multiclass %s %s -> %s (CM p.3)' % (cls_name, cre.levels[:len(classes)], levels))
        if levels and o['level_ability_bumps']:
            tot = sum(n for _, n in levels)
            k = R.KEY_ABILITY.get(levels[0][0], 0)
            if tot // 4:
                abil[k] += tot // 4
                notes.append('+%d %s for %d levels (CM p.4)' % (tot // 4, 'STR DEX CON INT WIS CHA'.split()[k], tot))
        spec = {'resref': cre.resref, 'track': track, 'family': fam['id'] if fam else None,
                'anim': '%04x' % cre.animation, 'name_strref': cre.name_strref, 'gender': gender,
                'alignment': R.align_toee(self.idsname('alignmen', cre.alignment)),
                'hostility': R.hostility(cre.ea), 'ie': {
                    'hp': cre.max_hp, 'ac': ie_ac, 'thac0': cre.thac0, 'apr': R.apr_ie(cre.attacks), 'levels': cre.levels,
                    'class': cls_name, 'race': race_name, 'str': '%d/%02d' % (cre.str, cre.str_bonus) if cre.str_bonus else cre.str,
                    'saves': cre.saves, 'xp': cre.xp_value, 'morale': cre.morale, 'morale_break': cre.morale_break,
                    'resist': res, 'mr': mr}}
        # ---- template proto + model
        if track == 'class':
            rp = self.gd.cb['race_protos']; rm = self.gd.cb['race_models']
            key = race_name.upper() if race_name.upper() in rp else 'default'
            pid = rp[key][1 if gender == 'female' else 0]
            if fam and fam.get('id') != 'class_based' and fam.get('proto'):
                pid = fam['proto']
            model = None
            scale = self.gd.cb['race_scale'].get(race_name.upper(), 100)
            if '%04x' % cre.animation in [x[2:] for x in self.gd.cb['child_anims']]:
                scale = self.gd.cb['child_scale']; notes.append('child: scale %d' % scale)
            how = 'race'
        elif fam:
            pid, model, how = self.toee.resolve(fam)
            scale = fam.get('scale', 100)
        else:
            pid, model, how, scale = None, None, 'unmapped', 100
        if pid is None:
            spec['status'] = 'no_model'; spec['notes'] = notes + ['no ToEE model for this creature (%s)' %
                                                                  (fam['label'] if fam else 'unmapped animation')]
            return spec
        spec.update(proto=pid, model=model, scale=scale, template=how)
        trow = self.toee.protos.get(pid, [''] * 334)
        size = trow[24] or 'size_medium'
        mtype = (trow[163] or 'mc_type_humanoid').replace('mc_type_', '')
        # ---- hit dice / hp
        conm = R.mod(abil[2])
        if track == 'class' and levels:
            hd = sum(n for _, n in levels)
            avg = sum(R.HIT_DIE[c] for c, _ in levels[:1]) + sum((R.HIT_DIE[c] // 2 + 1) * n for c, n in levels) \
                - (R.HIT_DIE[levels[0][0]] // 2 + 1)
            avg += conm * hd
            spec['levels'] = levels
            spec['monster_hd'] = None
            bab = R.bab_from_classes(levels); saves = R.base_saves(levels)
        else:
            if track == 'class':   # commoner
                hd, die = 1, 8 if gender == 'male' else 6
                mtype = 'humanoid'
            else:
                thd = re.match(r'(\d+)d(\d+)', trow[162] or '')
                die = R.TYPE_TABLE.get(mtype, (8,))[0]
                ie_hd = max(1, cre.levels[0])
                hd = ie_hd
                if thd and o['track_a_stats'] == 'srd' and ie_hd < int(thd.group(1)):
                    notes.append('IE level %d below template HD %s: kept template HD' % (ie_hd, thd.group(1)))
                    hd = int(thd.group(1))
            avg = hd * (die + 1) // 2 + conm * hd
            spec['monster_hd'] = [hd, die if track != 'class' else (8 if gender == 'male' else 6), 0]
            bab = R.monster_bab(mtype, hd); saves = R.monster_saves(mtype, hd)
        if track == 'monster' and o['track_a_stats'] == 'srd':
            tab = [int(trow[c]) if trow[c].lstrip('-').isdigit() else 10 for c in range(101, 107)]
            if o['strength_table'] and st > tab[0] + 2:
                notes.append('IE STR %s > template %d: keep IE' % (spec['ie']['str'], tab[0])); tab[0] = st
            abil = tab
            conm = R.mod(abil[2])
        hpmode = o['hp']
        hp = cre.max_hp if hpmode == 'ie' else (max(cre.max_hp, avg) if hpmode == 'max_ie_3e' else avg)
        spec['hp'] = max(1, hp); spec['hp_3e_avg'] = avg; spec['hd_total'] = hd
        if hp != cre.max_hp:
            notes.append('HP %d (IE %d, 3e average %d; ADJ-4 %s)' % (hp, cre.max_hp, avg, hpmode))
        abil_base = list(abil)
        if track == 'class':
            adj = RACE_ABILITY_ADJ.get(race_name.upper().replace('-', '_'))
            if adj and any(adj):
                # IE scores already include the racial adjustment; Temple+ adds it again on top of base stats
                abil_base = [a - d for a, d in zip(abil, adj)]
                notes.append('base abilities minus %s racial adjustment %s (Temple+ re-applies it)' % (race_name, adj))
        spec['abilities'] = abil_base     # what stat_base_set gets; AC/saves below use the effective scores
        # ---- AC (CM p.11/21)
        dexm = R.mod(abil[1])
        nat = R.natural_armor(ie_ac, abil[1], size)
        tnat = int(trow[161]) if trow[161].lstrip('-').isdigit() else 0
        if track == 'monster' and o['track_a_stats'] == 'srd':
            spec['natural_ac'] = max(tnat, 0) if tnat else nat
            if nat > tnat + 2:
                spec['natural_ac'] = nat; notes.append('IE AC %d -> natural +%d (template +%d)' % (ie_ac, nat, tnat))
        else:
            spec['natural_ac'] = 0 if gear and any(g[2].type in (2, 60, 61, 62, 63, 64, 65, 66, 68) for g in gear) else nat
        spec['ac_3e_target'] = R.ac_3e(ie_ac)
        # ---- attack (CM p.11) and saves (CM p.12)
        ie_ab = R.attack_from_thac0(cre.thac0)
        spec['bab'] = bab
        if o['attack_from_ie'] == 'bonus_if_better' and ie_ab - bab >= 3:
            spec['to_hit_bonus'] = ie_ab - bab
            notes.append('THAC0 %d ~ +%d vs 3e BAB +%d: +%d to-hit (ADJ-6)' % (cre.thac0, ie_ab, bab, ie_ab - bab))
        sv = cre.saves
        ie_saves = [R.save_from_2e(sv['death']), R.save_from_2e(sv['spells']), R.save_from_2e(sv['spells'])]
        base = [saves[0] + conm, saves[1] + dexm, saves[2] + R.mod(abil[4])]
        bonus = [0, 0, 0]
        if o['saves_from_ie'] == 'bonus_if_better':
            for k in range(3):
                if ie_saves[k] - base[k] >= 2:
                    bonus[k] = ie_saves[k] - base[k]
            if any(bonus):
                notes.append('IE saves %s ~ %s vs 3e %s: bonus F/R/W %s (ADJ-5)' % (
                    [sv['death'], sv['spells']], ie_saves, base, bonus))
        spec['save_bonus'] = bonus
        # ---- defences
        conds = []
        spec['invulnerable'] = invuln
        if invuln and self.opt['plot_minimum_hp'] == 'invulnerable':
            notes.append('IE minimum-HP effect (op 208): ambient/plot creature -> invulnerable, DR/regen dropped (ADJ-14)')
            res = dict((k, 0) for k in res); regen = None; weapon_imm = None
        sr = R.spell_resistance(mr)
        if sr:
            conds.append(['Monster Spell Resistance', sr]); notes.append('MR %d%% -> SR %d (CM p.22)' % (mr, sr))
        for k, dt in (('fire', 10), ('cold', 8), ('electricity', 9), ('acid', 7)):
            er = R.energy_resistance(res[k], hd, o['energy_resistance'])
            if er == 'immune':
                conds.append(['Monster Energy Immunity', dt]); notes.append('%s %d%% -> immunity (ADJ-7)' % (k, res[k]))
            elif er == 'vuln':
                notes.append('%s %d%%: vulnerability (no Temple+ condition yet)' % (k, res[k]))
            elif er:
                conds.append(['Monster Energy Resistance', dt, er]); notes.append('%s %d%% -> resist %d (ADJ-7)' % (k, res[k], er))
        dr = R.physical_dr(res, weapon_imm)
        if dr:
            name = {'bludgeoning': 'Monster DR Bludgeoning', 'slashing': 'Monster DR Slashing', 'piercing': 'Monster DR Piercing',
                    'magic': 'Monster DR Magic', 'silver': 'Monster DR Silver', '-': 'Monster DR All',
                    'cold_iron': 'Monster DR Magic'}[dr[1]]
            conds.append([name, dr[0], 0]); notes.append('DR %d/%s (ADJ-8)' % dr)
        if regen:
            conds.append(['Monster Fast Healing', min(10, regen), 0]); notes.append('IE regeneration %s -> fast healing (ADJ-8b)' % regen)
        spec['conditions'] = conds
        # ---- morale (ADJ-10)
        spec['no_flee'] = cre.morale_break == 0 or cre.morale >= 20
        # ---- CR (ADJ-11)
        tcr = trow[157]
        tcr = int(tcr) if tcr.lstrip('-').isdigit() else None
        thd = re.match(r'(\d+)d', trow[162] or '')
        spec['cr'] = R.cr_estimate('class' if levels else 'monster', levels, tcr, int(thd.group(1)) if thd else None,
                                   spec['hd_total'])
        spec['ie_xp_hd_equiv'] = R.hd_from_2e_xp(cre.xp_value)
        # ---- gear
        items = []
        ib = self.gd.g['items']
        im = self.item_mapper
        for slot, ref, it in gear:
            pid2 = None
            if im is not None and self.opt.get('gear', 'items') == 'items':     # ITEMS phase: real converted items
                e = im.map(ref)
                if e.get('proto'):
                    items.append({'slot': slot, 'proto': e['proto'], 'res': ref, 'ie_type': it.type_name,
                                  'enchantment': it.enchantment, 'status': e['status']})
                    continue
            if it.type == 2:
                pid2 = ib['armor_by_anim'].get(it.anim.upper())
            if pid2 is None and it.flags & 2:
                pid2 = ib['two_handed_by_type'].get(str(it.type))
            if pid2 is None:
                pid2 = ib['by_type'].get(str(it.type))
            if pid2:
                items.append({'slot': slot, 'proto': pid2, 'ie_type': it.type_name, 'enchantment': it.enchantment})
            else:
                notes.append('item %s (%s) not converted' % (ref, it.type_name))
        if track == 'class' and not any(i['ie_type'] in ('armor', 'robe') for i in items):
            garb = self.gd.cb.get('default_garb') or []
            if garb:
                h = sum(bytearray(cre.resref.encode('latin-1'))) + cre.colors.get('major', 0)
                items.append({'slot': 'armor', 'proto': garb[h % len(garb)], 'ie_type': 'garb (default)', 'enchantment': 0})
            if self.gd.cb.get('default_boots'):
                items.append({'slot': 'boots', 'proto': self.gd.cb['default_boots'], 'ie_type': 'boots (default)', 'enchantment': 0})
        # monsters on a bare PC body (orc = half-orc PC mesh, barbarians, animated plate, ...): IE draws their armour as
        # part of the animation, the CRE carries none, and ToEE renders the body unclothed -> the family's default gear
        # (guidance "gear": [{slot, protos, unless}]), else the class track's garb + boots; never over a worn item
        mid = self.toee.col(pid, 34).strip() if pid else ''
        mesh = str(self.toee.meshes.get(int(mid), '')) if mid.isdigit() else ''
        if track == 'monster' and mesh.lower().startswith('pcs\\'):
            # the IE AC already holds the animation's armour (natural_ac above is derived from it): worn default gear
            # spends that budget (guidance "gear_ac" = 3e armour/shield bonus per proto) instead of adding to it, so
            # the heaviest piece that fits is picked and only the rest stays natural armour; never on top of real armour
            have = {i['slot'] for i in items}
            types = {i['ie_type'] for i in items}
            gac = {int(k): v for k, v in (fam.get('gear_ac') or {}).items()}
            budget = spec.get('natural_ac') or 0
            gear_d = fam.get('gear') or [{'slot': 'armor', 'protos': self.gd.cb.get('default_garb') or []},
                                         {'slot': 'boots', 'protos': [self.gd.cb['default_boots']] if self.gd.cb.get('default_boots') else []}]
            for gd_ in gear_d:
                sl = gd_['slot']
                if sl in have or not gd_.get('protos') or types & set(gd_.get('unless', ())):
                    continue
                if sl == 'armor' and types & {'armor', 'robe'}:
                    continue
                fit = sorted((p_ for p_ in gd_['protos'] if gac.get(p_, 0) <= budget), key=lambda p_: -gac.get(p_, 0))
                if not fit:
                    continue
                pid3 = fit[0]; budget -= gac.get(pid3, 0)
                items.append({'slot': sl, 'proto': pid3, 'ie_type': '%s (default)' % sl, 'enchantment': 0})
                have.add(sl)
            if budget != (spec.get('natural_ac') or 0):
                notes.append('default gear AC %d taken from natural armour (%d -> %d)' % (spec['natural_ac'] - budget, spec['natural_ac'], budget))
                spec['natural_ac'] = budget
        spec['items'] = items
        # ---- spells: IE memorised / known spells -> Temple+ spell lists (ie_spells.SpellMapper, docs/spells.md)
        sp, miss, strat = self.npc_spells(cre, spec)
        spec['spells'] = sp; spec['spells_unmatched'] = miss
        if strat:
            spec['ai_strategy'] = strat
        ok = lambda r: r and r.strip() and r.strip().lower() != 'none'
        dlg = (actor or {}).get('dialog')
        spec['dialog'] = (dlg if ok(dlg) else cre.dialog if ok(cre.dialog) else '').lower()
        order = ('override', 'specific', 'class', 'race', 'general', 'default')   # IE evaluation order
        asc = (actor or {}).get('scripts') or {}
        src = asc if any(ok(v) for v in asc.values()) else cre.scripts
        spec['scripts'] = [src[k].lower() for k in order if ok(src.get(k))]
        dg = self.difficulty_gate([v for v in list(asc.values()) + list(cre.scripts.values()) if ok(v)])
        if dg:
            spec['difficulty'] = dg
        spec['status'] = 'ok'
        spec['notes'] = notes
        return spec

    @property
    def item_mapper(self):
        """ie_items.ItemMapper (docs/items.md) when the item guidance is there; None -> the creatures-phase stand-in gear."""
        if getattr(self, '_items', False) is False:
            try:
                import ie_items
                self._items = ie_items.ItemMapper(self.game, self.toee.td.root, self.tp_root)
            except Exception as e:
                print('item mapper unavailable (%s): stand-in gear' % e)
                self._items = None
        return self._items

    @property
    def spells(self):
        if self._spells is None:
            import ie_spells
            tp = ie_spells.TPSpells(self.toee.td.root, self.tp_root)
            self._spells = ie_spells.SpellMapper(self.game, tp, {k: v for k, v in self.opt.items()
                                                                 if k in ie_spells.SPELL_OPTIONS})
        return self._spells

    def npc_spells(self, cre, spec):
        """IE spell lists -> [{res, toee, cls (Temple+ class key or 'domain_special'), lvl, n, mem}] plus unmatched
        [(res, ie level, ie type, class)] and a Temple+ custom AI strategy that casts them (SPL-ADJ-3/5/6/7)."""
        import ie_spells
        mp = self.spells
        lv = dict(spec.get('levels') or [])
        keys = {'cleric': 'clr', 'druid': 'drd', 'wizard': 'wiz', 'sorcerer': 'sor', 'bard': 'brd', 'paladin': 'pal',
                'ranger': 'rgr'}
        have = {keys[c]: n for c, n in lv.items() if c in keys}

        def max_level(k, n):
            if k in ('clr', 'drd', 'wiz'):
                return min(9, (n + 1) // 2)
            if k == 'sor':
                return min(9, n // 2)
            if k == 'brd':
                return min(6, (n + 1) // 3) if n > 1 else 0
            return min(4, (n - 1) // 3) if n >= 4 else 0     # paladin / ranger
        counts = collections.Counter()
        known_only = set()
        for m in cre.memorized:
            counts[(m['resref'], m['type'])] += 1 if m.get('memorized', True) else 0
        for k in cre.known_spells:
            if (k['resref'], k['type']) not in counts:
                known_only.add((k['resref'], k['type']))
        out, miss = [], []
        for (ref, typ) in sorted(set(counts) | known_only):
            m = mp.lookup(ref)
            if m['toee'] is None:
                miss.append((ref, m['ie_level'], typ, m['cls'])); continue
            ck = next((k for k in ie_spells.CLASS_KEYS.get(typ, ()) if k in have and k in m['lv']), None)
            if typ == 'wizard' and ck is None and 'wiz' in have:
                ck = 'wiz'
            if typ == 'priest' and ck is None:
                ck = next((k for k in ('clr', 'drd') if k in have), None)
            if ck is None:
                if mp.opt['innate'] == 'skip' and typ == 'innate':
                    miss.append((ref, m['ie_level'], typ, 'innate_skipped')); continue
                ck = 'domain_special'
            lvl = mp.slot_level(m, ck) if ck != 'domain_special' else max(1, min(9, m['ie_level'] or 1))
            if ck != 'domain_special' and mp.opt['npc_spells'] == 'cap_level' and lvl > max_level(ck, have.get(ck, 0)):
                miss.append((ref, m['ie_level'], typ, 'above_max_level')); continue
            n = counts.get((ref, typ), 0)
            out.append(dict(res=ref, toee=m['toee'], name=m['label'], cls=ck, lvl=lvl, n=n, mem=n > 0, ai=m['ai']))
        return out, miss, self.strategy(out)

    @staticmethod
    def strategy(spells):
        """Temple+ custom AI strategy (ai_strategy_set_custom triplets): buff self, heal friends, then offensive and
        crowd-control spells at the nearest enemy, then melee. Spells are named the way strategy.tab names them."""
        cast, seen = [], set()
        for s in spells:                     # several IE spells can map to one ToEE spell: one strategy entry each
            if s['mem'] and s['toee'] not in seen:
                seen.add(s['toee']); cast.append(s)
        if not cast:
            return None
        cls = lambda s: 'domain_special' if s['cls'] == 'domain_special' else 'class_' + {
            'clr': 'cleric', 'drd': 'druid', 'wiz': 'wizard', 'sor': 'sorcerer', 'brd': 'bard', 'pal': 'paladin',
            'rgr': 'ranger'}[s['cls']]
        ent = lambda s: "'%s' %s %d" % (s['name'], cls(s), s['lvl'])
        by = lambda pre: sorted([s for s in cast if s['ai'].startswith(pre)], key=lambda s: -s['lvl'])
        t = ['ie2toee']
        buffs = by('ai_action_defensive')
        if buffs:
            t += ['clear target', '', '', 'target self', '', '']
            for s in buffs[:3]:
                t += ['cast single', '', ent(s)]
        heals = by('ai_action_heal')
        if heals:
            t += ['clear target', '', '', 'target friend hurt', '', '']
            for s in heals[:3]:
                t += ['cast single', '', ent(s)]
        t += ['clear target', '', '', 'target closest', '', '']
        for s in by('ai_action_offensive') + by('ai_action_summon'):
            t += ['cast single', '', ent(s)]
        t += ['use potion', '', '', 'attack', '', '', 'approach', '', '', 'attack', '', '']
        return t


# Portraits (vanilla ToEE portraits.mes base ids only; no Co8 art). Keyed by IE CRE resref. Townsfolk rotate through
# generic sets so the same face doesn't repeat across a map. Monsters and unlisted CREs keep their template proto's portrait.
# TODO(ai-art): children (damien, eboy1/2, egirl1/2) and squirel have no fitting ToEE portrait; they keep the proto
# fallback until AI-generated portraits are added (planned as new portraits.mes ids 9000+).
PORTRAITS = {
    'apsel': 7020, 'innkpr': 6050, 'everard': 6000, 'accalia': 6250, 'hroth': 6330, 'gaspar': 6040,
    'pomab': 6100, 'hildreth': 2040, 'erevain': 1040, 'elisia': 7740, 'jhonen': 7640, 'oldjed': 6140,
    'churin': 6610, 'barkeep': 7620,
}
PORTRAIT_TODO = ('damien', 'eboy1', 'eboy2', 'egirl1', 'egirl2', 'squirel')
ORC_PORTRAITS = (6470, 6480)   # ToEE's half-orc NPCs Pintark (14207) and Tuelk (14206)
ORC_FAMILIES = ('orc', 'orog')
TOWNSMEN = (7830, 6620, 6700, 7660)
TOWNSWOMEN = (7840, 7670, 7910, 7920, 7690)


def pick_portrait(resref, gender, n):
    """Portrait base id for a converted actor, or None to keep the template proto's. n: running generic count."""
    r = (resref or '').lower()
    if r in PORTRAITS:
        return PORTRAITS[r]
    if r.startswith(('towniem', 'townief', 'stoolm', 'chairm')):
        pool = TOWNSWOMEN if gender == 'female' else TOWNSMEN
        return pool[n % len(pool)]
    return None


# Our own names for creature variants the game's own (tlk) name doesn't tell apart: CRE resref -> {tlk name: name}.
# The tlk name is kept unless it is the generic one listed here (so a translated tlk keeps its own names).
VARIANT_NAMES = {
    'goboaxe': {'Goblin': 'Axe Goblin'},
    'gobobow': {'Goblin': 'Goblin Archer'},
    'gobehq1': {'Goblin Elite': 'Goblin Elite Archer'},
}


def convert_area(game, toee_root, out, area, name_base=27000, options=None, script_base=None, tp_root=None):
    import toeedata
    tx = ToEEIndex(toeedata.ToEEData(toee_root))
    cv = Converter(game, tx, options, tp_root=tp_root)
    a = F.Are(game.read(area, 'are'))
    specs, names, dlg_args, used = [], {}, [], set()
    gen = [int(re.sub(r'\D', '', area) or 0) % 7] * 2   # per-area offset so adjacent maps start on different faces
    for i, act in enumerate(a.actors):
        try:
            data = act['embedded_cre'] or game.read(act['cre'], 'cre')
            cre = iecre.Cre(data, act['cre'])
        except Exception as e:
            specs.append({'actor': act['name'], 'resref': act['cre'], 'status': 'error', 'error': str(e)}); continue
        s = cv.convert(cre, act)
        s.update(actor=act['name'], x=act['x'], y=act['y'], orient=act['orient'], schedule=act['schedule'])
        if s.get('status') == 'ok':
            por = pick_portrait(act['cre'], s.get('gender'), gen[s.get('gender') == 'female'])
            if por is None and (s.get('family') in ORC_FAMILIES or s.get('model') == 104):   # orc / half-orc body
                por = ORC_PORTRAITS[i % 2]
            if por is not None:
                s['portrait'] = por
                if por in TOWNSMEN + TOWNSWOMEN:
                    gen[s.get('gender') == 'female'] += 1
        nid = name_base + i
        nm = cv.text(cre.name_strref) if cre.name_strref >= 0 else ''
        nm = VARIANT_NAMES.get(act['cre'].lower(), {}).get(nm.strip(), nm) or act['name']
        names[nid] = nm.replace('{', '(').replace('}', ')')
        s['name_id'] = nid
        if script_base and s.get('status') == 'ok' and (s.get('dialog') or s.get('scripts')):
            dv = re.sub(r'\W', '', (cre.death_var or '').lower())
            an = re.sub(r'\W', '', act['name'].lower())[:16]
            # IWD reuses death variables across creature types (Easthaven goblins carry 'ghast'): only trust one that
            # looks like this actor's name or CRE resref, otherwise name it after the actor
            if dv in ('', 'none') or (dv[:3] not in an and dv[:3] not in act['cre'].lower()):
                dv = an
            s['ident'] = dv if dv and dv not in used else '%s_%d' % (dv or re.sub(r'\W', '', act['name'].lower())[:16] or 'actor', i)
            used.add(s['ident'])
            s['script_id'] = script_base + i
            dlg_args.append('%s:%s:%d:%s:%s' % (s['ident'], area.upper(), s['script_id'], s['dialog'], ','.join(s['scripts'])))
        specs.append(s)
    os.makedirs(out, exist_ok=True)
    mesd = os.path.join(out, 'modules', 'ToEE', 'mes', 'description'); os.makedirs(mesd, exist_ok=True)
    if names:      # (an empty .mes in mes/description hangs the game at "Loading game system Description")
        open(os.path.join(mesd, 'ie2toee_%s.mes' % area.lower()), 'w', encoding='cp1252', errors='replace').write(
            ''.join('{%d}{%s}\n' % kv for kv in sorted(names.items())))
    elif os.path.exists(os.path.join(mesd, 'ie2toee_%s.mes' % area.lower())):
        os.remove(os.path.join(mesd, 'ie2toee_%s.mes' % area.lower()))
    keep = ('actor', 'resref', 'status', 'track', 'family', 'proto', 'model', 'scale', 'x', 'y', 'orient', 'gender',
            'alignment', 'hostility', 'abilities', 'levels', 'monster_hd', 'hp', 'natural_ac', 'bab', 'to_hit_bonus',
            'save_bonus', 'conditions', 'no_flee', 'invulnerable', 'ident', 'cr', 'items', 'spells', 'ai_strategy', 'name_id',
            'script_id', 'schedule', 'portrait', 'difficulty')
    py = ['# Generated by ie2toee ie_creatures.py from the player\'s own IE install. Do not distribute.',
          'AREA = %r' % area.upper(), 'CREATURES = [']
    for s in specs:
        if s.get('status') == 'ok':
            py.append('    %r,' % {k: s[k] for k in keep if k in s})
    py.append(']')
    open(os.path.join(out, 'ie_creatures_%s.py' % area.lower()), 'w').write('\n'.join(py) + '\n')
    open(os.path.join(out, 'dialogue_actors.txt'), 'w').write(''.join('--actor %s\n' % a for a in dlg_args))
    json.dump({'area': area, 'flavor': cv.fl, 'options': cv.opt, 'creatures': specs}, open(
        os.path.join(out, '%s_creatures.json' % area.upper()), 'w'), indent=1, default=list)
    return specs


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    s1 = sub.add_parser('survey'); s1.add_argument('games', nargs='+'); s1.add_argument('--md', required=True); s1.add_argument('--json')
    s2 = sub.add_parser('convert'); s2.add_argument('game'); s2.add_argument('toee'); s2.add_argument('out')
    s2.add_argument('--area', required=True); s2.add_argument('--name-base', type=int, default=27000)
    s2.add_argument('--script-base', type=int, help='give actors with a dialog/script ToEE script ids base+index and '
                    'write <out>/dialogue_actors.txt (--actor args for ie_dialogue.py)')
    s2.add_argument('--option', action='append', default=[], help='key=value (see ie_rules.DEFAULT_OPTIONS, '
                    'ie_spells.SPELL_OPTIONS)')
    s2.add_argument('--tp', help='Temple+ install (tpdata/*.dat) for the Temple+ spell list')
    a = ap.parse_args()
    if a.cmd == 'survey':
        reps = [survey(iefs.IEGame(g)) for g in a.games]
        open(a.md, 'w').write(survey_md(reps))
        if a.json:
            json.dump(reps, open(a.json, 'w'), indent=1)
        for r in reps:
            print(r['flavor'], {k: r[k] for k in ('cre_files', 'referenced_cres', 'placements', 'unreferenced_cres',
                                                  'coverage_placements', 'coverage_cres')})
    elif a.cmd == 'convert':
        opts = dict(kv.split('=', 1) for kv in a.option)
        specs = convert_area(iefs.IEGame(a.game), a.toee, a.out, a.area, a.name_base, opts, a.script_base, a.tp)
        c = collections.Counter(s.get('status') for s in specs)
        print(a.area, dict(c))
        for s in specs:
            print('%-10s %-9s %-6s %-14s proto=%s hp=%s ab=%s lv=%s nat=%s conds=%s items=%s' % (
                s.get('actor', '')[:10], s.get('resref'), s.get('track'), s.get('family'), s.get('proto'), s.get('hp'),
                s.get('abilities'), s.get('levels') or s.get('monster_hd'), s.get('natural_ac'),
                [c[0] for c in s.get('conditions', [])], [i['proto'] for i in s.get('items', [])]))
    else:
        ap.print_help()


if __name__ == '__main__':
    main()
