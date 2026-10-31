"""Temple+ map script tick entry point (Temple+ feature/map-script-tick: TimeEventSystem::MapScriptTick).

The engine calls on_tick(map_id, elapsed_ms) every N ms of the anim game clock (it stops while the game is paused by
the Esc menu, inventory/charsheet etc.), independently of the time event queue, so it survives save/load and map
changes. The return value is the next interval in ms. Older Temple+ builds never call this; ie_cutscene then falls
back to its self-rescheduling time event loop.
"""
def on_tick(map_id, elapsed_ms):
    try:
        import ie_cutscene
        return ie_cutscene.map_tick(map_id, elapsed_ms)
    except ImportError:
        return 1000
