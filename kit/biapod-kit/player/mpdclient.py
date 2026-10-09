"""Small MPD protocol client; keeps the player UI dependency-free."""

import json
import socket


class MPD:
    def __init__(self, host="127.0.0.1", port=6600):
        self.host = host
        self.port = port

    def command(self, name, *args):
        parts = [name, *(json.dumps(str(arg), ensure_ascii=False) for arg in args)]
        with socket.create_connection((self.host, self.port), timeout=2) as conn:
            stream = conn.makefile("rwb")
            greeting = stream.readline().decode("utf-8", "replace")
            if not greeting.startswith("OK MPD "):
                raise RuntimeError("Risposta MPD non valida")
            stream.write((" ".join(parts) + "\n").encode("utf-8"))
            stream.flush()
            rows = []
            while True:
                line = stream.readline().decode("utf-8", "replace").rstrip("\r\n")
                if line == "OK":
                    return rows
                if not line or line.startswith("ACK "):
                    raise RuntimeError(line or "MPD ha chiuso la connessione")
                key, sep, value = line.partition(": ")
                if sep:
                    rows.append((key, value))

    def command_list(self, commands):
        """Send queue edits together, without one connection per song directory."""
        with socket.create_connection((self.host, self.port), timeout=5) as conn:
            conn.settimeout(30)
            stream = conn.makefile("rwb")
            greeting = stream.readline().decode("utf-8", "replace")
            if not greeting.startswith("OK MPD "):
                raise RuntimeError("Risposta MPD non valida")
            lines = ["command_list_begin"]
            for name, *args in commands:
                lines.append(" ".join(
                    [name, *(json.dumps(str(arg), ensure_ascii=False) for arg in args)]))
            lines.append("command_list_end")
            stream.write(("\n".join(lines) + "\n").encode("utf-8"))
            stream.flush()
            while True:
                line = stream.readline().decode("utf-8", "replace").rstrip("\r\n")
                if line == "OK":
                    return
                if not line or line.startswith("ACK "):
                    raise RuntimeError(line or "MPD ha chiuso la connessione")


def first(rows, key, default=""):
    return next((value for field, value in rows if field.lower() == key.lower()), default)


def grouped(rows, start_key):
    result = []
    for key, value in rows:
        if key.lower() == start_key.lower():
            result.append({key.lower(): value})
        elif result:
            result[-1][key.lower()] = value
    return result
