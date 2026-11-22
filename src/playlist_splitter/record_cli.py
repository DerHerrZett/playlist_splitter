"""Command line interface: record a playlist song by song (resumable)."""

import argparse
import os
from pathlib import Path

from playlist_splitter import reaper
from playlist_splitter.library import MODES, Library
from playlist_splitter.recorder import record_track, wait_until_paused
from playlist_splitter.playlist import Playlist, fetch_playlist
from playlist_splitter.player import Player

DEFAULT_RECORD_DIR = Path("/mnt/d/Reaper_Temp/playlist_recorder")


def add_output_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("playlist", help="Spotify playlist link")
    p.add_argument("output", type=Path, nargs="?", default=Path("output"))
    p.add_argument("--mode", choices=MODES, default="playlist",
                   help="playlist: one folder per playlist; album: one folder per album")
    p.add_argument("--client-id", default=os.environ.get("PLAYLIST_CLIENT_ID"),
                   help="Spotify app client ID (first login only)")
    p.add_argument("--no-covers", action="store_true", help="skip album covers")


def open_library(args: argparse.Namespace, playlist: Playlist,
                 player: Player) -> Library:
    return Library(args.output, playlist, args.mode, player.album)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Record a playlist song by song via Reaper.")
    add_output_args(p)
    p.add_argument("--record-dir", type=Path, default=DEFAULT_RECORD_DIR,
                   help="recorder project's recording folder as seen from here")
    p.add_argument("--reaper-port", type=int, default=8080)
    p.add_argument("--device", help="Spotify device name (default: active computer)")
    p.add_argument("--threshold", type=float, default=-100.0,
                   help="dBFS above which the song is considered started (default -100)")
    p.add_argument("--limit", type=int, help="record at most this many songs")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    playlist = fetch_playlist(args.playlist)
    command_id = reaper.tab_command_id()
    player = Player(args.client_id)
    library = open_library(args, playlist, player)

    todo = []
    for pos, track in enumerate(playlist.tracks, 1):
        if not library.is_done(track):
            todo.append((pos, track))
        elif not library.manifest.is_recorded(track):
            library.add(track, pos, reused=True)  # album mode: already in album folder
    print(f"{playlist.name}: {len(playlist.tracks)} songs, {len(todo)} to record")
    todo = todo[: args.limit]
    if not todo:
        return

    daw = reaper.Reaper(args.reaper_port)
    daw.open_recorder_tab(command_id)
    daw.metronome_off()
    if daw.transport() != 0:
        raise SystemExit("Reaper must be stopped.")
    device = player.device_id(args.device)
    wait_until_paused(player)

    for n, (pos, track) in enumerate(todo, 1):
        out = library.song_path(track)
        print(f"[{n}/{len(todo)}] #{pos} {out.relative_to(args.output)} "
              f"({int(track.duration // 60)}:{int(track.duration % 60):02d})")
        out.parent.mkdir(parents=True, exist_ok=True)
        extra = record_track(track, out, daw, player, device, args.record_dir, args.threshold)
        if not args.no_covers:
            library.save_cover(track)
        library.add(track, pos, **extra)


def setup_main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Install the Reaper recorder project and tab script.")
    p.add_argument("--record-dir", type=Path, default=DEFAULT_RECORD_DIR)
    p.add_argument("--input", type=int, default=3,
                   help="first channel of the stereo input pair (default 3 = input 3/4)")
    args = p.parse_args(argv)
    script = reaper.install(args.record_dir, args.input)
    print(f"Project: {args.record_dir / reaper.PROJECT_NAME}\nScript:  {script}")
    try:
        print(f"Script already loaded in Reaper as action {reaper.tab_command_id()}.")
    except SystemExit:
        print("Now load the script once in Reaper: Actions > Show action list > "
              "New action > Load ReaScript... > select the script above.")
