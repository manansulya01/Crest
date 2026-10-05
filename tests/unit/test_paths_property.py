"""Property-style checks on scope matching and membership."""
import random

from crest.paths import scope_matches

ALPHABET = "abcxyz/*?.-/"


def test_scope_matches_never_crashes_and_star_matches_all():
    rng = random.Random(0)
    for _ in range(500):
        s = "".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 20)))
        p = "".join(rng.choice(ALPHABET) for _ in range(rng.randint(0, 20)))
        try:
            _ = scope_matches(s, p)
        except Exception as exc:  # pragma: no cover
            raise AssertionError(f"crash on {s!r} vs {p!r}: {exc}")
    for p in ["a/b/c.txt", "docs/readme.md", "x"]:
        assert scope_matches("*", p)


def test_star_star_is_cross_segment():
    assert scope_matches("docs/**", "docs/a/b/c.txt")
    assert scope_matches("docs/**", "docs")
    assert not scope_matches("docs/*", "docs/a/b.txt")
