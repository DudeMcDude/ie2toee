# Test harness helper (developer tool): probes schedule their steps through this module, which is installed in the
# module's scr dir. A save made by a probe pickles the pending step time events by reference to this module; a later
# run that loads the save can unpickle them (the probe module itself is imported only after the autoload), and
# they run only if a probe registered a handler (stale steps are dropped by the probe's run token).
HANDLER = [None]

def step(*args):
    if HANDLER[0] is not None:
        return HANDLER[0](*args)
    return 0
