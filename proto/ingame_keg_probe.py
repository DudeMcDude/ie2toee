# IWD2 keg check (Temple+ Python 2.7): kegs are critters with the barrel mesh (spec "mesh" 11013). On the first visit
# of map 5951 (I2AR1001) find them, log mesh/flags/HP, screenshot, kill one with damage, screenshot; on 5953 log
# Guthewulfe's feats/skills. Runs beside ingame_exiticon_probe (same log).
from toee import *
import os
LOG = os.environ.get('IE2TOEE_PROBE_LOG', 'ie2toee_probe.log')
def log(s):
    f = open(LOG, 'a'); f.write(s + '\n'); f.close()
st = {'done': set()}
def crit():
    l = game.leader
    return [o for o in game.obj_list_vicinity(l.location, OLC_CRITTERS) if o not in game.party]
def poll():
    try:
        m = game.leader.map
        if m not in st['done']:
            st['done'].add(m); game.timeevent_add(survey, (m,), 3000, 1)
        if m == 5952 and 'keg' not in st['done']:
            st['done'].add('keg'); game.timeevent_add(kegs, (), 2500, 1)
    except Exception, e:
        log('KEG poll error %s' % e)
    if 'keg' not in st['done'] or 'k' in st and 'clicked' not in st['done'] or 5950 not in st['done']: game.timeevent_add(poll, (), 1000, 1)
    return 0
def kegs():
    try:
        k = [o for o in crit() if o.obj_get_int(37) == 11013]
        log('KEG found %d kegs: %s' % (len(k), [(o.obj_get_int(37), o.obj_get_int(38), o.stat_level_get(stat_hp_current), o.object_flags_get() & (OF_CLICK_THROUGH | OF_DONTDRAW | OF_OFF)) for o in k]))
        if k:
            o = k[0]; st['k'] = o; game.scroll_to(o); log('SHOT keg_before')
            st['hp0'] = o.stat_level_get(stat_hp_current); game.timeevent_add(click, (), 1500, 1)
    except Exception, e:
        import traceback; log('KEG error %s' % traceback.format_exc())
    return 0
def click():
    log('CLICK 640 408'); game.timeevent_add(clicked, (), 4000, 1); return 0
def clicked():
    o = st['k']; st['done'].add('clicked')
    log('KEG click: hp %d -> %d, leader target ok %s' % (st['hp0'], o.stat_level_get(stat_hp_current), True)); log('SHOT keg_clicked')
    game.timeevent_add(kill, (), 1000, 1); return 0
def survey(m):
    try:
        c = crit(); ic = [o for o in c if o.has_feat(feat_improved_critical_gauntlet)]
        log('SURVEY map %d critters %d improved_critical %d %s' % (m, len(c), len(ic), [str(o) for o in ic][:5]))
        if m == 5950:
            ps = [o for o in game.obj_list_vicinity(game.leader.location, OLC_PORTAL)][:3]
            for i, o in enumerate(ps):
                game.timeevent_add(doorshot, (o, i), 1500 * (i + 1), 1)
    except Exception, e:
        import traceback; log('SURVEY error %s' % traceback.format_exc())
    return 0
def doorshot(o, i):
    game.scroll_to(o); log('SHOT door_%d' % i); return 0
def kill():
    try:
        o = st['k']
        o.damage(game.leader, D20DT_BLUDGEONING, dice_new('30d10'))
        log('KEG after damage hp %d dead %s' % (o.stat_level_get(stat_hp_current), bool(o.critter_flags_get() & OCF_DEAD) if 'OCF_DEAD' in globals() else '?'))
        log('SHOT keg_after_kill')
    except Exception, e:
        import traceback; log('KEG kill error %s' % traceback.format_exc())
    return 0
def guth():
    try:
        g = [o for o in crit() if o.stat_level_get(stat_level_barbarian) > 0]
        for o in g:
            log('GUTH %s mesh %d lvl ftr %d bbn %d feats dodge %s tough %s skills ms %d' % (o, o.obj_get_int(37), o.stat_level_get(stat_level_fighter), o.stat_level_get(stat_level_barbarian), o.has_feat(feat_dodge), o.has_feat(feat_toughness), o.skill_ranks_get(skill_move_silently)))
            game.scroll_to(o); log('SHOT guthewulfe')
        if not g: log('GUTH none found')
    except Exception, e:
        import traceback; log('GUTH error %s' % traceback.format_exc())
    return 0
game.timeevent_add(poll, (), 1000, 1)
