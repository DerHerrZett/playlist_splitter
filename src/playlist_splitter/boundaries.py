"""Find cut points from expected durations and the loudness envelope."""

from dataclasses import dataclass

import numpy as np

from playlist_splitter.analysis import Envelope


@dataclass(frozen=True)
class Cut:
    seconds: float
    expected: float
    level_db: float


def _smooth(db: np.ndarray, width: int) -> np.ndarray:
    if width <= 1:
        return db
    return np.convolve(db, np.ones(width) / width, mode="same")


def first_sound(env: Envelope, threshold_db: float) -> int:
    idx = np.flatnonzero(env.db > threshold_db)
    return int(idx[0]) if idx.size else 0


def last_sound(env: Envelope, threshold_db: float) -> int:
    idx = np.flatnonzero(env.db > threshold_db)
    return int(idx[-1]) + 1 if idx.size else len(env.db)


def quietest_near(env: Envelope, expected: float, window: float) -> int:
    """Index of the quietest point within +-window seconds of expected."""
    smoothed = _smooth(env.db, 5)
    lo = max(env.to_index(expected - window), 0)
    hi = min(env.to_index(expected + window), len(env.db) - 1)
    if hi <= lo:
        return min(max(env.to_index(expected), 0), len(env.db) - 1)
    seg = smoothed[lo : hi + 1]
    # among near-minimal candidates, prefer the one closest to the expectation
    candidates = np.flatnonzero(seg <= seg.min() + 1.0) + lo
    return int(candidates[np.argmin(np.abs(candidates - env.to_index(expected)))])


def find_cuts(
    env: Envelope, durations: list[float], window: float, threshold_db: float
) -> list[Cut]:
    """len(durations)+1 cuts: start, inner boundaries, end."""
    start = first_sound(env, threshold_db)
    cuts = [Cut(env.to_seconds(start), 0.0, float(env.db[start]))]
    pos = env.to_seconds(start)
    for d in durations:
        expected = pos + d
        idx = quietest_near(env, expected, window)
        pos = env.to_seconds(idx)
        cuts.append(Cut(pos, expected, float(env.db[idx])))
    # recording may continue after the last song: never cut past the last sound
    end = last_sound(env, threshold_db)
    if env.to_index(cuts[-1].seconds) > end:
        last = cuts.pop()
        cuts.append(Cut(env.to_seconds(end), last.expected, float(env.db[end - 1])))
    return cuts
