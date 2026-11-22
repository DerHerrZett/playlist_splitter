"""Record one song: Reaper records while Spotify plays it, then trim."""

import filecmp
import itertools
import time
from pathlib import Path

from playlist_splitter.analysis import first_sound_frame
from playlist_splitter.reaper import Reaper, wait_for_new_wav
from playlist_splitter.playlist import Track
from playlist_splitter.player import Player
from playlist_splitter.wavfile import read_info, write_slice

PREROLL = 1.0  # seconds recorded before playback starts
POSTROLL = 1.5  # seconds recorded after the reported end
START_TIMEOUT = 20.0
MAX_TAKES = 3


def _play_until_end(player: Player, track: Track, device: str) -> None:
    player.play_track(track.track_id, device)
    deadline = time.monotonic() + START_TIMEOUT
    while not ((s := player.state()).is_playing and s.track_id == track.track_id):
        if time.monotonic() > deadline:
            raise RuntimeError("Spotify did not start playing the track")
        time.sleep(0.5)
    while True:
        s = player.state()
        remaining = track.duration - s.progress
        if s.track_id != track.track_id or not s.is_playing:
            if s.track_id == track.track_id and remaining > 5:
                raise RuntimeError("Playback was paused or interrupted")
            time.sleep(POSTROLL)
            return
        if remaining <= 3:
            time.sleep(max(remaining, 0) + POSTROLL)
            return
        time.sleep(min(remaining - 3, 5))


def wait_until_paused(player: Player, timeout: float = 10.0) -> None:
    player.pause()
    deadline = time.monotonic() + timeout
    while player.state().is_playing:
        if time.monotonic() > deadline:
            raise RuntimeError("Spotify does not pause")
        time.sleep(0.5)
    time.sleep(1.0)  # let the audio output drain


def record_take(track: Track, out: Path, reaper: Reaper, player: Player,
                device: str, record_dir: Path, threshold_db: float) -> dict:
    """Records track once into out; returns extra manifest fields."""
    before = set(record_dir.glob("*.wav"))
    reaper.start_recording()
    try:
        time.sleep(PREROLL)
        _play_until_end(player, track, device)
    finally:
        player.pause()
        reaper.stop_recording()
        reaper.remove_recorded_item()
    raw = wait_for_new_wav(record_dir, before)

    info = read_info(raw)
    search_from = int(PREROLL / 2 * info.sample_rate)  # nothing before play belongs to the song
    start = first_sound_frame(info, threshold_db, from_frame=search_from)
    if start == search_from:
        print("    warning: sound already present before playback started")
    elif first_sound_frame(info, threshold_db) < search_from:
        print("    warning: unexpected sound before playback (ignored)")
    end = start + round(track.duration * info.sample_rate)
    if end > info.n_frames:
        raise RuntimeError(f"Recording too short, kept raw file {raw}")
    write_slice(info, start, end, out)
    raw.unlink()
    return {"lead_in": round(start / info.sample_rate, 3)}


def first_difference(a: Path, b: Path, chunk: int = 1 << 20) -> int | None:
    """Byte offset of the first difference between two files, or None."""
    with open(a, "rb") as fa, open(b, "rb") as fb:
        pos = 0
        while True:
            x, y = fa.read(chunk), fb.read(chunk)
            if x != y:
                n = min(len(x), len(y))
                k = next((i for i in range(n) if x[i] != y[i]), n)
                return pos + k
            if not x:
                return None
            pos += len(x)


def pick_identical(takes: list[Path]) -> Path | None:
    """First take that is byte-identical to another one."""
    for a, b in itertools.combinations(takes, 2):
        if filecmp.cmp(a, b, shallow=False):
            return a
    return None


def record_track(track: Track, out: Path, verify: bool, **kwargs) -> dict | None:
    """Records track into out. With verify, until two takes are identical (max 3).

    Returns extra manifest fields, or None if verification failed.
    """
    if not verify:
        return record_take(track, out, **kwargs)
    takes: list[Path] = []
    try:
        while len(takes) < MAX_TAKES:
            take = out.with_name(f"{out.stem}.take{len(takes) + 1}.wav")
            print(f"    take {len(takes) + 1}")
            extra = record_take(track, take, **kwargs)
            for i, other in enumerate(takes, 1):
                diff = first_difference(other, take)
                if diff is not None:
                    info = read_info(take)
                    t = max(diff - info.data_offset, 0) // info.block_align / info.sample_rate
                    print(f"    differs from take {i} at {t:.3f} s")
            takes.append(take)
            if (match := pick_identical(takes)):
                match.replace(out)
                return {**extra, "verified": True, "takes": len(takes)}
        print(f"    warning: no two of {MAX_TAKES} takes identical, skipped")
        return None
    finally:
        for t in takes:
            t.unlink(missing_ok=True)
