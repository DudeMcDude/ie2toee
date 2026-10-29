# ie2toee runtime: converted IE items (docs/items.md). Python 2.2 (ToEE / Temple+ embedded interpreter).
# Data: ie_itemmap.py, generated on the player's machine by proto/ie_items.py convert:
#   ITEMS[res] = {p: base proto, c: [[condition, arg1, arg2]], w: worth (cp), n: name id (description .mes; n+1 = unidentified),
#                 i: inventory icon id, id: starts identified, q: quantity, ch: charges, m: magical, k: kind, s: status}
#   CONTAINERS[AREA] = [{name, toee: [x, y], proto, lock, items: [[res, qty]]}]
#   STORES[res] = {type, sell, buy, items: [[res, count]], container}
from toee import *
from utilities import location_from_axis

try:
    import ie_itemmap
    ITEMS, CONTAINERS, STORES = ie_itemmap.ITEMS, ie_itemmap.CONTAINERS, ie_itemmap.STORES
except ImportError:
    ITEMS, CONTAINERS, STORES = {}, {}, {}

LOG = [None]
# ITEM-ADJ-5: writing obj_f_item_spell_charges_idx hung the game in the pilot; wands keep the ToEE charge count
SET_CHARGES = 0
_SEEN = {}


def _log(s):
    try:
        if callable(LOG[0]):
            LOG[0](s)
        elif LOG[0]:
            f = open(LOG[0], 'a'); f.write(s + '\n'); f.close()
    except Exception:
        pass

# vanilla Python constants below obj_f_hp_pts are off by two in Temple+ (see ie_critters.FIELDS)
FIELDS = {'obj_f_description': 25}


def _field(f):
    if FIELDS.has_key(f):
        return FIELDS[f]
    return globals()[f]


def _c(name, default=None):
    try:
        return globals()[name]
    except KeyError:
        return default

# condition argument names -> engine enums (fallbacks: Temple+ enum values)
_ARG = {'saving_throw_fortitude': ('D20_Save_Fortitude', 0), 'saving_throw_reflex': ('D20_Save_Reflex', 1),
        'saving_throw_will': ('D20_Save_Will', 2),
        'attribute_strength': ('stat_strength', 0), 'attribute_dexterity': ('stat_dexterity', 1),
        'attribute_constitution': ('stat_constitution', 2), 'attribute_intelligence': ('stat_intelligence', 3),
        'attribute_wisdom': ('stat_wisdom', 4), 'attribute_charisma': ('stat_charisma', 5),
        'Acid': ('D20DT_ACID', 6), 'Cold': ('D20DT_COLD', 7), 'Electricity': ('D20DT_ELECTRICITY', 8),
        'Fire': ('D20DT_FIRE', 9), 'Sonic': ('D20DT_SONIC', 10)}


def _arg(v):
    if type(v) == type(0):
        return v
    if _ARG.has_key(v):
        n, d = _ARG[v]
        return _c(n, d)
    x = _c(v)
    if x is not None:
        return x
    _log('IE_ITEM arg %s unknown' % v)
    return 0


def entry(res):
    e = ITEMS.get(res.lower())
    if e is None and not _SEEN.has_key(res.lower()):
        _SEEN[res.lower()] = 1
        _log('IE_ITEM_UNMAPPED %s' % res)
    return e


def proto(res):
    e = entry(res)
    return e and e['p'] or None


def _set(o, f, v):
    try:
        o.obj_set_int(_field(f), v)
        return 1
    except Exception, ex:
        _log('IE_ITEM set %s failed: %s' % (f, ex))
        return 0


def apply(o, res, qty=None):
    """Turn a freshly created base-proto object into the converted IE item."""
    e = entry(res)
    if not e:
        return o
    for c in e.get('c') or ():
        try:
            o.item_condition_add_with_args(c[0], _arg(c[1]), _arg(c[2]))
        except Exception, ex:
            _log('IE_ITEM %s condition %s failed: %s' % (res, c, ex))
    if e.get('n'):
        _set(o, 'obj_f_description', e['n'])
        _set(o, 'obj_f_item_description_unknown', e['n'] + 1)
    if e.get('i'):
        _set(o, 'obj_f_item_inv_aid', e['i'])
    if e.get('w'):
        _set(o, 'obj_f_item_worth', e['w'])
    if e.get('t'):   # built throwing weapon (e.g. IWD2 throwing axe on the handaxe proto)
        try:
            _set(o, 'obj_f_weapon_flags', o.obj_get_int(_field('obj_f_weapon_flags')) | OWF_THROWABLE)
            _set(o, 'obj_f_weapon_range', e['t'])
        except Exception, ex:
            _log('IE_ITEM thrown %s: %s' % (res, ex))
    q = qty or e.get('q')
    if q:
        if o.type == obj_t_ammo:
            _set(o, 'obj_f_ammo_quantity', q)
        elif o.type == obj_t_money:
            _set(o, 'obj_f_money_quantity', q)
    if e.get('ch') and SET_CHARGES:
        try:
            o.obj_set_idx_int(obj_f_item_spell_charges_idx, 0, e['ch'])
        except Exception:
            pass
    try:
        if e.get('m'):
            o.item_flag_set(OIF_IS_MAGICAL)
        if e.get('id'):
            o.item_flag_set(OIF_IDENTIFIED)
        else:
            o.item_flag_unset(OIF_IDENTIFIED)
    except Exception, ex:
        _log('IE_ITEM flags %s: %s' % (res, ex))
    return o


def make(res, loc, qty=None):
    p = proto(res)
    if not p:
        return None
    o = game.obj_create(p, loc)
    return apply(o, res, qty)


def give(res, holder, qty=None):
    o = make(res, holder.location, qty)
    if o is not None:
        holder.item_get(o)
    return o


def _inv(holder):
    out = []
    for i in range(0, 200):
        try:
            it = holder.inventory_item(i)
        except Exception:
            break
        if it != OBJ_HANDLE_NULL:
            out.append(it)
    for i in range(0, 16):
        try:
            it = holder.item_worn_at(i)
        except Exception:
            break
        if it != OBJ_HANDLE_NULL:
            out.append(it)
    return out


def find(holder, res):
    """The converted IE item res in holder's inventory (base proto + its own name id), or None."""
    e = entry(res)
    if not e or holder is None:
        return None
    for it in _inv(holder):
        try:
            if it.proto == e['p'] and (not e.get('n') or it.obj_get_int(_field('obj_f_description')) == e['n']):
                return it
        except Exception:
            pass
    return None


def fill_containers(area, log_each=1):
    """Create the IE area's containers at their converted positions with their converted contents."""
    made = []
    for c in CONTAINERS.get(area.upper(), []):
        if not c.get('toee'):
            _log('IE_CONTAINER %s: no position' % c['name'])
            continue
        loc = location_from_axis(int(c['toee'][0]), int(c['toee'][1]))
        box = game.obj_create(c['proto'], loc)
        got = []
        for res, q in c['items']:
            it = make(res, loc, q > 1 and q or None)
            if it is not None:
                box.item_get(it); got.append(res)
        if c.get('lock'):
            try:
                box.container_flag_set(OCOF_LOCKED)
                box.obj_set_int(obj_f_container_lock_dc, min(40, 10 + c['lock'] / 5))
            except Exception, ex:
                _log('IE_CONTAINER lock: %s' % ex)
        made.append(box)
        if log_each:
            _log('IE_CONTAINER %s %s at %s: %s' % (area, c['name'], c['toee'], got))
    return made


def stock_store(npc, store):
    """IE store -> the merchant's ToEE substitute inventory (a hidden container next to him)."""
    s = STORES.get(store.lower())
    if not s:
        _log('IE_STORE %s unknown' % store)
        return None
    box = None
    try:
        box = npc.substitute_inventory
    except Exception:
        box = None
    if box is not None and box != OBJ_HANDLE_NULL:
        try:
            if box.inventory_item(0) != OBJ_HANDLE_NULL:      # baked (ie_bake.store_box) or stocked before: keep it
                return box
        except Exception:
            pass
    if box is None or box == OBJ_HANDLE_NULL:
        box = game.obj_create(s.get('container') or 1001, npc.location)
        box.object_flag_set(OF_DONTDRAW)
        box.object_flag_set(OF_CLICK_THROUGH)
        try:
            npc.substitute_inventory = box
        except Exception, ex:
            _log('IE_STORE substitute inventory unavailable (%s): stocking %s directly' % (ex, store))
            box.destroy(); box = npc
        got = []
        for res, n in s['items']:
            for k in range(n):
                it = make(res, box.location)
                if it is not None:
                    try:
                        it.item_flag_set(OIF_IDENTIFIED)     # IE stores sell identified goods
                    except Exception:
                        pass
                    box.item_get(it)
            got.append(res)
        _log('IE_STORE %s stocked: %s' % (store, got))
    return box


def open_store(store, npc, pc):
    stock_store(npc, store)
    pc.barter(npc)
