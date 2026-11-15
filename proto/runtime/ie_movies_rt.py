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


def prologue(slide):
    """The new-game chapter screen (IWD AR1006's prologue break): the intro first if it has not played yet (the area
    script can tick before the first critter heartbeat that plays it), then the slide, in one queue. Skippable like
    every movie/slide (Temple+: Space, Enter, Esc or a click)."""
    try:
        import ie_movies_data
        mv = ie_movies_data.MOVIES
    except ImportError:
        return 0
    ids = []
    if mv.get('intro') and not game.global_vars[FLAG_VAR]:
        game.global_vars[FLAG_VAR] = 1
        ids += list(mv['intro'])
    ids += list(mv.get(slide) or [])
    for m in ids:
        game.moviequeue_add(m)
    if ids:
        game.moviequeue_play()
    return len(ids)


def play(key):
    """Queue and play a converted movie / chapter slide by key ('intro', 'chapter1', 'middle', ...)."""
    try:
        import ie_movies_data
        ids = ie_movies_data.MOVIES.get(key)
    except ImportError:
        return 0
    if not ids:
        return 0
    for m in ids:
        game.moviequeue_add(m)
    game.moviequeue_play()
    return 1
