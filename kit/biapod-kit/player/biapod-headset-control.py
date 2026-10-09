#!/usr/bin/env python3
"""Handle single, double and triple presses of a wired headset button."""

from pathlib import Path
import select
import struct
import subprocess
import sys
import time


MEDIA_KEY = 164  # Linux KEY_PLAYPAUSE, reported by PinePhone codec-jack.
CLICK_WINDOW = 0.38
EVENT = struct.Struct("llHHi")


def headset_device():
    for event in Path("/sys/class/input").glob("event*"):
        try:
            name = (event / "device/name").read_text().strip()
        except OSError:
            continue
        if "codec-jack" in name:
            return Path("/dev/input") / event.name
    return None


def media_action(clicks):
    action = "toggle" if clicks == 1 else "next" if clicks == 2 else "previous"
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("biapod-media-key.py")), action],
        timeout=4, check=False,
    )


def listen(device):
    clicks = 0
    deadline = None
    with open(device, "rb", buffering=0) as stream:
        while True:
            timeout = None if deadline is None else max(0, deadline - time.monotonic())
            ready, _, _ = select.select([stream], [], [], timeout)
            if not ready:
                try:
                    media_action(clicks)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                clicks, deadline = 0, None
                continue
            packet = stream.read(EVENT.size)
            if len(packet) != EVENT.size:
                raise OSError("Headset input ended")
            _seconds, _microseconds, event_type, code, value = EVENT.unpack(packet)
            if event_type == 1 and code == MEDIA_KEY and value == 1:
                clicks = min(3, clicks + 1)
                deadline = time.monotonic() + CLICK_WINDOW


def main():
    while True:
        device = headset_device()
        if device:
            try:
                listen(device)
            except OSError:
                pass
        time.sleep(2)


if __name__ == "__main__":
    main()
