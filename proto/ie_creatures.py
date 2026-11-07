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

    def family(self, fl, anim, resref=None):
        f = self.g.get('resref_families', {}).get((resref or '').lower())
        if f:
            return f
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
        fam = self.gd.family(self.fl, cre.animation, cre.resref)
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
# fallback until AI-generated portraits are added (new portraits.mes ids 9900+ via ie_portraits.py;
# Co8 already uses 9000-9754).
PORTRAITS = {
    'apsel': 7020, 'innkpr': 6050, 'accalia': 6250, 'gaspar': 6040,
    'pomab': 6100, 'hildreth': 2040, 'erevain': 1040, 'elisia': 7740, 'jhonen': 7640, 'oldjed': 6140,
    'churin': 6610, 'barkeep': 7620,
    # commissioned art (ie_portraits.py, ids 9900+); these replace the vanilla stand-ins above
    'hroth': 9900, 'hroth1': 9900, 'everard': 9910, 'everard2': 9910, 'arundel': 9920, 'arundel1': 9920,
    'poquelin': 9930, 'belhif': 9940, 'yxungirl': 9950, 'kress': 9960, 'conlan': 9970,
}
PORTRAIT_TODO = ()   # batch 4 covered the children and the squirrel
ORC_PORTRAITS = (6470, 6480)   # ToEE's half-orc NPCs Pintark (14207) and Tuelk (14206)
ORC_FAMILIES = ('orc', 'orog')
TOWNSMEN = (7830, 6620, 6700, 7660, 10210)            # + commissioned old townsman
TOWNSWOMEN = (7840, 7670, 7910, 7920, 7690, 10200)     # + commissioned fisherwoman
# Commissioned children / critters (batch 4), IWD + IWD2 resrefs.
PORTRAITS.update({
    'damien': 10140, 'damien2': 10140, 'eboy1': 10150, '50childm': 10150, 'eboy2': 10160, 'kukid': 10160,
    '10kidboy': 10160, 'egirl1': 10170, '10kidgrl': 10170, 'egirl2': 10180, '50childf': 10180,
})
PORTRAITS.update({'51hhrma': 10420, '50abomin': 10640})   # batch 6 bosses (own art, no flip)
# batch 8 part A: IWD1 Easthaven (replace the vanilla stand-ins; Quimby keeps his until redelivered)
PORTRAITS.update({
    'hildreth': 11270, 'pomab': 11250, 'accalia': 11260, 'erevain': 11280, 'erevdead': 11280, 'elisia': 11290, 'jhonen': 11300,
    'gaspar': 11310, 'barkeep': 11320, 'apsel': 11340, 'oldjed': 11350, 'eeoldjed': 11350, 'churin': 11360,
    'eepomab': 11370, 'pomimg': 11370, 'cyclops': 11380, 'eecyc1': 11380, 'mcyc': 11380, 'sentry': 11390,
    'mcapvil': 11410, 'mcapvilh': 11410, 'cmcapvil': 11410, 'fmcapvil': 11410,
    'fcapvil': 11420, 'fcapvilh': 11420, 'cfcapvil': 11420, 'ffcapvil': 11420,
})
TOWNSMEN = TOWNSMEN + (11460, 12200, 11470, 12210, 11490, 12230, 11430)   # batch 8 fishermen, dockworker, Cradle regular
TOWNSWOMEN = TOWNSWOMEN + (11480, 12220, 11510, 12240)                     # batch 8 fishwife, dock hand
PORTRAITS.update({'innkpr': 11330})   # batch 8 Quimby redo
TOWNSMEN = TOWNSMEN + (11540, 12270, 11560, 12290, 11600, 12330, 11630, 12360, 11650, 12380, 11660, 12390, 11680, 12410)   # batch 8 rest
TOWNSWOMEN = TOWNSWOMEN + (11580, 12310, 11590, 12320, 11610, 12340, 11640, 12370)
# Generic monsters (batch 5): resref -> art family. Each instance picks a portrait from the family's normal pool
# (art + mirrored flip, ie_portraits.FLIPS) by a hash of area/position, so a pack doesn't share one face;
# resrefs in MONSTER_UPGRADED (elite, chief, high-level random-spawn entries) use the family's upgraded pool.
MONSTER_POOLS = {   # family -> (normal ids, upgraded ids); upgraded falls back to normal when there's no art
    'yeti': ((10230, 10310), (10240, 10320)), 'verbeeg': ((10250, 10330), ()),
    'frost_giant': ((10260, 10340), (10270, 10350)), 'winter_wolf': ((10280, 10360), (10650, 10930)),
    'boring_beetle': ((10290, 10370), (10300, 10380)), 'squirrel': ((10190, 10390), ()),
    # batch 6
    'dire_wolf': ((10520, 10810), (10530, 10820)),
    'rhino_beetle': ((10580, 10870), ()),
    'skeleton_elite': ((10630, 10920), ()),
    'goblin_elite': ((10680, 10960), ()),
    'ice_troll': ((10450, 10740), (10460, 10750)),
    'salamander_frost': ((10620, 10910), ()),
    'snow_troll': ((10430, 10720), (10440, 10730)),
    'wight': ((10590, 10880), (10600, 10890)),
    'lizardman': ((10500, 10790), (10510, 10800)),
    'orc_elite': ((10670, 10950), ()),
    'orc_shaman': ((10660, 10940), ()),
    'salamander': ((10610, 10900), ()),
    'yuanti': ((10470, 10760), (10480, 10770)),
    'umber_hulk': ((10560, 10850), ()),
    'yuanti_abomination': ((10490, 10780), ()),
    'bombardier_beetle': ((10570, 10860), ()),
    'hook_horror': ((10400, 10700), (10410, 10710)),
    'wyvern': ((10690, 10970), ()),
    'malarite': ((10540, 10830), (10550, 10840)),
}
MONSTER_FAMILY = {}
for _fam, _rs in {
    'yeti': 'ms4yeti rvsyeti vslyeti vsyeti kuyeti yetitund 40ryetit 40yetitu 52yettu 52yettur 52yetuh 00syeti '
            'vscyeti wtcyeti wtyeti 52yetgh 52yettg 52yettgr 00sdyet 00sshyet 00ssyet 41sdyet',
    'verbeeg': 'ms5verb rtfgverb ss2vrb6 ss2vrb7 ss2vrb8 verbdead verbeeg verbeegd 21verb 31giaver',
    'frost_giant': 'giantfn giantfro 30frgnt 00ssfgnt 41ssfgnt giantfg 00sdfgnt 00sfrgnt 00sshfgt 41sdfgnt 41sfrgnt 41sshfgt',
    'winter_wolf': 'as3wint wolfwint winwolf winwolfp rwtwwolf 00swtwlf 41swtwlf 30wwlf 40rwolfw 40wolfwi 50wfwh 50wlfwi '
                   '50wlfwir druidww 50wfwgh 50wlfwg 50wlfwgr',
    'boring_beetle': 'beetbor beetleb mbbr druidbb gisborb ms3borb psborbtl 40rbetbo 40betbor 00sbtl13',
    'squirrel': 'squirel squirel2 eesquirl',
    # batch 6 (CRE name based, both games: placed, rest-table, 00s/41s spawnables)
    'dire_wolf': '00sdwlf 41sdwlf 50wfdfh 50wfdh 50wlfdf 50wlfdfr 50wlfdi 50wlfdir as2dire',
    'rhino_beetle': '00sbtl15 41sbtl15 beetrhin mbrh',
    'skeleton_elite': '00sabgd 00sarskl 00sbgd 00segbgd 00sgrbgd 41sabgd 41sarskl 41sbgd 41sbgd2 41segbgd 41sgrbgd 61skearm 63abgd 63abgden 63abgdn 65sarskl 67abgd 67grbgd 67grbgd2 bon8005 bon8013 bonegard ktskh1 ktskh2 ktskh3 ktsks1 kttga1 kttga2 kttga3 kttgm1 kttgm3 lskarmms lskarmsw ms7bgrd mskb rkttguam skarmax skarmms skarmsw skelarm skelblad skelbong skelserr skelwaxe skelwham skelwswd sklich undeadlt',
    'goblin_elite': '00gobare 00gobe 10gobec 12gobare 12gobe 30dgobe 30gobaes 30gobes 31gobhc 62hagob 62hagob1 67ehagob 67hagobe gobehq1 gobline goblinea goblinsp goboeaxe goboebow mgo3 ms2gobb ms2gobe rkpgobe rkpgobea ss2gob1 ss2gob2 ss2gob3',
    'ice_troll': '20troice 30firtlg 30firtrl 30icetrl 41rtroic 41troice 51troic icetroll rwtgice trollice wticetr1 wticetr2 wticetrl',
    'salamander_frost': '00sfsal 61salfro invissal ms6salc msmsalc rwtsalf sal8013 salamanf wtsalf1 wtsalf2 wtsalf3',
    'snow_troll': '41trosno 50trosg 50trosgr 50trosh 50trosn 50trosnr 50tross 50trossh invistrl mtsn trollsno wtsnotro',
    'wight': '00sbwht 41sbwht 50wit 60wight 60wighth 60wightl 62bwht 63swlmr 63wlmr 65sbwht 65wlmr 67wlmrs ktwgt1 ktwgti1 lwight mwig rdecwig udwight wight wight2 wight3 wightcld wightimb',
    'lizardman': '00selzds 61dlizle 61lizlea 61lizler 61lizsha 61lizshr 61lizwar 61lizwrr lizdead lizking lizman lm1hwax lm1hwaxy lm1hwms lm1hwmsy lm1hwpo lm1hwpoy lm2hwla lm2hwlay lm2hwna lm2hwnay lm2hwte lm2hwtey lmsham1 lmsham2 lmsham3 lmshkid mliz ms2lizm ms3tliz rdeliza rdeliztl slizman ss1liz3 ss1liz4 ss1liz5 ss2liz5 ss2liz6 ss2liz7 tlizman',
    'orc_elite': '00orcare 21orcace 21orcelt 31orcare 31orchc 31orcwa mor3 mor4 orcewaxe orcewbow sdorcax3 udorc',
    'orc_shaman': '20orcshm 20orcshv 30orcsh1 30orcshh 30orcwd 31orchsb 31orchsh 31orcsh1 31orcsh2 31orcwd 31orcwd2 mor5 orcsham sdorcshm',
    'salamander': '00sdsal 00ssal 00sshsal 00sssal 41sdsal 41sssal ms6salf msmsalf rldsalfi sal8001 sal8005 sal8008 salamand salamanr',
    'yuanti': '60abprie 60ranyta 60ytarch 60ytcook 60ytelit 60ythipr 60ytprie 60ytsorc 61dyaarc 61dyapri 61dyasen 61dyhpri 61dyhsor 61dypbla 61dypfig 61ryhpri 61ryhsor 61yaarch 61yaprie 61yasent 61yasumm 61yhprie 61yhsorc 61ypblad 61ypblar 61ypfigh 61ypfigr 62hayua 62hayua1 62hayua2 62hayua3 62hayua4 62hayua5 66hayua 66hayua1 66hayua2 66hayua3 ms6yuan msmyuan rdeyuane yuaewax yuaewbl yuaewbo yuaewsw yuanti yuantie yuantip yuanwax yuanwbi yuanwsw yuaxdin yubldin yuchamp yuswdin',
    'umber_hulk': '00sduhk 00sshuhk 00ssuhk 00suhk 41sduhk 41ssuhk 51umb 51umbr ms7umbh psumbh rldumbh ss3umb8 ss3umb9 traphulk uhlk8004 uhlk8009 uhlk8010 umberhlk',
    'yuanti_abomination': '60ranyt 60yuanti yuantia',
    'bombardier_beetle': '00sbtl11 41sbtl11 beetbomb gisbomb ms2bbtl',
    'hook_horror': '00shkh 51hhr 51hhrgh 51hhrgu 51hhrh',
    'wyvern': '00swyv 41swyv 50wyv 50wyvh 50wyvr 61awyver 61dawyve 61wyvern 61wyverr',
    'malarite': '20malara 20malarh 20malarp 20rndmal',
}.items():
    MONSTER_FAMILY.update(dict.fromkeys(_rs.split(), _fam))
# batch 8: Easthaven temple acolytes share the Tempus acolyte/priest art (+ priest flip)
MONSTER_POOLS['tempus'] = ((11440, 11520, 12250), ())
MONSTER_FAMILY.update(dict.fromkeys(('acolyte', 'acolyted', 'acoldead', 'acolpois'), 'tempus'))
MONSTER_UPGRADED = set('vscyeti wtcyeti wtyeti 52yetgh 52yettg 52yettgr 00sdyet 00sshyet 00ssyet 41sdyet '
                       'giantfg 00sdfgnt 00sfrgnt 00sshfgt 41sdfgnt 41sfrgnt 41sshfgt 00sbtl13 '
                       '50wfwgh 50wlfwg 50wlfwgr'.split())   # greater winter wolves (batch 6 art)
MONSTER_UPGRADED |= set('00selzds 20malarh 20malarp 30firtlg 30firtrl 30icetrl 50trosg 50trosgr 50tross 50trossh 50wfdfh 50wlfdf 50wlfdfr 51hhrgh 51hhrgu 60abprie 60wightl 60ytelit 60ythipr 60ytprie 60ytsorc 61dlizle 61dyapri 61dyasen 61dyhpri 61dyhsor 61lizlea 61lizler 61lizsha 61lizshr 61ryhpri 61ryhsor 61yaprie 61yasent 61yasumm 61yhprie 61yhsorc 63swlmr 63wlmr 65wlmr 67wlmrs ktwgti1 lizking lm2hwla lm2hwlay lm2hwna lm2hwnay lm2hwte lm2hwtey lmsham1 lmsham2 lmsham3 lmshkid ms3tliz ms6yuan msmyuan rdeliztl rdeyuane rwtgice slizman ss2liz5 ss2liz6 ss2liz7 tlizman wightimb wticetr1 wticetrl yuaewax yuaewbl yuaewbo yuaewsw yuantie yuantip yuchamp'.split())   # batch 6 elites
# batch 8: IWD1 monsters -> location-themed IWD1 art (overrides the IWD2 stand-ins for these resrefs)
MONSTER_POOLS['iwd_goblin'] = ((11690, 12420), (10680, 10960))
MONSTER_FAMILY.update(dict.fromkeys('goblin goblind goboaxe gobobow mgo1 mgo2 mgo4 mgo5 ms1goba ms1gobm ss1gob1 ss1gob2 ss1gob3 gobehq1 goboeaxe goboebow mgo3 ms2gobb ms2gobe ss2gob1 ss2gob2 ss2gob3 sdgobax1 sdgobax2 sdgobax3 sdgobtrn'.split(), 'iwd_goblin'))
MONSTER_POOLS['iwd_goblin_archer'] = ((11700, 12430), ())
MONSTER_FAMILY.update(dict.fromkeys('goblina goblinad goblinea rkpgobea sdgobbw1 sdgobbw2'.split(), 'iwd_goblin_archer'))
MONSTER_POOLS['iwd_orc'] = ((11710, 12440), (10670, 10950))
MONSTER_FAMILY.update(dict.fromkeys('mor1 mor2 orc2004 orca2004 orcwaxe orcwbow rocorca mor3 mor4 orcewaxe orcewbow udorc mor5 orcsham'.split(), 'iwd_orc'))
MONSTER_POOLS['iwd_orc_shadowed'] = ((11720, 12450), ())
MONSTER_FAMILY.update(dict.fromkeys('rshorcb sdorcbw1 rshorca sdorcax1 sdorcbw2 sdorcshm sdorcax2 sdorcax3'.split(), 'iwd_orc_shadowed'))
MONSTER_POOLS['iwd_wolf'] = ((11730, 12460), (10520, 10810))
MONSTER_FAMILY.update(dict.fromkeys('as1wolf wolf wolf12 wolfbel as2dire'.split(), 'iwd_wolf'))
MONSTER_POOLS['iwd_winter_wolf'] = ((11740, 12470), ())
MONSTER_FAMILY.update(dict.fromkeys('as3wint rwtwwolf winwolf winwolfp wolfwint'.split(), 'iwd_winter_wolf'))
MONSTER_POOLS['iwd_beetle'] = ((11750, 12480), ())
MONSTER_FAMILY.update(dict.fromkeys('beetle beetled beetleg ehbeetle mbet beetfire mbfi ms1fb'.split(), 'iwd_beetle'))
MONSTER_POOLS['iwd_bombardier'] = ((11760, 12490), ())
MONSTER_FAMILY.update(dict.fromkeys('beetbomb gisbomb mbbm ms2bbtl'.split(), 'iwd_bombardier'))
MONSTER_POOLS['iwd_skeleton'] = ((11770, 12500), (10630, 10920))
MONSTER_FAMILY.update(dict.fromkeys('ad1sklm ad2sklm ad3sklm ktsk1 msk1 rktskelm rktskelr skeleton ad2sklr ad3sklr ad4sklr ktska1 ktska2 ktska3 skelbow ktskt1 ktskt2 kttas1 kttas2 kttas3 shskltat skeltatt sktatax sktatsw lskarmms lskarmsw skarmax skarmms skarmsw skelarm skelwaxe skelwham skelwswd sklich skelblad skelblst skelblaz skelserr bon8005 bon8013 bonegard ms7bgrd mskb skelbong'.split(), 'iwd_skeleton'))
MONSTER_POOLS['iwd_zombie'] = ((11780, 12510), ())
MONSTER_FAMILY.update(dict.fromkeys('ad2zomb ad3zomb ad4zomb ad5zomb ktzom1 lzombie mzo2 zombie zombie2 lzombiej ms5jzom zombiej zombiep ktzomj'.split(), 'iwd_zombie'))
MONSTER_POOLS['iwd_ghoul'] = ((11790, 12520), ())
MONSTER_FAMILY.update(dict.fromkeys('ghoul ghoul1 ghoul2 ktghl1 lghoul mgh2 ms3ghl udghoul ghast ktgst1 lghast mgha ms4ghst udghast'.split(), 'iwd_ghoul'))
MONSTER_POOLS['iwd_wight'] = ((11800, 12530), (10600, 10890))
MONSTER_FAMILY.update(dict.fromkeys('ktwgt1 lwight mwig udwight wight wight2 wight3 rdecwig wightcld'.split(), 'iwd_wight'))
MONSTER_POOLS['iwd_shadow'] = ((11810, 12540, 12860, 12870), ())
MONSTER_FAMILY.update(dict.fromkeys('shadow sumshad vsshad1 vsshadow shadowb'.split(), 'iwd_shadow'))
MONSTER_POOLS['iwd_mummy'] = ((11820, 12550, 12840, 12850), ())
MONSTER_FAMILY.update(dict.fromkeys('ktmum1 mmum ms7mumy mummy'.split(), 'iwd_mummy'))
MONSTER_POOLS['iwd_lizardman'] = ((11830, 12560, 12820, 12830), (10510, 10800))
MONSTER_FAMILY.update(dict.fromkeys('lizdead lizman lm1hwax lm1hwaxy lm1hwms lm1hwmsy lm1hwpo lm1hwpoy mliz ms2lizm rdeliza ss1liz3 ss1liz4 ss1liz5 lm2hwla lm2hwlay lm2hwna lm2hwnay lm2hwte lm2hwtey ms3tliz rdeliztl ss2liz5 ss2liz6 ss2liz7 tlizman lmsham1 lmsham2 lmsham3 lmshkid slizman'.split(), 'iwd_lizardman'))
MONSTER_POOLS['iwd_yuanti'] = ((11840, 12570, 12880, 12890), (12080,))
MONSTER_FAMILY.update(dict.fromkeys('yuanti yuanwax yuanwbi yuanwsw yuaxdin yubldin yuswdin yuantip ms6yuan msmyuan rdeyuane yuaewax yuaewbl yuaewbo yuaewsw yuantie yuchamp'.split(), 'iwd_yuanti'))
MONSTER_POOLS['iwd_salamander'] = ((11850, 12580), ())
MONSTER_FAMILY.update(dict.fromkeys('ms6salf msmsalf rldsalfi sal8001 sal8005 sal8008 salamand salamanr'.split(), 'iwd_salamander'))
MONSTER_POOLS['iwd_frost_salamander'] = ((11860, 12590), ())
MONSTER_FAMILY.update(dict.fromkeys('invissal ms6salc msmsalc rwtsalf sal8013 salamanf wtsalf1 wtsalf2 wtsalf3'.split(), 'iwd_frost_salamander'))
MONSTER_POOLS['iwd_troll'] = ((11870, 12600), ())
MONSTER_FAMILY.update(dict.fromkeys('ms6trol pstroll ss1trl6 ss1trl7 ss1trl8 ss3trl6 ss3trl7 ss3trl8 troll trollt trolly'.split(), 'iwd_troll'))
MONSTER_POOLS['iwd_ice_troll'] = ((11880, 12610), ())
MONSTER_FAMILY.update(dict.fromkeys('icetroll trollice wticetr2'.split(), 'iwd_ice_troll'))
MONSTER_POOLS['iwd_verbeeg'] = ((11890, 12620), ())
MONSTER_FAMILY.update(dict.fromkeys('ms5verb rtfgverb ss2vrb6 ss2vrb7 ss2vrb8 verbdead verbeeg verbeegd'.split(), 'iwd_verbeeg'))
MONSTER_POOLS['iwd_frost_giant'] = ((11900, 12630), (10270, 10350))
MONSTER_FAMILY.update(dict.fromkeys('giantfn giantfro giantfg'.split(), 'iwd_frost_giant'))
MONSTER_POOLS['iwd_yeti'] = ((11910, 12640), (10240, 10320))
MONSTER_FAMILY.update(dict.fromkeys('ms4yeti rvsyeti vslyeti vsyeti kuyeti yetitund wtyeti'.split(), 'iwd_yeti'))
MONSTER_POOLS['iwd_umber_hulk'] = ((11920, 12650), (12180,))
MONSTER_FAMILY.update(dict.fromkeys('ms7umbh psumbh rldumbh ss3umb8 ss3umb9 traphulk uhlk8004 uhlk8009 uhlk8010 umberhlk'.split(), 'iwd_umber_hulk'))
MONSTER_POOLS['iwd_spider'] = ((11940, 12670), ())
MONSTER_FAMILY.update(dict.fromkeys('ms5gspi spidgi ms3hspi spidhu spidland ms6pspi msmpspi spidph udspider spidsw rdespiw spidkid spidwr'.split(), 'iwd_spider'))
MONSTER_POOLS['iwd_orog'] = ((11950, 12680), ())
MONSTER_FAMILY.update(dict.fromkeys('kaorog ms3orog neoorog neoorogs rudorog kaoroge neooroge rudoroge udorog neoorogg'.split(), 'iwd_orog'))
MONSTER_POOLS['iwd_ogre'] = ((11960, 12690), ())
MONSTER_FAMILY.update(dict.fromkeys('ecogre ms4ogr ogre sdogre sdogre2'.split(), 'iwd_ogre'))
MONSTER_POOLS['iwd_minotaur'] = ((11990, 12720), ())
MONSTER_FAMILY.update(dict.fromkeys('min8013 minotaur ms5mino psmino min8005 minotaub'.split(), 'iwd_minotaur'))
MONSTER_POOLS['iwd_iron_golem'] = ((12010, 12740), ())
MONSTER_FAMILY.update(dict.fromkeys('golemiro'.split(), 'iwd_iron_golem'))
MONSTER_UPGRADED |= set('as2dire bon8005 bon8013 bonegard giantfg gobehq1 goboeaxe goboebow lm2hwla lm2hwlay lm2hwna lm2hwnay lm2hwte lm2hwtey lmsham1 lmsham2 lmsham3 lmshkid mgo3 mor3 mor4 mor5 ms2gobb ms2gobe ms3tliz ms6yuan ms7bgrd ms7umbh mskb msmyuan orcewaxe orcewbow orcsham rdecwig rdeliztl rdeyuane sdgobtrn skelblad skelblaz skelblst skelbong skelserr slizman ss2gob1 ss2gob2 ss2gob3 ss2liz5 ss2liz6 ss2liz7 tlizman udorc wightcld wtyeti yuaewax yuaewbl yuaewbo yuaewsw yuantie yuantip yuchamp'.split())
PORTRAITS.update({'biknight': 12130, 'gobline': 12030, 'goblinsp': 12030, 'rkpgobe': 12030, 'rwtgice': 12060, 'wticetr1': 12060, 'wticetrl': 12060, 'mummyg': 12100, 'ktwgti1': 12170, 'wightimb': 12170, 'giantfs': 12150, 'neoorogc': 12040, 'lizking': 12070, 'myrkuls': 12120, 'sdelfof1': 12160, 'sdelfof2': 12160, 'sdelfof3': 12160, 'spknight': 12110, 'talonaf': 12090, 'wyrm': 12140, 'wtcyeti': 12050, 'vscyeti': 12050, 'deadvil': 11670, 'deadvilf': 12400})   # batch 8 elites (own art) + captive villagers
TOWNSMEN = TOWNSMEN + (12900, 12910)   # batch 8 extra: Kuldahar elder (man)


def monster_portrait(resref, seed):
    """Per-instance portrait for a generic monster resref (None if not ours). seed: stable per spawn, e.g. 'AREA:x:y'."""
    import zlib
    r = (resref or '').lower(); fam = MONSTER_FAMILY.get(r)
    if not fam:
        return None
    normal, up = MONSTER_POOLS[fam]
    pool = (up if r in MONSTER_UPGRADED else ()) or normal
    return pool[zlib.crc32(('%s:%s' % (r, seed)).encode()) % len(pool)]


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
            if por is None:
                por = monster_portrait(act['cre'], '%s:%s:%s' % (area.upper(), act['x'], act['y']))
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
    mesh_protos(cv.toee, specs, out)
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


def spawnable_pool(resref):
    """Portrait pool for runtime spawns of a generic monster (upgraded pool for elite resrefs), or None."""
    r = (resref or '').lower(); fam = MONSTER_FAMILY.get(r)
    if not fam:
        return None
    normal, up = MONSTER_POOLS[fam]
    return list((up if r in MONSTER_UPGRADED else ()) or normal)


def mesh_protos(toee, specs, out):
    """A critter on a foreign mesh (IWD2 kegs: barrel) gets its own critter proto: a copy of its proto row with the
    model column swapped, in an additive rules/protos/*.tab (Temple+ ProtoSystem). Swapping obj_f_base_mesh at runtime
    does not work: obj_create already built the model. Ids are stable per (proto, mesh), one file per pair."""
    d = os.path.join(out, 'modules', 'ToEE', 'rules', 'protos')
    for s in specs:
        if not s.get('mesh') or s.get('proto') not in toee.protos:
            continue
        key = (int(s['proto']), int(s['mesh']))
        pid = 14000 + (key[0] * 31 + key[1] * 7) % 1000
        while pid in toee.protos and toee.protos[pid][34].strip() != str(key[1]):
            pid = 14000 + (pid - 14000 + 1) % 1000
        if pid not in toee.protos:
            row = list(toee.protos[key[0]]); row[0] = str(pid); row[34] = str(key[1])
            toee.protos[pid] = row
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, 'ie2toee_%d.tab' % pid), 'w', encoding='latin-1').write('\t'.join(row).rstrip('\t') + '\n')
        s['proto'] = pid; s.pop('mesh', None)


# name ids: the engine shows description ids only below ~30000 (30100 fails, 29800 works), so spawn names live
# in the free gap above vanilla description.mes (max 20207) and below the item names (22000+)
def _actor_have(game, a):
    """Drop a --actor arg's DLG / BCS refs the game doesn't have (CREs naming e.g. 10catw.dlg that never shipped)."""
    def has(r, ext):
        try:
            game.read(r, ext); return True
        except Exception:
            return False
    idt, ar, sid, dlg, bcs = a.split(':')
    dlg = dlg if dlg and has(dlg, 'dlg') else ''
    return ':'.join((idt, ar, sid, dlg, ','.join(b for b in bcs.split(',') if b and has(b, 'bcs'))))


def convert_spawnables(game, toee_root, out, areas, scr_dirs=(), name_base=20300, options=None, tp_root=None, whole_game=False,
                       script_base=None, script_max=None):
    """Creatures that appear at runtime: CreateCreature("cre", ...) in the converted scripts/dialogs (scanned in
    scr_dirs), plus the area .INI spawns and ARE rest-encounter tables of `areas`. Writes <out>/ie_spawnables.py
    (SPECS: cre -> spawn spec, INI_SPAWNS, REST) and <out>/modules/ToEE/mes/description/ie2toee_spawn.mes."""
    import toeedata
    tx = ToEEIndex(toeedata.ToEEData(toee_root))
    cv = Converter(game, tx, options, tp_root=tp_root)
    refs, points, rest = set(), {}, {}
    for d in scr_dirs:
        for root, _, fs in os.walk(d):
            for f in fs:
                if f.endswith('.py'):
                    for r in re.findall(r'CreateCreature\w*\(c, "(\w+)"', open(os.path.join(root, f), encoding='cp1252', errors='replace').read()):
                        refs.add(r.lower())
    if whole_game:   # every CRE a script/dialog CreateCreature or a spawn point/rest table anywhere in the game names
        r_, where, _, _ = creature_refs(game, S.IdsSet(game))
        refs.update(r for r in r_ if set(where[r]) - {'area actor'})
        # IWD2 00s*/41s*: summoned/spawned monsters named only by SPL effects (summon spells), not by scripts
        refs.update(r.lower() for r in game.list('cre') if r.lower().startswith(('00s', '41s')))
    try:     # creatures named by summon spells (SPL opcode 67 / IWD2 410/411): ie_spawn.summon at runtime
        import ie_spells
        refs.update(c[2] for b in ie_spells.summon_table(game).values() for _, l in b for c in l)
    except Exception as e:
        print('warning: summon spells: %s' % e)
    for ar in areas:
        try:
            a = F.Are(game.read(ar, 'are'))
        except Exception:
            continue
        try:     # ARE spawn points are unused (0) in IWD/IWD2: their spawns are the area .INI files
            ini = F.parse_spawn_ini(game.read(ar, 'ini').decode('latin-1'))
        except Exception:
            ini = None
        if ini and (ini['enter'] or ini['events']):
            points[ar.upper()] = ini
            d_ = game.read(ar, 'are')
            if d_[4:8] == b'V9.1':        # ARE V9.1 0x54: average party level for area difficulty 2 / 3
                ini['diff'] = (d_[0x54], d_[0x55])
            refs.update(c['cre'] for k in ('enter', 'events') for g in ini[k] for c in g['critters'])
        r_ = a.rest
        if r_ and r_['creatures'] and r_['enabled']:
            rest[ar.upper()] = dict(r_, creatures=[c.lower() for c in r_['creatures']])
            refs.update(rest[ar.upper()]['creatures'])
    keep = ('resref', 'family', 'proto', 'model', 'scale', 'gender', 'alignment', 'hostility', 'abilities', 'levels',
            'monster_hd', 'hp', 'natural_ac', 'bab', 'to_hit_bonus', 'save_bonus', 'conditions', 'no_flee', 'cr', 'items',
            'spells', 'ai_strategy', 'name_id', 'portrait', 'portrait_pool', 'difficulty', 'feats', 'skills', 'mesh', 'ident',
            'script_id')
    specs, names, dlg_args, used, cre_dlg = {}, {}, [], set(), {}
    for i, r in enumerate(sorted(refs)):
        try:
            cre = iecre.Cre(game.read(r, 'cre'), r)
            s = cv.convert(cre, {'cre': r, 'name': r, 'x': 0, 'y': 0, 'orient': 0, 'schedule': 0xFFFFFF,
                                 'dialog': '', 'scripts': {}, 'embedded_cre': None})
        except Exception as e:
            print('spawnable %s: %s' % (r, e)); continue
        if s.get('status') != 'ok':
            continue
        s['resref'] = r
        por = PORTRAITS.get(r)
        if por is not None:
            s['portrait'] = por
        else:
            pool = spawnable_pool(r)
            if pool:
                s['portrait_pool'] = pool
            elif s.get('family') in ORC_FAMILIES or s.get('model') == 104:
                s['portrait_pool'] = list(ORC_PORTRAITS)
        dv = re.sub(r'\W', '', (cre.death_var or '').lower())
        if dv and dv != 'none':
            s['ident'] = dv          # IE: a created creature answers to its script name (N("Veira"))
        cre_dlg[r] = s.get('dialog') or ''
        if script_base and (s.get('dialog') or s.get('scripts')):
            # its own IE scripts + dialogue (ie_dialogue.py --actor IDENT::SID:DLG:BCS; AREA "" = per-instance at runtime)
            sid = script_base + len(dlg_args)
            if script_max and sid > script_max:
                print('spawnable %s: no script id left (%d..%d), its scripts stay off' % (r, script_base, script_max))
            else:
                idt = s.get('ident') or re.sub(r'\W', '', r)
                if idt in used:
                    idt = '%s_%s' % (idt, r)
                used.add(idt); s['ident'] = idt; s['script_id'] = sid
                dlg_args.append('%s::%d:%s:%s' % (idt, sid, s.get('dialog') or '', ','.join(s.get('scripts') or ())))
        nid = name_base + i
        nm = cv.text(cre.name_strref) if cre.name_strref >= 0 else ''
        names[nid] = (VARIANT_NAMES.get(r, {}).get(nm.strip(), nm) or r).replace('{', '(').replace('}', ')')
        s['name_id'] = nid
        specs[r] = {k: s[k] for k in keep if k in s}
    # INI critters with their own scripts (script_override / script_special_1.. / script_movement) or dialog: a
    # script of their own, ident = their script_name (ie_spawn.ini_critter passes the id to the spawn)
    for ar in sorted(points):
        for k in ('enter', 'events'):
            for g in points[ar][k]:
                for c in g['critters']:
                    if not script_base or c['cre'] not in specs or not (c.get('scripts') or c.get('dialog')):
                        continue
                    sid = script_base + len(dlg_args)
                    if script_max and sid > script_max:
                        print('INI spawn %s/%s: no script id left' % (ar, c['name'])); continue
                    idt = re.sub(r'\W', '', (c.get('script_name') or c['name']).lower())
                    if idt in used:
                        idt = '%s_%s' % (idt, ar.lower())
                    used.add(idt); c['ident'] = idt; c['script_id'] = sid
                    dlg_args.append('%s::%d:%s:%s' % (idt, sid, c.get('dialog') or cre_dlg.get(c['cre'], ''),
                                                      ','.join(c.get('scripts') or ())))
    mesh_protos(cv.toee, specs.values(), out)
    os.makedirs(out, exist_ok=True)
    dlg_args = [_actor_have(game, a) for a in dlg_args]
    mesd = os.path.join(out, 'modules', 'ToEE', 'mes', 'description'); os.makedirs(mesd, exist_ok=True)
    if names:
        open(os.path.join(mesd, 'ie2toee_spawn.mes'), 'w', encoding='cp1252', errors='replace').write(
            ''.join('{%d}{%s}\n' % kv for kv in sorted(names.items())))
    py = ['# Generated by ie2toee ie_creatures.py from the player\'s own IE install. Do not distribute.',
          'SPECS = {'] + ['    %r: %r,' % kv for kv in sorted(specs.items())] + ['}',
          'INI_SPAWNS = %r' % points, 'REST = %r' % rest]
    open(os.path.join(out, 'ie_spawnables.py'), 'w').write('\n'.join(py) + '\n')
    open(os.path.join(out, 'dialogue_actors.txt'), 'w').write(''.join('--actor %s\n' % a for a in dlg_args))
    print('spawnables: %d CREs (%d refs), INI spawns in %d areas, rest tables in %d' % (len(specs), len(refs), len(points), len(rest)))
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
    s3 = sub.add_parser('spawnables'); s3.add_argument('game'); s3.add_argument('toee'); s3.add_argument('out')
    s3.add_argument('--area', action='append', default=[]); s3.add_argument('--scr', action='append', default=[])
    s3.add_argument('--name-base', type=int, default=20300); s3.add_argument('--tp'); s3.add_argument('--whole-game', action='store_true')
    s3.add_argument('--option', action='append', default=[])
    s3.add_argument('--script-base', type=int, help='script ids base.. for spawnables with a dialog/scripts (dialogue_actors.txt)')
    s3.add_argument('--script-max', type=int)
    a = ap.parse_args()
    if a.cmd == 'spawnables':
        convert_spawnables(iefs.IEGame(a.game), a.toee, a.out, a.area, a.scr, a.name_base,
                           dict(kv.split('=', 1) for kv in a.option), a.tp, a.whole_game,
                           a.script_base, a.script_max)
        return
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
