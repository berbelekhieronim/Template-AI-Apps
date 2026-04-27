#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APP 4 - MALOWANIE GLOSEM I WZROKIEM

Artsy prototype:
- Gaze paints on a living canvas (Tobii)
- Voice timbre and loudness shape brush color, size and pulse
- Strong jitter compensation keeps movement fluid but stable

Controls:
- SPACE: finish artwork
- C: clear canvas
- S: save snapshot now
- ESC: quit
"""

import colorsys
import math
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

# ============================================================================
# 0. TOBII CONFIGURATION
# ============================================================================
HERE = Path(__file__).resolve().parent
SDK_PATH = HERE.parent / "x3-120 SDK" / "64"

if not SDK_PATH.exists():
    raise FileNotFoundError(f"Nie znaleziono SDK Tobii: {SDK_PATH}")
sdk_str = str(SDK_PATH)
if sdk_str not in sys.path:
    sys.path.insert(0, sdk_str)

# ============================================================================
# 1. IMPORTS
# ============================================================================
try:
    from psychopy import core, event, logging, visual
except ImportError as exc:
    raise ImportError("Brak PsychoPy. Zainstaluj: pip install psychopy") from exc

import tobii_research as tr

try:
    import sounddevice as sd

    SOUNDDEVICE_OK = True
except Exception:
    SOUNDDEVICE_OK = False
    sd = None

try:
    from PIL import Image

    PIL_OK = True
except Exception:
    PIL_OK = False
    Image = None

logging.console.setLevel(logging.ERROR)

# ============================================================================
# 2. PARAMETERS
# ============================================================================
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN = True

ACTIVE_SCREEN_WIDTH = float(SCREEN_WIDTH)
ACTIVE_SCREEN_HEIGHT = float(SCREEN_HEIGHT)

CANVAS_W = 1280
CANVAS_H = 720

SESSION_SECONDS = 120.0

# ============================================================================
# 3. GAZE TOOLS + CURSOR VISIBILITY
# ============================================================================
def norm_to_pix(nx, ny):
    px = (nx - 0.5) * ACTIVE_SCREEN_WIDTH
    py = (0.5 - ny) * ACTIVE_SCREEN_HEIGHT
    return px, py


def update_active_screen_size(win):
    global ACTIVE_SCREEN_WIDTH, ACTIVE_SCREEN_HEIGHT
    try:
        w, h = win.size
        ACTIVE_SCREEN_WIDTH = max(1.0, float(w))
        ACTIVE_SCREEN_HEIGHT = max(1.0, float(h))
    except Exception:
        ACTIVE_SCREEN_WIDTH = float(SCREEN_WIDTH)
        ACTIVE_SCREEN_HEIGHT = float(SCREEN_HEIGHT)


CURSOR_WATCHER = None
CURSOR_REVEALED = False


def init_hidden_cursor(win):
    global CURSOR_WATCHER, CURSOR_REVEALED
    CURSOR_WATCHER = event.Mouse(win=win)
    CURSOR_WATCHER.getRel()
    CURSOR_REVEALED = False
    win.mouseVisible = False


def reveal_cursor_if_moved(win, threshold=0.0):
    global CURSOR_REVEALED
    if CURSOR_WATCHER is None or CURSOR_REVEALED:
        return
    dx, dy = CURSOR_WATCHER.getRel()
    if abs(dx) > threshold or abs(dy) > threshold:
        win.mouseVisible = True
        CURSOR_REVEALED = True


class GazeCollector:
    def __init__(self, eyetracker, win=None):
        self._et = eyetracker
        self._win = win
        self._last = None
        self.active = False

    def start(self):
        self._et.subscribe_to(
            tr.EYETRACKER_GAZE_DATA,
            self._callback,
            as_dictionary=True,
        )
        self.active = True

    def stop(self):
        if self.active:
            self._et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._callback)
        self.active = False

    def _callback(self, data):
        self._last = data

    def get_gaze_pix(self):
        d = self._last
        if d is None:
            return None

        l_valid = d["left_gaze_point_validity"]
        r_valid = d["right_gaze_point_validity"]
        xs, ys = [], []

        if l_valid:
            xs.append(d["left_gaze_point_on_display_area"][0])
            ys.append(d["left_gaze_point_on_display_area"][1])
        if r_valid:
            xs.append(d["right_gaze_point_on_display_area"][0])
            ys.append(d["right_gaze_point_on_display_area"][1])

        if not xs:
            return None
        nx = sum(xs) / len(xs)
        ny = sum(ys) / len(ys)
        if not np.isfinite(nx) or not np.isfinite(ny):
            return None
        nx = max(-0.3, min(1.3, nx))
        ny = max(-0.3, min(1.3, ny))
        return norm_to_pix(nx, ny)


def connect_eyetracker():
    trackery = tr.find_all_eyetrackers()
    if not trackery:
        return None

    et = trackery[0]
    print(f"Polaczono: {et.model} | SN: {et.serial_number}")
    return et


def run_calibration(win, eyetracker):
    calibration = tr.ScreenBasedCalibration(eyetracker)
    calibration.enter_calibration_mode()

    points = [(0.5, 0.5), (0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
    dot = visual.Circle(win, radius=20, fillColor="white", lineColor=None)
    center = visual.Circle(win, radius=4, fillColor="black", lineColor=None)

    instrukcja = visual.TextStim(
        win,
        text="Patrz na punkty kalibracyjne. Nacisnij SPACJE, aby zaczac.",
        color="white",
        height=30,
        wrapWidth=1300,
    )
    instrukcja.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        calibration.leave_calibration_mode()
        return None

    for nx, ny in points:
        px, py = norm_to_pix(nx, ny)
        for frame in range(48):
            reveal_cursor_if_moved(win)
            dot.radius = max(8, 24 - frame * 0.3)
            dot.pos = (px, py)
            center.pos = (px, py)
            dot.draw()
            center.draw()
            win.flip()

        calibration.collect_data(nx, ny)
        dot.fillColor = "green"
        dot.radius = 20
        dot.draw()
        center.draw()
        win.flip()
        core.wait(0.2)
        dot.fillColor = "white"

    result = calibration.compute_and_apply()
    calibration.leave_calibration_mode()

    # Do not hard-stop the app on imperfect calibration; continue with warning.
    status = getattr(result, "status", None)
    if status != tr.CALIBRATION_STATUS_SUCCESS:
        print(f"[APP4] Warning: calibration status = {status}. Continuing anyway.")
    return True


# ============================================================================
# 4. AUDIO ANALYSIS
# ============================================================================
class VoiceAnalyzer:
    """Continuously estimates RMS + spectral centroid + ZCR from microphone input."""

    def __init__(self, samplerate=16000, blocksize=1024):
        self.sr = samplerate
        self.blocksize = blocksize
        self.lock = threading.Lock()

        self.rms = 0.0
        self.centroid = 0.25  # normalized 0..1
        self.zcr = 0.1  # normalized 0..1

        self._stream = None
        self.available = False
        self.mode = "SIM"

        self._sim_t = 0.0

    def _callback(self, indata, frames, callback_time, status):
        x = np.asarray(indata[:, 0], dtype=np.float32)
        if x.size == 0:
            return

        x = np.nan_to_num(x, copy=False)
        rms = float(np.sqrt(np.mean(x * x) + 1e-12))

        xw = x * np.hanning(len(x))
        spec = np.abs(np.fft.rfft(xw))
        freqs = np.fft.rfftfreq(len(xw), d=1.0 / self.sr)

        ssum = float(np.sum(spec)) + 1e-12
        centroid_hz = float(np.sum(spec * freqs) / ssum)
        centroid_n = max(0.0, min(1.0, centroid_hz / (self.sr * 0.5)))

        z = np.sign(x)
        z[z == 0] = 1
        zcr = float(np.mean(np.abs(np.diff(z))) * 0.5)
        zcr = max(0.0, min(1.0, zcr))

        with self.lock:
            self.rms = 0.82 * self.rms + 0.18 * rms
            self.centroid = 0.75 * self.centroid + 0.25 * centroid_n
            self.zcr = 0.75 * self.zcr + 0.25 * zcr

    def start(self):
        if SOUNDDEVICE_OK:
            try:
                self._stream = sd.InputStream(
                    channels=1,
                    samplerate=self.sr,
                    blocksize=self.blocksize,
                    callback=self._callback,
                )
                self._stream.start()
                self.available = True
                self.mode = "MIC"
                return
            except Exception:
                self._stream = None

        self.available = False
        self.mode = "SIM"

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def get_features(self, dt):
        if self.available:
            with self.lock:
                return self.rms, self.centroid, self.zcr

        # Soft procedural fallback when no microphone backend is available.
        self._sim_t += dt
        rms = 0.10 + 0.08 * (0.5 + 0.5 * math.sin(2.0 * math.pi * 0.42 * self._sim_t))
        centroid = 0.35 + 0.25 * (0.5 + 0.5 * math.sin(2.0 * math.pi * 0.17 * self._sim_t + 1.2))
        zcr = 0.18 + 0.10 * (0.5 + 0.5 * math.sin(2.0 * math.pi * 0.31 * self._sim_t + 0.4))
        return rms, centroid, zcr


# ============================================================================
# 5. PAINTING ENGINE
# ============================================================================
class GazeSmoother:
    """Adaptive smoothing + deadzone to remove fixation jitter while preserving flow."""

    def __init__(self):
        self.has_point = False
        self.x = 0.0
        self.y = 0.0
        self.last_t = None

    def update(self, px, py, now_t):
        if not self.has_point:
            self.x, self.y = px, py
            self.has_point = True
            self.last_t = now_t
            return self.x, self.y, 0.0

        dt = max(1e-4, now_t - (self.last_t or now_t))
        self.last_t = now_t

        dx = px - self.x
        dy = py - self.y
        dist = math.hypot(dx, dy)
        speed = dist / dt

        deadzone = 8.0
        if dist < deadzone:
            return self.x, self.y, speed

        alpha = 0.08 + min(0.30, speed / 1200.0)
        self.x += alpha * dx
        self.y += alpha * dy
        return self.x, self.y, speed


def build_base_canvas(w, h):
    yy = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]

    r = 0.02 + 0.08 * (1.0 - yy) + 0.02 * np.sin(2 * math.pi * (xx * 0.7 + yy * 0.2))
    g = 0.03 + 0.07 * (1.0 - yy) + 0.02 * np.sin(2 * math.pi * (xx * 0.3 + yy * 0.5 + 0.2))
    b = 0.05 + 0.11 * (1.0 - yy)
    b = np.broadcast_to(b, (h, w))

    canvas = np.stack([r, g, b], axis=2)
    return np.clip(canvas, 0.0, 1.0).astype(np.float32)


def add_soft_stamp(canvas, cx, cy, radius, color_rgb, alpha, shape_kind="circle", texture=0.0):
    h, w, _ = canvas.shape
    if not np.isfinite(cx) or not np.isfinite(cy):
        return
    if not np.isfinite(radius) or radius <= 0:
        return
    if not np.isfinite(alpha):
        return

    rr = max(2.0, float(radius))
    cx = max(0.0, min(float(w - 1), float(cx)))
    cy = max(0.0, min(float(h - 1), float(cy)))

    x0 = max(0, int(cx - rr * 1.8))
    x1 = min(w, int(cx + rr * 1.8) + 1)
    y0 = max(0, int(cy - rr * 1.8))
    y1 = min(h, int(cy + rr * 1.8) + 1)
    if x1 <= x0 or y1 <= y0:
        return

    ys = np.arange(y0, y1, dtype=np.float32)[:, None]
    xs = np.arange(x0, x1, dtype=np.float32)[None, :]

    dx = xs - cx
    dy = ys - cy
    dist2 = dx ** 2 + dy ** 2
    sigma2 = (rr * 0.62) ** 2

    if shape_kind == "square":
        edge = np.maximum(np.abs(dx), np.abs(dy))
        mask = np.exp(-(edge ** 2) / (2.0 * sigma2))
    elif shape_kind == "diamond":
        manhattan = np.abs(dx) + np.abs(dy)
        mask = np.exp(-(manhattan ** 2) / (2.0 * sigma2))
    elif shape_kind == "ring":
        dist = np.sqrt(np.maximum(0.0, dist2))
        r0 = rr * (0.55 + 0.25 * texture)
        band = rr * (0.12 + 0.16 * texture)
        mask = np.exp(-((dist - r0) ** 2) / (2.0 * max(1e-6, band ** 2)))
    elif shape_kind == "star":
        ang = np.arctan2(dy, dx)
        dist = np.sqrt(np.maximum(0.0, dist2))
        petals = 5.0
        radial = 0.70 + 0.30 * np.cos(petals * ang)
        dist_mod = dist / np.maximum(1e-4, radial)
        mask = np.exp(-(dist_mod ** 2) / (2.0 * sigma2))
    else:
        mask = np.exp(-dist2 / (2.0 * sigma2))

    # Voice-driven grain texture on top of the base brush shape.
    if texture > 0.0:
        noise = np.random.uniform(1.0 - texture, 1.0, size=mask.shape).astype(np.float32)
        mask *= noise

    mask *= max(0.0, min(1.0, alpha))

    region = canvas[y0:y1, x0:x1, :]
    blend = mask[..., None]
    target = np.array(color_rgb, dtype=np.float32)[None, None, :]
    region[:] = region * (1.0 - blend) + target * blend


def add_impressionistic_splatter(canvas, cx, cy, color_rgb, strength, shape_kind="circle", texture=0.0):
    if not np.isfinite(cx) or not np.isfinite(cy):
        return
    if not np.isfinite(strength):
        return

    strength = max(0.0, min(1.0, float(strength)))
    n = int(2 + strength * 8)
    for _ in range(n):
        angle = random.uniform(0.0, 2.0 * math.pi)
        dist = random.uniform(4.0, 95.0 + 250.0 * strength)
        rx = cx + math.cos(angle) * dist
        ry = cy + math.sin(angle) * dist
        radius = random.uniform(6.0, 14.0 + 30.0 * strength)
        alpha = random.uniform(0.10, 0.22 + 0.22 * strength)
        add_soft_stamp(canvas, rx, ry, radius, color_rgb, alpha, shape_kind=shape_kind, texture=texture)


def choose_brush_shape(rms, centroid, zcr):
    """Pick brush shape from audio features so voice changes texture and geometry."""
    if zcr > 0.22:
        candidates = ["star", "ring", "diamond", "circle"]
    elif centroid > 0.45:
        candidates = ["diamond", "square", "ring", "circle"]
    elif rms > 0.16:
        candidates = ["square", "circle", "diamond", "ring"]
    else:
        candidates = ["circle", "diamond", "square", "ring"]
    return random.choice(candidates)


def pix_to_canvas(px, py):
    if not np.isfinite(px) or not np.isfinite(py):
        return None

    nx = (px / ACTIVE_SCREEN_WIDTH) + 0.5
    ny = 0.5 - (py / ACTIVE_SCREEN_HEIGHT)
    nx = max(0.0, min(1.0, nx))
    ny = max(0.0, min(1.0, ny))

    x = nx * (CANVAS_W - 1)
    y = ny * (CANVAS_H - 1)
    return x, y


def save_canvas(canvas, out_path):
    arr = np.clip(canvas * 255.0, 0, 255).astype(np.uint8)
    if PIL_OK:
        Image.fromarray(arr, mode="RGB").save(str(out_path))
        return str(out_path)

    npy_path = out_path.with_suffix(".npy")
    np.save(npy_path, canvas)
    return str(npy_path)


# ============================================================================
# 6. VISUAL FLOW
# ============================================================================
def show_intro(win):
    text = visual.TextStim(
        win,
        text=(
            "APP 4: MALOWANIE GLOSEM I WZROKIEM\n\n"
            "Patrz tam, gdzie chcesz malowac.\n"
            "Mow do mikrofonu, a barwa i puls pedzla beda sie zmieniac\n"
            "na podstawie cech dzwieku (glosnosc + widmo), nie znaczenia slow.\n\n"
            "Sterowanie:\n"
            "SPACE = zakoncz obraz\n"
            "C = wyczysc plotno\n"
            "S = zapisz obraz teraz\n"
            "ESC = wyjscie\n\n"
            "SPACJA = start"
        ),
        color="white",
        height=30,
        wrapWidth=1600,
    )
    text.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    return "escape" not in keys


def show_outro(win, saved_path):
    txt = visual.TextStim(
        win,
        text=(
            "Gotowe. Twoj obraz zostal zapisany.\n\n"
            f"Plik: {saved_path}\n\n"
            "SPACJA = zakoncz"
        ),
        color="white",
        height=32,
        wrapWidth=1700,
    )

    while True:
        reveal_cursor_if_moved(win)
        txt.draw()
        win.flip()
        keys = event.getKeys(["space", "escape"])
        if keys:
            return


def show_checkpoint(win):
    txt = visual.TextStim(
        win,
        text=(
            "Kalibracja zakonczona.\n"
            "Zaraz startuje sesja malowania.\n\n"
            "ENTER = start sesji\n"
            "ESC = wyjscie"
        ),
        color="white",
        height=32,
        wrapWidth=1500,
    )
    txt.draw()
    win.flip()
    keys = event.waitKeys(keyList=["return", "escape"])
    return "escape" not in keys


def show_runtime_error(win, err):
    msg = str(err)
    if len(msg) > 500:
        msg = msg[:500] + "..."
    txt = visual.TextStim(
        win,
        text=(
            "APP 4 - blad wykonania\n\n"
            "Aplikacja nie zamknela sie cicho, tylko przechwycila blad.\n"
            "Skopiuj ten komunikat i wyslij prowadzacemu:\n\n"
            f"{msg}\n\n"
            "SPACJA = zamknij"
        ),
        color="white",
        height=26,
        wrapWidth=1700,
    )
    while True:
        txt.draw()
        win.flip()
        keys = event.getKeys(["space", "escape", "return"])
        if keys:
            return


def run_session(win, collector):
    update_active_screen_size(win)
    view_w = ACTIVE_SCREEN_WIDTH
    view_h = ACTIVE_SCREEN_HEIGHT

    base_canvas = build_base_canvas(CANVAS_W, CANVAS_H)
    canvas = base_canvas.copy()
    frame_tex = np.clip(canvas * 2.0 - 1.0, -1.0, 1.0).astype(np.float32)
    try:
        image = visual.ImageStim(
            win,
            image=frame_tex,
            units="pix",
            size=(view_w, view_h),
            pos=(0, 0),
            interpolate=True,
        )
    except Exception:
        image = visual.ImageStim(
            win,
            image=frame_tex,
            units="pix",
            size=(view_w, view_h),
            pos=(0, 0),
            interpolate=False,
        )

    vignette = None

    status = visual.TextStim(
        win,
        text="",
        color=[0.72, 0.72, 0.72],
        height=14,
        pos=(0, -0.46 * view_h),
        wrapWidth=1800,
    )

    smoother = GazeSmoother()
    voice = VoiceAnalyzer()
    voice.start()

    hue = random.random()
    pulse_phase = 0.0

    clock = core.Clock()
    frame_clock = core.Clock()
    start_guard_until = 0.60

    saved_path = None
    render_warned = False
    brush_shape = "circle"
    status_update_t = 0.0
    smooth_rms = 0.0
    smooth_centroid = 0.0
    smooth_zcr = 0.0

    try:
        while True:
            dt = max(1e-4, frame_clock.getTime())
            frame_clock.reset()

            now_t = clock.getTime()
            if now_t > SESSION_SECONDS:
                break

            reveal_cursor_if_moved(win)
            keys = event.getKeys(["escape", "space", "c", "s"])
            if "escape" in keys:
                return None
            # Ignore stale SPACE keypress right after calibration/instructions.
            if "space" in keys and now_t >= start_guard_until:
                break
            if "c" in keys:
                canvas = base_canvas.copy()
            if "s" in keys:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                candidate = HERE / f"app4_artwork_{ts}.png"
                saved_path = save_canvas(canvas, candidate)

            gaze = collector.get_gaze_pix()
            rms, centroid, zcr = voice.get_features(dt)

            # Smooth readout to avoid a "dancing" status line.
            smooth_rms = 0.90 * smooth_rms + 0.10 * rms
            smooth_centroid = 0.90 * smooth_centroid + 0.10 * centroid
            smooth_zcr = 0.90 * smooth_zcr + 0.10 * zcr

            # Reduce mic sensitivity: ignore quiet-room noise and compress dynamics.
            # Normal speaking volume should still expand the brush steadily.
            rms_floor = 0.035
            rms_eff = max(0.0, rms - rms_floor)
            rms_drive = min(1.0, math.sqrt(rms_eff / 0.22))

            pulse_phase += dt * (1.5 + 6.0 * centroid)
            pulse = 0.5 + 0.5 * math.sin(pulse_phase * 2.0 * math.pi)

            hue = (hue + dt * (0.04 + 0.5 * centroid + 0.22 * zcr + 0.10 * pulse)) % 1.0
            sat = max(0.35, min(1.0, 0.45 + 0.9 * centroid))
            val = max(0.35, min(1.0, 0.45 + 1.15 * rms_drive + 0.2 * pulse))
            rgb = colorsys.hsv_to_rgb(hue, sat, val)
            brush_shape = choose_brush_shape(rms, centroid, zcr)
            brush_texture = max(0.0, min(0.65, 0.08 + 1.4 * zcr + 0.28 * rms_drive))

            if gaze is not None:
                sx, sy, speed = smoother.update(gaze[0], gaze[1], now_t)
                xy = pix_to_canvas(sx, sy)
                if xy is None:
                    continue
                cx, cy = xy

                # Bigger and more permanent-feeling blobs.
                brush_radius = 16.0 + 92.0 * rms_drive + 18.0 * pulse + min(30.0, speed * 0.010)
                brush_alpha = max(0.12, min(0.62, 0.16 + 0.36 * rms_drive + 0.16 * pulse))

                add_soft_stamp(
                    canvas,
                    cx,
                    cy,
                    brush_radius,
                    rgb,
                    brush_alpha,
                    shape_kind=brush_shape,
                    texture=brush_texture,
                )
                add_impressionistic_splatter(
                    canvas,
                    cx,
                    cy,
                    rgb,
                    min(1.0, 0.25 + rms_drive * 1.7),
                    shape_kind=brush_shape,
                    texture=brush_texture,
                )

            # Keep strokes permanent; this app should behave like a paintbrush.
            canvas[:] = np.clip(canvas, 0.0, 1.0)

            frame_tex = np.clip(canvas * 2.0 - 1.0, -1.0, 1.0).astype(np.float32)
            try:
                image.image = frame_tex
                image.draw()
            except Exception as exc:
                if not render_warned:
                    print(f"[APP4] Warning: texture update fallback enabled ({exc})")
                    render_warned = True
                image = visual.ImageStim(
                    win,
                    image=frame_tex,
                    units="pix",
                    size=(view_w, view_h),
                    pos=(0, 0),
                    interpolate=False,
                )
                image.draw()
            if vignette is not None:
                vignette.draw()

            if now_t >= status_update_t:
                status.text = (
                    f"MIC: {voice.mode} | glosnosc={smooth_rms:.3f}  widmo={smooth_centroid:.3f}"
                    f"  ziarnistosc={smooth_zcr:.3f} | pedzel: {brush_shape}"
                    f" | czas: {int(max(0, SESSION_SECONDS - now_t))}s"
                )
                status_update_t = now_t + 0.18
            status.draw()

            win.flip()
    finally:
        voice.stop()

    if saved_path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        candidate = HERE / f"app4_artwork_{ts}.png"
        saved_path = save_canvas(canvas, candidate)

    return saved_path


# ============================================================================
# 7. MAIN
# ============================================================================
def main():
    eyetracker = connect_eyetracker()
    if eyetracker is None:
        print("Brak eye-trackera. Podlacz Tobii i uruchom ponownie.")
        return

    win = visual.Window(
        size=(SCREEN_WIDTH, SCREEN_HEIGHT),
        units="pix",
        fullscr=FULLSCREEN,
        color=[-0.96, -0.96, -0.96],
        waitBlanking=True,
    )

    update_active_screen_size(win)

    init_hidden_cursor(win)

    try:
        if not show_intro(win):
            return

        cal_result = run_calibration(win, eyetracker)
        if cal_result is None:
            print("Kalibracja anulowana.")
            return

        # Flush key events so held SPACE from previous screens does not end session.
        event.clearEvents(eventType="keyboard")
        core.wait(0.15)
        event.clearEvents(eventType="keyboard")

        if not show_checkpoint(win):
            return

        event.clearEvents(eventType="keyboard")

        collector = GazeCollector(eyetracker, win=win)
        collector.start()

        try:
            try:
                saved_path = run_session(win, collector)
            except Exception as exc:
                print(f"[APP4] Runtime error: {exc}")
                show_runtime_error(win, exc)
                return
            if saved_path is None:
                return
            show_outro(win, saved_path)
        finally:
            collector.stop()

    finally:
        win.close()
        core.quit()


if __name__ == "__main__":
    main()
