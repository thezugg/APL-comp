import random
import pytest
from app.engine import draw_slots, round_count


@pytest.mark.parametrize("n", [2, 3, 4, 5, 7, 8, 16, 31, 32, 33, 48, 50, 73, 128, 500, 512])
def test_draws(n):
    slots = draw_slots(list(range(n)), random.Random(42))
    size = 1 << (n - 1).bit_length()
    assert len(slots) == size // 2
    assert sum(x is None for row in slots for x in row) == size - n
    assert all(any(x is not None for x in match) for match in slots)
    assert set(x for match in slots for x in match if x is not None) == set(range(n))
    assert round_count(n) == (n - 1).bit_length()


def test_duplicate_entrants():
    with pytest.raises(ValueError):
        draw_slots([1, 1])
