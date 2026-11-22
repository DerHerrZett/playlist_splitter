"""Per-playlist record of recorded songs: <name>_<id>_metadata.json."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from playlist_splitter.playlist import Playlist, Track, safe_name


class Manifest:
    def __init__(self, directory: Path, playlist: Playlist):
        self.dir = directory
        self.path = directory / f"{safe_name(playlist.name)}_{playlist.id}_metadata.json"
        existing = sorted(directory.glob(f"*_{playlist.id}_metadata.json"))
        if existing and existing[0] != self.path:
            existing[0].rename(self.path)  # playlist was renamed
        self.data = (json.loads(self.path.read_text(encoding="utf-8"))
                     if self.path.exists() else {"tracks": {}})
        self.data.update(playlist_id=playlist.id, playlist_name=playlist.name)

    def entry(self, track: Track) -> dict | None:
        return self.data["tracks"].get(track.track_id)

    def is_recorded(self, track: Track) -> bool:
        entry = self.entry(track)
        return bool(entry) and (self.dir / entry["file"]).exists()

    def add(self, track: Track, position: int, file: Path, **extra) -> None:
        self.data["tracks"][track.track_id] = {
            "position": position, "title": track.title, "artist": track.artist,
            "duration": track.duration,
            "file": Path(os.path.relpath(file, self.dir)).as_posix(),
            "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **extra,
        }
        self.save()

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
