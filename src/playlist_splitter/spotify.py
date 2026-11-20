"""Track list from a Spotify playlist link (public embed page, no login)."""

import json
import re
import urllib.request
from dataclasses import dataclass

EMBED_URL = "https://open.spotify.com/embed/playlist/{}"
USER_AGENT = "Mozilla/5.0"
ARTIST_SEPARATOR = ",\xa0"  # Spotify joins artists with comma + no-break space


@dataclass(frozen=True)
class Track:
    title: str
    artist: str  # main artist
    duration: float  # seconds
    track_id: str = ""

    @property
    def stem(self) -> str:
        """Safe file name stem 'Artist - Title'."""
        name = f"{self.artist} - {self.title}"
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")

    @property
    def filename(self) -> str:
        return f"{self.stem}.wav"


def playlist_id(link: str) -> str:
    """Playlist ID from a link or spotify: URI."""
    m = re.search(r"playlist[/:]([A-Za-z0-9]{22})", link)
    if not m:
        raise ValueError(f"No Spotify playlist ID in {link!r}")
    return m.group(1)


def parse_embed(html: str) -> list[Track]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise ValueError("Unexpected Spotify page format (no __NEXT_DATA__)")
    entity = json.loads(m.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
    return [
        Track(
            title=t["title"].strip(),
            artist=t["subtitle"].split(ARTIST_SEPARATOR)[0].strip(),
            duration=t["duration"] / 1000,
            track_id=t.get("uri", "").rsplit(":", 1)[-1],
        )
        for t in entity["trackList"]
    ]


def fetch_tracks(link: str) -> list[Track]:
    url = EMBED_URL.format(playlist_id(link))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return parse_embed(resp.read().decode("utf-8"))
