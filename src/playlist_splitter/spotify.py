"""Track list from a Spotify playlist link (public embed page, no login)."""

import json
import re
import urllib.request
from dataclasses import dataclass

EMBED_URL = "https://open.spotify.com/embed/playlist/{}"
USER_AGENT = "Mozilla/5.0"
ARTIST_SEPARATOR = ",\xa0"  # Spotify joins artists with comma + no-break space


def safe_name(name: str) -> str:
    """Name usable as a file name on Windows and Linux."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")


@dataclass(frozen=True)
class Track:
    title: str
    artist: str  # main artist
    duration: float  # seconds
    track_id: str = ""

    @property
    def stem(self) -> str:
        """Safe file name stem 'Artist - Title'."""
        return safe_name(f"{self.artist} - {self.title}")

    @property
    def filename(self) -> str:
        return f"{self.stem}.wav"


def playlist_id(link: str) -> str:
    """Playlist ID from a link or spotify: URI."""
    m = re.search(r"playlist[/:]([A-Za-z0-9]{22})", link)
    if not m:
        raise ValueError(f"No Spotify playlist ID in {link!r}")
    return m.group(1)


@dataclass(frozen=True)
class Playlist:
    id: str
    name: str
    tracks: list[Track]


def _entity(html: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("Unexpected Spotify page format (no __NEXT_DATA__)")
    return json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]


def parse_embed(html: str) -> list[Track]:
    entity = _entity(html)
    return [
        Track(
            title=t["title"].strip(),
            artist=t["subtitle"].split(ARTIST_SEPARATOR)[0].strip(),
            duration=t["duration"] / 1000,
            track_id=t.get("uri", "").rsplit(":", 1)[-1],
        )
        for t in entity["trackList"]
    ]


def fetch_playlist(link: str) -> Playlist:
    pid = playlist_id(link)
    req = urllib.request.Request(EMBED_URL.format(pid), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")
    return Playlist(pid, _entity(html).get("name", ""), parse_embed(html))


def fetch_tracks(link: str) -> list[Track]:
    return fetch_playlist(link).tracks
