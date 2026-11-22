from playlist_splitter.recorder import pick_identical


def test_pick_identical(tmp_path):
    a, b, c = (tmp_path / n for n in "abc")
    a.write_bytes(b"1"), b.write_bytes(b"2"), c.write_bytes(b"2")
    assert pick_identical([a, b]) is None and pick_identical([a, b, c]) == b


def test_first_difference(tmp_path):
    from playlist_splitter.recorder import first_difference

    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"x" * 5000), b.write_bytes(b"x" * 4321 + b"y" * 679)
    assert first_difference(a, b, chunk=1000) == 4321 and first_difference(a, a) is None
