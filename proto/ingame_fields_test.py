# Developer experiment: dump low object field numbers on two critters to locate name/description fields.
from toee import *
import toee, os
from utilities import location_from_axis, location_to_axis
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
def run():
    try:
        log('CONST ' + ' '.join('%s=%s' % (n, getattr(toee, n, None)) for n in (
            'obj_f_description', 'obj_f_name', 'obj_f_hp_pts', 'obj_f_critter_inventory_source', 'obj_f_npc_ac_bonus',
            'obj_f_critter_description_unknown', 'obj_f_model_scale', 'obj_f_critter_gender', 'obj_f_critter_alignment',
            'obj_f_npc_hitdice_idx', 'obj_f_critter_level_idx', 'obj_f_npc_save_fortitude_bonus', 'obj_f_hp_damage')))
        lx, ly = location_to_axis(game.leader.location)
        for p in (14000, 14186):
            o = game.obj_create(p, location_from_axis(lx + 2, ly + 2))
            vals = []
            for i in range(0, 420):
                try:
                    v = o.obj_get_int(i)
                except Exception:
                    continue
                if v:
                    vals.append('%d:%d' % (i, v))
            log('FIELDS %d %s' % (p, ' '.join(vals)))
    except Exception, e:
        import traceback; log('ERR %s %s' % (e, traceback.format_exc()))
    log('DONE')
game.fade_and_teleport(0, 0, 0, int(os.environ['IE2TOEE_MAP']), 482, 520)
game.timeevent_add(run, (), 8000, 1)
