"""Run from the command line with Python 3.

    python test_offline_encounter.py
    python test_offline_encounter.py --core "path/to/IWD2/modules/ToEE_core" --save-vars docks.iev

With an IWD2 conversion, run the dock encounter and, if the conversion supplies
container scripts, the crane wheel hand-in. --save-vars writes the final dock
scenario variables for inspection with the usual .iev tools.
"""
import argparse
import importlib
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from offline_game import install, location_to_axis


def check_model(game, rt):
    import ie_cutscene
    pc = game.spawn('pc', tile=(0, 0), hp=4)
    foe = game.spawn('tester', tile=(5, 0), hp=3, damage=2, hostile=True)
    game.party.append(pc)
    here = rt.Ctx(pc, foe, 'pc', 'TEST1')
    there = rt.Ctx(foe, pc, 'tester', 'TEST2')
    guard = game.spawn('guard', tile=(0, 1))
    guard_ctx = rt.Ctx(guard, pc, 'guard', 'TEST1')
    # Hedron and Reig start dialogue as the final action of an input lock.
    rt.A.StartCutSceneMode(guard_ctx)
    rt.A.Dialogue(guard_ctx, None)
    assert ie_cutscene.active()
    rt.A.Dialogue(guard_ctx, pc)
    assert not ie_cutscene.active()
    # A scene with actions remaining still owns its lock until its last block completes.
    with patch.dict(ie_cutscene._RUN, res='test_scene', left=1):
        rt.A.StartCutSceneMode(guard_ctx)
        rt.A.Dialogue(guard_ctx, pc)
        assert ie_cutscene.active()
        ie_cutscene._block_done('test_scene')
        assert not ie_cutscene.active()
    foe.object_flag_set(rt.OF_OFF)
    assert rt.F(guard_ctx, EA=255) is None and not rt.T.See(guard_ctx, foe, 0)
    foe.object_flag_unset(rt.OF_OFF)
    assert rt.F(guard_ctx, EA=255) == foe
    assert rt.T.See(guard_ctx, foe, 0)
    assert rt.T.LOS(guard_ctx, pc, 0) and guard_ctx.last_trigger == pc
    assert not rt.T.See(guard_ctx, None, 0)
    assert rt.O(rt.Ctx(guard), 'LastMarkedObject') == foe
    assert rt.O(here, 'LastSeenBy', guard) == foe
    assert rt.O(there, 'LastMarkedObject') is None
    # IWD2's palisade scripts pass separate x, y and facing values. A
    # previous generator passed a point and facing to the same action.
    for args in ((3251, 1194, 10), ((3251, 1194), 10)):
        rt.A.SetSavedLocationPoint(here, *args)
        assert location_to_axis(rt._saved['pc']) == rt.ie_to_tile('TEST1', 3251, 1194)
    # STATS.IDS from both Icewind Dale games. The scores must remain distinct.
    pc.abilities.update(strength=11, intelligence=12, wisdom=13, dexterity=14, constitution=15, charisma=16)
    for index, score in zip((36, 38, 39, 40, 41, 42), range(11, 17)):
        assert rt.T.CheckStat(here, pc, score, index)
    pc.abilities['level_fighter'] = 1
    for code, stats in rt.CLASS_LEVELS.items():
        assert rt.T.ClassEx(here, pc, code) == (stats == ('stat_level_fighter',))
    assert rt.T.TimeLT(here, 7) and not rt.T.TimeGT(here, 19)
    rt.A.SetGlobal(here, 'stage', 'GLOBAL', 1)
    rt.A.SetGlobal(here, 'stage', 'LOCALS', 2)
    rt.A.SetGlobal(there, 'stage', 'MYAREA', 3)
    assert rt.T.Global(there, 'stage', 'GLOBAL', 1)
    assert rt.T.Global(there, 'stage', 'LOCALS', 0)
    assert rt.T.Global(here, 'stage', 'MYAREA', 0)

    rt.A.MoveToObject(here, foe)
    assert location_to_axis(pc.location) == (0, 0)
    assert not rt.T.Range(here, foe, 9)
    clock_events = []
    game.timeevent_add(lambda: clock_events.append(game.t), (), 2100)
    game.tick()
    game.tick()
    assert not clock_events
    game.tick()
    assert location_to_axis(pc.location) == (3, 0)
    assert clock_events == [1003]
    rt.A.Attack(here, foe)
    assert game.combat_is_active()
    for _ in range(6):
        game.tick()
    assert rt.T.Dead(there, pc) and foe.hp > 0
    assert not game.combat_is_active()

    scout = game.spawn('scout', tile=(0, 2))
    game.party.append(scout)
    scout.attack(foe)
    assert game.combat_is_active()
    game.fade_and_teleport(0, 0, 0, 5019, 0, 2)
    assert not game.combat_is_active() and not scout.can_see(foe)
    assert foe not in game.obj_list_vicinity(scout.location, 'npc')
    game.fade_and_teleport(0, 0, 0, 5018, 0, 2)
    assert not game.combat_is_active()
    assert rt.T.Global(here, 'stage', 'GLOBAL', 1)

    with TemporaryDirectory() as directory:
        path = Path(directory, 'vars.iev')
        game.save_script_vars(path)
        game.reset()
        assert rt.O(guard_ctx, 'LastMarkedObject') is None
        assert rt.T.Global(here, 'stage', 'GLOBAL', 0)
        game.load_script_vars(path)
        assert rt.T.Global(here, 'stage', 'GLOBAL', 1)
        assert rt.T.Global(here, 'stage', 'LOCALS', 2)
        assert rt.T.Global(there, 'stage', 'MYAREA', 3)
    print('PASS movement, delayed callback, party defeat and scoped variable round-trip')


def check_door_keys(game):
    import ie_doors
    import ie_itemrt
    from unittest.mock import Mock
    user, companion, stranger = [game.spawn(name) for name in ('user', 'companion', 'stranger')]
    game.party.extend((user, companion))
    portal = Mock(type=0)
    portal.portal_flags_get.return_value = 1
    gate = {'key': 'KEYGATE', 'name': 'Outer Gate'}
    items = {'keygate': {'p': 12011, 'n': 101}, 'keysanc': {'p': 12011, 'n': 102}}
    with patch.dict(ie_itemrt.ITEMS, items), patch.multiple(
            ie_doors, game=game, obj_t_portal=0, OPF_LOCKED=1, RUN_DEFAULT=1,
            _doors=[(gate, portal, False)], create=True):
        ie_itemrt.give('keysanc', user)
        assert ie_doors.use_key(portal, user) == 1
        portal.portal_flag_unset.assert_not_called()
        ie_itemrt.give('keygate', companion)
        ie_doors.use_key(portal, stranger)
        portal.portal_flag_unset.assert_not_called()
        ie_doors.use_key(portal, user)
        portal.portal_flag_unset.assert_called_once_with(1)
    print('PASS converted door accepts the matching party key and rejects another key with the same prototype')


def check_dam_planks(game):
    from unittest.mock import Mock
    import ie_doors
    import ie_itemrt
    opener = game.spawn('opener')
    game.party.append(opener)
    portal = Mock(type=0)
    portal.portal_flags_get.return_value = 0
    spec = {'name': 'AR2101_Door2_Support1', 'script': '21DORSPT'}
    area = 'I2AR2101'
    with patch.dict(ie_itemrt.ITEMS, {'21genwp': {'p': 12011, 'n': 1}}), patch.multiple(
            ie_doors, game=game, obj_t_portal=0, OPF_LOCKED=2, OPF_OPEN=1,
            RUN_DEFAULT=1, _area=area, _doors=[[spec, portal, False]], _door_users={},
            _apply=Mock(), create=True):
        ie_doors.use_key(portal, opener)
        ie_doors.poll(area)
        assert not opener.inventory
        portal.portal_flags_get.return_value = 1
        ie_doors.poll(area)
        ie_doors.poll(area)
        assert len(opener.inventory) == 1 and ie_itemrt.find(opener, '21genwp')
    print('PASS opening the dam support grants the original wood planks exactly once per opening')


def check_inventory(game, rt):
    import ie_itemrt
    giver = game.spawn('giver')
    pc = game.spawn('pc')
    game.party.append(pc)
    ctx = rt.Ctx(giver, pc)
    entries = {'letter': {'p': 1, 'n': 100}, 'scroll': {'p': 1, 'n': 102}}
    with patch.dict(ie_itemrt.ITEMS, entries):
        rt.A.GiveItemCreate(ctx, ' Letter ', giver)
        first = ie_itemrt.find(giver, 'letter')
        rt.A.GiveItemCreate(ctx, 'letter', giver)
        rt.A.GiveItemCreate(ctx, 'scroll', giver)
        rt.A.GiveItem(ctx, 'LETTER', pc)
        assert not rt.T.ItemIsIdentified(ctx, 'letter', None)
        first.flags = 1
        assert rt.T.ItemIsIdentified(ctx, 'letter', None)
        assert not rt.T.ItemIsIdentified(ctx, 'letter', giver)
        assert ie_itemrt.find(pc, 'letter') is first and first.holder is pc
        assert len(giver.inventory) == 2 and rt.T.HasItem(ctx, 'letter', giver)
        pc.item_get(first)
        assert pc.inventory == [first]
        rt.A.TakePartyItem(ctx, 'letter')
        assert first.destroyed and first.holder is None and not rt.T.PartyHasItem(ctx, 'letter')
        assert rt.T.HasItem(ctx, 'scroll', giver) and ie_itemrt.find(giver, 'letter') is not first
        assert ie_itemrt.give('unmapped_fixture_item', pc) is None and not pc.inventory
        entries = {'bolts': {'p': 9, 'type': 'ammo'}}
        with patch.dict(ie_itemrt.ITEMS, entries):
            bolts = ie_itemrt.give('bolts', pc, 7)
            rt.A.TakePartyItemNum(ctx, 'bolts', 2)
            assert bolts.quantity == 5 and ie_itemrt.find(giver, 'bolts').quantity == 2
            rt.A.DestroyItem(ctx, 'bolts')
            assert ie_itemrt.find(giver, 'bolts') is None
            rt.A.TakePartyItemNum(ctx, 'bolts', 5)
            assert bolts.holder is giver and ie_itemrt.find(pc, 'bolts') is None
        kept = ie_itemrt.give('scroll', pc)
        carried = list(giver.inventory)
        # An old conversion can also list an item whose actual owner is a PC.
        giver.inventory.append(kept)
        rt.A.DestroySelf(ctx)
        assert giver.destroyed and carried and all(item.destroyed for item in carried)
        assert kept.holder is pc and not kept.destroyed
        print('PASS scripted despawn removes carried gear and preserves transferred items')
    print('PASS item identity, duplicate copies, transfer, removal and shared base prototypes')


def check_targos_dialogue(game, rt):
    import ie_spawnables
    leader = game.spawn('first portrait')
    speaker = game.spawn('speaker')
    actor = game.spawn('Reig')
    game.party.extend([leader, speaker])
    assert rt.dlg_cond(actor, speaker, 'reig', 'AR1000',
                       lambda c: rt.O(c, 'Protagonist') is speaker and rt.O(c, 'Player1') is leader)
    awards = []
    leader.award_experience = speaker.award_experience = awards.append
    rt.A.AddXPVar(rt.Ctx(actor, speaker), 'Level_1_Average', 1484)
    assert awards == [200, 200]
    keg_spec = next(c for g in ie_spawnables.INI_SPAWNS['AR1200']['enter'] for c in g['critters']
                    if c.get('script_name') == '12KegArc')
    ident = keg_spec['ident'] + '#2'
    keg = game.spawn(ident)
    rt.bind(keg, ident, 'AR1200')
    assert keg.d20_query('Combat Practice Target') and not keg.hostile
    blasting_keg = game.spawn('dynokeg', hostile=True)
    rt.bind(blasting_keg, 'dynokeg', 'AR1200')
    assert blasting_keg.hostile and not blasting_keg.d20_query('Combat Practice Target')
    ctx = rt.Ctx(actor, speaker, 'Gable', 'AR1200')
    assert rt.N(ctx, '12KegArc') is keg and not rt.T.Dead(ctx, '12KegArc')
    rt.event(ident, 'Die', speaker)
    assert rt.T.Dead(ctx, '12KegArc')
    print('PASS Targos dialogue speaker, table XP reward and the named archery target death')


def check_crane(game, rt, core):
    import ie_areas, ie_cutscene, ie_itemrt
    from toee import OCOF_LOCKED
    if not getattr(ie_cutscene, 'CONTAINER_SCRIPTS', {}).get('AR1100', {}).get('AR1100_Wheel'):
        print('SKIP crane: this conversion has no AR1100_Wheel container script')
        return

    script, = (core / 'scr').glob('py*ie_10jorun.py')
    jorun = importlib.import_module(script.stem)
    dock = ie_areas.MAPS[jorun.AREA]
    palisade = ie_areas.MAPS['AR1100']
    pc = game.spawn('pc', dock)
    game.party.append(pc)
    npc = game.spawn(jorun.IDENT, dock)
    ctx = rt.Ctx(npc, pc, jorun.IDENT, jorun.AREA)
    game.enable_area_scripts()
    # Start at the generated dialogue reply in which Jorun gives the PC the wheel.
    jorun.ie_a231(npc, pc)
    wheel = ie_itemrt.find(pc, '10gencrw')
    assert wheel and rt.T.Global(ctx, 'Lumber_Quest', 'GLOBAL', 4)
    game.fade_and_teleport(0, 0, 0, palisade, 519, 495)
    game.tick()
    crane, = (box for box in game.containers[palisade] if box.name == 'AR1100_Wheel')
    barrel = next(box for box in game.containers[palisade] if box.name.startswith('Rain Barrel') and box.inventory)
    stock = list(barrel.inventory)
    assert rt.T.Global(ctx, 'Crane_Wheel', 'GLOBAL', 0)
    barrel.item_get(wheel)
    game.tick()
    assert rt.T.Global(ctx, 'Crane_Wheel', 'GLOBAL', 0) and not rt.T.PartyHasItem(ctx, '10gencrw')
    crane.item_get(wheel)
    assert barrel.inventory == stock
    game.fade_and_teleport(0, 0, 0, dock, 480, 470)
    game.tick()
    assert wheel.holder is crane and rt.T.Global(ctx, 'Crane_Wheel', 'GLOBAL', 0)
    xp_before = pc.experience
    game.fade_and_teleport(0, 0, 0, palisade, 519, 495)
    game.tick()
    assert rt.T.Global(ctx, 'Crane_Wheel', 'GLOBAL', 1) and wheel.destroyed
    assert not crane.inventory and crane.container_flags_get() & OCOF_LOCKED
    xp_after = pc.experience
    assert xp_after > xp_before
    game.tick()
    assert pc.experience == xp_after and rt.T.Global(ctx, 'Crane_Wheel', 'GLOBAL', 1) and barrel.inventory == stock
    print('PASS Jorun gives the wheel; the AR1100 crane consumes it and locks on the active map')


def check_docks(game, rt, core):
    import ie_areas
    from ie_creatures_ar1002 import CREATURES

    area = 'AR1002'
    map_id = ie_areas.MAPS[area]
    game.enable_area_scripts()
    hostiles = [data for data in CREATURES if data.get('hostility') == 'hostile']
    assert len(hostiles) > 1, 'converted dock encounter has too few hostile placements'
    first = hostiles[0]
    x, y = rt.ie_to_tile(area, first['x'], first['y'])
    pc = game.spawn('pc', map_id, (x - 6, y), hp=40, damage=3)
    game.party.append(pc)
    ctx = rt.Ctx(pc, None, 'area_' + area, area)
    enemies = []
    if any(d.get('area_spawn') for d in hostiles):
        assert len(hostiles) == 12
        for level, expected in ((1,5), (2,9), (3,12)):
            rt.ie_vars.put(area + ':ie2toee_spawn_difficulty', 0)
            pc.abilities['level_fighter'] = level
            assert sum(rt.area_spawn_allowed(d) for d in hostiles) == expected
        rt.ie_vars.put(area + ':ie2toee_spawn_difficulty', 0)
        pc.abilities['level_fighter'] = 1
        hostiles = [d for d in hostiles if rt.area_spawn_allowed(d)]
        pc.abilities['level_fighter'] = 3
        assert sum(rt.area_spawn_allowed(d) for d in CREATURES if d.get('hostility') == 'hostile') == 5
        print('PASS Targos warehouse spawns 5, 9 or 12 goblins at party levels 1, 2 or 3; visits persist')
    for data in hostiles:
        tile = rt.ie_to_tile(area, data['x'], data['y'])
        enemy = game.spawn(data['ident'], map_id, tile, hp=data['hp'], damage=1, hostile=True)
        script, = (core / 'scr').glob('py%05die_*.py' % data['script_id'])
        enemy.script_mod = importlib.import_module(script.stem)
        rt.bind(enemy, data['ident'], area)
        assert rt.N(ctx, data['actor']) is enemy, data['actor']
        enemies.append((enemy, data['actor']))

    flag = area + '_GOBLINS_CLEAR'
    game.tick()
    assert rt.T.Global(ctx, flag, 'GLOBAL', 0)
    for enemy, name in enemies:
        rt.A.Attack(ctx, enemy)
        for _ in range(200):
            game.tick()
            if any(actor.hp for actor, _ in enemies):
                assert rt.T.Global(ctx, flag, 'GLOBAL', 0), 'area cleared with a living goblin'
            if not game.combat_is_active():
                break
        assert pc.hp and enemy.is_dead_or_destroyed(), 'encounter failed at ' + name
        assert rt.T.Global(ctx, 'SPRITE_IS_DEAD' + name, 'GLOBAL', 1), 'missing death event for ' + name
    assert rt.T.Global(ctx, flag, 'GLOBAL', 1)
    assert rt.T.Global(ctx, 'Dock_Goblin_Quest', 'GLOBAL', 0), 'other dock maps are still uncleared'
    print('PASS %s: %d goblins defeated; the area script set %s' % (area, len(enemies), flag))


def check_shaengarne(game, rt):
    import ie_travel_data as travel
    import ie_areas
    area = travel.AREAS.get('I2AR2000')
    if area is None:
        return  # prologue-only installation
    pc = game.spawn('leader', travel.AREAS['I2AR1000']['map'])
    game.party.append(pc)
    game.enable_area_scripts()
    game.tick()
    assert rt.get_var(None, 'Chapter', 'GLOBAL') == 0
    entry = area['entrances']['FRWMAP']
    game.fade_and_teleport(0, 0, 0, area['map'], *entry[:2])
    game.tick()
    assert rt.get_var(None, 'Chapter', 'GLOBAL') == 1
    game.tick()
    assert rt.get_var(None, 'Chapter', 'GLOBAL') == 1
    assert 'AR2000' in ie_areas.SCRIPTS
    trigger = next(r for r in area['triggers'] if r['name'] == 'Torak_Call_2')
    script = importlib.import_module(trigger['module'])
    ctx = rt.Ctx(None, pc, 'area_AR2000', 'AR2000', {'Entered': pc})
    with patch.object(rt.A, 'StartCutScene') as start:
        rt.run_script(ctx, script.BLOCKS)
        start.assert_called_once_with(ctx, '20cTorD2')
    import ie_travel
    assert trigger.get('one_shot'), 'the original Torak proximity trap cannot reset'
    x, y = trigger['poly'][0]
    def enter(region):
        ie_travel._triggers('I2AR2000', [region], [pc], [(x, y)])
    with patch.object(rt.A, 'StartCutScene') as start:
        enter(trigger)
        ie_travel._inside.clear()  # reload the map, retaining the save-backed variables
        enter(trigger)
        assert start.call_count == 1
        repeat = dict(trigger, name='resettable', one_shot=False)
        enter(repeat)
        ie_travel._inside.clear()
        enter(repeat)
        assert start.call_count == 3
    print('PASS Shaengarne arrival and Torak cutscene triggers')


def check_dereth_camps(game, rt):
    import ie_areas
    if 'AR2000' not in ie_areas.MAPS:
        return
    from ie_bcs_ar2000_area import BLOCKS
    from ie_creatures_ar2000 import CREATURES
    mid = ie_areas.MAPS['AR2000']
    pc = game.spawn('leader', mid)
    game.party.append(pc)
    import py01099ie_baked as shared_script
    assert shared_script._map_area(pc) == 'AR2000'
    # The same installed script also runs back in Targos.
    assert shared_script._map_area(game.spawn('town_actor', ie_areas.MAPS['AR1000'])) == 'AR1000'
    ctx = rt.Ctx(None, pc, 'area_AR2000', 'AR2000')
    for team, flag in ((3, 'SR_Dereth_Freed'), (4, 'SR_Cleared_House')):
        active = []
        for spec in CREATURES:
            if not spec['actor'].startswith('T%d_' % team) or not rt.area_spawn_allowed(spec):
                continue
            obj = game.spawn(spec['ident'], mid)
            rt.bind(obj, spec['ident'], 'AR2000')
            active.append((spec, obj))
        spec, guard = next(pair for pair in active if pair[0]['actor'] == 'T%d_Orc_1' % team)
        wrapper = importlib.import_module('py%05die_%s' % (spec['script_id'], spec['ident']))
        alert = next(s for s in wrapper.SCRIPTS if s.RESREF == '00t%02det' % team)
        rt.run_script(rt.Ctx(guard, pc, spec['ident'], 'AR2000', {'AttackedBy': pc}), alert.BLOCKS)
        assert rt.get_var(ctx, 'TEAM_%d' % team, 'MYAREA') == 1
        for _ in range(4):  # arrival and Torak's greeting can run before the camp blocks
            rt.run_script(ctx, BLOCKS)
        assert rt.get_var(ctx, flag, 'GLOBAL') == 1
        for _, obj in active:
            obj.hp = 0
        rt.run_script(ctx, BLOCKS)
        assert rt.get_var(ctx, flag, 'GLOBAL') == 2
    print('PASS attacking the original guards activates both Dereth camps and clearing each advances its quest')


def check_camp_visibility(game, core):
    import ie_areas
    if 'AR2001' not in ie_areas.MAPS:
        return
    from ie_bake_i2ar2001 import OBJS
    from toeemob import read_mob
    actors = {entry['spec']['actor']: guid.lower() for guid, entry in OBJS.items()
              if entry.get('k') == 'npc'}
    directory = core.parent / 'ToEE' / 'maps' / 'I2AR2001'
    for actor, hidden in [('Torak2', False), ('Arte', True), ('Emma', True)]:
        obj = read_mob((directory / (actors[actor] + '.mob')).read_bytes())
        assert bool(obj.get('flags') & 2) == hidden, actor
    print('PASS Torak at the mill starts visible and the two scripted reveals stay hidden')

    from types import SimpleNamespace
    from ie_creatures_ar2001 import CREATURES
    import ie_runtime as rt
    wrappers = {s['ident']: s['script_id'] for s in CREATURES if s.get('script_id')}
    for ident, passive in [('20arte', True), ('20kaitln', True), ('20orcwar_29', False)]:
        actor = game.spawn(ident, ie_areas.MAPS['AR2001'])
        wrapper = importlib.import_module('py%05die_%s' % (wrappers[ident], ident))
        wrapper.san_first_heartbeat(actor, None)
        assert bool(actor.npc_flags_get() & rt.ONF_NO_ATTACK) == passive, ident
    print('PASS Arte and Kaitlin retain their escape scripts without joining the mill fight as attackers')
    checked = 0
    for guid, entry in OBJS.items():
        spec = entry.get('spec', {})
        if spec.get('family') != 'keg':
            continue
        ident = spec['ident']
        wrapper = importlib.import_module('py%05die_%s' % (wrappers[ident], ident))
        if not wrapper.SCRIPTS:
            assert wrapper.san_start_combat(SimpleNamespace(id=guid), None) == rt.SKIP_DEFAULT
            checked += 1
    assert checked > 0
    assert rt.scriptless_combat_turn(SimpleNamespace(id='unrelated'), 'AR2001') == rt.RUN_DEFAULT
    print('PASS %d scriptless keg placements skip native monster AI' % checked)


def check_bridge(game, rt):
    import ie_areas
    if 'AR2102' not in ie_areas.MAPS:
        return
    from ie_creatures_ar2102 import CREATURES
    from ie_bcs_ar2102_area import BLOCKS
    area = 'AR2102'
    mid = ie_areas.MAPS[area]
    pc = game.spawn('leader', mid)
    game.party.append(pc)
    ctx = rt.Ctx(None, pc, 'area_' + area, area)
    actors = {}
    omitted = next(s for s in CREATURES if s.get('ident') and not rt.area_spawn_allowed(s))
    other = game.spawn(omitted['ident'], ie_areas.MAPS['AR2000'])
    rt.bind(other, omitted['ident'], 'AR2000')
    assert rt.N(ctx, omitted['actor']) is None, 'difficulty-omitted placement resolved to a different map'
    for spec in CREATURES:
        if not rt.area_spawn_allowed(spec):
            continue
        actor = game.spawn(spec['ident'], mid, rt.ie_to_tile(area, spec['x'], spec['y']))
        rt.bind(actor, spec['ident'], area)
        actors[spec['actor']] = actor
    beams = [actors[name] for name in ('Support_Beam_North', 'Support_Beam_South')]
    expected = {s['actor'] for s in CREATURES}
    assert {'Cutscene_Commander', 'Bugbear_Captain_5', 'GTH05_08'} <= expected
    with patch.object(rt.A, 'StartCutScene'):
        for _ in range(6):
            rt.run_script(ctx, BLOCKS)
        assert not rt.get_var(ctx, 'Shaengarne_Bridge_Destroyed', 'GLOBAL')
        assert not rt.get_var(ctx, 'Shaengarne_Bridge_Cleared', 'GLOBAL')
        beams[0].hp = 0
        rt.run_script(ctx, BLOCKS)
        assert rt.get_var(ctx, 'Shaengarne_Bridge_Destroyed', 'GLOBAL') == 1
        beams[1].hp = 0
        rt.run_script(ctx, BLOCKS)
        assert rt.get_var(ctx, 'Shaengarne_Bridge_Destroyed', 'GLOBAL') == 2
        for name, actor in actors.items():
            if name.startswith(('GTH', 'Bugbear_Captain', 'Ogre_')):
                actor.hp = 0
        for _ in range(4):
            rt.run_script(ctx, BLOCKS)
        assert rt.get_var(ctx, 'Shaengarne_Bridge_Cleared', 'GLOBAL') == 1
        assert rt.get_var(ctx, 'Shaengarne_Award_XPVar', 'GLOBAL') == 1
    print('PASS bridge starts intact and its area script counts the two supports separately')


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, help='installed IWD2 ToEE_core directory')
    parser.add_argument('--save-vars', type=Path, help='write the final scenario variable store')
    args = parser.parse_args()
    if args.core and not (args.core / 'scr/ie_bcs_ar1002_area.py').is_file():
        parser.error('--core must contain the converted IWD2 dock scripts')
    sys.path.insert(0, str(Path(__file__).parent / 'runtime'))
    if args.core:
        sys.path.insert(0, str(args.core / 'scr'))
    game = install()
    import ie_runtime as rt
    rt._real = lambda: game.t
    check_door_keys(game)
    game.reset()
    check_inventory(game, rt)
    game.reset()
    check_model(game, rt)
    if args.core:
        game.reset()
        check_targos_dialogue(game, rt)
        game.reset()
        check_crane(game, rt, args.core)
        game.reset()
        check_docks(game, rt, args.core)
    if args.save_vars:
        game.save_script_vars(args.save_vars)
    if args.core:
        game.reset()
        check_shaengarne(game, rt)
        if (args.core / 'scr/ie_bcs_21dorspt_door.py').is_file():
            game.reset()
            check_dam_planks(game)
        game.reset()
        check_dereth_camps(game, rt)
        check_camp_visibility(game, args.core)
        game.reset()
        check_bridge(game, rt)


if __name__ == '__main__':
    main()
