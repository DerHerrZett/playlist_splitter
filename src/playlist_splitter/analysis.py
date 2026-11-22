"""Loudness envelope of a WAV file (read-only analysis)."""

from dataclasses import dataclass

import numpy as np

from playlist_splitter.wavfile import WavInfo

HOP_SECONDS = 0.05
CHUNK_HOPS = 2000


@dataclass(frozen=True)
class Envelope:
    db: np.ndarray  # level per hop in dBFS
    hop_frames: int
    sample_rate: int

    def to_seconds(self, index: int) -> float:
        return index * self.hop_frames / self.sample_rate

    def to_index(self, seconds: float) -> int:
        return int(round(seconds * self.sample_rate / self.hop_frames))


def decode_pcm(raw: bytes, bits: int, channels: int) -> np.ndarray:
    """Integer PCM bytes -> float array (frames, channels) in [-1, 1)."""
    width = bits // 8
    if width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        ints = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        ints = np.where(ints & 0x800000, ints - 0x1000000, ints)
    elif width in (1, 2, 4):
        dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[width]
        ints = np.frombuffer(raw, dtype=dtype).astype(np.float64)
        if width == 1:
            ints -= 128
    else:
        raise ValueError(f"Unsupported bit depth {bits}")
    return (ints / 2.0 ** (bits - 1)).reshape(-1, channels)


def compute_envelope(info: WavInfo) -> Envelope:
    hop = int(info.sample_rate * HOP_SECONDS)
    chunk_bytes = hop * CHUNK_HOPS * info.block_align
    levels = []
    with open(info.path, "rb") as f:
        f.seek(info.data_offset)
        remaining = info.n_frames * info.block_align
        while remaining > 0:
            raw = f.read(min(chunk_bytes, remaining))
            remaining -= len(raw)
            samples = decode_pcm(raw, info.bits, info.channels)
            n = len(samples) // hop * hop
            if n == 0:
                break
            power = (samples[:n] ** 2).mean(axis=1).reshape(-1, hop).mean(axis=1)
            levels.append(10 * np.log10(power + 1e-12))
            print(f"\rAnalysing audio: {1 - remaining / info.data_size:6.1%}", end="")
    print()
    return Envelope(np.concatenate(levels), hop, info.sample_rate)


def first_sound_frame(info: WavInfo, threshold_db: float, chunk_seconds: float = 1.0,
                      from_frame: int = 0) -> int:
    """Index of the first frame >= from_frame whose peak exceeds threshold_db."""
    threshold = 10 ** (threshold_db / 20)
    chunk_frames = int(info.sample_rate * chunk_seconds)
    with open(info.path, "rb") as f:
        f.seek(info.data_offset + from_frame * info.block_align)
        for start in range(from_frame, info.n_frames, chunk_frames):
            n = min(chunk_frames, info.n_frames - start)
            peak = np.abs(decode_pcm(f.read(n * info.block_align), info.bits,
                                     info.channels)).max(axis=1)
            loud = np.flatnonzero(peak > threshold)
            if loud.size:
                return start + int(loud[0])
    raise ValueError(f"No sound above {threshold_db} dBFS in {info.path}")
