#!/usr/bin/env python3
"""BiaPod: a dedicated touch music player for the original PinePhone."""

from datetime import datetime
from pathlib import Path
import subprocess
from threading import Thread
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from clickwheel import ClickWheel
from coverflow import CoverFlow
from library import scan_music
from mpdclient import MPD, first, grouped


MUSIC = Path.home() / "Music"
BATTERY = Path("/sys/class/power_supply/axp20x-battery")
ALBUM_PAGE_SIZE = 24


def track_order(song):
    def number(field):
        try:
            return int(song.get(field, "0").split("/", 1)[0])
        except ValueError:
            return 0
    return number("disc"), number("track"), song["file"].casefold()


class BiaPod(Gtk.Window):
    def __init__(self):
        super().__init__(title="BiaPod")
        self.mpd = MPD()
        self.albums = []
        self.album_by_uri = {}
        self.filtered_albums = []
        self.selected_artist = None
        self.artist_rows = {}
        self.album_page_count = 0
        self.flow_index = 0
        self.detail_album = None
        self.detail_tracks = []
        self.detail_origin = "albums"
        self.current_file = None
        self.dragging_seek = False
        self.dragging_volume = False
        self.wheel_volume_timer = None
        self.wheel_volume_pending = None
        self.art_cache = {}
        self.sleep_inhibitor = self._inhibitor_running()
        self.inhibit_retry_after = 0
        self.inhibit_check_after = 0

        self.set_default_size(720, 1440)
        self.fullscreen()
        self.connect("destroy", self._shutdown)
        self.connect("key-press-event", self._on_key)
        self._style()

        self.layer = Gtk.Overlay()
        self.add(self.layer)
        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=11)
        self.root.set_border_width(17)
        self.layer.add(self.root)
        self._header()

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(180)
        self.root.pack_start(self.stack, True, True, 0)
        self._player_page()
        self._albums_page()
        self._artists_page()
        self._detail_page()
        self._flow_page()
        self._playlists_page()

        self.notice = Gtk.Label(label="")
        self.notice.get_style_context().add_class("hint")
        self.notice.set_line_wrap(True)
        self.root.pack_end(self.notice, False, False, 0)
        self._navigation()
        self._touch_lock()

        self.show_all()
        self.touch_blocker.hide()
        self.stack.set_visible_child_name("player")
        self._clock()
        self._scan_catalog()
        self._update()
        GLib.timeout_add_seconds(2, self._update)
        GLib.timeout_add_seconds(30, self._clock)

    def _style(self):
        css = b"""
        * { font-family: sans-serif; }
        window { background: #101719; color: #f4f6f5; }
        button { background: #253236; color: #f4f6f5; border: 1px solid #49636a;
                 border-radius: 14px; padding: 10px; font-size: 18px; }
        button:hover, button:active { background: #355056; }
        .big { font-size: 28px; font-weight: bold; }
        .song { font-size: 27px; font-weight: bold; }
        .subtitle { font-size: 19px; color: #a9c4bc; }
        .hint { font-size: 16px; color: #a9c4bc; }
        .transport { font-size: 28px; font-weight: bold; color: #82e3cb;
                     min-width: 68px; min-height: 60px; }
        .nav { font-size: 17px; min-height: 52px; }
        .nav-active { background: #315e58; color: #b4ffeb; }
        .side-cover { opacity: 0.65; }
        .album-card { min-width: 210px; min-height: 260px; }
        .artist-item { min-height: 54px; }
        .artist-search { background: #253236; color: #f4f6f5;
                         border: 1px solid #49636a; border-radius: 12px;
                         font-size: 18px; min-height: 42px; }
        .artist-list, .artist-list row { background: #101719; border: 0; }
        .artist-list row { padding: 2px 0; }
        .track-row { padding: 5px; }
        .touch-lock { background: #101719; }
        .unlock { min-width: 240px; min-height: 80px; font-size: 25px; }
        scale trough { min-height: 6px; }
        scale slider { min-width: 22px; min-height: 22px; }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _header(self):
        row = Gtk.Box(spacing=8)
        self.root.pack_start(row, False, False, 0)
        logo = Path(__file__).with_name("biapod-logo.png")
        if logo.is_file():
            image = Gtk.Image.new_from_pixbuf(
                GdkPixbuf.Pixbuf.new_from_file_at_scale(str(logo), 215, -1, True))
        else:
            image = Gtk.Label(label="BiaPod")
            image.get_style_context().add_class("big")
        row.pack_start(image, False, False, 0)
        self.status_label = Gtk.Label(label="")
        self.status_label.get_style_context().add_class("hint")
        row.pack_end(self.status_label, False, False, 0)
        lock = Gtk.Button(label="Blocca")
        lock.connect("clicked", self._lock_touch)
        row.pack_end(lock, False, False, 0)

    def _clock(self):
        try:
            percent = (BATTERY / "capacity").read_text().strip()
            charging = (BATTERY / "status").read_text().strip() == "Charging"
            battery = f"{percent}%{'+' if charging else ''}"
        except OSError:
            battery = ""
        self.status_label.set_text(f"{datetime.now():%H:%M}  {battery}")
        return True

    def _navigation(self):
        bar = Gtk.Box(spacing=6)
        self.root.pack_end(bar, False, False, 0)
        self.nav_buttons = {}
        for title, page, callback in (("Ora", "player", self._show_player),
                                      ("Album", "albums", self._show_albums),
                                      ("Cover Flow", "flow", self._show_flow),
                                      ("Playlist", "playlists", self._show_playlists)):
            button = Gtk.Button(label=title)
            button.get_style_context().add_class("nav")
            button.connect("clicked", callback)
            bar.pack_start(button, True, True, 0)
            self.nav_buttons[page] = button
        self.stack.connect("notify::visible-child-name", self._nav_state)

    def _nav_state(self, *_args):
        page = self.stack.get_visible_child_name()
        if page in ("detail", "artists"):
            page = "albums"
        for name, button in self.nav_buttons.items():
            context = button.get_style_context()
            if name == page:
                context.add_class("nav-active")
            else:
                context.remove_class("nav-active")

    def _touch_lock(self):
        self.touch_blocker = Gtk.EventBox()
        self.touch_blocker.get_style_context().add_class("touch-lock")
        self.touch_blocker.set_halign(Gtk.Align.FILL)
        self.touch_blocker.set_valign(Gtk.Align.FILL)
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        panel.set_halign(Gtk.Align.CENTER)
        panel.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label="Tocchi bloccati")
        title.get_style_context().add_class("big")
        panel.pack_start(title, False, False, 0)
        hint = Gtk.Label(label="La musica continua. Tieni premuto per sbloccare.")
        hint.set_line_wrap(True)
        hint.get_style_context().add_class("subtitle")
        panel.pack_start(hint, False, False, 0)
        unlock = Gtk.Button(label="Tieni premuto")
        unlock.get_style_context().add_class("unlock")
        self.unlock_gesture = Gtk.GestureLongPress.new(unlock)
        self.unlock_gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        self.unlock_gesture.set_property("delay-factor", 2.0)
        self.unlock_gesture.connect("pressed", self._unlock_touch)
        panel.pack_start(unlock, False, False, 0)
        self.touch_blocker.add(panel)
        self.layer.add_overlay(self.touch_blocker)
        self.layer.set_overlay_pass_through(self.touch_blocker, False)

    def _lock_touch(self, *_args):
        self.touch_blocker.show_all()

    def _unlock_touch(self, *_args):
        self.touch_blocker.hide()

    def _player_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_valign(Gtk.Align.CENTER)
        self.stack.add_named(page, "player")
        self.player_art = Gtk.Image()
        self.player_art_button = Gtk.EventBox()
        self.player_art_button.add(self.player_art)
        self.player_art_button.connect("button-release-event", self._open_current_album)
        page.pack_start(self.player_art_button, False, False, 0)
        self.song_label = Gtk.Label(label="Nessun brano")
        self.song_label.set_line_wrap(True)
        self.song_label.get_style_context().add_class("song")
        page.pack_start(self.song_label, False, False, 0)
        self.artist_label = Gtk.Label(label="Copia gli album nella libreria")
        self.artist_label.set_line_wrap(True)
        self.artist_label.get_style_context().add_class("subtitle")
        page.pack_start(self.artist_label, False, False, 0)

        self.seek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.seek.set_draw_value(False)
        self.seek.connect("button-press-event", self._seek_start)
        self.seek.connect("button-release-event", self._seek_end)
        page.pack_start(self.seek, False, False, 0)
        self.time_label = Gtk.Label(label="0:00")
        self.time_label.get_style_context().add_class("hint")
        page.pack_start(self.time_label, False, False, 0)

        self.clickwheel = ClickWheel(self._wheel_volume, self._wheel_transport)
        page.pack_start(self.clickwheel, False, False, 0)

        volume_row = Gtk.Box(spacing=8)
        page.pack_start(volume_row, False, False, 0)
        volume_row.pack_start(Gtk.Label(label="Vol."), False, False, 0)
        self.volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume.set_draw_value(False)
        self.volume.connect("button-press-event", self._volume_start)
        self.volume.connect("button-release-event", self._volume_end)
        volume_row.pack_start(self.volume, True, True, 0)
        self.volume_label = Gtk.Label(label="0%")
        volume_row.pack_start(self.volume_label, False, False, 0)
        self.volume.connect("value-changed", self._volume_changed)
        favorite = Gtk.Button(label="Aggiungi ai Preferiti")
        favorite.connect("clicked", self._favorite_current)
        page.pack_start(favorite, False, False, 0)
        modes = Gtk.Box(spacing=8)
        page.pack_start(modes, False, False, 0)
        self.shuffle_button = Gtk.Button(label="Casuale: no")
        self.shuffle_button.connect("clicked", self._toggle_mode, "random")
        modes.pack_start(self.shuffle_button, True, True, 0)
        self.repeat_button = Gtk.Button(label="Ripeti: no")
        self.repeat_button.connect("clicked", self._toggle_mode, "repeat")
        modes.pack_start(self.repeat_button, True, True, 0)

    def _albums_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.stack.add_named(page, "albums")
        row = Gtk.Box(spacing=8)
        page.pack_start(row, False, False, 0)
        self.artist_button = Gtk.Button(label="Artisti: tutti  ›")
        self.artist_button.connect("clicked", self._show_artists)
        row.pack_start(self.artist_button, True, True, 0)
        refresh = Gtk.Button(label="Aggiorna")
        refresh.connect("clicked", self._refresh_library)
        row.pack_start(refresh, False, False, 0)
        self.album_count_label = Gtk.Label(label="Caricamento album…")
        self.album_count_label.get_style_context().add_class("hint")
        page.pack_start(self.album_count_label, False, False, 0)
        self.play_all_button = Gtk.Button(label="Tutta la musica · casuale")
        self.play_all_button.connect("clicked", self._play_all_random)
        page.pack_start(self.play_all_button, False, False, 0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.pack_start(scroller, True, True, 0)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scroller.add(content)
        self.album_grid = Gtk.FlowBox()
        self.album_grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self.album_grid.set_min_children_per_line(2)
        self.album_grid.set_max_children_per_line(2)
        self.album_grid.set_column_spacing(8)
        self.album_grid.set_row_spacing(8)
        content.pack_start(self.album_grid, False, False, 0)
        self.more_albums = Gtk.Button(label="Mostra altri album")
        self.more_albums.connect("clicked", self._append_album_page)
        content.pack_start(self.more_albums, False, False, 0)

    def _artists_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.stack.add_named(page, "artists")
        back = Gtk.Button(label="‹ Torna agli album")
        back.set_halign(Gtk.Align.START)
        back.connect("clicked", self._show_albums)
        page.pack_start(back, False, False, 0)
        title = Gtk.Label(label="Scegli un artista")
        title.get_style_context().add_class("big")
        title.set_xalign(0)
        page.pack_start(title, False, False, 0)
        self.artist_search = Gtk.SearchEntry()
        self.artist_search.get_style_context().add_class("artist-search")
        self.artist_search.set_placeholder_text("Cerca un artista")
        self.artist_search.connect("search-changed", self._search_artists)
        page.pack_start(self.artist_search, False, False, 0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.pack_start(scroller, True, True, 0)
        self.artist_list = Gtk.ListBox()
        self.artist_list.get_style_context().add_class("artist-list")
        self.artist_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scroller.add(self.artist_list)

    def _show_artists(self, *_args):
        self.artist_search.set_text("")
        self.stack.set_visible_child_name("artists")

    def _search_artists(self, *_args):
        query = self.artist_search.get_text().strip().casefold()
        for artist, row in self.artist_rows.items():
            row.set_visible(query in artist.casefold())

    def _select_artist(self, _button, artist):
        self.selected_artist = artist
        self.artist_button.set_label(f"Artisti: {artist or 'tutti'}  ›")
        self._filter_albums()
        self.stack.set_visible_child_name("albums")

    def _rebuild_artists(self):
        for row in self.artist_list.get_children():
            self.artist_list.remove(row)
        counts = {}
        for album in self.albums:
            counts[album["artist"]] = counts.get(album["artist"], 0) + 1
        self.artist_rows = {}
        for artist in (None, *sorted(counts, key=str.casefold)):
            label = f"Tutti gli artisti · {len(self.albums)} album" if artist is None else (
                f"{artist} · {counts[artist]} album")
            button = Gtk.Button(label=label)
            button.get_style_context().add_class("artist-item")
            button.get_child().set_line_wrap(True)
            button.get_child().set_xalign(0)
            button.connect("clicked", self._select_artist, artist)
            self.artist_list.add(button)
            self.artist_rows[artist or ""] = button.get_parent()
        self.artist_list.show_all()

    def _detail_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        self.stack.add_named(page, "detail")
        self.detail_back = Gtk.Button(label="‹ Album")
        self.detail_back.set_halign(Gtk.Align.START)
        self.detail_back.connect("clicked", self._leave_detail)
        page.pack_start(self.detail_back, False, False, 0)
        self.detail_art = Gtk.Image()
        page.pack_start(self.detail_art, False, False, 0)
        self.detail_title = Gtk.Label(label="")
        self.detail_title.set_line_wrap(True)
        self.detail_title.get_style_context().add_class("big")
        page.pack_start(self.detail_title, False, False, 0)
        self.detail_artist = Gtk.Label(label="")
        self.detail_artist.get_style_context().add_class("subtitle")
        page.pack_start(self.detail_artist, False, False, 0)
        actions = Gtk.Box(spacing=7)
        page.pack_start(actions, False, False, 0)
        for title, callback in (("Riproduci", self._play_detail),
                                ("In coda", self._queue_detail),
                                ("Crea playlist", self._save_detail_playlist)):
            button = Gtk.Button(label=title)
            button.connect("clicked", callback)
            actions.pack_start(button, True, True, 0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.pack_start(scroller, True, True, 0)
        self.track_list = Gtk.ListBox()
        self.track_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scroller.add(self.track_list)

    def _flow_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        page.set_valign(Gtk.Align.CENTER)
        self.stack.add_named(page, "flow")
        title = Gtk.Label(label="Cover Flow")
        title.get_style_context().add_class("big")
        page.pack_start(title, False, False, 0)
        self.flow_view = CoverFlow(self._flow_selected, self._flow_activate)
        page.pack_start(self.flow_view, False, False, 0)
        controls = Gtk.Box(spacing=12)
        controls.set_halign(Gtk.Align.CENTER)
        page.pack_start(controls, False, False, 0)
        for label, step in (("◀", -1), ("▶", 1)):
            button = Gtk.Button(label=label)
            button.get_style_context().add_class("transport")
            button.connect("clicked", lambda _b, n=step: self._flow_step(n))
            controls.pack_start(button, False, False, 0)
        self.flow_title = Gtk.Label(label="Caricamento copertine…")
        self.flow_title.set_line_wrap(True)
        self.flow_title.get_style_context().add_class("song")
        page.pack_start(self.flow_title, False, False, 0)
        self.flow_artist = Gtk.Label(label="")
        self.flow_artist.get_style_context().add_class("subtitle")
        page.pack_start(self.flow_artist, False, False, 0)
        play = Gtk.Button(label="Riproduci album")
        play.connect("clicked", self._play_flow)
        page.pack_start(play, False, False, 0)

    def _playlists_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        self.stack.add_named(page, "playlists")
        title = Gtk.Label(label="Playlist")
        title.get_style_context().add_class("big")
        page.pack_start(title, False, False, 0)
        save = Gtk.Button(label="Salva la coda attuale")
        save.connect("clicked", self._save_queue)
        page.pack_start(save, False, False, 0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        page.pack_start(scroller, True, True, 0)
        self.playlist_list = Gtk.ListBox()
        self.playlist_list.set_selection_mode(Gtk.SelectionMode.NONE)
        scroller.add(self.playlist_list)

    def _report(self, message):
        self.notice.set_text(message)

    def _shutdown(self, *_args):
        self._stop_sleep_inhibitor()
        Gtk.main_quit()

    def _inhibitor_running(self):
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "biapod-playback-inhibit.service"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _stop_sleep_inhibitor(self):
        if self.sleep_inhibitor:
            try:
                subprocess.run(
                    ["systemctl", "--user", "stop", "biapod-playback-inhibit.service"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.sleep_inhibitor = False

    def _sync_sleep_inhibitor(self, state):
        if state == "play":
            now = time.monotonic()
            if now < self.inhibit_check_after or now < self.inhibit_retry_after:
                return
            if self._inhibitor_running():
                self.sleep_inhibitor = True
                self.inhibit_check_after = now + 30
            else:
                try:
                    result = subprocess.run(
                        ["systemd-run", "--user", "--unit=biapod-playback-inhibit",
                         "--collect", "/usr/bin/systemd-inhibit", "--what=sleep",
                         "--mode=block", "--why=BiaPod-playback",
                         "/usr/bin/sleep", "infinity"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                    self.sleep_inhibitor = result.returncode == 0
                    self.inhibit_check_after = now + 30 if self.sleep_inhibitor else 0
                except (OSError, subprocess.TimeoutExpired):
                    self.sleep_inhibitor = False
                if not self.sleep_inhibitor:
                    self.inhibit_retry_after = now + 60
        elif self.sleep_inhibitor:
            self._stop_sleep_inhibitor()

    def _art(self, album, size):
        if not album or not album.get("cover"):
            label = Gtk.Label(label="♫")
            label.set_size_request(size, size)
            return label
        path = album["cover"]
        key = (path, size)
        try:
            if key not in self.art_cache:
                self.art_cache[key] = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    path, size, size, True)
            return Gtk.Image.new_from_pixbuf(self.art_cache[key])
        except GLib.Error:
            label = Gtk.Label(label="♫")
            label.set_size_request(size, size)
            return label

    def _album_for_file(self, file):
        parts = file.split("/")
        uri = "/".join(parts[:2]) if len(parts) >= 3 else parts[0] if len(parts) == 2 else ""
        return self.album_by_uri.get(uri)

    def _scan_catalog(self):
        def worker():
            try:
                albums = scan_music(MUSIC)
                GLib.idle_add(self._apply_catalog, albums)
            except OSError as error:
                GLib.idle_add(self._report, str(error))
        Thread(target=worker, daemon=True).start()

    def _apply_catalog(self, albums):
        self.albums = albums
        self.album_by_uri = {album["uri"]: album for album in albums}
        if self.selected_artist not in {album["artist"] for album in albums}:
            self.selected_artist = None
        self.artist_button.set_label(f"Artisti: {self.selected_artist or 'tutti'}  ›")
        self._rebuild_artists()
        self._filter_albums()
        self._render_flow()
        self._refresh_player_art()
        if albums and not self.current_file and self.stack.get_visible_child_name() == "player":
            self.stack.set_visible_child_name("albums")
        return False

    def _filter_albums(self, *_args):
        self.filtered_albums = [album for album in self.albums
                                if self.selected_artist in (None, album["artist"])]
        for child in self.album_grid.get_children():
            self.album_grid.remove(child)
        self.album_page_count = 0
        self.album_count_label.set_text(
            f"{len(self.filtered_albums)} album · {len({a['artist'] for a in self.filtered_albums})} artisti")
        self._append_album_page()

    def _append_album_page(self, *_args):
        next_count = min(self.album_page_count + ALBUM_PAGE_SIZE,
                         len(self.filtered_albums))
        for album in self.filtered_albums[self.album_page_count:next_count]:
            button = Gtk.Button()
            button.get_style_context().add_class("album-card")
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            card.pack_start(self._art(album, 190), False, False, 0)
            label = Gtk.Label(label=album["title"])
            label.set_line_wrap(True)
            label.set_max_width_chars(22)
            card.pack_start(label, False, False, 0)
            artist = Gtk.Label(label=album["artist"])
            artist.get_style_context().add_class("hint")
            card.pack_start(artist, False, False, 0)
            button.add(card)
            button.connect("clicked", self._open_album, album)
            self.album_grid.insert(button, -1)
        self.album_page_count = next_count
        self.more_albums.set_visible(next_count < len(self.filtered_albums))
        self.album_grid.show_all()

    def _album_tracks(self, album):
        songs = grouped(self.mpd.command("listallinfo", album["uri"]), "file")
        if not album["uri"]:
            songs = [song for song in songs if "/" not in song["file"]]
        return sorted(songs, key=track_order)

    def _open_album(self, _button, album):
        self.detail_origin = self.stack.get_visible_child_name()
        self.detail_back.set_label("‹ Ora" if self.detail_origin == "player" else
                                   "‹ Cover Flow" if self.detail_origin == "flow" else "‹ Album")
        self.detail_album = album
        self.detail_title.set_text(album["title"])
        self.detail_artist.set_text(f"{album['artist']} · {album['count']} brani")
        self.detail_art.clear()
        art = self._art(album, 220)
        if isinstance(art, Gtk.Image):
            self.detail_art.set_from_pixbuf(art.get_pixbuf())
        for child in self.track_list.get_children():
            self.track_list.remove(child)
        try:
            self.detail_tracks = self._album_tracks(album)
            for index, song in enumerate(self.detail_tracks):
                row = Gtk.Box(spacing=5)
                row.get_style_context().add_class("track-row")
                title = song.get("title", song["file"].rsplit("/", 1)[-1])
                play = Gtk.Button()
                play_label = Gtk.Label(label=f"{index + 1}. {title}")
                play_label.set_line_wrap(True)
                play_label.set_max_width_chars(34)
                play_label.set_xalign(0)
                play.add(play_label)
                play.connect("clicked", self._play_detail_track, index)
                row.pack_start(play, True, True, 0)
                queue = Gtk.Button(label="+")
                queue.connect("clicked", self._queue_file, song["file"])
                row.pack_start(queue, False, False, 0)
                favorite = Gtk.Button(label="☆")
                favorite.connect("clicked", self._favorite_file, song["file"])
                row.pack_start(favorite, False, False, 0)
                self.track_list.add(row)
            self.track_list.show_all()
            self.stack.set_visible_child_name("detail")
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _open_current_album(self, *_args):
        album = self._album_for_file(self.current_file or "")
        if album:
            self._open_album(None, album)
        else:
            self._report("Nessun album in riproduzione")
        return True

    def _leave_detail(self, *_args):
        self.stack.set_visible_child_name(self.detail_origin
                                          if self.detail_origin in ("player", "flow")
                                          else "albums")

    def _show_player(self, *_args):
        self.stack.set_visible_child_name("player")

    def _show_albums(self, *_args):
        self.stack.set_visible_child_name("albums")

    def _show_flow(self, *_args):
        self._render_flow()
        self.stack.set_visible_child_name("flow")

    def _flow_step(self, step):
        self.flow_view.step(step)

    def _flow_selected(self, index):
        self.flow_index = index
        self._render_flow()

    def _flow_activate(self):
        if self.albums:
            self._open_album(None, self.albums[self.flow_index])

    def _render_flow(self):
        if self.flow_view.albums is not self.albums:
            self.flow_view.set_albums(self.albums)
            self.flow_index = self.flow_view.index
        if not self.albums:
            self.flow_title.set_text("Nessun album")
            self.flow_artist.set_text("")
            return
        album = self.albums[self.flow_index]
        self.flow_title.set_text(album["title"])
        self.flow_artist.set_text(f"{album['artist']} · {self.flow_index + 1}/{len(self.albums)}")

    def _play_tracks(self, tracks, index=0, append=False):
        if not tracks:
            self._report("Nessun brano riproducibile")
            return
        try:
            if not append:
                self.mpd.command("clear")
            for song in tracks:
                self.mpd.command("add", song["file"])
            if not append:
                self.mpd.command("play", str(index))
                self._show_player()
            self._report("Album aggiunto alla coda" if append else "")
            self._update()
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _play_detail(self, *_args):
        self._play_tracks(self.detail_tracks)

    def _queue_detail(self, *_args):
        self._play_tracks(self.detail_tracks, append=True)

    def _play_detail_track(self, _button, index):
        self._play_tracks(self.detail_tracks, index)

    def _queue_file(self, _button, file):
        try:
            self.mpd.command("add", file)
            self._report("Brano aggiunto alla coda")
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _play_flow(self, *_args):
        if not self.albums:
            return
        try:
            self._play_tracks(self._album_tracks(self.albums[self.flow_index]))
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _play_all_random(self, *_args):
        self.play_all_button.set_sensitive(False)
        self._report("Preparo tutti i brani…")

        def worker():
            try:
                roots = [(kind.lower(), value) for kind, value in self.mpd.command("lsinfo")
                         if kind.lower() in ("directory", "file")]
                if not roots:
                    raise RuntimeError("La libreria musicale è vuota")
                commands = [("clear",)]
                commands.extend(("add", value) for _kind, value in roots)
                commands.extend((("shuffle",), ("random", "1"), ("play", "0")))
                self.mpd.command_list(commands)
                count = first(self.mpd.command("status"), "playlistlength", "0")
                GLib.idle_add(self._finish_play_all_random,
                              f"Riproduzione casuale · {count} brani")
            except (OSError, RuntimeError) as error:
                GLib.idle_add(self._finish_play_all_random, str(error))

        Thread(target=worker, daemon=True).start()

    def _finish_play_all_random(self, message):
        self.play_all_button.set_sensitive(True)
        self._show_player()
        self._report(message)
        self._update()
        return False

    def _playlist_names(self):
        return [value for key, value in self.mpd.command("listplaylists")
                if key.lower() == "playlist"]

    def _unique_playlist_name(self, proposed):
        proposed = "".join(ch for ch in proposed if ch not in "/\\\n\r").strip()[:55] or "Playlist"
        existing = set(self._playlist_names())
        if proposed not in existing:
            return proposed
        number = 2
        while f"{proposed} ({number})" in existing:
            number += 1
        return f"{proposed} ({number})"

    def _save_detail_playlist(self, *_args):
        if not self.detail_album or not self.detail_tracks:
            return
        try:
            name = self._unique_playlist_name(self.detail_album["title"])
            for song in self.detail_tracks:
                self.mpd.command("playlistadd", name, song["file"])
            self._report(f"Playlist «{name}» creata")
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _favorite_file(self, _button, file):
        try:
            existing = {value for key, value in self.mpd.command("listplaylist", "Preferiti")
                        if key.lower() == "file"} if "Preferiti" in self._playlist_names() else set()
            if file not in existing:
                self.mpd.command("playlistadd", "Preferiti", file)
            self._report("Aggiunto ai Preferiti")
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _favorite_current(self, button):
        if self.current_file:
            self._favorite_file(button, self.current_file)

    def _save_queue(self, *_args):
        try:
            status = self.mpd.command("status")
            if int(first(status, "playlistlength", "0")) == 0:
                self._report("La coda è vuota")
                return
            name = self._unique_playlist_name(f"Coda {datetime.now():%d-%m-%Y %H:%M}")
            self.mpd.command("save", name)
            self._show_playlists()
            self._report(f"Playlist «{name}» salvata")
        except (OSError, RuntimeError, ValueError) as error:
            self._report(str(error))

    def _show_playlists(self, *_args):
        for child in self.playlist_list.get_children():
            self.playlist_list.remove(child)
        try:
            names = sorted(self._playlist_names(), key=str.casefold)
            for name in names:
                row = Gtk.Box(spacing=7)
                play = Gtk.Button()
                play_label = Gtk.Label(label=name)
                play_label.set_line_wrap(True)
                play_label.set_max_width_chars(32)
                play.add(play_label)
                play.connect("clicked", self._play_playlist, name)
                row.pack_start(play, True, True, 0)
                delete = Gtk.Button(label="Elimina")
                delete.connect("clicked", self._confirm_delete, name)
                row.pack_start(delete, False, False, 0)
                self.playlist_list.add(row)
            if not names:
                self.playlist_list.add(Gtk.Label(label="Nessuna playlist salvata"))
            self.playlist_list.show_all()
            self.stack.set_visible_child_name("playlists")
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _play_playlist(self, _button, name):
        try:
            self.mpd.command("clear")
            self.mpd.command("load", name)
            self.mpd.command("play")
            self._show_player()
            self._update()
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _confirm_delete(self, button, name):
        if button.get_label() != "Conferma":
            button.set_label("Conferma")
            GLib.timeout_add_seconds(5, self._restore_delete, button)
            return
        try:
            self.mpd.command("rm", name)
            self._show_playlists()
            self._report(f"Playlist «{name}» eliminata")
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _restore_delete(self, button):
        if button.get_parent():
            button.set_label("Elimina")
        return False

    def _transport(self, _button, action):
        try:
            if action == "pause" and first(self.mpd.command("status"), "state") == "stop":
                action = "play"
            self.mpd.command(action)
            self._update()
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _wheel_transport(self, action):
        self._transport(None, action)

    def _wheel_volume(self, steps):
        current = int(round(self.volume.get_value()))
        target = max(0, min(100, current + steps))
        if target == current:
            return
        self.dragging_volume = True
        self.volume.set_value(target)
        self.clickwheel.set_state(target, self.clickwheel.playing)
        self.wheel_volume_pending = target
        if self.wheel_volume_timer is None:
            self.wheel_volume_timer = GLib.timeout_add(60, self._commit_wheel_volume)

    def _commit_wheel_volume(self):
        target = self.wheel_volume_pending
        self.wheel_volume_pending = None
        self.wheel_volume_timer = None
        try:
            self.mpd.command("setvol", str(target))
        except (OSError, RuntimeError) as error:
            self._report(str(error))
        self.dragging_volume = False
        return False

    def _toggle_mode(self, _button, mode):
        try:
            current = first(self.mpd.command("status"), mode, "0")
            self.mpd.command(mode, "0" if current == "1" else "1")
            self._update()
        except (OSError, RuntimeError) as error:
            self._report(str(error))

    def _on_key(self, _window, event):
        key = Gdk.keyval_name(event.keyval)
        if key in ("XF86AudioRaiseVolume", "XF86AudioLowerVolume"):
            try:
                status = self.mpd.command("status")
                current = int(first(status, "volume", "50"))
                step = 1 if key == "XF86AudioRaiseVolume" else -1
                self.mpd.command("setvol", str(max(0, min(100, current + step))))
                self._update()
            except (OSError, RuntimeError, ValueError) as error:
                self._report(str(error))
            return True
        if key in ("XF86AudioPlay", "XF86AudioPause"):
            self._transport(None, "pause")
            return True
        if key == "XF86AudioNext":
            self._transport(None, "next")
            return True
        if key == "XF86AudioPrev":
            self._transport(None, "previous")
            return True
        return False

    def _seek_start(self, *_args):
        self.dragging_seek = True
        return False

    def _seek_end(self, *_args):
        try:
            self.mpd.command("seekcur", str(int(self.seek.get_value())))
        except (OSError, RuntimeError) as error:
            self._report(str(error))
        self.dragging_seek = False
        return False

    def _volume_start(self, *_args):
        self.dragging_volume = True
        return False

    def _volume_changed(self, scale):
        self.volume_label.set_text(f"{round(scale.get_value())}%")

    def _volume_end(self, *_args):
        try:
            self.mpd.command("setvol", str(int(self.volume.get_value())))
        except (OSError, RuntimeError) as error:
            self._report(str(error))
        self.dragging_volume = False
        return False

    def _refresh_player_art(self):
        album = self._album_for_file(self.current_file or "")
        art = self._art(album, 300)
        self.player_art.clear()
        if isinstance(art, Gtk.Image):
            self.player_art.set_from_pixbuf(art.get_pixbuf())
        else:
            self.player_art.set_from_icon_name("audio-x-generic", Gtk.IconSize.DIALOG)

    def _update(self):
        try:
            status = self.mpd.command("status")
            song = self.mpd.command("currentsong")
            file = first(song, "file", "")
            if file != self.current_file:
                self.current_file = file
                self._refresh_player_art()
            title = first(song, "Title", file.rsplit("/", 1)[-1] or "Nessun brano")
            self.song_label.set_text(title)
            artist = first(song, "Artist", first(song, "Album", "Scegli un album"))
            self.artist_label.set_text(artist)
            state = first(status, "state")
            self._sync_sleep_inhibitor(state)
            self.shuffle_button.set_label("Casuale: sì" if first(status, "random") == "1" else "Casuale: no")
            self.repeat_button.set_label("Ripeti: sì" if first(status, "repeat") == "1" else "Ripeti: no")
            duration = float(first(status, "duration", "0") or 0)
            elapsed = float(first(status, "elapsed", "0") or 0)
            if duration > 0 and not self.dragging_seek:
                self.seek.set_range(0, duration)
                self.seek.set_value(elapsed)
            elif not self.dragging_seek:
                self.seek.set_range(0, 100)
                self.seek.set_value(0)
            self.time_label.set_text(f"{int(elapsed) // 60}:{int(elapsed) % 60:02d}  /  "
                                     f"{int(duration) // 60}:{int(duration) % 60:02d}")
            if not self.dragging_volume:
                self.volume.set_value(float(first(status, "volume", "0") or 0))
            self.clickwheel.set_state(round(self.volume.get_value()), state == "play")
            if self.notice.get_text() == "Attendo il motore musicale…":
                self._report("")
        except (OSError, RuntimeError, ValueError):
            self._report("Attendo il motore musicale…")
        return True

    def _refresh_library(self, *_args):
        try:
            self.mpd.command("update")
            self._scan_catalog()
            self._report("Aggiornamento della libreria avviato")
        except (OSError, RuntimeError) as error:
            self._report(str(error))


if __name__ == "__main__":
    BiaPod()
    Gtk.main()
