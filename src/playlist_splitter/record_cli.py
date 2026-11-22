"""Command line interface: record a playlist song by song (resumable)."""

import argparse
import os
from pathlib import Path

from playlist_splitter.covers import download_cover
from playlist_splitter.manifest import Manifest
from playlist_splitter.reaper import Reaper
from playlist_splitter.recorder import record_track, wait_until_paused
from playlist_splitter.spotify import fetch_playlist
from playlist_splitter.spotify_player import SpotifyPlayer


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record a Spotify playlist song by song via Reaper.")
    p.add_argument("playlist", help="Spotify playlist link")
    p.add_argument("output", type=Path, nargs="?", default=Path("output"))
    p.add_argument("--record-dir", type=Path, default=Path("/mnt/d/Reaper_Temp"),
                   help="Reaper's recording folder as seen from here")
    p.add_argument("--reaper-port", type=int, default=8080)
    p.add_argument("--device", help="Spotify device name (default: active computer)")
    p.add_argument("--client-id", default=os.environ.get("SPOTIFY_CLIENT_ID"))
    p.add_argument("--threshold", type=float, default=-100.0,
                   help="dBFS above which the song is considered started (default -100)")
    p.add_argument("--limit", type=int, help="record at most this many songs")
    p.add_argument("--no-covers", action="store_true", help="skip album cover download")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    playlist = fetch_playlist(args.playlist)
    manifest = Manifest(args.output, playlist)
    todo = [(i, t) for i, t in enumerate(playlist.tracks, 1) if not manifest.is_recorded(t)]
    print(f"{playlist.name}: {len(playlist.tracks)} songs, {len(todo)} to record")
    todo = todo[: args.limit]
    if not todo:
        return

    reaper = Reaper(args.reaper_port)
    if reaper.transport() != 0 or not reaper.has_armed_track():
        raise SystemExit("Reaper must be stopped with one armed track.")
    player = SpotifyPlayer(args.client_id)
    device = player.device_id(args.device)
    wait_until_paused(player)
    args.output.mkdir(parents=True, exist_ok=True)

    for n, (pos, track) in enumerate(todo, 1):
        print(f"[{n}/{len(todo)}] #{pos} {track.artist} - {track.title} "
              f"({int(track.duration // 60)}:{int(track.duration % 60):02d})")
        extra = record_track(track, args.output / track.filename, reaper, player,
                             device, args.record_dir, args.threshold)
        if not args.no_covers:
            try:
                download_cover(track.track_id, args.output / f"{track.stem}.jpg")
            except OSError as e:
                print(f"    cover download failed: {e}")
        manifest.add(track, pos, **extra)
