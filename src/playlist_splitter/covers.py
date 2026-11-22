"""Album covers via Spotify oEmbed (no login)."""

import json
import urllib.parse
import urllib.request
from pathlib import Path

OEMBED_URL = "https://open.spotify.com/oembed?url={}"
SIZE_300, SIZE_640 = "ab67616d00001e02", "ab67616d0000b273"  # Spotify image id prefixes


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def cover_url(track_id: str) -> str:
    """640x640 cover URL (falls back to oEmbed's 300x300 if the id differs)."""
    track = urllib.parse.quote(f"https://open.spotify.com/track/{track_id}", safe="")
    thumb = json.loads(_get(OEMBED_URL.format(track)))["thumbnail_url"]
    return thumb.replace(SIZE_300, SIZE_640)


def fetch_cover(track_id: str, out: Path) -> None:
    out.write_bytes(_get(cover_url(track_id)))
