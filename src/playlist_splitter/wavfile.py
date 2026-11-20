"""Minimal RIFF/WAV reader and byte-exact slice writer."""

import struct
from dataclasses import dataclass
from pathlib import Path

COPY_BUFFER = 16 * 1024 * 1024


@dataclass(frozen=True)
class WavInfo:
    path: Path
    fmt_chunk: bytes  # raw 'fmt ' chunk payload, copied verbatim
    channels: int
    sample_rate: int
    bits: int
    block_align: int
    data_offset: int
    data_size: int

    @property
    def n_frames(self) -> int:
        return self.data_size // self.block_align

    @property
    def duration(self) -> float:
        return self.n_frames / self.sample_rate


def read_info(path: Path) -> WavInfo:
    with open(path, "rb") as f:
        riff, _, wave = struct.unpack("<4sI4s", f.read(12))
        if riff != b"RIFF" or wave != b"WAVE":
            raise ValueError(f"{path} is not a RIFF/WAVE file")
        fmt = None
        while header := f.read(8):
            cid, size = struct.unpack("<4sI", header)
            if cid == b"fmt ":
                fmt = f.read(size)
            elif cid == b"data":
                if fmt is None:
                    raise ValueError("'data' chunk before 'fmt ' chunk")
                fmt_tag, ch, rate, _, align, bits = struct.unpack("<HHIIHH", fmt[:16])
                if fmt_tag not in (1, 0xFFFE):
                    raise ValueError(f"Unsupported WAV format tag {fmt_tag:#x}")
                return WavInfo(path, fmt, ch, rate, bits, align, f.tell(), size)
            else:
                f.seek(size, 1)
            if size % 2:
                f.seek(1, 1)
    raise ValueError(f"No 'data' chunk in {path}")


def write_slice(info: WavInfo, start_frame: int, end_frame: int, out: Path) -> None:
    """Copy frames [start, end) unchanged into a new WAV with the same fmt chunk."""
    size = (end_frame - start_frame) * info.block_align
    pad = size % 2
    fmt = info.fmt_chunk + (b"\0" if len(info.fmt_chunk) % 2 else b"")
    riff_size = 4 + 8 + len(fmt) + 8 + size + pad
    with open(info.path, "rb") as src, open(out, "wb") as dst:
        dst.write(struct.pack("<4sI4s", b"RIFF", riff_size, b"WAVE"))
        dst.write(struct.pack("<4sI", b"fmt ", len(info.fmt_chunk)) + fmt)
        dst.write(struct.pack("<4sI", b"data", size))
        src.seek(info.data_offset + start_frame * info.block_align)
        remaining = size
        while remaining:
            buf = src.read(min(COPY_BUFFER, remaining))
            if not buf:
                raise IOError("Unexpected end of input file")
            dst.write(buf)
            remaining -= len(buf)
        if pad:
            dst.write(b"\0")
