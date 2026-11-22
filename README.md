# playlist-splitter

Records a playlist song by song via Reaper into one WAV per song.
The recorded PCM data is trimmed by byte copy, never re-encoded.

## Output modes (`--mode`)

- `playlist` (default): `<output>/<playlist name>_<id>/Artist - Title.wav` (+ `.jpg` cover per song).
- `album`: `<output>/<Album artist> - <Album> (<Year>)/06 - Artist - Title.wav` (`1-06 - …` for multi-disc), one `cover.jpg` per album.

Each playlist gets `<playlist name>_<id>_metadata.json` (in the playlist folder, or in `<output>` in album mode).

## Usage

One-time setup:

```
uv run playlist-reaper-setup [--input 3]
```

Then load the printed `playlist_recorder_tab.lua` in Reaper (Actions > New action > Load ReaScript).
It opens a dedicated recorder project tab (recording into `D:\Reaper_Temp\playlist_recorder`).

```
uv run playlist-recorder "https://open.spotify.com/playlist/<id>" [output] [--mode album] [--limit N]
```

- Needs Reaper running (web interface on port 8080), Spotify Premium with the desktop app open,
  and a Spotify developer app (redirect URI `http://127.0.0.1:8888/callback`); pass its client ID
  once via `--client-id` or `PLAYLIST_CLIENT_ID`.
- Spotify: loudness normalization off, volume 100 %. For best results, download the playlist
  in Spotify first (quality "Very high"): streaming can cause short dropouts. Don't switch Reaper tabs during a run.
- `--verify`: record each song until two takes are bit-identical (max 3; off by default).
- Only songs missing from the metadata file (or, in album mode, from the album folder) are recorded.
