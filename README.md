# spotify-playlist-splitter

Splits a WAV playlist recording into one WAV per song. PCM data is byte-copied, never re-encoded.

```
uv run playlist-splitter input/spotify_playlist.wav "https://open.spotify.com/playlist/<id>" [output] [--dry-run]
```

- Track names and durations come from the Spotify playlist link.
- Each cut is placed at the quietest point within `--window` seconds of the expected boundary.
- Record without crossfade/gapless playback for clean cuts.
