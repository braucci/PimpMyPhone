"""Find the albums and artwork in BiaPod's local music directory."""

import os
from pathlib import Path

AUDIO_SUFFIXES = {".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus", ".wav"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
PREFERRED_COVERS = ("cover", "folder", "front", "album")


def _cover_in(directory):
    try:
        images = [path for path in directory.iterdir()
                  if path.is_file() and path.suffix.casefold() in IMAGE_SUFFIXES
                  and not path.name.startswith(".")]
    except OSError:
        return None
    for stem in PREFERRED_COVERS:
        for image in images:
            if image.stem.casefold() == stem:
                return image
    return sorted(images, key=lambda path: path.name.casefold())[0] if images else None


def find_cover(album_dir):
    cover = _cover_in(album_dir)
    if cover:
        return cover
    try:
        children = [path for path in album_dir.iterdir() if path.is_dir()]
    except OSError:
        return None
    for child in sorted(children, key=lambda path: path.name.casefold()):
        cover = _cover_in(child)
        if cover:
            return cover
    return None


def scan_music(root):
    root = Path(root)
    albums = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not name.startswith(".")
                   and not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if name.startswith(".") or path.suffix.casefold() not in AUDIO_SUFFIXES:
                continue
            relative = path.relative_to(root)
            if len(relative.parts) >= 3:
                album_parts = relative.parts[:2]
                artist, title = album_parts
            elif len(relative.parts) == 2:
                album_parts = relative.parts[:1]
                artist, title = "Artista sconosciuto", album_parts[0]
            else:
                album_parts = ()
                artist, title = "Artista sconosciuto", "Brani senza album"
            uri = "/".join(album_parts)
            album = albums.setdefault(uri, {"artist": artist, "title": title,
                                            "uri": uri, "count": 0, "cover": None})
            album["count"] += 1
    for album in albums.values():
        album_dir = root / album["uri"]
        cover = find_cover(album_dir)
        if cover:
            album["cover"] = str(cover)
    return sorted(albums.values(), key=lambda album:
                  (album["artist"].casefold(), album["title"].casefold()))
