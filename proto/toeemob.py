"""ToEE object files: .mob (one mobile object per file) and the object list at the end of a .sec sector file.

Both store objects in the same serialisation (Arcanum's "object file format", version 0x77). The layout and the
field table below follow Temple+ (gamesystems/objects: gameobject.cpp Write / objsystem.cpp LoadFromFile,
ReadFieldValue / objfields.cpp, temple_enums.h obj_f), cross-checked with the Co8 ToEE World Builder (MobHelper.cs,
SecHelper.cs). docs/mapfiles.md has the full description and the differences between the two.

  object := u32 0x77 | ObjectId proto | ObjectId id | u32 type | u16 prop_count | u32 bitmap[blocks(type)] | values
  ObjectId (24 bytes) := u16 kind | u16 pad | i32 unused | 16-byte body
      kind 0 null, 1 prototype (body: u32 proto number), 2 permanent (body: a Windows GUID),
      3 positional (body: x, y, temp id, map id; only ever created at run time for static sector objects)
  values, one per set bitmap bit, in field-enum order of the type's sections:
      Int32 / Float32: 4 bytes
      Int64, String, Obj, arrays: u8 present, then
          Int64: 8 bytes | String: u32 len, len+1 bytes (NUL included) | Obj: ObjectId
          arrays: u32 el_size, u32 count, u32 (stale index-map id), count * el_size bytes,
                  u32 n, u32 index_bitmap[n]   (sparse: bit i set = index i present; data packed in index order)

  .sec := lights | 4096 * 16 tile bytes | roof list | sections (0xAA000n) | objects | u32 object count
"""
import os, struct, uuid

# ---- field table (Temple+ temple_enums.h obj_f 0..404 with objfields.cpp types) ----
# B/E section begin/end, i Int32, f Float32, I Int64, s String, o Obj, A AbilityArray, U UnkArray, a Int32Array,
# L Int64Array, S ScriptArray, V Unk2Array, O ObjArray, P SpellArray
FIELDS = """
begin:B location:I offset_x:f offset_y:f 2D_shadow_art:i blit_flags:i blit_color:i transparency:i model_scale:i
light_flags:i light_material:i light_color:i light_radius:f light_angle_start:f light_angle_end:f light_type:i
light_facing_X:f light_facing_Y:f light_facing_Z:f light_offset_X:f light_offset_Y:f light_offset_Z:f flags:i
spell_flags:i name:i description:i size:i hp_pts:i hp_adj:i hp_damage:i material:i scripts_idx:S sound_effect:i
category:i rotation:f speed_walk:f speed_run:f base_mesh:i base_anim:i radius:f 3d_render_height:f conditions:a
condition_arg0:a permanent_mods:a initiative:i dispatcher:i subinitiative:i secretdoor_flags:i
secretdoor_effectname:i secretdoor_dc:i pad_i_7:i pad_i_8:i pad_i_9:i pad_i_0:i offset_z:f rotation_pitch:f
pad_f_3:f pad_f_4:f pad_f_5:f pad_f_6:f pad_f_7:f pad_f_8:f pad_f_9:f pad_f_0:f pad_i64_0:I pad_i64_1:I pad_i64_2:I
pad_i64_3:I pad_i64_4:I last_hit_by:o pad_obj_1:o pad_obj_2:o pad_obj_3:o pad_obj_4:o permanent_mod_data:a
attack_types_idx:a attack_bonus_idx:a strategy_state:a pad_ias_4:a pad_i64as_0:L pad_i64as_1:L pad_i64as_2:L
pad_i64as_3:L pad_i64as_4:L pad_objas_0:O pad_objas_1:O pad_objas_2:O end:E portal_begin:B portal_flags:i
portal_lock_dc:i portal_key_id:i portal_notify_npc:i portal_pad_i_1:i portal_pad_i_2:i portal_pad_i_3:i
portal_pad_i_4:i portal_pad_i_5:i portal_pad_obj_1:o portal_pad_ias_1:a portal_pad_i64as_1:L portal_end:E
container_begin:B container_flags:i container_lock_dc:i container_key_id:i container_inventory_num:i
container_inventory_list_idx:O container_inventory_source:i container_notify_npc:i container_pad_i_1:i
container_pad_i_2:i container_pad_i_3:i container_pad_i_4:i container_pad_i_5:i container_pad_obj_1:o
container_pad_obj_2:o container_pad_ias_1:a container_pad_i64as_1:L container_pad_objas_1:O container_end:E
scenery_begin:B scenery_flags:i scenery_pad_obj_0:o scenery_respawn_delay:i scenery_pad_i_0:i scenery_pad_i_1:i
scenery_teleport_to:i scenery_pad_i_4:i scenery_pad_i_5:i scenery_pad_obj_1:i scenery_pad_ias_1:a
scenery_pad_i64as_1:L scenery_end:E projectile_begin:B projectile_flags_combat:i projectile_flags_combat_damage:i
projectile_parent_weapon:o projectile_parent_ammo:o projectile_part_sys_id:i projectile_acceleration_x:f
projectile_acceleration_y:f projectile_acceleration_z:f projectile_pad_i_4:i projectile_pad_obj_1:o
projectile_pad_obj_2:o projectile_pad_obj_3:o projectile_pad_ias_1:a projectile_pad_i64as_1:L
projectile_pad_objas_1:O projectile_end:E item_begin:B item_flags:i item_parent:o item_weight:i item_worth:i
item_inv_aid:i item_inv_location:i item_ground_mesh:i item_ground_anim:i item_description_unknown:i
item_description_effects:i item_spell_idx:P item_spell_idx_flags:i item_spell_charges_idx:i item_ai_action:i
item_wear_flags:i item_material_slot:i item_quantity:i item_pad_i_1:i item_pad_i_2:i item_pad_i_3:i item_pad_i_4:i
item_pad_i_5:i item_pad_i_6:i item_pad_obj_1:o item_pad_obj_2:o item_pad_obj_3:o item_pad_obj_4:o item_pad_obj_5:o
item_pad_wielder_condition_array:a item_pad_wielder_argument_array:a item_pad_i64as_1:L item_pad_i64as_2:L
item_pad_objas_1:O item_pad_objas_2:O item_end:E weapon_begin:B weapon_flags:i weapon_range:i weapon_ammo_type:i
weapon_ammo_consumption:i weapon_missile_aid:i weapon_crit_hit_chart:i weapon_attacktype:i weapon_damage_dice:i
weapon_animtype:i weapon_type:i weapon_crit_range:i weapon_pad_i_1:i weapon_pad_i_2:i weapon_pad_obj_1:o
weapon_pad_obj_2:o weapon_pad_obj_3:o weapon_pad_obj_4:o weapon_pad_obj_5:o weapon_pad_ias_1:a weapon_pad_i64as_1:L
weapon_end:E ammo_begin:B ammo_flags:i ammo_quantity:i ammo_type:i ammo_pad_i_1:i ammo_pad_i_2:i ammo_pad_obj_1:o
ammo_pad_ias_1:a ammo_pad_i64as_1:L ammo_end:E armor_begin:B armor_flags:i armor_ac_adj:i armor_max_dex_bonus:i
armor_arcane_spell_failure:i armor_armor_check_penalty:i armor_pad_i_1:i armor_pad_ias_1:a armor_pad_i64as_1:L
armor_end:E money_begin:B money_flags:i money_quantity:i money_type:i money_pad_i_1:i money_pad_i_2:i
money_pad_i_3:i money_pad_i_4:i money_pad_i_5:i money_pad_ias_1:a money_pad_i64as_1:L money_end:E food_begin:B
food_flags:i food_pad_i_1:i food_pad_i_2:i food_pad_ias_1:a food_pad_i64as_1:L food_end:E scroll_begin:B
scroll_flags:i scroll_pad_i_1:i scroll_pad_i_2:i scroll_pad_ias_1:a scroll_pad_i64as_1:L scroll_end:E key_begin:B
key_key_id:i key_pad_i_1:i key_pad_i_2:i key_pad_ias_1:a key_pad_i64as_1:L key_end:E written_begin:B
written_flags:i written_subtype:i written_text_start_line:i written_text_end_line:i written_pad_i_1:i
written_pad_i_2:i written_pad_ias_1:a written_pad_i64as_1:L written_end:E bag_begin:B bag_flags:i bag_size:i
bag_end:E generic_begin:B generic_flags:i generic_usage_bonus:i generic_usage_count_remaining:i generic_pad_ias_1:a
generic_pad_i64as_1:L generic_end:E critter_begin:B critter_flags:i critter_flags2:i critter_abilities_idx:A
critter_level_idx:a critter_race:i critter_gender:i critter_age:i critter_height:i critter_weight:i
critter_experience:i critter_pad_i_1:i critter_alignment:i critter_deity:i critter_domain_1:i critter_domain_2:i
critter_alignment_choice:i critter_school_specialization:i critter_spells_known_idx:P
critter_spells_memorized_idx:P critter_spells_cast_idx:P critter_feat_idx:a critter_feat_count_idx:a
critter_fleeing_from:o critter_portrait:i critter_money_idx:a critter_inventory_num:i critter_inventory_list_idx:O
critter_inventory_source:i critter_description_unknown:i critter_follower_idx:O critter_teleport_dest:I
critter_teleport_map:i critter_death_time:i critter_skill_idx:a critter_reach:i critter_subdual_damage:i
critter_pad_i_4:i critter_pad_i_5:i critter_sequence:i critter_hair_style:i critter_strategy:i critter_pad_i_3:i
critter_monster_category:I critter_pad_i64_2:I critter_pad_i64_3:I critter_pad_i64_4:I critter_pad_i64_5:I
critter_damage_idx:a critter_attacks_idx:a critter_seen_maplist:L critter_pad_i64as_2:L critter_pad_i64as_3:L
critter_pad_i64as_4:L critter_pad_i64as_5:L critter_end:E pc_begin:B pc_flags:i pc_pad_ias_0:a pc_pad_i64as_0:L
pc_player_name:s pc_global_flags:a pc_global_variables:a pc_voice_idx:i pc_roll_count:i pc_pad_i_2:i
pc_weaponslots_idx:a pc_pad_ias_2:a pc_pad_i64as_1:L pc_end:E npc_begin:B npc_flags:i npc_leader:o npc_ai_data:i
npc_combat_focus:o npc_who_hit_me_last:o npc_waypoints_idx:L npc_waypoint_current:i
npc_standpoint_day_INTERNAL_DO_NOT_USE:I npc_standpoint_night_INTERNAL_DO_NOT_USE:I npc_faction:a
npc_retail_price_multiplier:i npc_substitute_inventory:o npc_reaction_base:i npc_challenge_rating:i
npc_reaction_pc_idx:O npc_reaction_level_idx:a npc_reaction_time_idx:a npc_generator_data:i npc_ai_list_idx:O
npc_save_reflexes_bonus:i npc_save_fortitude_bonus:i npc_save_willpower_bonus:i npc_ac_bonus:i npc_add_mesh:i
npc_waypoint_anim:i npc_pad_i_3:i npc_pad_i_4:i npc_pad_i_5:i npc_ai_flags64:I npc_pad_i64_2:I npc_pad_i64_3:I
npc_pad_i64_4:I npc_pad_i64_5:I npc_hitdice_idx:a npc_ai_list_type_idx:a npc_pad_ias_3:a npc_pad_ias_4:a
npc_pad_ias_5:a npc_standpoints:L npc_pad_i64as_2:L npc_pad_i64as_3:L npc_pad_i64as_4:L npc_pad_i64as_5:L npc_end:E
trap_begin:B trap_flags:i trap_difficulty:i trap_pad_i_2:i trap_pad_ias_1:a trap_pad_i64as_1:L trap_end:E
"""

FIELD_LIST = [tuple(t.rsplit(':', 1)) for t in FIELDS.split()]
FIELD_INDEX = {n: i for i, (n, _t) in enumerate(FIELD_LIST)}
ARRAY_TYPES = set('AUaLSVOP')
EL_SIZE = {'A': 4, 'a': 4, 'L': 8, 'S': 12, 'O': 24, 'P': 32}

OBJ_TYPES = ['portal', 'container', 'scenery', 'projectile', 'weapon', 'ammo', 'armor', 'money', 'food', 'scroll',
             'key', 'written', 'generic', 'pc', 'npc', 'trap', 'bag']
_SECTIONS = {'portal': ['portal'], 'container': ['container'], 'scenery': ['scenery'], 'projectile': ['projectile'],
             'pc': ['critter', 'pc'], 'npc': ['critter', 'npc'], 'trap': ['trap']}
for _t in ('weapon', 'ammo', 'armor', 'money', 'food', 'scroll', 'key', 'written', 'generic', 'bag'):
    _SECTIONS[_t] = ['item', _t]


def _range(section):
    b = FIELD_INDEX[section + '_begin' if section else 'begin']
    e = FIELD_INDEX[section + '_end' if section else 'end']
    return list(range(b + 1, e))


_TYPE_FIELDS = {}


def type_fields(otype):
    """Field indices an object type stores, in serialisation order."""
    if otype not in _TYPE_FIELDS:
        f = _range('')
        for s in _SECTIONS[OBJ_TYPES[otype]]:
            f += _range(s)
        _TYPE_FIELDS[otype] = f
    return _TYPE_FIELDS[otype]


def bitmap_blocks(otype):
    return max((i - 1) // 32 for i in type_fields(otype)) + 1


def bit(i):
    """Bitmap block and mask of field index i (Temple+: (field - 1) / 32, global over the whole enum)."""
    return (i - 1) // 32, 1 << ((i - 1) % 32)


# ---- object ids ----
NULL_ID = b'\0' * 24


def proto_id(n):
    return struct.pack('<HHi', 1, 0, 0) + struct.pack('<I', n) + b'\0' * 12


def permanent_id(guid=None):
    """A permanent id (kind 2) around a GUID (uuid.UUID; random if None). Windows GUID byte order."""
    g = guid or uuid.uuid4()
    return struct.pack('<HHi', 2, 0, 0) + g.bytes_le


def id_kind(raw):
    return struct.unpack_from('<H', raw)[0]


def id_guid(raw):
    return uuid.UUID(bytes_le=raw[8:24])


def guid_name(raw):
    """The G_XXXXXXXX_XXXX_XXXX_XXXX_XXXXXXXXXXXX string vanilla uses as the .mob file name."""
    return 'G_' + str(id_guid(raw)).upper().replace('-', '_')


def id_str(raw):
    k = id_kind(raw)
    if k == 0:
        return 'null'
    if k == 1:
        return 'proto %d' % struct.unpack_from('<I', raw, 8)[0]
    if k == 2:
        return guid_name(raw)
    if k == 3:
        return 'pos %d,%d tmp %d map %d' % struct.unpack_from('<4i', raw, 8)
    return 'kind %d' % k


# ---- arrays ----
class Array(object):
    """Sparse engine array: {index: element bytes}. el_size from the file (or EL_SIZE)."""

    def __init__(self, el_size, items=None, stale=0, idx_blocks=None):
        self.el_size, self.items, self.stale = el_size, dict(items or {}), stale
        self.idx_blocks = idx_blocks       # kept for byte-exact round trips (may carry extra zero blocks)

    def blocks(self):
        n = (max(self.items) // 32 + 1) if self.items else 0
        b = [0] * n
        for i in self.items:
            b[i // 32] |= 1 << (i % 32)
        if self.idx_blocks is not None and len(self.idx_blocks) >= n and \
                all((self.idx_blocks[j] if j < len(self.idx_blocks) else 0) == (b[j] if j < n else 0)
                    for j in range(len(self.idx_blocks))):
            return list(self.idx_blocks)
        return b

    def ints(self, fmt='<i'):
        return {i: struct.unpack(fmt, v)[0] for i, v in self.items.items()}

    def __repr__(self):
        return 'Array(%d, %d items)' % (self.el_size, len(self.items))


def int_array(values, fmt='<i'):
    """values: list (dense) or {index: value}."""
    if isinstance(values, (list, tuple)):
        values = dict(enumerate(values))
    return Array(struct.calcsize(fmt), {i: struct.pack(fmt, v) for i, v in values.items()})


def obj_array(ids):
    return Array(24, dict(enumerate(ids)))


def script_array(entries):
    """entries: {script slot: (flags, counters, script id)}."""
    return Array(12, {i: struct.pack('<IIi', *v) for i, v in entries.items()})


# ---- objects ----
class GameObject(object):
    def __init__(self, otype, proto, oid=NULL_ID, fields=None):
        self.type = otype
        self.proto = proto_id(proto) if isinstance(proto, int) else proto
        self.id = oid
        self.fields = dict(fields or {})   # field index -> value
        self.prop_count = None             # as stored (written back verbatim when the field set is unchanged)
        self.prop_count_fields = None
        self.extra_bits = None

    @property
    def proto_num(self):
        return struct.unpack_from('<I', self.proto, 8)[0]

    def get(self, name, default=None):
        return self.fields.get(FIELD_INDEX[name], default)

    def set(self, name, value):
        i = FIELD_INDEX[name]
        if i not in type_fields(self.type):
            raise KeyError('%s does not store %s' % (OBJ_TYPES[self.type], name))
        self.fields[i] = value
        return self

    def unset(self, name):
        self.fields.pop(FIELD_INDEX[name], None)

    def names(self):
        return {FIELD_LIST[i][0]: v for i, v in sorted(self.fields.items())}

    def __repr__(self):
        return '<%s %s proto %d, %d fields>' % (OBJ_TYPES[self.type], id_str(self.id), self.proto_num, len(self.fields))


class _Reader(object):
    def __init__(self, b, p=0):
        self.b, self.p = b, p

    def take(self, n):
        v = self.b[self.p:self.p + n]
        if len(v) != n:
            raise ValueError('truncated object data at %d' % self.p)
        self.p += n
        return v

    def u(self, fmt):
        v = struct.unpack_from(fmt, self.b, self.p)
        self.p += struct.calcsize(fmt)
        return v if len(v) > 1 else v[0]


def read_object(r):
    if r.u('<I') != 0x77:
        raise ValueError('not an object (version != 0x77) at %d' % (r.p - 4))
    proto = r.take(24); oid = r.take(24)
    otype = r.u('<I')
    if id_kind(proto) != 1:
        raise ValueError('prototype id expected')
    nprop = r.u('<H')
    nb = bitmap_blocks(otype)
    bm = list(r.u('<%dI' % nb)) if nb > 1 else [r.u('<I')]
    o = GameObject(otype, proto, oid)
    o.prop_count = nprop
    for i in type_fields(otype):
        blk, m = bit(i)
        if not bm[blk] & m:
            continue
        o.fields[i] = _read_value(r, FIELD_LIST[i][1])
    # bits set for fields the type does not store would be ignored by the engine; keep them for exactness
    want = [0] * nb
    for i in o.fields:
        blk, m = bit(i); want[blk] |= m
    o.prop_count_fields = set(o.fields)
    if want != bm:
        o.extra_bits = [a & ~b for a, b in zip(bm, want)]
    return o


def _read_value(r, t):
    if t == 'i':
        return r.u('<i')
    if t == 'f':
        return r.u('<f')
    if not r.u('<B'):
        return None
    if t == 'I':
        return r.u('<q')
    if t == 's':
        n = r.u('<I'); return r.take(n + 1)[:-1]
    if t == 'o':
        return r.take(24)
    if t in ARRAY_TYPES:
        el, cnt, stale = r.u('<3I')
        data = r.take(el * cnt)
        n = r.u('<I')
        blocks = list(struct.unpack_from('<%dI' % n, r.take(4 * n))) if n else []
        idx = [j * 32 + k for j, w in enumerate(blocks) for k in range(32) if w >> k & 1]
        if len(idx) != cnt:
            raise ValueError('array index bitmap (%d) and count (%d) disagree' % (len(idx), cnt))
        return Array(el, {ix: data[q * el:(q + 1) * el] for q, ix in enumerate(idx)}, stale, blocks)
    raise ValueError('field type %r' % t)


def write_object(o):
    out = bytearray(struct.pack('<I', 0x77)) + o.proto + o.id + struct.pack('<I', o.type)
    nb = bitmap_blocks(o.type)
    bm = [0] * nb
    order = [i for i in type_fields(o.type) if i in o.fields]
    for i in order:
        blk, m = bit(i); bm[blk] |= m
    if o.extra_bits:
        bm = [a | b for a, b in zip(bm, o.extra_bits)]
    n = len(order)
    if o.prop_count is not None and o.prop_count != n and o.prop_count_fields == set(order):
        n = o.prop_count              # unusual stored count, object unchanged: keep it for byte-exact output
    out += struct.pack('<H', n) + struct.pack('<%dI' % nb, *bm)
    for i in order:
        out += _write_value(FIELD_LIST[i][1], o.fields[i])
    return bytes(out)


def _write_value(t, v):
    if t == 'i':
        return struct.pack('<i', v if v < 0x80000000 else v - 0x100000000)
    if t == 'f':
        return struct.pack('<f', v)
    if v is None:
        return b'\0'
    if t == 'I':
        return b'\1' + struct.pack('<q', v)
    if t == 's':
        v = v.encode('latin-1') if isinstance(v, str) else v
        return b'\1' + struct.pack('<I', len(v)) + v + b'\0'
    if t == 'o':
        return b'\1' + v
    if t in ARRAY_TYPES:
        items = sorted(v.items.items())
        blocks = v.blocks()
        return (b'\1' + struct.pack('<3I', v.el_size, len(items), v.stale) + b''.join(d for _i, d in items)
                + struct.pack('<I', len(blocks)) + struct.pack('<%dI' % len(blocks), *blocks))
    raise ValueError('field type %r' % t)


# ---- .mob ----
def read_mob(data):
    r = _Reader(data)
    o = read_object(r)
    if r.p != len(data):
        raise ValueError('%d trailing bytes after the object' % (len(data) - r.p))
    return o


def write_mob(o):
    return write_object(o)


def mob_filename(o):
    return guid_name(o.id) + '.mob'


# ---- .sec ----
class Sector(object):
    """head: everything before the object list (lights, tiles, roofs, sections) kept as bytes; objects: list."""

    def __init__(self, head, objects):
        self.head, self.objects = head, objects

    @staticmethod
    def objects_offset(b):
        p = 0
        n = struct.unpack_from('<i', b, p)[0]; p += 4
        for _ in range(n):
            flags = struct.unpack_from('<i', b, p + 8)[0]; p += 0x40
            if flags & 0x10:
                p += 8
            elif flags & 0x40:
                p += 0x2C
        p += 4096 * 16
        roof = struct.unpack_from('<i', b, p)[0]; p += 4
        if roof != 1:
            p += 0x400
        sh = struct.unpack_from('<I', b, p)[0]; p += 4
        if sh != 0xAA0000:
            if not 0xAA0000 < sh <= 0xAA0004:
                raise ValueError('bad sector section header %x' % sh)
            if sh >= 0xAA0001:
                p += 4 + 0x18 * struct.unpack_from('<i', b, p)[0]
            if sh >= 0xAA0002:
                p += 12
            if sh >= 0xAA0003:
                p += 12
            if sh >= 0xAA0004:
                p += 12
        return p

    @classmethod
    def read(cls, b):
        p = cls.objects_offset(b)
        n = struct.unpack_from('<i', b, len(b) - 4)[0]
        r = _Reader(b, p)
        objs = [read_object(r) for _ in range(n)]
        if r.p != len(b) - 4:
            raise ValueError('object list ends at %d, count at %d' % (r.p, len(b) - 4))
        return cls(b[:p], objs)

    def write(self):
        return bytes(self.head) + b''.join(write_object(o) for o in self.objects) + struct.pack('<i', len(self.objects))


def sector_id(sx, sy):
    """Sector file number from sector column (x, 64 tiles each) and row (y)."""
    return (sy << 26) | sx


def sector_of(x, y):
    return sector_id(x // 64, y // 64)


def location(x, y):
    """obj_f_location: tile x in the low dword, y in the high dword."""
    return (y << 32) | (x & 0xffffffff)


def loc_xy(v):
    return v & 0xffffffff, (v >> 32) & 0xffffffff
