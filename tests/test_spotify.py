import json

from playlist_splitter.spotify import parse_embed, playlist_id

PID = "62vu4Mn0HlwBJAyokriK4B"


def test_playlist_id():
    assert playlist_id(f"https://open.spotify.com/playlist/{PID}?si=x") == PID
    assert playlist_id(f"spotify:playlist:{PID}") == PID


def test_parse_embed():
    entity = {"trackList": [{"title": "A/B", "subtitle": "X,\xa0Y", "duration": 1500,
                             "uri": "spotify:track:abc"}]}
    data = {"props": {"pageProps": {"state": {"data": {"entity": entity}}}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'
    [t] = parse_embed(html)
    assert (t.artist, t.duration, t.filename, t.track_id) == ("X", 1.5, "X - A_B.wav", "abc")
