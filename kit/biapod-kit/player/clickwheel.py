"""Touch click wheel for BiaPod's now-playing screen."""

import math
import time

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk


class ClickWheel(Gtk.DrawingArea):
    def __init__(self, on_volume, on_transport):
        super().__init__()
        self.on_volume = on_volume
        self.on_transport = on_transport
        self.volume = 0
        self.playing = False
        self.press = None
        self.last_angle = None
        self.angle_remainder = 0.0
        self.rotated = False
        self.ignore_mouse_until = 0.0
        self.set_size_request(390, 390)
        self.set_halign(Gtk.Align.CENTER)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.TOUCH_MASK)
        self.connect("draw", self._draw)
        self.connect("button-press-event", self._mouse_press)
        self.connect("button-release-event", self._mouse_release)
        self.connect("motion-notify-event", self._mouse_motion)
        self.connect("touch-event", self._touch)

    def set_state(self, volume, playing):
        volume = max(0, min(100, int(volume)))
        if volume != self.volume or playing != self.playing:
            self.volume = volume
            self.playing = playing
            self.queue_draw()

    def _geometry(self):
        side = min(self.get_allocated_width(), self.get_allocated_height())
        cx = self.get_allocated_width() / 2
        cy = self.get_allocated_height() / 2
        return cx, cy, side / 2 - 5

    @staticmethod
    def _text(cr, label, x, y, size, bold=False):
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(size)
        extents = cr.text_extents(label)
        cr.move_to(x - extents.width / 2 - extents.x_bearing,
                   y - extents.height / 2 - extents.y_bearing)
        cr.show_text(label)

    def _draw(self, _widget, cr):
        cx, cy, radius = self._geometry()
        cr.set_antialias(cairo.ANTIALIAS_BEST)
        cr.set_source_rgba(0, 0, 0, 0.38)
        cr.arc(cx, cy + 6, radius, 0, math.tau)
        cr.fill()

        ring = cairo.RadialGradient(cx - radius * 0.35, cy - radius * 0.5,
                                    radius * 0.1, cx, cy, radius)
        ring.add_color_stop_rgb(0, 0.27, 0.38, 0.39)
        ring.add_color_stop_rgb(0.65, 0.18, 0.29, 0.31)
        ring.add_color_stop_rgb(1, 0.10, 0.19, 0.21)
        cr.set_source(ring)
        cr.arc(cx, cy, radius, 0, math.tau)
        cr.fill_preserve()
        cr.set_source_rgb(0.45, 0.75, 0.70)
        cr.set_line_width(2)
        cr.stroke()

        # A narrow illuminated track shows the current level as the wheel turns.
        cr.set_source_rgba(0.51, 0.91, 0.80, 0.18)
        cr.set_line_width(5)
        cr.arc(cx, cy, radius - 9, -math.pi / 2,
               -math.pi / 2 + math.tau * self.volume / 100)
        cr.stroke()

        cr.set_source_rgb(0.70, 0.96, 0.88)
        self._text(cr, "+", cx, cy - radius * 0.72, 30)
        self._text(cr, "−", cx, cy + radius * 0.75, 33)
        self._text(cr, "◀◀", cx - radius * 0.72, cy, 17, True)
        self._text(cr, "▶▶", cx + radius * 0.72, cy, 17, True)

        inner = radius * 0.42
        cr.set_source_rgb(0.06, 0.12, 0.13)
        cr.arc(cx, cy + 2, inner + 3, 0, math.tau)
        cr.fill()
        center = cairo.LinearGradient(0, cy - inner, 0, cy + inner)
        center.add_color_stop_rgb(0, 0.23, 0.39, 0.38)
        center.add_color_stop_rgb(1, 0.13, 0.25, 0.26)
        cr.set_source(center)
        cr.arc(cx, cy, inner, 0, math.tau)
        cr.fill_preserve()
        cr.set_source_rgb(0.48, 0.79, 0.73)
        cr.set_line_width(2)
        cr.stroke()
        cr.set_source_rgb(0.77, 1.0, 0.91)
        self._text(cr, "Ⅱ" if self.playing else "▶", cx, cy, 36, True)
        return False

    def _begin(self, x, y):
        cx, cy, radius = self._geometry()
        distance = math.hypot(x - cx, y - cy)
        if distance > radius:
            return
        self.press = (x, y, distance)
        self.last_angle = math.atan2(y - cy, x - cx)
        self.angle_remainder = 0.0
        self.rotated = False

    def _move(self, x, y):
        if self.press is None:
            return
        cx, cy, radius = self._geometry()
        distance = math.hypot(x - cx, y - cy)
        if self.press[2] < radius * 0.47 or distance < radius * 0.47:
            return
        angle = math.atan2(y - cy, x - cx)
        delta = (angle - self.last_angle + math.pi) % math.tau - math.pi
        self.last_angle = angle
        if abs(delta) > 0.75:
            return
        if math.hypot(x - self.press[0], y - self.press[1]) > 8:
            self.rotated = True
        if not self.rotated:
            return
        self.angle_remainder += delta
        tick = math.radians(12)
        steps = math.trunc(self.angle_remainder / tick)
        if steps:
            self.angle_remainder -= steps * tick
            self.on_volume(steps)

    def _end(self, x, y):
        if self.press is None:
            return
        cx, cy, radius = self._geometry()
        distance = math.hypot(x - cx, y - cy)
        press = self.press
        rotated = self.rotated
        self.press = None
        self.last_angle = None
        if rotated or distance > radius or math.hypot(x - press[0], y - press[1]) > 22:
            return
        if distance < radius * 0.46:
            self.on_transport("pause")
        else:
            angle = math.atan2(y - cy, x - cx)
            if -math.pi / 4 <= angle < math.pi / 4:
                self.on_transport("next")
            elif math.pi / 4 <= angle < 3 * math.pi / 4:
                self.on_volume(-1)
            elif -3 * math.pi / 4 <= angle < -math.pi / 4:
                self.on_volume(1)
            else:
                self.on_transport("previous")

    def _mouse_press(self, _widget, event):
        if event.button == 1 and time.monotonic() >= self.ignore_mouse_until:
            self._begin(event.x, event.y)
        return True

    def _mouse_motion(self, _widget, event):
        if self.press is not None and time.monotonic() >= self.ignore_mouse_until:
            self._move(event.x, event.y)
        return True

    def _mouse_release(self, _widget, event):
        if event.button == 1 and time.monotonic() >= self.ignore_mouse_until:
            self._end(event.x, event.y)
        self.press = None
        return True

    def _touch(self, _widget, event):
        if event.type == Gdk.EventType.TOUCH_BEGIN:
            self._begin(event.x, event.y)
        elif event.type == Gdk.EventType.TOUCH_UPDATE:
            self._move(event.x, event.y)
        elif event.type == Gdk.EventType.TOUCH_END:
            self._end(event.x, event.y)
            self.ignore_mouse_until = time.monotonic() + 0.25
        elif event.type == Gdk.EventType.TOUCH_CANCEL:
            self.press = None
        return True
