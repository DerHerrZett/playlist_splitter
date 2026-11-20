import numpy as np

from playlist_splitter.analysis import Envelope, decode_pcm
from playlist_splitter.boundaries import find_cuts


def test_decode_24bit():
    raw = bytes([0xFF, 0xFF, 0x7F, 0x00, 0x00, 0x80])  # max, min
    assert decode_pcm(raw, 24, 2).tolist() == [[(2**23 - 1) / 2**23, -1.0]]


def test_find_cuts_snaps_to_gap_and_ignores_trailing_audio():
    db = np.full(400, -20.0)  # 10 Hz envelope, 40 s
    db[:20] = db[148:153] = -90.0  # lead-in, gap near 15 s
    env = Envelope(db, hop_frames=1, sample_rate=10)
    cuts = find_cuts(env, [13.5, 10.0], window=3.0, threshold_db=-60)
    assert [round(c.seconds, 1) for c in cuts] == [2.0, 15.0, 25.0]
