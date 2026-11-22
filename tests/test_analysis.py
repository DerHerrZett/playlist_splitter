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


def test_first_sound_frame(tmp_path):
    import wave

    from playlist_splitter.analysis import first_sound_frame
    from playlist_splitter.wavfile import read_info

    frames = bytearray(6 * 1000)
    frames[6 * 700 + 2] = 0x10  # frame 700, left channel, high byte
    with wave.open(str(tmp_path / "a.wav"), "wb") as w:
        w.setnchannels(2), w.setsampwidth(3), w.setframerate(1000)
        w.writeframes(bytes(frames))
    assert first_sound_frame(read_info(tmp_path / "a.wav"), -100, chunk_seconds=0.3) == 700
