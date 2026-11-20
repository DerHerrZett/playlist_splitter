"""Command line interface."""

import argparse
from pathlib import Path

from playlist_splitter.analysis import compute_envelope
from playlist_splitter.boundaries import find_cuts
from playlist_splitter.covers import download_cover
from playlist_splitter.spotify import fetch_tracks
from playlist_splitter.wavfile import read_info, write_slice


def _fmt(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f"{int(m) // 60}:{int(m) % 60:02d}:{s:06.3f}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Split a WAV playlist recording into songs.")
    p.add_argument("wav", type=Path, help="input WAV recording")
    p.add_argument("playlist", help="Spotify playlist link")
    p.add_argument("output", type=Path, nargs="?", default=Path("output"))
    p.add_argument("--window", type=float, default=10.0,
                   help="search +-seconds around the expected cut (default 10)")
    p.add_argument("--threshold", type=float, default=-60.0,
                   help="silence threshold in dBFS for lead-in/out (default -60)")
    p.add_argument("--dry-run", action="store_true", help="only print the cuts")
    p.add_argument("--no-covers", action="store_true", help="skip album cover download")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    info = read_info(args.wav)
    tracks = fetch_tracks(args.playlist)
    durations = [t.duration for t in tracks]
    print(f"Recording {_fmt(info.duration)}, tracks total {_fmt(sum(durations))}")

    cuts = find_cuts(compute_envelope(info), durations, args.window, args.threshold)

    args.output.mkdir(parents=True, exist_ok=True)
    for i, track in enumerate(tracks):
        a, b = cuts[i], cuts[i + 1]
        print(f"{i + 1:3d} {_fmt(a.seconds)} - {_fmt(b.seconds)}  "
              f"Δ{b.seconds - b.expected:+6.2f}s {b.level_db:6.1f}dB  {track.filename}")
        if not args.dry_run:
            write_slice(info, round(a.seconds * info.sample_rate),
                        round(b.seconds * info.sample_rate),
                        args.output / track.filename)
            if not args.no_covers and track.track_id:
                try:
                    download_cover(track.track_id, args.output / f"{track.stem}.jpg")
                except OSError as e:
                    print(f"    cover download failed: {e}")
