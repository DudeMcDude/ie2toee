"""Play the converted IE intro once per new game (called from the first heartbeat of baked critters)."""
from toee import *
FLAG_VAR = 990     # game.global_vars slot: 1 = the intro was played in this game


def play_intro():
    try:
        import ie_movies_data
        mid = ie_movies_data.MOVIES.get('intro')
    except ImportError:
        return 0
    if not mid or game.global_vars[FLAG_VAR]:
        return 0
    game.global_vars[FLAG_VAR] = 1
    for m in (mid if isinstance(mid, list) else [mid]):
        game.moviequeue_add(m)
    game.moviequeue_play()
    return 1
