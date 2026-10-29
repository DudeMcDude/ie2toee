"""Infinity Engine dialogue / script formats: TLK V1, IDS, DLG V1.0, BCS (compiled script) and the
text form of triggers/actions used inside DLG files.

Written from the IESDP format descriptions (https://gibberlings3.github.io/iesdp/); no GemRB code.
Everything here reads the player's own install at convert time; nothing it returns is meant to be shipped.

Common AST (shared by BCS and DLG):
    Call(name, args, neg=False)  - trigger / action / object function, e.g. Global("x","GLOBAL",1)
    Obj(...)                     - an object reference: name ("deathvar"), ids (Player1, NearestEnemyOf(..)),
                                   or a filter [EA.GENERAL.RACE.CLASS.SPECIFIC.GENDER.ALIGN]
    Sym(name)                    - an IDS symbol used as an integer (MALE, HUMAN, CHR...), resolved at run time
    Point(x, y)
    str / int                    - literal arguments
"""
import re, struct

# ----------------------------------------------------------------------------------------------- AST
class Call(object):
    __slots__ = ('name', 'args', 'neg', 'op')
    def __init__(self, name, args=(), neg=False, op=None):
        self.name, self.args, self.neg, self.op = name, list(args), neg, op
    def __repr__(self):
        return '%s%s(%s)' % ('!' if self.neg else '', self.name, ','.join(map(fmt_arg, self.args)))

class Obj(object):
    """name: death variable / script name; chain: object.ids functions outermost first (e.g. ['NearestEnemyOf',
    'Myself']); filt: dict of EA/GENERAL/... -> int or symbol; rect: (x0,y0,x1,y1) area restriction or None."""
    __slots__ = ('name', 'chain', 'filt', 'rect')
    def __init__(self, name='', chain=(), filt=None, rect=None):
        self.name, self.chain, self.filt, self.rect = name, list(chain), dict(filt or {}), rect
    def empty(self):
        return not (self.name or self.chain or any(self.filt.values()))
    def __repr__(self):
        if self.name:
            return '"%s"' % self.name
        s = ''
        if any(self.filt.values()):
            s = '[%s]' % '.'.join(str(self.filt.get(k, 0)) for k in OBJ_FILTER_FIELDS)
        for f in reversed(self.chain):
            s = '%s(%s)' % (f, s) if s else f
        return s or 'Nothing'

class Sym(object):
    __slots__ = ('name',)
    def __init__(self, name): self.name = name
    def __repr__(self): return self.name

class Point(object):
    __slots__ = ('x', 'y')
    def __init__(self, x, y): self.x, self.y = x, y
    def __repr__(self): return '[%d.%d]' % (self.x, self.y)

def fmt_arg(a):
    if isinstance(a, str):
        return '"%s"' % a
    return repr(a)

OBJ_FILTER_FIELDS = ('EA', 'GENERAL', 'RACE', 'CLASS', 'SPECIFIC', 'GENDER', 'ALIGN')

# ----------------------------------------------------------------------------------------------- TLK
class Tlk(object):
    """TLK V1 (dialog.tlk). get(strref) -> text ('' for unused entries)."""
    def __init__(self, data):
        if data[:8] != b'TLK V1  ':
            raise ValueError('not a TLK V1 file')
        self.lang, self.count, self.stroff = struct.unpack_from('<HII', data, 8)
        self.data = data
    @classmethod
    def load(cls, path):
        return cls(open(path, 'rb').read())
    def entry(self, strref):
        if strref < 0 or strref >= self.count:
            return None
        flags, sound, _vol, _pitch, off, ln = struct.unpack_from('<H8sIIII', self.data, 18 + strref * 26)
        raw = self.data[self.stroff + off:self.stroff + off + ln].split(b'\0')[0]
        try:            # Enhanced Edition TLKs are UTF-8, classic ones Windows-1252
            txt = raw.decode('utf-8')
        except UnicodeDecodeError:
            txt = raw.decode('cp1252', 'replace')
        return {'flags': flags, 'sound': sound.split(b'\0')[0].decode('latin-1'), 'text': txt}
    def get(self, strref):
        e = self.entry(strref)
        return e['text'] if e else ''

def find_tlk(root, lang=None, female=False):
    """dialog.tlk of a classic install (game root) or an Enhanced Edition install (lang/<locale>/dialog.tlk,
    default locale from lang= or the first of en_US / any). Returns a path or None."""
    import os
    name = 'dialogf.tlk' if female else 'dialog.tlk'
    def ci(d, n):
        try:
            for x in os.listdir(d):
                if x.lower() == n.lower():
                    return os.path.join(d, x)
        except OSError:
            pass
        return None
    p = ci(root, name)
    if p:
        return p
    ld = ci(root, 'lang')
    if ld:
        locs = sorted(os.listdir(ld))
        order = ([lang] if lang else []) + ['en_US'] + locs
        for loc in order:
            d = ci(ld, loc)
            if d and ci(d, name):
                return ci(d, name)
    return None

class StrrefText(object):
    """Text source used by the converters: real TLK text when the player's dialog.tlk is available,
    otherwise '[strref N]' placeholders (so the structure can be built and tested without any text)."""
    def __init__(self, tlk=None):
        self.tlk = tlk
    def __call__(self, strref):
        if strref in (0xFFFFFFFF, -1):
            return ''
        if self.tlk is not None:
            t = self.tlk.get(strref)
            if t:
                return t
        return '[strref %d]' % strref

# ----------------------------------------------------------------------------------------------- IDS
class Ids(object):
    """IDS lookup table (value <-> name). For trigger/action IDS also keeps the parameter signature."""
    def __init__(self, text=None):
        self.by_val, self.by_name, self.sig = {}, {}, {}
        if text:
            self.parse(text)
    def parse(self, text):
        if isinstance(text, bytes):
            if text[:2] == b'\xff\xff':
                raise ValueError('encrypted IDS file (not supported yet)')
            text = text.decode('latin-1')
        for line in text.splitlines():
            m = re.match(r'\s*(0x[0-9A-Fa-f]+|-?\d+)\s+([^\s(]+)\s*(?:\((.*)\))?', line)
            if not m:
                continue
            v = int(m.group(1), 0); n = m.group(2)
            self.add(v, n, m.group(3))
        return self
    def add(self, v, n, sig=None):
        self.by_val.setdefault(v, n); self.by_name.setdefault(n.lower(), v)
        if sig is not None:
            self.sig.setdefault(v, parse_sig(sig))
    def name(self, v, default=None):
        return self.by_val.get(v, default)
    def value(self, n, default=None):
        return self.by_name.get(n.lower(), default)

def parse_sig(sig):
    """'S:Name*,S:Area*,I:Value*Boolean' -> [('S','Name',''), ('S','Area',''), ('I','Value','Boolean')]"""
    out = []
    for p in sig.split(','):
        p = p.strip()
        if not p:
            continue
        m = re.match(r'([SIOPA])\s*:\s*([^*]*)\*?(.*)', p)
        if m:
            out.append((m.group(1), m.group(2).strip(), m.group(3).strip()))
    return out

class IdsSet(object):
    """The IDS files the script code needs. Loaded from the player's install (TRIGGER/ACTION/OBJECT/...);
    `fallback` (dict like {'triggers': {hex: [name, sig]}, 'actions': {...}, 'ids': {file: {val: name}}})
    fills gaps, e.g. while developing against an install that lacks DEFAULT.BIF."""
    FILES = ('trigger', 'action', 'object', 'ea', 'general', 'race', 'class', 'specific', 'gender', 'alignmen',
             'state', 'stats', 'svtriobj', 'spell')
    def __init__(self, game=None, fallback=None):
        self.t = {f: Ids() for f in self.FILES}
        self.missing = []
        for f in self.FILES:
            data = None
            if game is not None:
                try:
                    data = game.read(f, 'ids')
                except Exception:
                    data = None
            if data:
                try:
                    self.t[f].parse(data)
                except ValueError:
                    self.missing.append(f)
            else:
                self.missing.append(f)
        if fallback:
            for k, (n, s) in fallback.get('triggers', {}).items():
                self.t['trigger'].add(int(k, 16), n, s)
            for k, (n, s) in fallback.get('triggers_bg2', {}).items():
                self.t['trigger'].add(int(k, 16), n, s)
            for k, (n, s) in fallback.get('actions', {}).items():
                self.t['action'].add(int(k), n, s)
            for f, d in fallback.get('ids', {}).items():
                for v, n in d.items():
                    self.t[f].add(int(v), n)
    def __getitem__(self, f):
        return self.t[f]

# ----------------------------------------------------------------------------------------------- DLG
class Dlg(object):
    """DLG V1.0. states: list of dict(text, first, count, trigger); transitions: list of dict(flags, text, journal,
    trigger, action, next_dlg, next_state); trigger/action tables are the raw script strings."""
    FLAG_TEXT, FLAG_TRIGGER, FLAG_ACTION, FLAG_END, FLAG_JOURNAL = 1, 2, 4, 8, 16
    def __init__(self, data, resref=''):
        if data[:8] != b'DLG V1.0':
            raise ValueError('not a DLG V1.0 file')
        self.resref = resref.lower()
        (ns, so, nt, to, sto, nst, tto, ntt, ao, na) = struct.unpack_from('<10I', data, 8)
        self.flags = struct.unpack_from('<I', data, 0x30)[0] if so >= 0x34 else 0
        def strtab(off, n):
            out = []
            for i in range(n):
                o, l = struct.unpack_from('<II', data, off + i * 8)
                out.append(data[o:o + l].decode('latin-1'))
            return out
        self.state_triggers, self.trans_triggers, self.actions = strtab(sto, nst), strtab(tto, ntt), strtab(ao, na)
        self.states = []
        for i in range(ns):
            text, first, cnt, trig = struct.unpack_from('<IIII', data, so + i * 16)
            self.states.append({'text': text, 'first': first, 'count': cnt,
                                'trigger': None if trig == 0xFFFFFFFF else trig})
        self.transitions = []
        for i in range(nt):
            fl, text, jour, trig, act = struct.unpack_from('<IIIII', data, to + i * 32)
            nd = data[to + i * 32 + 20:to + i * 32 + 28].split(b'\0')[0].decode('latin-1').lower()
            nxt = struct.unpack_from('<I', data, to + i * 32 + 28)[0]
            self.transitions.append({
                'flags': fl, 'text': text if fl & 1 else None, 'journal': jour if fl & 16 else None,
                'trigger': trig if fl & 2 else None, 'action': act if fl & 4 else None,
                'end': bool(fl & 8), 'next_dlg': None if fl & 8 else nd, 'next_state': None if fl & 8 else nxt})
    def state_trigger(self, i):
        t = self.states[i]['trigger']
        return self.state_triggers[t] if t is not None and t < len(self.state_triggers) else ''
    def trans_trigger(self, t):
        i = self.transitions[t]['trigger']
        return self.trans_triggers[i] if i is not None and i < len(self.trans_triggers) else ''
    def trans_action(self, t):
        i = self.transitions[t]['action']
        return self.actions[i] if i is not None and i < len(self.actions) else ''

# ----------------------------------------------------------------------------------------------- script text
_TOK = re.compile(r'''\s*(?:
    (?P<str>"[^"]*"|~[^~]*~)
  | (?P<num>-?0x[0-9A-Fa-f]+|-?\d+)
  | (?P<brk>\[[^\]]*\])
  | (?P<id>[A-Za-z_][A-Za-z0-9_#\-]*)
  | (?P<p>[(),!])
)''', re.X)

def _strip_comments(s):
    s = re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)
    return re.sub(r'//[^\n]*', ' ', s)

def tokenize(s):
    s = _strip_comments(s); pos, out = 0, []
    while pos < len(s):
        if s[pos:].strip() == '':
            break
        m = _TOK.match(s, pos)
        if not m or m.end() == pos:
            raise SyntaxError('cannot tokenize at %r' % s[pos:pos + 30])
        k = m.lastgroup; v = m.group(k); pos = m.end()
        out.append((k, v))
    return out

def _bracket(v):
    inner = v[1:-1].strip()
    parts = [p.strip() for p in inner.split('.')]
    if len(parts) == 2 and all(re.match(r'-?\d+$', p) for p in parts):
        return Point(int(parts[0]), int(parts[1]))
    filt = {}
    for k, p in zip(OBJ_FILTER_FIELDS, parts):
        if p in ('', '0'):
            continue
        filt[k] = int(p, 0) if re.match(r'-?(0x)?\d+$', p) else Sym(p.upper())
    return Obj(filt=filt)

OBJECT_FUNCS = None  # set by callers who know object.ids names; text parser treats nested calls as Obj chains

def parse_script_text(s, object_names=None):
    """Parse a DLG trigger or action string (or a BAF-like list) into a list of Call. Nested calls inside an
    argument are object functions (NearestEnemyOf(Myself)) except for ActionOverride's 2nd argument, which is an
    action. Bare identifiers are object.ids names when listed in object_names, otherwise IDS symbols."""
    objn = set(n.lower() for n in (object_names or ()))
    toks = tokenize(s); i = [0]
    def peek(k=0):
        return toks[i[0] + k] if i[0] + k < len(toks) else (None, None)
    def take():
        t = toks[i[0]]; i[0] += 1; return t
    def call(neg=False, as_action=False):
        k, v = take()
        if k != 'id':
            raise SyntaxError('expected name, got %r' % (v,))
        args = []
        if peek()[1] == '(':
            take()
            idx = 0
            while peek()[1] != ')':
                if peek()[0] is None:
                    raise SyntaxError('unterminated call %s' % v)
                inner_action = v.lower() == 'actionoverride' and idx == 1
                args.append(arg(inner_action))
                idx += 1
                if peek()[1] == ',':
                    take()
            take()
        return Call(v, args, neg)
    def arg(as_action):
        k, v = peek()
        if k == 'str':
            take(); return v[1:-1]
        if k == 'num':
            take(); return int(v, 0) if v[:2].lower() in ('0x', '0b', '0o') or not v.startswith('0') else int(v, 10)
        if k == 'brk':
            take(); return _bracket(v)
        if k == 'id':
            if as_action:
                return call()
            if peek(1)[1] == '(':      # object function chain: NearestEnemyOf(Myself), LastTalkedToBy(Myself)
                take(); take(); inner = arg(False) if peek()[1] != ')' else Obj()
                take()
                if isinstance(inner, Obj):
                    return Obj(name=inner.name, chain=[v] + inner.chain, filt=inner.filt)
                if isinstance(inner, str):
                    return Obj(name=inner, chain=[v])
                return Obj(chain=[v])
            take()
            if v.lower() in objn:
                return Obj(chain=[v])
            return Sym(v)
        raise SyntaxError('bad argument %r' % (v,))
    out = []
    while peek()[0] is not None:
        neg = False
        while peek()[1] == '!':
            take(); neg = not neg
        out.append(call(neg))
    return out

# ----------------------------------------------------------------------------------------------- BCS
class Bcs(object):
    """Compiled script. blocks: list of (triggers: [Call], responses: [(weight, [Call])])."""
    def __init__(self, data, ids, resref='', layout=None):
        self.resref = resref.lower(); self.ids = ids; self.layout = layout
        self.text = data.decode('latin-1')
        self.toks = re.findall(r'"[^"]*"|\[[^\]]*\]|-?\d+|[A-Z]{2}', self.text)
        self.i = 0; self.unknown = set()
        self.blocks = self._script()

    def _t(self):
        t = self.toks[self.i]; self.i += 1; return t
    def _expect(self, tag):
        t = self._t()
        if t != tag:
            raise SyntaxError('%s: expected %s got %s at token %d' % (self.resref, tag, t, self.i))
    def _int(self):
        return int(self._t())
    def _str(self):
        t = self._t()
        if not t.startswith('"'):
            raise SyntaxError('%s: expected string got %s' % (self.resref, t))
        return t[1:-1]

    def _script(self):
        self._expect('SC'); blocks = []
        while self.toks[self.i] == 'CR':
            self._t(); self._expect('CO'); trig = []
            while self.toks[self.i] == 'TR':
                trig.append(self._trigger())
            self._expect('CO'); self._expect('RS'); resp = []
            while self.toks[self.i] == 'RE':
                self._t(); w = self._int(); acts = []
                while self.toks[self.i] == 'AC':
                    acts.append(self._action())
                self._expect('RE'); resp.append((w, acts))
            self._expect('RS'); self._expect('CR'); blocks.append((trig, resp))
        self._expect('SC')
        return blocks

    def _object(self):
        self._expect('OB'); ints = []
        while re.match(r'-?\d+$', self.toks[self.i]):
            ints.append(self._int())
        rect = None
        if self.toks[self.i].startswith('['):
            r = [int(x) for x in self._t()[1:-1].split('.')]
            rect = tuple(r) if any(v != -1 for v in r) else None
        name = self._str()
        iwd2 = self.layout == 'iwd2' or (self.layout is None and len(ints) == 13)
        if iwd2:   # IWD2: 2 more ints after the name
            while re.match(r'-?\d+$', self.toks[self.i]): self._int()
        self._expect('OB')
        # IWD / BG2 / EE layout (12 ints): EA GENERAL RACE CLASS SPECIFIC GENDER ALIGN ID1..ID5; EE engines may
        # append extra fields after the identifiers (kept out of the filter). PST (14) inserts FACTION TEAM after EA.
        # IWD2 (13 + 2 after the name) inserts SUBRACE after ALIGN (kept in the filter as SUBRACE).
        sub = 0
        if iwd2:
            sub = ints[7]; ints = ints[:7] + ints[8:]
        if self.layout == 'pst' or (self.layout is None and len(ints) == 14):
            ints = [ints[0]] + ints[3:]
        filt = dict((k, v) for k, v in zip(OBJ_FILTER_FIELDS, ints[:7]) if v)
        if sub: filt['SUBRACE'] = sub
        # stored innermost first (Myself, NearestEnemyOf) -> keep outermost first like the text form
        chain = [self.ids['object'].name(v, 'Object%d' % v) for v in reversed(ints[7:12]) if v]
        return Obj(name=name, chain=chain, filt=filt, rect=rect)

    def _trigger(self):
        self._expect('TR')
        tid, i1, flags, i2, i3 = [self._int() for _ in range(5)]
        s1, s2 = self._str(), self._str()
        obj = self._object(); self._expect('TR')
        name = self.ids['trigger'].name(tid)
        sig = self.ids['trigger'].sig.get(tid)
        if name is None:
            name = 'Trigger_0x%04X' % tid; self.unknown.add(name)
        return Call(name, _spell_res(sig, _place(sig, [obj], [i1, i2, i3], [s1, s2], None), s1), bool(flags & 1),
                    op=tid)

    def _action(self):
        self._expect('AC'); aid = self._int()
        o = [self._object() for _ in range(3)]
        i1 = self._int(); px, py = self._int(), self._int(); i2, i3 = self._int(), self._int()
        s1, s2 = self._str(), self._str(); self._expect('AC')
        name = self.ids['action'].name(aid); sig = self.ids['action'].sig.get(aid)
        if name is None:
            name = 'Action_%d' % aid; self.unknown.add(name)
        c = Call(name, _spell_res(sig, _place(sig, o[1:], [i1, i2, i3], [s1, s2], Point(px, py)), s1), op=aid)
        if not o[0].empty() and aid != 1:
            return Call('ActionOverride', [o[0], c], op=1)
        return c

_AREA_TAGS = ('area', 'scope', 'area1', 'area2', 'areaname')

def _spell_res(sig, args, s1):
    """EE '...RES' spell actions/triggers share their opcode with the SPELL.IDS form (Spell/SpellRES, HaveSpell/
    HaveSpellRES); the compiled script stores the resref in the first string slot. Put it in the I:Spell slot so
    generated code sees the resref (a str) instead of 0."""
    if sig and s1:
        for k, p in enumerate(sig):
            if p[0] == 'I' and p[2].lower() == 'spell' and k < len(args):
                args[k] = s1.lower()
                break
    return args

def spell_resref(v, spell_ids=None):
    """SPELL.IDS number (or symbol / resref string) -> spell resref, by the IE convention: 1xxx SPPR, 2xxx SPWI,
    3xxx SPIN, 4xxx SPCL + the last three digits."""
    if isinstance(v, Sym):
        v = spell_ids.value(v.name) if spell_ids is not None else None
        if v is None:
            return None
    if isinstance(v, str):
        return v.lower() or None
    if not isinstance(v, int) or v <= 0:
        return None
    pre = {1: 'sppr', 2: 'spwi', 3: 'spin', 4: 'spcl'}.get(v // 1000)
    return pre + '%03d' % (v % 1000) if pre else None

def _place(sig, objs, ints, strs, point):
    """Map the fixed compiled parameter slots onto the IDS signature order. Strings of Name+Area pairs are stored
    concatenated (area first, 6 chars) in one slot."""
    if sig is None:   # unknown opcode: keep every non-default slot so nothing is lost
        out = [o for o in objs if not o.empty()] + [v for v in ints if v] + [s for s in strs if s]
        if point is not None and (point.x or point.y):
            out.append(point)
        return out
    oi = ii = si = 0; out = []
    stypes = [p for p in sig if p[0] == 'S']
    concat = len(stypes) >= 2 and any(p[1].lower() in _AREA_TAGS for p in stypes) and \
        sum(1 for s in strs if s) < len(stypes)
    split = []
    if concat:
        for s in strs:
            split += [s[:6], s[6:]] if s else []
    for typ, tag, idsf in sig:
        if typ == 'O':
            out.append(objs[oi] if oi < len(objs) else Obj()); oi += 1
        elif typ == 'I':
            v = ints[ii] if ii < len(ints) else 0; ii += 1
            out.append(v)
        elif typ == 'P':
            out.append(point if point is not None else Point(-1, -1))
        elif typ == 'S':
            if concat:
                # signature order is Name, Area; storage is AREA+NAME
                pair = si // 2; area, nm = (split[pair * 2:pair * 2 + 2] + ['', ''])[:2]
                out.append(area if tag.lower() in _AREA_TAGS else nm)
            else:
                out.append(strs[si] if si < len(strs) else '')
            si += 1
        elif typ == 'A':
            out.append(None)
    return out

def walk_calls(calls):
    """Yield every Call including nested ActionOverride actions."""
    for c in calls:
        yield c
        for a in c.args:
            if isinstance(a, Call):
                for x in walk_calls([a]):
                    yield x
