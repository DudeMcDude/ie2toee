"""Small Temple+ stand-in for running converted Python scripts in an offline scenario.

Call install() before importing ie_runtime. A tick is one simulated second. Actors
step one tile on each axis towards their destination. In melee, actors within one
tile deal fixed damage in spawn order. Scenarios decide when to issue orders.
"""
import heapq
import itertools
import math
import sys
import types
from collections import defaultdict


FEET_PER_TILE = 20 * math.sqrt(2) / 12


def location_from_axis(x, y):
    return x | (y << 32)


def location_to_axis(location):
    return location & 0xffffffff, location >> 32


class Item:
    def __init__(self, res, entry, quantity):
        self.id = id(self)
        self.res, self.proto, self.description = res, entry['p'], entry.get('n')
        self.quantity = quantity
        self.type = entry.get('type', 'item')
        self.holder = None
        self.destroyed = False
        self.flags = int(bool(entry.get('id')))

    def obj_get_obj(self, field):
        if field != 'item_parent':
            raise KeyError(field)
        return self.holder

    def obj_get_int(self, field):
        if field in ('ammo_quantity', 'money_quantity'):
            return self.quantity
        if field != 'item_flags':
            raise KeyError(field)
        return self.flags

    def obj_set_int(self, field, value):
        if field not in ('ammo_quantity', 'money_quantity'):
            raise KeyError(field)
        self.quantity = value

    def destroy(self):
        if self.holder is not None:
            self.holder.inventory.remove(self)
            self.holder = None
        self.destroyed = True


class InventoryHolder:
    def __init__(self):
        self.inventory = []

    def item_get(self, item):
        if item.destroyed:
            raise ValueError('cannot transfer a destroyed item')
        if item.holder is self:
            return
        if item.holder is not None:
            item.holder.inventory.remove(item)
        self.inventory.append(item)
        item.holder = self


class ItemRuntime(types.ModuleType):
    def __init__(self):
        super().__init__('ie_itemrt')
        try:
            from ie_itemmap import CONTAINERS, ITEMS
        except ImportError:
            CONTAINERS, ITEMS = {}, {}
        self.CONTAINERS, self.ITEMS = CONTAINERS, ITEMS

    def entry(self, res):
        return self.ITEMS.get(res.strip().lower())

    @staticmethod
    def _inv(holder):
        return list(holder.inventory)

    @staticmethod
    def matches(item, entry):
        return entry and item.proto == entry['p'] and (not entry.get('n') or item.description == entry['n'])

    def find(self, holder, res):
        entry = self.entry(res)
        if entry and holder is not None:
            return next((item for item in holder.inventory if self.matches(item, entry)), None)

    def give(self, res, holder, qty=None):
        entry = self.entry(res)
        if entry and holder is not None:
            item = Item(res.strip().lower(), entry, qty or entry.get('q') or 1)
            holder.item_get(item)
            return item


class Container(InventoryHolder):
    type = 'container'

    def __init__(self, spec, map_id):
        super().__init__()
        self.name, self.proto, self.map = spec['name'], spec['proto'], map_id
        self.location = location_from_axis(*map(int, spec['toee']))
        # Older item maps only record lock difficulty, which also occurs on unlocked boxes.
        self.flags = int(bool(spec.get('locked')))

    def container_flag_set(self, flag):
        self.flags |= flag

    def container_flags_get(self):
        return self.flags


class Actor(InventoryHolder):
    @property
    def type(self):
        return 'pc' if self in self.game.party else 'npc'

    def obj_get_idx_obj_size(self, field):
        if field != 'critter_inventory':
            raise KeyError(field)
        return len(self.inventory)

    def obj_get_idx_obj(self, field, index):
        if field != 'critter_inventory':
            raise KeyError(field)
        return self.inventory[index]

    def __init__(self, ident, name, map_id, tile, hp, damage, hostile, game):
        super().__init__()
        self.id, self.name, self.map = ident, name, map_id
        self.location = location_from_axis(*tile)
        self.hp = self.max_hp = hp
        self.experience = 0
        self.game = game
        self.copper = 0
        self.abilities = {}
        self.damage, self.hostile = damage, hostile
        self.object_flags = 0
        self.npc_flags = 0
        self.conditions = set()
        self.destroyed = False
        self.destination = self.target = self.dialog = self.script_mod = None
        self.scripts = defaultdict(int)

    def begin_dialog(self, npc, line):
        self.dialog = (npc, line)

    def award_experience(self, amount):
        self.experience += amount

    def reputation_has(self, reputation):
        return self in self.game.party and reputation in self.game.reputations

    def reputation_add(self, reputation):
        if self in self.game.party:
            self.game.reputations.add(reputation)

    def reputation_remove(self, reputation):
        if self in self.game.party:
            self.game.reputations.discard(reputation)

    def money_get(self):
        return self.copper

    def money_adj(self, amount):
        self.copper += amount

    def object_script_execute(self, other, evt):
        if self.script_mod:
            self.script_mod.san_dialog(self, other)
        elif other.script_mod:
            other.script_mod.san_dialog(other, self)

    def distance_to(self, other):
        if self.map != other.map or self.destroyed or other.destroyed:
            return math.inf
        # Temple+ distance_to returns feet; tiles are 20 * sqrt(2) inches wide.
        return math.dist(location_to_axis(self.location), location_to_axis(other.location)) * FEET_PER_TILE

    def can_see(self, other):
        return self.map == other.map and self.hp > 0 and not other.destroyed

    def npc_flags_get(self):
        return self.npc_flags | int(self.hostile)  # ONF_KOS in the test module

    def npc_flag_set(self, flag):
        self.npc_flags |= flag & ~1
        if flag & 1:
            self.hostile = True

    def npc_flag_unset(self, flag):
        self.npc_flags &= ~flag
        if flag & 1:
            self.hostile = False

    def condition_add(self, name):
        self.conditions.add(name)

    def d20_query(self, query):
        return query == 'Combat Practice Target' and 'IE Combat Practice Target' in self.conditions

    def is_dead_or_destroyed(self):
        return self.hp == 0

    is_unconscious = is_dead_or_destroyed

    def stat_level_get(self, stat):
        if stat == 'level':
            return max(1, sum(n for name,n in self.abilities.items() if name.startswith('level_')))
        if stat.startswith('level_'):
            return self.abilities.get(stat, 0)
        if stat in self.abilities:
            return self.abilities[stat]
        return {'hp_current': self.hp, 'hp_max': self.max_hp}[stat]

    def run_to(self, loc):
        self.target = None
        self.destination = loc

    def object_flags_get(self):
        return self.object_flags

    def object_flag_set(self, flag):
        self.object_flags |= flag

    def object_flag_unset(self, flag):
        self.object_flags &= ~flag

    def move(self, loc):
        self.location = loc
        self.destination = self.target = None

    def destroy(self):
        self.destroyed = True
        self.hp = 0
        self.destination = self.target = None

    def attack(self, other):
        if other is self or not self.hp or not other.hp or self.map != other.map:
            return
        self.target, self.destination = other, None
        if not other.has_target():
            other.target, other.destination = self, None

    def has_target(self):
        return bool(self.hp and self.target and self.target.hp and self.map == self.target.map)

    def step(self):
        if not self.hp:
            return
        if not self.has_target():
            self.target = None
        dest = self.target.location if self.target else self.destination
        if dest is None:
            return
        x, y = location_to_axis(self.location)
        tx, ty = location_to_axis(dest)
        if self.target and max(abs(tx - x), abs(ty - y)) <= 1:
            victim = self.target
            victim.hp = max(0, victim.hp - self.damage)
            if not victim.hp:
                victim.target = victim.destination = self.target = None
                if victim.script_mod and hasattr(victim.script_mod, 'san_dying'):
                    victim.script_mod.san_dying(victim, self)
            return
        x += (tx > x) - (tx < x)
        y += (ty > y) - (ty < y)
        self.location = location_from_axis(x, y)
        if self.location == self.destination:
            self.destination = None

    def turn_towards(self, other): pass
    def turn_towards_loc(self, loc): pass
    def float_text_line(self, *args): pass
    def float_line(self, *args): pass
    def standpoint_set(self, *args): pass


class Game:
    def __init__(self):
        self._sequence = itertools.count(1)
        self.time = self
        self.reset()

    def reset(self):
        self.t = 1000
        self.reputations = set()
        self.party, self.events, self.teleports, self.movies, self.played = [], [], [], [], []
        self.objects = {}
        self.containers = {}
        self.area_scripts = False
        self.current_map = None
        self.global_vars = defaultdict(int)
        self.quests = defaultdict(lambda: types.SimpleNamespace(state=0))
        if 'ie_runtime' in sys.modules:
            import ie_runtime as rt
            for state in (rt._busy, rt._queues, rt._bound, rt._events, rt._first, rt._last_tick,
                          rt._saved, rt._loops):
                state.clear()
            if hasattr(rt, '_dropped'):
                rt._dropped.clear()
            rt._clk[:] = [None, 0.0]
            if hasattr(rt, '_leave'):
                rt._leave[:] = [None, 0.0]
            rt.ie_vars.clear()
        if 'ie_cutscene' in sys.modules:
            import ie_cutscene
            ie_cutscene._area.clear()
            ie_cutscene.STATE.update(hook=0, cut=0, cut_since=0)

    def enable_area_scripts(self):
        """Drive the converted Temple+ map hook once per simulated second."""
        import ie_areas, ie_cutscene, ie_runtime
        ie_runtime.AREA_MAPS.update(ie_areas.MAPS)
        for area, placement in ie_areas.PLACEMENTS.items():
            ie_runtime.set_placement(area, *placement)
        ie_cutscene.STATE['hook'] = 1
        self.area_scripts = True

    def _tick_map(self):
        import ie_areas, ie_cutscene, ie_itemrt, ie_travel_data
        map_id = self.leader.map
        if map_id not in self.containers:
            boxes = []
            for area, mid in ie_areas.MAPS.items():
                if mid != map_id:
                    continue
                for spec in ie_itemrt.CONTAINERS.get(area, ()):
                    if spec.get('toee'):
                        box = Container(spec, map_id)
                        for res, qty in spec['items']:
                            ie_itemrt.give(res, box, qty)
                        boxes.append(box)
            self.containers[map_id] = boxes
        if map_id != self.current_map:
            if 'ie_travel' in sys.modules and hasattr(sys.modules['ie_travel'], '_inside'):
                sys.modules['ie_travel']._inside.clear()
            self.current_map = map_id
        ie_cutscene.map_tick(map_id, 1000)
        area = ie_travel_data.BY_MAP.get(map_id)
        regions = ie_travel_data.AREAS.get(area, {}).get('triggers', ())
        if regions and self.leader.map == map_id:
            import ie_travel
            party = [pc for pc in self.party if pc.map == map_id]
            ie_travel._triggers(area, regions, party, [location_to_axis(pc.location) for pc in party])

    def spawn(self, name, map_id=5018, tile=(480, 470), hp=10, damage=1, hostile=False):
        if hp <= 0 or damage <= 0:
            raise ValueError('expected positive starting HP and damage')
        actor = Actor(next(self._sequence), name, map_id, tile, hp, damage, hostile, self)
        self.objects[actor.id] = actor
        return actor

    @property
    def leader(self):
        return self.party[0]

    def get_obj_by_id(self, ident):
        actor = self.objects.get(ident)
        return actor if actor and not actor.destroyed else None

    def save_script_vars(self, path):
        """Write the runtime's .iev variable file (actors and pending orders are transient)."""
        import ie_vars
        ie_vars.items()  # Assign this game's token even when no variable has been set.
        ie_vars.write_file(str(path))

    def load_script_vars(self, path):
        import ie_vars
        ie_vars.read_file(str(path))
        # In Temple+ the matching token comes from the engine save alongside the .iev.
        self.global_vars[ie_vars.TOKEN_VAR] = ie_vars._state['token'] or 0

    def obj_list_vicinity(self, loc, kind):
        # Only actors on the current map and within 40 tiles of the query.
        if not self.party or kind not in ('npc', 'critters', 'container'):
            return []
        x, y = location_to_axis(loc)
        result = []
        objects = self.containers.get(self.leader.map, ()) if kind == 'container' else self.objects.values()
        for actor in objects:
            if actor.map != self.leader.map or getattr(actor, 'destroyed', False) or (kind == 'npc' and actor in self.party):
                continue
            ax, ay = location_to_axis(actor.location)
            if max(abs(ax - x), abs(ay - y)) <= 40:
                result.append(actor)
        return result

    def combat_is_active(self):
        return any(actor.has_target() for actor in self.objects.values())

    def time_game_in_seconds(self, clock):
        return self.t

    def time_game_in_hours(self, clock):
        return int(self.t // 3600) % 24

    def timeevent_add(self, fn, args, ms, real=0):
        due = self.t + max(1, math.ceil(ms / 1000))
        heapq.heappush(self.events, (due, next(self._sequence), fn, args))

    def tick(self):
        self.t += 1
        for actor in list(self.objects.values()):
            actor.step()
        while self.events and self.events[0][0] <= self.t:
            _, _, fn, args = heapq.heappop(self.events)
            fn(*args)
        if self.area_scripts and self.party:
            self._tick_map()

    def fade_and_teleport(self, t, tb, mv, mp, x, y):
        self.teleports.append((mp, x, y))
        for actor in self.party:
            actor.map = mp
            actor.move(location_from_axis(x, y))
        for actor in self.objects.values():
            if actor.target and actor.target.map != actor.map:
                actor.target = None

    def fade(self, *args): pass
    def scroll_to(self, *args): pass
    def moviequeue_add(self, movie): self.movies.append(movie)
    def moviequeue_play(self):
        self.played.append(self.movies[:])
        self.movies.clear()


def install():
    """Install the process-local engine modules used by the standalone test runners."""
    game = Game()
    toee = types.ModuleType('toee')
    toee.stat_level = 'level'
    for ability in ('strength', 'intelligence', 'wisdom', 'dexterity', 'constitution', 'charisma'):
        setattr(toee, 'stat_' + ability, ability)
    for cls in 'barbarian bard cleric druid fighter monk paladin ranger rogue sorcerer wizard'.split():
        setattr(toee, 'stat_level_' + cls, 'level_' + cls)
    toee.obj_t_ammo, toee.obj_t_money = 'ammo', 'money'
    toee.obj_t_npc = 'npc'
    toee.obj_f_critter_inventory_list_idx, toee.obj_f_item_parent = 'critter_inventory', 'item_parent'
    toee.OF_OFF, toee.OF_DONTDRAW = 2, 0x100
    toee.obj_f_ammo_quantity, toee.obj_f_money_quantity = 'ammo_quantity', 'money_quantity'
    toee.obj_f_item_flags, toee.OIF_IDENTIFIED = 'item_flags', 1
    vars(toee).update(game=game, OBJ_HANDLE_NULL=None, OLC_CRITTERS='critters', OLC_CRITTER='critters', OLC_NPC='npc',
                      OLC_CONTAINER='container', obj_t_container='container', obj_t_portal='portal', OCOF_LOCKED=1, OCOF_OPEN=2,
                      ONF_KOS=1, ONF_NO_ATTACK=0x20000000, stat_hp_current='hp_current', stat_hp_max='hp_max',
                      STANDPOINT_DAY=0, STANDPOINT_NIGHT=1, RUN_DEFAULT=1, SKIP_DEFAULT=0, san_dialog=9,
                      location_from_axis=location_from_axis, location_to_axis=location_to_axis)
    sys.modules['toee'] = toee
    utilities = types.ModuleType('utilities')
    utilities.location_from_axis, utilities.location_to_axis = location_from_axis, location_to_axis
    sys.modules['utilities'] = utilities
    # The native item and map adapters depend on the game's embedded Python 2.
    sys.modules['ie_itemrt'] = ItemRuntime()
    bake = types.ModuleType('ie_bakert')
    bake.first_heartbeat = lambda obj, area: None
    sys.modules['ie_bakert'] = bake
    spawn = types.ModuleType('ie_spawn')
    spawn.hook_rest = spawn.area_spawns = spawn.tick = lambda *args: None
    sys.modules['ie_spawn'] = spawn
    return game
