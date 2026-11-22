from playlist_splitter.analysis import decode_pcm


def test_decode_24bit():
    raw = bytes([0xFF, 0xFF, 0x7F, 0x00, 0x00, 0x80])  # max, min
    assert decode_pcm(raw, 24, 2).tolist() == [[(2**23 - 1) / 2**23, -1.0]]


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
