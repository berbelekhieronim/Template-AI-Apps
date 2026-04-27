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

Press ESC at any time to quit.
"""

import sys
from pathlib import Path

# ============================================================================
# 0. TOBII SDK SETUP
# ============================================================================
HERE = Path(__file__).resolve().parent
SDK_PATH = HERE.parent / "x3-120 SDK" / "64"

if not SDK_PATH.exists():
    raise FileNotFoundError(f"Tobii SDK not found at: {SDK_PATH}")

sdk_str = str(SDK_PATH)
if sdk_str not in sys.path:
    sys.path.insert(0, sdk_str)

# ============================================================================
# 1. IMPORTS
# ============================================================================
try:
    from psychopy import visual, core, event, logging
    logging.console.setLevel(logging.ERROR)
except ImportError as exc:
    raise ImportError(
        "\n\nPsychoPy is not installed.\n"
        "Install it with: pip install psychopy\n"
        "Or download standalone from https://www.psychopy.org/download.html\n"
    ) from exc

import tobii_research as tr

# ============================================================================
# 2. CONSTANTS
# ============================================================================
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN = True

CAL_ACTIVE_COLOR = "white"
CAL_DOT_RADIUS = 20
GAZE_CURSOR_RADIUS = 15
GAZE_CURSOR_COLOR = [1.0, 0.2, 0.2]

CALIBRATION_POINTS = [
    (0.5, 0.5),
    (0.1, 0.1),
    (0.9, 0.1),
    (0.9, 0.9),
    (0.1, 0.9),
]


# ============================================================================
# 3. HELPERS
# ============================================================================
def norm_to_pix(nx, ny):
    px = (nx - 0.5) * SCREEN_WIDTH
    py = (0.5 - ny) * SCREEN_HEIGHT
    return px, py


def connect_eyetracker():
    print("\n[AI TEMPLATE] Searching for eye tracker...")
    trackers = tr.find_all_eyetrackers()
    if not trackers:
        print("[AI TEMPLATE] No eye tracker found.")
        return None

    et = trackers[0]
    print(f"[AI TEMPLATE] Connected  : {et.model}")
    print(f"[AI TEMPLATE] Serial     : {et.serial_number}")
    print(f"[AI TEMPLATE] Address    : {et.address}")
    return et


class GazeCollector:
    def __init__(self, eyetracker):
        self._et = eyetracker
        self._last = None
        self.active = False

    def start(self):
        self._et.subscribe_to(
            tr.EYETRACKER_GAZE_DATA,
            self._callback,
            as_dictionary=True,
        )
        self.active = True
        print("[AI TEMPLATE] Gaze stream started.")

    def stop(self):
        if self.active:
            self._et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._callback)
        self.active = False
        print("[AI TEMPLATE] Gaze stream stopped.")

    def _callback(self, data):
        self._last = data

    def get_gaze_pix(self):
        d = self._last
        if d is None:
            return None

        xs, ys = [], []
        if d["left_gaze_point_validity"]:
            xs.append(d["left_gaze_point_on_display_area"][0])
            ys.append(d["left_gaze_point_on_display_area"][1])
        if d["right_gaze_point_validity"]:
            xs.append(d["right_gaze_point_on_display_area"][0])
            ys.append(d["right_gaze_point_on_display_area"][1])

        if not xs:
            return None

        return norm_to_pix(sum(xs) / len(xs), sum(ys) / len(ys))


def run_calibration(win, eyetracker):
    calibration = tr.ScreenBasedCalibration(eyetracker)
    calibration.enter_calibration_mode()
    print("[AI TEMPLATE] Calibration mode entered.")

    dot = visual.Circle(win, radius=CAL_DOT_RADIUS, fillColor=CAL_ACTIVE_COLOR, lineColor=None)
    inner = visual.Circle(win, radius=4, fillColor="black", lineColor=None)
    instruction = visual.TextStim(
        win,
        text="Look at each dot as it appears.\n\nPress SPACE to begin.",
        height=28,
        color="white",
        pos=(0, 0),
    )

    instruction.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        calibration.leave_calibration_mode()
        return False

    for nx, ny in CALIBRATION_POINTS:
        px, py = norm_to_pix(nx, ny)
        for frame in range(60):
            dot.radius = max(8, CAL_DOT_RADIUS - frame * 0.25)
            dot.pos = (px, py)
            inner.pos = (px, py)
            dot.draw()
            inner.draw()
            win.flip()

        calibration.collect_data(nx, ny)
        core.wait(0.3)

        if "escape" in event.getKeys():
            calibration.leave_calibration_mode()
            return False

    result = calibration.compute_and_apply()
    calibration.leave_calibration_mode()

    success = result.status == tr.CALIBRATION_STATUS_SUCCESS
    status_text = "Calibration OK!" if success else "Calibration FAILED - try again."
    print(f"[AI TEMPLATE] {status_text}")

    msg = visual.TextStim(win, text=status_text, height=32, color="white")
    msg.draw()
    win.flip()
    core.wait(1.5)

    return success


def run_gaze_demo(win, gaze_collector):
    cursor = visual.Circle(
        win,
        radius=GAZE_CURSOR_RADIUS,
        fillColor=GAZE_CURSOR_COLOR,
        lineColor=None,
        opacity=0.8,
    )
    mode_label = visual.TextStim(
        win,
        text="LIVE - Tobii X3-120",
        height=20,
        color="lime",
        pos=(-SCREEN_WIDTH // 2 + 10, SCREEN_HEIGHT // 2 - 20),
        anchorHoriz="left",
        anchorVert="top",
    )
    instructions = visual.TextStim(
        win,
        text="Gaze tracking active | ESC to quit",
        height=22,
        color="white",
        pos=(0, -SCREEN_HEIGHT // 2 + 30),
    )
    no_signal = visual.TextStim(win, text="No gaze signal", height=22, color="orange")

    gaze_collector.start()

    while True:
        if "escape" in event.getKeys():
            break

        gaze_pix = gaze_collector.get_gaze_pix()

        win.clearBuffer()
        instructions.draw()
        mode_label.draw()

        if gaze_pix is not None:
            cursor.pos = gaze_pix
            cursor.draw()
        else:
            no_signal.draw()

        win.flip()

    gaze_collector.stop()


# ============================================================================
# 4. ENTRY POINT
# ============================================================================
def main():
    eyetracker = connect_eyetracker()

    win = visual.Window(
        size=(SCREEN_WIDTH, SCREEN_HEIGHT),
        fullscr=FULLSCREEN,
        color="black",
        units="pix",
        screen=0,
    )

    if eyetracker is None:
        msg = visual.TextStim(
            win,
            text="No eye tracker found.\n\nMake sure the Tobii X3-120 is plugged in.\n\nPress any key to quit.",
            height=30,
            color="orange",
            wrapWidth=900,
        )
        msg.draw()
        win.flip()
        event.waitKeys()
        win.close()
        return

    calibrated = run_calibration(win, eyetracker)
    if not calibrated:
        win.close()
        return

    gaze_collector = GazeCollector(eyetracker)
    run_gaze_demo(win, gaze_collector)

    win.close()
    print("[AI TEMPLATE] Done.")


if __name__ == "__main__":
    main()
