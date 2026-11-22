from playlist_splitter.manifest import Manifest
from playlist_splitter.playlist import Playlist, Track

T = Track("Song", "Band", 10.0, "id1")


def test_record_and_rename(tmp_path):
    m = Manifest(tmp_path, Playlist("PID", "Old", [T]))
    assert not m.is_recorded(T)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / T.filename).write_bytes(b"x")
    m.add(T, 1, tmp_path / "sub" / T.filename, lead_in=1.0)
    m2 = Manifest(tmp_path, Playlist("PID", "New/Name", [T]))
    assert m2.path.name == "New_Name_PID_metadata.json" and m2.is_recorded(T)
    assert m2.entry(T)["file"] == "sub/Band - Song.wav"
    assert not (tmp_path / "Old_PID_metadata.json").exists()
