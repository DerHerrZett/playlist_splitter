import struct
import wave

from playlist_splitter.wavfile import read_info, write_slice


def _make_wav(path, frames=1000, width=3, channels=2):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(44100)
        n = frames * width * channels
        w.writeframes((bytes(range(256)) * (n // 256 + 1))[:n])
    return path


def test_slice_is_byte_exact(tmp_path):
    info = read_info(_make_wav(tmp_path / "in.wav"))
    assert (info.channels, info.bits, info.n_frames) == (2, 24, 1000)
    write_slice(info, 100, 300, tmp_path / "out.wav")
    out = read_info(tmp_path / "out.wav")
    src = (tmp_path / "in.wav").read_bytes()[info.data_offset + 600 : info.data_offset + 1800]
    dst = (tmp_path / "out.wav").read_bytes()[out.data_offset :]
    assert out.fmt_chunk == info.fmt_chunk and out.n_frames == 200 and src == dst
    assert struct.unpack("<I", (tmp_path / "out.wav").read_bytes()[4:8])[0] == len(dst) + 36
