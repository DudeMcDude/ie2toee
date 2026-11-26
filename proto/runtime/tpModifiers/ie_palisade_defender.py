from templeplus.pymod import PythonModifier
from templeplus.constants import ET_OnD20PythonQuery
from toee import game, ONF_KOS, Q_Critter_Is_Charmed
import ie_vars


def can_disengage(attachee, args, evt_obj):
    if (ie_vars.get('GLOBAL:goblin_palisade_quest')
            and not ie_vars.get('GLOBAL:targos_hostile')
            and not ie_vars.get('AR1200:team_0')
            and not (attachee.npc_flags_get() & ONF_KOS)):
        evt_obj.return_val = 1
    return 0


def party_combat_ally(attachee, args, evt_obj):
    import ie_runtime as rt
    if (rt.targos_guard is not None and game.party
            and not (attachee.npc_flags_get() & ONF_KOS)
            and not attachee.d20_query(Q_Critter_Is_Charmed)
            and game.leader.reputation_has(rt.targos_guard.REPUTATION)
            and attachee.faction_has(rt.targos_guard.FACTION)):
        evt_obj.return_val = 1
    return 0


defender = PythonModifier("IE Palisade Defender", 0)
defender.AddHook(ET_OnD20PythonQuery, "Party Combat Ally", party_combat_ally, ())
defender.AddHook(ET_OnD20PythonQuery, "Can Disengage From Party", can_disengage, ())


def practice_target(attachee, args, evt_obj):
    evt_obj.return_val = 1
    return 0


practice = PythonModifier("IE Combat Practice Target", 0)
practice.AddHook(ET_OnD20PythonQuery, "Combat Practice Target", practice_target, ())


def household_ally(attachee, args, evt_obj):
    import ie_runtime as rt
    if (rt.targos_guard is not None and game.party
            and game.leader.reputation_has(rt.targos_guard.REPUTATION)
            and not ie_vars.get('AR1004:team_1')
            and not (attachee.npc_flags_get() & ONF_KOS)
            and not attachee.d20_query(Q_Critter_Is_Charmed)):
        evt_obj.return_val = 1
    return 0


household = PythonModifier("IE Firtha Household", 0)
household.AddHook(ET_OnD20PythonQuery, "Party Combat Ally", household_ally, ())
household.AddHook(ET_OnD20PythonQuery, "Can Disengage From Party", household_ally, ())
