# ie_vars: save-backed store for every IE script variable (Python 2.7 in game; also importable offline for tests).
#
# One dict, keyed by scope:name (scope upper case, names lower case without spaces, as the IE ignores both):
#   'GLOBAL:join_posse'   'AR1200:goblin_team_1_state'   'LOCALS:10gob_19:#timer18'   'LOCALS:10hedron:#talked'
# Values are ints (timers hold absolute script-clock stamps). No slot table, so it scales to any number of variables
# (later chapters, BG) - ToEE's 2000 game.global_vars keep only the few flags the engine side reads:
#   990 intro played (ie_movies_rt), 991 new-game IE globals set (ie_cutscene), 992 TOKEN_VAR (below).
#
# Persistence: <save dir>/<save name>.iev next to the save's archive (.tfai/.tfaf), plain JSON (no pickling, no object handles),
# written by Temple+'s post_save hook and read by its load hook (templeplus.savehook; chained by install_hooks(),
# never replacing what is there, e.g. a Co8 _co8init hook). Every store has a random token that is also written to
# game.global_vars[TOKEN_VAR] (part of the save): a new game (token var 0) or a save whose .iev is missing clears the
# dict on first use, so values cannot leak from one game or save into another. The load hook clears before reading.
import os, random

TOKEN_VAR = 992
VERSION = 1
EXT = '.iev'

STORE = {}
_state = {'token': None, 'hooked': False, 'last_file': None}
_log = [None]          # optional logger (ie_runtime.log)

def _say(msg):
    f = _log[0]
    if f:
        try:
            f(msg)
        except Exception:
            pass
    else:
        try:
            print('IE_VARS ' + msg)
        except Exception:
            pass

def _game():
    try:
        from toee import game
        return game
    except Exception:
        return None

def _gv(game, v=None):
    if game is None:
        return None
    try:
        if v is None:
            return game.global_vars[TOKEN_VAR]
        game.global_vars[TOKEN_VAR] = v
    except Exception:
        return None

def clear(reason=''):
    STORE.clear(); _state['token'] = None
    if reason:
        _say('clear (%s)' % reason)

def _check():
    """Before any read/write in game: the store must belong to the running game (token var)."""
    g = _game()
    if g is None:
        return
    t = _gv(g)
    if t is None:
        return                    # (no readable global_vars: keep the store)
    if t and t == _state['token']:
        return
    if STORE:
        _say('store of another game/save dropped (token %r, game %r): %d vars' % (_state['token'], t, len(STORE)))
    STORE.clear()
    nt = random.randint(1, 0x7fffffff)
    _state['token'] = nt; _gv(g, nt)
    if t:
        _say('no variable file for this save (token %d): starting empty' % t)

def get(k, default=0):
    _check()
    return STORE.get(k, default)

def put(k, v):
    _check()
    v = int(v)
    if v == 0:
        STORE.pop(k, None)        # 0 = unset in the IE: keeps the file small
    else:
        STORE[k] = v
    return v

def items():
    _check()
    return list(STORE.items())

# ------------------------------------------------------------------------------------------------ files
def dumps():
    import json
    return json.dumps({'version': VERSION, 'token': _state['token'], 'vars': STORE}, sort_keys=True, indent=0)

def loads(text):
    import json
    d = json.loads(text)
    vs = d.get('vars') or {}
    STORE.clear()
    for k, v in vs.items():
        STORE[str(k)] = int(v)
    _state['token'] = d.get('token')

def save_dir(filename):
    """Folder holding the save archive <filename>.tfai (Temple+ 'save\\' = modules\\<module>\\save), searched from
    the game folder. Temple+ names the save's .gsi <filename><display name>.gsi, so the archive is the key."""
    cands = []
    try:
        for m in os.listdir('modules'):
            for sd in ('save', 'Save'):
                if os.path.isdir(os.path.join('modules', m, sd)):
                    cands.append(os.path.join('modules', m, sd))
    except Exception:
        pass
    cands += ['save', 'Save', os.path.join('data', 'save')]
    for d in cands:
        if os.path.isfile(os.path.join(d, filename + '.tfai')):
            return d
    return None

def write_file(path):
    tmp = path + '.tmp'
    f = open(tmp, 'w')
    try:
        f.write(dumps())
    finally:
        f.close()
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp, path)

def read_file(path):
    f = open(path, 'r')
    try:
        loads(f.read())
    finally:
        f.close()

def on_save(filename):
    try:
        _check()
        d = save_dir(filename)
        if d is None:
            _say('save %s: save folder not found, variables NOT saved' % filename); return
        p = os.path.join(d, filename + EXT)
        write_file(p); _state['last_file'] = p
        _say('saved %d vars to %s' % (len(STORE), p))
    except Exception as e:
        _say('save %s failed: %s' % (filename, e))

def on_load(filename):
    clear()
    try:
        d = save_dir(filename)
        p = d and os.path.join(d, filename + EXT)
        if not p or not os.path.isfile(p):
            _say('load %s: no %s file, variables start empty' % (filename, EXT)); return
        read_file(p); _state['last_file'] = p
        g = _game(); t = _gv(g)
        if g is not None and t != _state['token']:
            _say('load %s: token %r does not match the save (%r): dropped' % (filename, _state['token'], t))
            clear()
            return
        _say('loaded %d vars from %s' % (len(STORE), p))
    except Exception as e:
        clear(); _say('load %s failed: %s' % (filename, e))

# ------------------------------------------------------------------------------------------------ Temple+ hooks
def install_hooks():
    """Chain on_save / on_load into templeplus.savehook (Temple+ calls its load() on every load and post_save() after
    every save, looking the functions up each time). The previous functions still run (Co8 _co8init etc.)."""
    if _state['hooked']:
        return True
    try:
        import templeplus.savehook as sh
    except Exception as e:
        _say('no templeplus.savehook (%s): variables will not be saved' % e)
        return False
    if getattr(sh, '_ie_vars_hooked', False):
        _state['hooked'] = True; return True
    prev_load, prev_save = getattr(sh, 'load', None), getattr(sh, 'post_save', None)
    def load(filename):
        on_load(filename)
        if prev_load:
            return prev_load(filename)
    def post_save(filename):
        on_save(filename)
        if prev_save:
            return prev_save(filename)
    sh.load, sh.post_save = load, post_save
    sh._ie_vars_hooked = True
    _state['hooked'] = True
    _say('save/load hooks installed')
    return True
