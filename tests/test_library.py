from playlist_splitter.library import Library
from playlist_splitter.playlist import Album, Playlist, Track

T = Track("Song", "Band", 10.0, "id1")
A = Album("Best Of", "Band", "1999", 6, 2, True)


def test_playlist_mode_and_rename(tmp_path):
    (tmp_path / "Old_PID").mkdir()
    lib = Library(tmp_path, Playlist("PID", "New", [T]), "playlist")
    assert lib.song_path(T) == tmp_path / "New_PID" / "Band - Song.wav"
    assert (tmp_path / "New_PID").is_dir() and not (tmp_path / "Old_PID").exists()


def test_album_mode_reuses_existing_file(tmp_path):
    lib = Library(tmp_path, Playlist("PID", "P", [T]), "album", lambda _: A)
    path = lib.song_path(T)
    assert path == tmp_path / "Band - Best Of (1999)" / "2-06 - Band - Song.wav"
    assert not lib.is_done(T)
    path.parent.mkdir()
    path.write_bytes(b"x")
    assert lib.is_done(T)
    lib.add(T, 1)
    lib2 = Library(tmp_path, Playlist("PID", "P", [T]), "album", None)  # album from manifest
    assert lib2.song_path(T) == path
