"""Spotify Web API playback control (OAuth PKCE, token cached locally)."""

import base64
import hashlib
import http.server
import json
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from playlist_splitter.playlist import Album

API = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
REDIRECT_PORT = 8888
REDIRECT_URI = f"http://127.0.0.1:{REDIRECT_PORT}/callback"
SCOPES = "user-read-playback-state user-modify-playback-state"
TOKEN_FILE = Path.home() / ".cache" / "playlist_splitter" / "token.json"


@dataclass(frozen=True)
class PlaybackState:
    is_playing: bool
    track_id: str | None
    progress: float  # seconds


def _post_token(params: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data), timeout=30) as r:
        return json.load(r)


def _wait_for_code(state: str) -> str:
    result: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Spotify login done. You can close this tab.")

        def log_message(self, *args):
            pass

    with http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), Handler) as server:
        while "code" not in result and "error" not in result:
            server.handle_request()
    if result.get("state") != state or "code" not in result:
        raise RuntimeError(f"Spotify login failed: {result.get('error', 'state mismatch')}")
    return result["code"]


def login(client_id: str) -> dict:
    """Interactive browser login; returns the token dict."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "response_type": "code", "redirect_uri": REDIRECT_URI,
        "code_challenge_method": "S256", "code_challenge": challenge,
        "scope": SCOPES, "state": state,
    })
    print(f"Log in to Spotify in your browser:\n{url}")
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", f"Start-Process '{url}'"],
                   capture_output=True)
    token = _post_token({
        "grant_type": "authorization_code", "code": _wait_for_code(state),
        "redirect_uri": REDIRECT_URI, "client_id": client_id, "code_verifier": verifier,
    })
    return token


class Player:
    def __init__(self, client_id: str | None = None, token_file: Path = TOKEN_FILE):
        self.token_file = token_file
        self._album_discs: dict[str, int] = {}  # album id -> number of discs
        saved = json.loads(token_file.read_text()) if token_file.exists() else {}
        self.client_id = client_id or saved.get("client_id")
        if not self.client_id:
            raise SystemExit("Spotify client ID needed (--client-id or PLAYLIST_CLIENT_ID).")
        if saved.get("client_id") == self.client_id and "refresh_token" in saved:
            self.token = saved
        else:
            self._store(login(self.client_id))

    def _store(self, token: dict) -> None:
        token = {**getattr(self, "token", {}), **token, "client_id": self.client_id,
                 "expires_at": time.time() + token.get("expires_in", 3600) - 60}
        self.token = token
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_file.write_text(json.dumps(token))
        self.token_file.chmod(0o600)

    def _access_token(self) -> str:
        if time.time() > self.token["expires_at"]:
            self._store(_post_token({"grant_type": "refresh_token", "client_id": self.client_id,
                                     "refresh_token": self.token["refresh_token"]}))
        return self.token["access_token"]

    def _request(self, method: str, path: str, body: dict | None = None) -> dict | None:
        req = urllib.request.Request(
            API + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self._access_token()}",
                     "Content-Type": "application/json"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    raw = r.read()
                    try:
                        return json.loads(raw) if raw else None
                    except json.JSONDecodeError:
                        return None  # some endpoints answer with plain text
            except urllib.error.HTTPError as e:
                if e.code == 429 or e.code >= 500:
                    time.sleep(int(e.headers.get("Retry-After", 2 ** attempt)))
                    continue
                raise RuntimeError(f"Spotify {method} {path}: {e.code} {e.read()[:300]!r}")
        raise RuntimeError(f"Spotify {method} {path}: giving up after retries")

    def device_id(self, name: str | None) -> str:
        """ID of the device with this name, or of the active/only computer."""
        devices = (self._request("GET", "/me/player/devices") or {}).get("devices", [])
        if name:
            match = [d for d in devices if d["name"].lower() == name.lower()]
        else:
            match = ([d for d in devices if d["is_active"]]
                     or [d for d in devices if d["type"] == "Computer"])
        if len(match) != 1:
            names = [d["name"] for d in devices]
            raise SystemExit(f"Choose a Spotify device with --device. Available: {names}")
        return match[0]["id"]

    def play_track(self, track_id: str, device: str) -> None:
        q = f"?device_id={device}"
        self._request("PUT", "/me/player/play" + q,
                      {"uris": [f"spotify:track:{track_id}"], "position_ms": 0})
        self._request("PUT", f"/me/player/shuffle?state=false&device_id={device}")
        self._request("PUT", f"/me/player/repeat?state=off&device_id={device}")

    def pause(self) -> None:
        try:
            self._request("PUT", "/me/player/pause")
        except RuntimeError:
            pass  # already paused

    def state(self) -> PlaybackState:
        s = self._request("GET", "/me/player") or {}
        item = s.get("item") or {}
        track_id = (item.get("linked_from") or {}).get("id") or item.get("id")
        return PlaybackState(bool(s.get("is_playing")), track_id,
                             (s.get("progress_ms") or 0) / 1000)

    def album(self, track_id: str) -> Album:
        """Album info of a track (single-track endpoint; batch is not allowed)."""
        t = self._request("GET", f"/tracks/{track_id}")
        a = t["album"]
        discs = self._album_discs
        if a["id"] not in discs:
            total = a.get("total_tracks") or 1
            last = self._request("GET", f"/albums/{a['id']}/tracks?limit=1&offset={total - 1}")
            discs[a["id"]] = max([i["disc_number"] for i in last["items"]] or [1])
        return Album(a["name"], a["artists"][0]["name"], (a.get("release_date") or "")[:4],
                     t["track_number"], t["disc_number"],
                     discs[a["id"]] > 1 or t["disc_number"] > 1)
