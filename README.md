# spotify-playlist-splitter

Splits playlist recordings into one WAV per song. PCM data is byte-copied, never re-encoded.

## Record song by song (Reaper + Spotify, resumable)

```
uv run playlist-recorder "https://open.spotify.com/playlist/<id>" [output] [--limit N]
```

- Needs: Reaper running, stopped, one armed track (web interface on port 8080);
  Spotify Premium, desktop app open; a Spotify developer app (redirect URI
  `http://127.0.0.1:8888/callback`), its client ID via `--client-id` or `SPOTIFY_CLIENT_ID` (first run only).
- Spotify: loudness normalization off, volume 100 %.
- Recorded songs are listed in `<output>/<playlist name>_<id>_metadata.json`; only missing songs are recorded.

## Split an existing recording

```
uv run playlist-splitter recording.wav "https://open.spotify.com/playlist/<id>" [output] [--dry-run]
```

- Each cut is placed at the quietest point within `--window` seconds of the expected boundary.
- Record without crossfade/gapless playback for clean cuts.

Album covers (640px JPEG) are saved next to each WAV; skip with `--no-covers`.
