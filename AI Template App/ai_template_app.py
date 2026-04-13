#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI TEMPLATE APP
===============
Eye Tracking starter template using Tobii X3-120 + PsychoPy.

Structure for students:
  1. SDK setup & device connection
  2. 5-point screen-based calibration
  3. Gaze data streaming with live cursor
  4. Clean shutdown

Press  ESC  at any time to quit.
"""

import sys
import time
from pathlib import Path

# ============================================================================
# 1. SDK PATH  –  must come before any tobii_research import
# ============================================================================
HERE = Path(__file__).resolve().parent        # …/AI Template App/
SDK_PATH = HERE.parent / "x3-120 SDK" / "64"

if not SDK_PATH.exists():
    raise FileNotFoundError(f"Tobii SDK not found at: {SDK_PATH}")

sdk_str = str(SDK_PATH)
if sdk_str not in sys.path:
    sys.path.insert(0, sdk_str)

# ============================================================================
# 2. IMPORTS
# ============================================================================
import tobii_research as tr
from psychopy import visual, core, event, logging

logging.console.setLevel(logging.ERROR)   # suppress PsychoPy noise

# ============================================================================
# 3. CONSTANTS  –  tweak these to change behaviour
# ============================================================================
SCREEN_WIDTH  = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN    = True

# Calibration dot colours
CAL_ACTIVE_COLOR  = "white"
CAL_DONE_COLOR    = "green"
CAL_DOT_RADIUS    = 20   # pixels

# Gaze cursor
GAZE_CURSOR_RADIUS = 15
GAZE_CURSOR_COLOR  = [1.0, 0.2, 0.2]   # red-ish

# ============================================================================
# 4. HELPERS  –  coordinate conversion
# ============================================================================
def norm_to_pix(nx, ny):
    """
    Convert Tobii normalised display-area coords (0–1, origin top-left)
    to PsychoPy pixel coords (origin centre, y up).
    """
    px = (nx - 0.5) * SCREEN_WIDTH
    py = (0.5 - ny) * SCREEN_HEIGHT
    return px, py


# ============================================================================
# 5. DEVICE CONNECTION
# ============================================================================
def connect_eyetracker():
    """
    Discover the first available Tobii eye tracker and return it.
    Returns None if no device is found.
    """
    print("\n[AI TEMPLATE] Searching for eye tracker...")
    trackers = tr.find_all_eyetrackers()

    if not trackers:
        print("[AI TEMPLATE] No eye tracker found.")
        return None

    et = trackers[0]
    print(f"[AI TEMPLATE] Connected  : {et.model}")
    print(f"[AI TEMPLATE] Serial     : {et.serial_number}")
    print(f"[AI TEMPLATE] Address    : {et.address}")
    print(f"[AI TEMPLATE] Frequencies: {et.get_all_gaze_output_frequencies()} Hz")

    return et


# ============================================================================
# 6. GAZE COLLECTOR
# ============================================================================
class GazeCollector:
    """
    Subscribes to the Tobii gaze stream and keeps the most recent sample.

    Usage:
        gc = GazeCollector(eyetracker)
        gc.start()
        x, y = gc.get_gaze_pix()   # current gaze in PsychoPy pixels
        gc.stop()
    """

    def __init__(self, eyetracker):
        self._et      = eyetracker
        self._last    = None          # most recent raw gaze dict
        self.active   = False

    # ---- subscription lifecycle ----

    def start(self):
        self._et.subscribe_to(
            tr.EYETRACKER_GAZE_DATA,
            self._callback,
            as_dictionary=True
        )
        self.active = True
        print("[AI TEMPLATE] Gaze stream started.")

    def stop(self):
        self._et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._callback)
        self.active = False
        print("[AI TEMPLATE] Gaze stream stopped.")

    # ---- callback (runs in Tobii thread) ----

    def _callback(self, data):
        self._last = data

    # ---- read helpers ----

    def get_gaze_norm(self):
        """
        Return averaged gaze position as normalised (x, y) or None if invalid.
        Averages left and right eye; falls back to whichever eye is valid.
        """
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

        return sum(xs) / len(xs), sum(ys) / len(ys)

    def get_gaze_pix(self):
        """
        Return gaze position in PsychoPy pixel coordinates or None.
        """
        norm = self.get_gaze_norm()
        if norm is None:
            return None
        return norm_to_pix(*norm)


# ============================================================================
# 7. CALIBRATION  –  5-point screen-based
# ============================================================================
CALIBRATION_POINTS = [
    (0.5,  0.5),   # centre
    (0.1,  0.1),   # top-left
    (0.9,  0.1),   # top-right
    (0.9,  0.9),   # bottom-right
    (0.1,  0.9),   # bottom-left
]

def run_calibration(win, eyetracker):
    """
    Run a 5-point screen-based calibration.
    Returns True on success, False on failure.
    """
    calibration = tr.ScreenBasedCalibration(eyetracker)
    calibration.enter_calibration_mode()
    print("[AI TEMPLATE] Calibration mode entered.")

    dot = visual.Circle(
        win, radius=CAL_DOT_RADIUS,
        fillColor=CAL_ACTIVE_COLOR, lineColor=None
    )
    inner = visual.Circle(
        win, radius=4,
        fillColor="black", lineColor=None
    )
    instruction = visual.TextStim(
        win, text="Look at each dot as it appears.\n\nPress SPACE to begin.",
        height=28, color="white", pos=(0, 0)
    )

    # --- wait for SPACE ---
    instruction.draw()
    win.flip()
    event.waitKeys(keyList=["space", "escape"])
    if "escape" in event.getKeys():
        calibration.leave_calibration_mode()
        return False

    # --- collect samples at each point ---
    for nx, ny in CALIBRATION_POINTS:
        px, py = norm_to_pix(nx, ny)

        # Animate dot shrinking so participant knows when to fixate
        for frame in range(60):              # ~1 s at 60 fps
            dot.radius = CAL_DOT_RADIUS * (1 - frame / 80)
            dot.pos    = (px, py)
            inner.pos  = (px, py)
            dot.draw()
            inner.draw()
            win.flip()

        calibration.collect_data(nx, ny)

        # Flash green to confirm
        dot.fillColor = CAL_DONE_COLOR
        dot.radius    = CAL_DOT_RADIUS
        dot.draw()
        inner.draw()
        win.flip()
        core.wait(0.3)

        dot.fillColor = CAL_ACTIVE_COLOR

        if "escape" in event.getKeys():
            calibration.leave_calibration_mode()
            return False

    # --- compute result ---
    result = calibration.compute_and_apply()
    calibration.leave_calibration_mode()

    success = result.status == tr.CALIBRATION_STATUS_SUCCESS
    status_text = "Calibration OK!" if success else "Calibration FAILED – try again."
    print(f"[AI TEMPLATE] {status_text}")

    msg = visual.TextStim(win, text=status_text, height=32, color="white")
    msg.draw()
    win.flip()
    core.wait(1.5)

    return success


# ============================================================================
# 8. MAIN LOOP  –  live gaze visualisation
# ============================================================================
def run_gaze_demo(win, gaze_collector):
    """
    Draw a gaze cursor that follows the participant's eyes in real time.
    Press ESC to exit.

    -----------------------------------------------------------------
    STUDENT EXERCISE:  replace or extend this function with your own
    experiment logic.  gaze_collector.get_gaze_pix() gives you the
    current eye position on every frame.
    -----------------------------------------------------------------
    """
    cursor = visual.Circle(
        win,
        radius=GAZE_CURSOR_RADIUS,
        fillColor=GAZE_CURSOR_COLOR,
        lineColor=None,
        opacity=0.8
    )
    instructions = visual.TextStim(
        win,
        text="Gaze tracking active\nESC to quit",
        height=22, color="white",
        pos=(0, -SCREEN_HEIGHT // 2 + 40),
        anchorVert="bottom"
    )
    no_signal = visual.TextStim(
        win, text="No gaze signal", height=22, color="orange"
    )

    gaze_collector.start()

    while True:
        if "escape" in event.getKeys():
            break

        gaze_pix = gaze_collector.get_gaze_pix()

        win.clearBuffer()
        instructions.draw()

        if gaze_pix is not None:
            cursor.pos = gaze_pix
            cursor.draw()
        else:
            no_signal.draw()

        win.flip()

    gaze_collector.stop()


# ============================================================================
# 9. ENTRY POINT
# ============================================================================
def main():
    # --- connect ---
    eyetracker = connect_eyetracker()

    win = visual.Window(
        size=(SCREEN_WIDTH, SCREEN_HEIGHT),
        fullscr=FULLSCREEN,
        color="black",
        units="pix",
        screen=0
    )

    if eyetracker is None:
        msg = visual.TextStim(
            win,
            text="No eye tracker found.\n\nMake sure the Tobii X3-120 is plugged in.\n\nPress any key to quit.",
            height=30, color="orange", wrapWidth=900
        )
        msg.draw()
        win.flip()
        event.waitKeys()
        win.close()
        return

    # --- calibrate ---
    calibrated = run_calibration(win, eyetracker)
    if not calibrated:
        win.close()
        return

    # --- stream gaze ---
    gaze_collector = GazeCollector(eyetracker)
    run_gaze_demo(win, gaze_collector)

    win.close()
    print("[AI TEMPLATE] Done.")


if __name__ == "__main__":
    main()
