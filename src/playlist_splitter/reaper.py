"""Reaper remote control via its web interface, called through Windows curl.exe."""

import subprocess
import time
from importlib.resources import files
from pathlib import Path

# Reaper action IDs
UNSELECT_ALL_ITEMS = 40289
GO_TO_END = 40043
RECORD = 1013
STOP = 1016
REMOVE_SELECTED_ITEMS = 40006
TOGGLE_METRONOME = 40364

ARMED_FLAG = 64
STEREO_INPUT_FLAG = 1024
TRACK_NAME = "playlist_recorder AES"
PROJECT_NAME = "playlist_recorder.rpp"
SCRIPT_NAME = "playlist_recorder_tab.lua"


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

    def tracks(self) -> list[tuple[str, bool]]:
        """(name, armed) of all tracks except master."""
        lines = self._call("NTRACK;TRACK").splitlines()
        return [(f[2], bool(int(f[3]) & ARMED_FLAG))
                for f in (ln.split("\t") for ln in lines)
                if f[0] == "TRACK" and f[1] != "0"]

    def open_recorder_tab(self, command_id: str) -> None:
        """Run the tab script, then check that the recorder project is active."""
        self._call(command_id)
        deadline = time.monotonic() + 15
        while self.tracks() != [(TRACK_NAME, True)]:
            if time.monotonic() > deadline:
                raise RuntimeError("Reaper recorder project is not the active tab")
            time.sleep(0.5)

    def command_state(self, command: int) -> int:
        """Toggle state of an action: 1 on, 0 off, -1 not a toggle."""
        return int(self._call(f"GET/{command}").split("\t")[2])

    def metronome_off(self) -> None:
        if self.command_state(TOGGLE_METRONOME) == 1:
            self._call(TOGGLE_METRONOME)
        if self.command_state(TOGGLE_METRONOME) != 0:
            raise RuntimeError("Could not switch off the Reaper metronome")

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


def _wslpath(option: str, path: str) -> str:
    return subprocess.run(["wslpath", option, path], capture_output=True, text=True,
                          check=True).stdout.strip()


def resource_dir() -> Path:
    """Reaper's resource folder (%APPDATA%\\REAPER) as seen from WSL."""
    appdata = subprocess.run(["cmd.exe", "/c", "echo %APPDATA%"], cwd="/mnt/c",
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             text=True, errors="replace", check=True).stdout.strip()
    return Path(_wslpath("-u", appdata)) / "REAPER"


def install(record_dir: Path, first_input: int) -> Path:
    """Writes the recorder project (into record_dir) and the tab script; returns the script."""
    record_dir.mkdir(parents=True, exist_ok=True)
    project = record_dir / PROJECT_NAME
    src = files("playlist_splitter") / "reaper_files"
    project.write_text((src / PROJECT_NAME).read_text().format(
        record_path=_wslpath("-w", str(record_dir)), track_name=TRACK_NAME,
        rec_input=STEREO_INPUT_FLAG + first_input - 1), newline="\r\n")
    script = resource_dir() / "Scripts" / SCRIPT_NAME
    script.write_text((src / SCRIPT_NAME).read_text().replace(
        "{project_path}", _wslpath("-w", str(project))), newline="\r\n")
    return script


def tab_command_id() -> str:
    """Action ID of the loaded tab script, from reaper-kb.ini."""
    kb = resource_dir() / "reaper-kb.ini"
    for line in kb.read_text(errors="replace").splitlines():
        parts = line.split()
        if line.startswith("SCR ") and parts[2] == "0" and line.endswith(SCRIPT_NAME):
            return "_" + parts[3]
    raise SystemExit(f"Load {SCRIPT_NAME} in Reaper first: run playlist-reaper-setup.")
