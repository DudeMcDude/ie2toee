"""Python code generation for IE triggers / actions (shared by dlg2toee and bcs2py).

Produces Python 2.7 source that only calls ie_runtime (T.*, A.*, O/N/F, rt.CONT). IDS symbols are resolved to
numbers at convert time with the player's IDS files when possible; unknown symbols are kept as strings and the
runtime logs them. Variable names seen in Global/SetGlobal-style calls are collected so the converter can
allocate persistent game.global_vars slots for them.
"""
import keyword
import iescript as S

VAR_TRIGGERS = {'global', 'globalgt', 'globallt', 'bitglobal', 'globaltimerexpired', 'globaltimernotexpired',
                'globaltimerexact'}
VAR_ACTIONS = {'setglobal', 'incrementglobal', 'bitglobal', 'setglobaltimer', 'setglobalrandom'}
STRREF_ACTIONS = {'floatmessage', 'displaystring', 'displaystringhead', 'displaystringnoname',
                  'displaystringnonamedlg', 'addjournalentry'}
PY_RENAME = {'True': 'True_', 'False': 'False_'}

def pystr(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch in '\\"':
            out.append('\\' + ch)
        elif 32 <= o < 127:
            out.append(ch)
        else:   # ToEE text is Windows-1252: escape its byte (EE TLKs are UTF-8: em dash U+2014 -> \x97)
            try:
                out.append(''.join('\\x%02x' % b for b in bytearray(ch.encode('cp1252'))))
            except UnicodeEncodeError:
                out.append('?')
    return '"%s"' % ''.join(out)

class Gen(object):
    def __init__(self, ids, ident, area):
        self.ids, self.ident, self.area = ids, ident, area
        self.vars = set()          # var keys as ie_runtime.var_key would build them
        self.unknown = {}          # name -> count (not in TRIGGER/ACTION.IDS)
        self.strrefs = set()       # strrefs used by actions (FloatMessage...) -> ie_strings.py
        self.journals = {}         # journal strref -> kind ('quest' / 'info' / 'done') -> ToEE logbook quests

    # -------------------------------------------------------------- names / signatures
    def _canon(self, kind, name):
        t = self.ids['trigger' if kind == 'T' else 'action']
        v = t.value(name)
        if v is None:
            self.unknown[kind + ':' + name] = self.unknown.get(kind + ':' + name, 0) + 1
            return name, None
        return t.name(v), t.sig.get(v)

    def _sym(self, sym, idsfile):
        cands = [idsfile.lower()] if idsfile else []
        cands += [f for f in ('ea', 'general', 'race', 'class', 'specific', 'gender', 'alignmen', 'stats', 'state')
                  if f not in cands]
        alias = {'align': 'alignmen', 'alignment': 'alignmen', 'stat': 'stats'}
        for f in cands:
            f = alias.get(f, f)
            try:
                v = self.ids[f].value(sym.name)
            except KeyError:
                continue
            if v is not None:
                return str(v)
        return pystr(sym.name)

    # -------------------------------------------------------------- expressions
    def obj(self, o):
        if o is None:
            return 'None'
        if o.name and not o.chain:
            return 'N(c, %s)' % pystr(o.name)
        if o.filt and not o.chain:
            return 'F(c, %s)' % ', '.join('%s=%s' % (k, v if isinstance(v, int) else self._sym(v, k))
                                          for k, v in sorted(o.filt.items()))
        if not o.chain:
            return 'O(c, "Myself")' if not o.name else 'N(c, %s)' % pystr(o.name)
        inner = None
        if o.name:
            inner = 'N(c, %s)' % pystr(o.name)
        elif o.filt:
            inner = self.obj(S.Obj(filt=o.filt))
        for f in reversed(o.chain):
            inner = 'O(c, %s)' % pystr(f) if inner is None else 'O(c, %s, %s)' % (pystr(f), inner)
        return inner

    def arg(self, a, param=None):
        if isinstance(a, str):
            return pystr(a)
        if isinstance(a, bool):
            return str(int(a))
        if isinstance(a, int):
            return str(a)
        if isinstance(a, S.Sym):
            if param and param[0] == 'O':
                return 'O(c, %s)' % pystr(a.name)
            return self._sym(a, param[2] if param else None)
        if isinstance(a, S.Point):
            return '(%d, %d)' % (a.x, a.y)
        if isinstance(a, S.Obj):
            return self.obj(a)
        if isinstance(a, S.Call):
            return 'lambda c: %s' % self.action(a)
        if a is None:
            return 'None'
        return repr(a)

    def _args(self, call, sig):
        out = []
        for i, a in enumerate(call.args):
            p = sig[i] if sig and i < len(sig) else None
            out.append(self.arg(a, p))
        return out

    def _note_var(self, call, kind):
        n = call.name.lower()
        if (kind == 'T' and n in VAR_TRIGGERS) or (kind == 'A' and n in VAR_ACTIONS):
            if len(call.args) >= 2 and isinstance(call.args[0], str) and isinstance(call.args[1], str):
                self.vars.add(self.var_key(call.args[0], call.args[1]))
        if kind == 'T' and (n.startswith('numtimestalked') or n.startswith('numberoftimestalked')) or (kind == 'A' and n == 'setnumtimestalkedto'):
            self.vars.add(self.var_key('#talked', 'LOCALS'))
        if n in ('starttimer', 'startrandomtimer', 'timeractive', 'timerexpired') and call.args and \
                isinstance(call.args[0], int):
            self.vars.add(self.var_key('#timer%d' % call.args[0], 'LOCALS'))

    def var_key(self, name, scope):
        s = scope.upper(); n = name.lower()
        if s == 'GLOBAL':
            return 'global:' + n
        if s == 'LOCALS':
            return 'locals:%s:%s' % (self.ident.lower(), n)
        if s == 'MYAREA':
            s = self.area.upper()
        return 'area:%s:%s' % (s.lower(), n)

    def trigger(self, call):
        name, sig = self._canon('T', call.name)
        self._note_var(call, 'T')
        e = 'T.%s(%s)' % (PY_RENAME.get(name, name), ', '.join(['c'] + self._args(call, sig)))
        return ('not ' + e) if call.neg else e

    def condition(self, calls):
        """AND of triggers with OR(n) groups -> python expression."""
        parts, i = [], 0
        while i < len(calls):
            t = calls[i]
            if t.name.lower() == 'or' and t.args and isinstance(t.args[0], int):
                n = t.args[0]
                grp = [self.trigger(x) for x in calls[i + 1:i + 1 + n]]
                parts.append('(' + ' or '.join(grp or ['False']) + ')')
                i += 1 + n
            else:
                parts.append(self.trigger(t)); i += 1
        return ' and '.join(parts) if parts else 'True'

    def action(self, call):
        if call.name.lower() == 'continue':
            return 'rt.CONT(c)'
        name, sig = self._canon('A', call.name)
        self._note_var(call, 'A')
        if sig:
            for p, a in zip(sig, call.args):
                if p[0] == 'I' and 'strref' in (p[1] + p[2]).lower() and isinstance(a, int):
                    self.strrefs.add(a)
        if name.lower() in STRREF_ACTIONS:
            self.strrefs.update(a for a in call.args if isinstance(a, int) and a > 0)
        if name.lower() in ('addjournalentry', 'setquestdone') and call.args and isinstance(call.args[0], int) and call.args[0] > 0:
            ka = str(call.args[1]).upper() if len(call.args) > 1 else ''
            k = 'done' if name.lower() == 'setquestdone' or 'DONE' in ka or ka == '2' else 'info' if 'INFO' in ka or ka == '4' else 'quest'
            self.journals.setdefault(call.args[0], k); self.strrefs.add(call.args[0])
        if name.lower() == 'actionoverride' and len(call.args) == 2:
            for x in S.walk_calls([call.args[1]]):
                self._note_var(x, 'A')
            return 'A.ActionOverride(c, %s, lambda c: %s)' % (self.arg(call.args[0]), self.action(call.args[1]))
        return 'A.%s(%s)' % (name, ', '.join(['c'] + self._args(call, sig)))

    def action_list(self, calls):
        items = []
        for a in calls:
            if a.name.lower() == 'continue':
                items.append('rt.CONT')
            else:
                items.append('lambda c: %s' % self.action(a))
        return '[%s]' % ', '.join(items)
