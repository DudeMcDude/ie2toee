# Imported by Temple+ at startup with the other tpModifiers (before any save is loaded): chains the IE variable
# store's save/load into templeplus.savehook (ie_vars.install_hooks). Must never raise (tpModifiers errors quit).
try:
    import ie_vars
    ie_vars.install_hooks()
except Exception as e:
    print('IE_VARS hook install failed: %s' % e)
