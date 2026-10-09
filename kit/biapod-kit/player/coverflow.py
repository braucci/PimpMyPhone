"""Lightweight animated cover browser for BiaPod's GTK 3 interface."""

from collections import OrderedDict
import math
import time

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk


ART_SIZE = 300
CACHE_LIMIT = 14


class CoverFlow(Gtk.DrawingArea):
    """Draw a small window of album art and animate its fractional position."""

    def __init__(self, on_select, on_activate):
        super().__init__()
        self.on_select = on_select
        self.on_activate = on_activate
        self.albums = []
        self.position = 0.0
        self.target = 0
        self.animation_from = 0.0
        self.animation_started = 0.0
        self.animation_duration = 0.28
        self.timer = None
        self.cache = OrderedDict()
        self.pointer_start = None
        self.touch_start = None
        self.ignore_mouse_until = 0.0
        self.set_size_request(580, 410)
        self.set_hexpand(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.TOUCH_MASK)
        self.connect("draw", self._draw)
        self.connect("button-press-event", self._button_press)
        self.connect("button-release-event", self._button_release)
        self.connect("touch-event", self._touch)

    @property
    def index(self):
        return self.target % len(self.albums) if self.albums else 0

    def set_albums(self, albums):
        selected_uri = self.albums[self.index]["uri"] if self.albums else None
        self.albums = albums
        if self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None
        selected = next((i for i, album in enumerate(albums)
                         if album["uri"] == selected_uri), 0)
        self.position = self.target = selected
        self.cache.clear()
        self._warm(self.target)
        self.queue_draw()

    def step(self, delta):
        if len(self.albums) < 2 or not delta:
            return
        delta = max(-3, min(3, int(delta)))
        now = time.monotonic()
        if self.timer is not None:
            self._advance(now)
        self.animation_from = self.position
        self.target += delta
        self.animation_started = now
        self.animation_duration = 0.28 + 0.07 * (abs(delta) - 1)
        self._warm(self.target)
        self.on_select(self.index)
        if self.timer is None:
            self.timer = GLib.timeout_add(16, self._tick)
        self.queue_draw()

    def _advance(self, now):
        progress = min(1.0, (now - self.animation_started) / self.animation_duration)
        eased = 1 - (1 - progress) ** 3
        self.position = self.animation_from + (self.target - self.animation_from) * eased
        return progress < 1.0

    def _tick(self):
        moving = self._advance(time.monotonic())
        if not moving:
            self.position = self.target = self.index
            self.timer = None
            self._warm(self.target)
        self.queue_draw()
        return moving

    def _warm(self, center):
        if not self.albums:
            return
        for offset in range(-3, 4):
            self._surface(self.albums[(center + offset) % len(self.albums)])

    def _surface(self, album):
        key = album.get("cover") or album["uri"]
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, ART_SIZE, ART_SIZE)
        cr = cairo.Context(surface)
        cr.set_source_rgb(0.12, 0.18, 0.20)
        cr.paint()
        path = album.get("cover")
        if path:
            try:
                art = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    path, ART_SIZE, ART_SIZE, True)
                x = (ART_SIZE - art.get_width()) / 2
                y = (ART_SIZE - art.get_height()) / 2
                Gdk.cairo_set_source_pixbuf(cr, art, x, y)
                cr.paint()
            except GLib.Error:
                path = None
        if not path:
            cr.set_source_rgb(0.49, 0.89, 0.80)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(130)
            cr.move_to(96, 192)
            cr.show_text("♫")
        self.cache[key] = surface
        if len(self.cache) > CACHE_LIMIT:
            self.cache.popitem(last=False)
        return surface

    def _draw_card(self, cr, album, relative, width, height):
        distance = min(abs(relative), 2.5)
        size = 254 - 86 * min(distance, 1) - 62 * max(0, distance - 1)
        x_offset = 179 * min(distance, 1) + 111 * max(0, distance - 1)
        x = width / 2 + math.copysign(x_offset, relative) if relative else width / 2
        baseline = height * 0.69 + 8 * min(distance, 1)
        top = baseline - size
        alpha = max(0.35, 1 - 0.25 * distance)
        scale = size / ART_SIZE
        tilt = 0.14 * min(distance, 1) * (1 if relative < 0 else -1)
        art = self._surface(album)

        cr.save()
        cr.translate(x - size / 2, top)
        cr.translate(-tilt * size / 2, 0)
        cr.transform(cairo.Matrix(1, 0, tilt, 1, 0, 0))
        cr.set_source_rgba(0, 0, 0, 0.30 * alpha)
        cr.rectangle(5, 8, size, size)
        cr.fill()
        cr.scale(scale, scale)
        cr.set_source_surface(art, 0, 0)
        cr.paint_with_alpha(alpha)
        cr.set_source_rgba(0.80, 0.98, 0.94, 0.65 * alpha)
        cr.set_line_width(2 / scale)
        cr.rectangle(1, 1, ART_SIZE - 2, ART_SIZE - 2)
        cr.stroke()
        cr.restore()

        # A short, faded reflection gives depth without loading extra artwork.
        reflection_height = min(60, height - baseline - 10)
        if reflection_height > 0:
            cr.save()
            cr.rectangle(x - size / 2 - 10, baseline + 7, size + 20,
                         reflection_height)
            cr.clip()
            cr.translate(x - size / 2, baseline + 7 + size * 0.24)
            cr.scale(scale, -scale * 0.24)
            cr.set_source_surface(art, 0, 0)
            cr.paint_with_alpha(0.11 * alpha)
            cr.restore()

    def _draw(self, _widget, cr):
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        background = cairo.LinearGradient(0, 0, 0, height)
        background.add_color_stop_rgb(0, 0.06, 0.10, 0.11)
        background.add_color_stop_rgb(1, 0.07, 0.13, 0.14)
        cr.set_source(background)
        cr.paint()
        horizon = height * 0.69 + 11
        cr.set_source_rgba(0.54, 0.89, 0.79, 0.19)
        cr.set_line_width(1)
        cr.move_to(20, horizon)
        cr.line_to(width - 20, horizon)
        cr.stroke()
        if not self.albums:
            return False
        base = math.floor(self.position)
        positions = [i for i in range(base - 3, base + 4)
                     if abs(i - self.position) <= 2.5]
        positions.sort(key=lambda i: abs(i - self.position), reverse=True)
        for virtual_index in positions:
            album = self.albums[virtual_index % len(self.albums)]
            self._draw_card(cr, album, virtual_index - self.position,
                            width, height)
        return False

    def _button_press(self, _widget, event):
        if event.button == 1 and time.monotonic() >= self.ignore_mouse_until:
            self.pointer_start = (event.x, event.y)
        return True

    def _button_release(self, _widget, event):
        if event.button == 1 and self.pointer_start is not None:
            start = self.pointer_start
            self.pointer_start = None
            if time.monotonic() >= self.ignore_mouse_until:
                self._gesture_end(start, (event.x, event.y))
        return True

    def _touch(self, _widget, event):
        if event.type == Gdk.EventType.TOUCH_BEGIN:
            self.touch_start = (event.x, event.y)
        elif event.type == Gdk.EventType.TOUCH_END and self.touch_start is not None:
            start = self.touch_start
            self.touch_start = None
            self.ignore_mouse_until = time.monotonic() + 0.25
            self._gesture_end(start, (event.x, event.y))
        elif event.type == Gdk.EventType.TOUCH_CANCEL:
            self.touch_start = None
        return True

    def _gesture_end(self, start, end):
        dx, dy = end[0] - start[0], end[1] - start[1]
        if abs(dx) > 35 and abs(dx) > abs(dy):
            steps = min(3, max(1, round(abs(dx) / 125)))
            self.step(steps if dx < 0 else -steps)
        elif abs(dx) < 25 and abs(dy) < 25:
            width = self.get_allocated_width()
            if end[0] < width * 0.37:
                self.step(-1)
            elif end[0] > width * 0.63:
                self.step(1)
            elif self.albums:
                self.on_activate()
