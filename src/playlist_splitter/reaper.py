"""Reaper remote control via its web interface, called through Windows curl.exe."""

import subprocess
import time
from pathlib import Path

# Reaper action IDs
UNSELECT_ALL_ITEMS = 40289
GO_TO_END = 40043
RECORD = 1013
STOP = 1016
REMOVE_SELECTED_ITEMS = 40006

ARMED_FLAG = 64


class Reaper:
    def __init__(self, port: int = 8080, curl: str = "curl.exe"):
        self.base = f"http://localhost:{port}/_/"
        self.curl = curl

    def _call(self, *commands: object) -> str:
        url = self.base + ";".join(map(str, commands))
        out = subprocess.run([self.curl, "-s", "-f", "-m", "5", url],
                             capture_output=True, text=True)
        if out.returncode:
            raise RuntimeError(f"Reaper web interface not reachable ({url})")
        return out.stdout

    def transport(self) -> int:
        """0 stopped, 1 playing, 2 paused, 5 recording."""
        return int(self._call("TRANSPORT").split("\t")[1])

    def has_armed_track(self) -> bool:
        lines = self._call("NTRACK;TRACK").splitlines()
        return any(
            int(f[3]) & ARMED_FLAG for f in (ln.split("\t") for ln in lines)
            if f[0] == "TRACK" and f[1] != "0"
        )

    def start_recording(self) -> None:
        self._call(UNSELECT_ALL_ITEMS, GO_TO_END, RECORD)

    def stop_recording(self) -> None:
        self._call(STOP)

    def remove_recorded_item(self) -> None:
        """Removes the selected items, i.e. the item just recorded."""
        self._call(REMOVE_SELECTED_ITEMS)


def wait_for_new_wav(record_dir: Path, before: set[Path], timeout: float = 30) -> Path:
    """The single new WAV in record_dir, once its size is stable."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        new = set(record_dir.glob("*.wav")) - before
        if len(new) > 1:
            raise RuntimeError(f"Several new recordings: {sorted(new)}")
        if new:
            path = new.pop()
            size = path.stat().st_size
            time.sleep(1.0)
            if path.stat().st_size == size and size > 0:
                return path
        else:
            time.sleep(0.5)
    raise RuntimeError(f"No new recording appeared in {record_dir}")
