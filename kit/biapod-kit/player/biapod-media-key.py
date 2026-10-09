#!/usr/bin/env python3
"""Route PinePhone hardware and wired-headset media keys to MPD."""

import sys

from mpdclient import MPD, first


def main(action):
    mpd = MPD()
    if action in ("volume-up", "volume-down"):
        current = int(first(mpd.command("status"), "volume", "0"))
        delta = 1 if action == "volume-up" else -1
        mpd.command("setvol", max(0, min(100, current + delta)))
    elif action == "toggle":
        state = first(mpd.command("status"), "state")
        if state == "play":
            mpd.command("pause", 1)
        elif state == "pause":
            mpd.command("pause", 0)
        else:
            mpd.command("play")
    elif action in ("next", "previous", "stop"):
        mpd.command(action)
    else:
        raise ValueError(f"Comando sconosciuto: {action}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Uso: biapod-media-key.py <azione>")
    main(sys.argv[1])
