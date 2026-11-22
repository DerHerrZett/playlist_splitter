"""Record one song: Reaper records while Spotify plays it, then trim."""

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


def record_track(track: Track, out: Path, reaper: Reaper, player: Player,
                 device: str, record_dir: Path, threshold_db: float) -> dict:
    """Records track into out; returns extra manifest fields."""
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
