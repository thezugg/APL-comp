"""Pure knockout engine, migrated from the v3 prototype with extra tests."""
import random


def draw_slots(entrant_ids, rng=None):
    ids = list(entrant_ids)
    if len(ids) < 2:
        raise ValueError("At least two entrants are needed")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate entry IDs")
    rng = rng or random.SystemRandom()
    rng.shuffle(ids)
    size = 1 << (len(ids) - 1).bit_length()
    first_matches = size // 2
    matches = [[ids[i], None] for i in range(first_matches)]
    available = list(range(first_matches))
    rng.shuffle(available)
    for ident, index in zip(ids[first_matches:], available):
        matches[index][1] = ident
    rng.shuffle(matches)
    for match in matches:
        if rng.randrange(2):
            match.reverse()
    return matches


def round_count(entrants):
    if entrants < 2:
        raise ValueError("At least two entrants are needed")
    return (entrants - 1).bit_length()
