"""Output layout: playlist mode (one folder per playlist) or album mode (one per album)."""

from dataclasses import asdict
from pathlib import Path
from typing import Callable

from playlist_splitter.covers import fetch_cover
from playlist_splitter.manifest import Manifest
from playlist_splitter.playlist import Album, Playlist, Track, safe_name

MODES = ("playlist", "album")


class Library:
    def __init__(self, output: Path, playlist: Playlist, mode: str,
                 album_lookup: Callable[[str], Album] | None = None):
        self.mode = mode
        if mode == "playlist":
            self.root = output / f"{safe_name(playlist.name)}_{playlist.id}"
            old = [d for d in output.glob(f"*_{playlist.id}") if d.is_dir()]
            if old and not self.root.exists():
                old[0].rename(self.root)  # playlist was renamed
        else:
            self.root = output
        self.manifest = Manifest(self.root, playlist)
        self.albums: dict[str, Album] = {}
        if mode == "album":
            for t in playlist.tracks:
                cached = (self.manifest.entry(t) or {}).get("album")
                self.albums[t.track_id] = Album(**cached) if cached else album_lookup(t.track_id)

    def song_path(self, track: Track) -> Path:
        if self.mode == "playlist":
            return self.root / track.filename
        album = self.albums[track.track_id]
        return self.root / album.folder / album.song_filename(track)

    def is_done(self, track: Track) -> bool:
        """Recorded for this playlist, or (album mode) already in its album folder."""
        return self.manifest.is_recorded(track) or (
            self.mode == "album" and self.song_path(track).exists())

    def save_cover(self, track: Track) -> None:
        song = self.song_path(track)
        cover = song.with_suffix(".jpg") if self.mode == "playlist" else song.parent / "cover.jpg"
        if self.mode == "album" and cover.exists():
            return
        try:
            fetch_cover(track.track_id, cover)
        except OSError as e:
            print(f"    cover failed: {e}")

    def add(self, track: Track, position: int, **extra) -> None:
        album = self.albums.get(track.track_id)
        if album:
            extra["album"] = asdict(album)
        self.manifest.add(track, position, self.song_path(track), **extra)
