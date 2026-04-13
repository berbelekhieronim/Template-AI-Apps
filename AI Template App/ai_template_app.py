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

---------------------------------------------------------------------
DEV_MODE  (set below)
---------------------------------------------------------------------
True  → runs on any laptop with no eye tracker.
        Your mouse cursor acts as the simulated gaze point.
        Use this while building your app.

False → real Tobii X3-120 mode.  Only works on the teacher's PC
        that has the tracker connected.  Set this to False before
        handing your code to the teacher for testing.
---------------------------------------------------------------------
"""

import sys
import time
import math
import random
from pathlib import Path

# ============================================================================
# 0. DEV_MODE  ← STUDENTS: change this flag
# ============================================================================
DEV_MODE = True   # True = mouse simulation  |  False = real Tobii tracker

# ============================================================================
# 1. SDK PATH  –  only needed when DEV_MODE is False
# ============================================================================
HERE     = Path(__file__).resolve().parent        # …/AI Template App/
SDK_PATH = HERE.parent / "x3-120 SDK" / "64"

if not DEV_MODE:
    if not SDK_PATH.exists():
        raise FileNotFoundError(f"Tobii SDK not found at: {SDK_PATH}")
    sdk_str = str(SDK_PATH)
    if sdk_str not in sys.path:
        sys.path.insert(0, sdk_str)

# ============================================================================
# 2. IMPORTS
# ============================================================================
try:
    from psychopy import visual, core, event, logging
    logging.console.setLevel(logging.ERROR)
except ImportError:
    raise ImportError(
        "\n\nPsychoPy is not installed.\n"
        "Install it with:  pip install psychopy\n"
        "Or download the standalone from https://www.psychopy.org/download.html\n"
    )

if not DEV_MODE:
    import tobii_research as tr

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
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI TEMPLATE APP
===============
Eye Tracking starter template using Tobii X3-120 + PsychoPy.

Structure for students:
  1. Mode selection (Dev / Teacher) at startup
  2. SDK setup & device connection
  3. 5-point screen-based calibration
  4. Gaze data streaming with live cursor
  5. Clean shutdown

Press  ESC  at any time to quit.
"""

import sys
import time
import math
import random
from pathlib import Path

# ============================================================================
# 0. STARTUP MODE SELECTION
# ============================================================================
HERE     = Path(__file__).resolve().parent
SDK_PATH = HERE.parent / "x3-120 SDK" / "64"

print()
print("=" * 50)
print("        AI TEMPLATE APP - Mode Selection")
print("=" * 50)
print()
print("  [1]  DEV MODE    - no eye tracker needed")
print("                     mouse cursor = gaze")
print()
print("  [2]  TEACHER MODE - real Tobii X3-120")
print("                     tracker must be plugged in")
print()

while True:
    choice = input("Select mode (1 or 2): ").strip()
    if choice in ("1", "2"):
        break
    print("  Please enter 1 or 2.")

DEV_MODE = (choice == "1")
print()
print("  Running in: " + ("DEV MODE (mouse simulation)" if DEV_MODE else "TEACHER MODE (real tracker)"))
print()

# ============================================================================
# 1. SDK PATH  -  only needed in Teacher Mode
# ============================================================================
if not DEV_MODE:
    if not SDK_PATH.exists():
        raise FileNotFoundError(f"Tobii SDK not found at: {SDK_PATH}")
    sdk_str = str(SDK_PATH)
    if sdk_str not in sys.path:
        sys.path.insert(0, sdk_str)

# ============================================================================
# 2. IMPORTS
# ============================================================================
try:
    from psychopy import visual, core, event, logging
    logging.console.setLevel(logging.ERROR)
except ImportError:
    raise ImportError(
        "\n\nPsychoPy is not installed.\n"
        "Install it with:  pip install psychopy\n"
        "Or download the standalone from https://www.psychopy.org/download.html\n"
    )

if not DEV_MODE:
    import tobii_research as tr

# ============================================================================
# 3. CONSTANTS
# ============================================================================
SCREEN_WIDTH  = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN    = True

CAL_ACTIVE_COLOR  = "white"
CAL_DONE_COLOR    = "green"
CAL_DOT_RADIUS    = 20

GAZE_CURSOR_RADIUS = 15
GAZE_CURSOR_COLOR  = [1.0, 0.2, 0.2]


# ============================================================================
# 4. HELPERS
# ============================================================================
def norm_to_pix(nx, ny):
    """Convert Tobii normalized coords to PsychoPy pixel coordinates."""
    px = (nx - 0.5) * SCREEN_WIDTH
    py = (0.5 - ny) * SCREEN_HEIGHT
    return px, py


# ============================================================================
# 5. DEVICE CONNECTION
# ============================================================================
def connect_eyetracker():
    """
    Discover the first available Tobii eye tracker and return it.
    In DEV_MODE returns a sentinel so the app can run without hardware.
    """
    if DEV_MODE:
        print("[AI TEMPLATE] DEV_MODE: skipping eye tracker, mouse will simulate gaze.")
        return "DEV_MODE"

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
    """Collects gaze samples from Tobii or mouse (DEV_MODE)."""

    def __init__(self, eyetracker, win=None):
        self._et = eyetracker
        self._win = win
        self._last = None
        self._mouse = None
        self.active = False

    def start(self):
        if DEV_MODE:
            self._mouse = event.Mouse(win=self._win)
            self.active = True
            print("[AI TEMPLATE] DEV_MODE gaze stream started (mouse simulation).")
            return

        self._et.subscribe_to(
            tr.EYETRACKER_GAZE_DATA,
            self._callback,
            as_dictionary=True,
        )
        self.active = True
        print("[AI TEMPLATE] Gaze stream started.")

    def stop(self):
        if not DEV_MODE and self.active:
            self._et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._callback)
        self.active = False
        print("[AI TEMPLATE] Gaze stream stopped.")

    def _callback(self, data):
        self._last = data

    def get_gaze_norm(self):
        """Return averaged gaze as normalized (x, y) in [0,1] or None."""
        if DEV_MODE:
            if self._mouse is None:
                return None
            mx, my = self._mouse.getPos()
            nx = (mx / SCREEN_WIDTH) + 0.5
            ny = 0.5 - (my / SCREEN_HEIGHT)
            return nx, ny

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
        """Return gaze position in PsychoPy pixel coordinates or None."""
        norm = self.get_gaze_norm()
        if norm is None:
            return None
        return norm_to_pix(*norm)


# ============================================================================
# 7. CALIBRATION  –  5-point screen-based (skipped in DEV_MODE)
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
    In DEV_MODE shows a message and skips straight to the experiment.
    Returns True on success, False on failure.
    """
    if DEV_MODE:
        msg = visual.TextStim(
            win,
            text="DEV MODE – calibration skipped.\n\nYour mouse cursor simulates gaze.\n\nPress SPACE to start.",
            height=30, color="yellow", wrapWidth=900
        )
        msg.draw()
        win.flip()
        event.waitKeys(keyList=["space", "escape"])
        return True

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

    instruction.draw()
    win.flip()
    event.waitKeys(keyList=["space", "escape"])
    if "escape" in event.getKeys():
        calibration.leave_calibration_mode()
        return False

    for nx, ny in CALIBRATION_POINTS:
        px, py = norm_to_pix(nx, ny)

        for frame in range(60):
            dot.radius = CAL_DOT_RADIUS * (1 - frame / 80)
            dot.pos    = (px, py)
            inner.pos  = (px, py)
            dot.draw()
            inner.draw()
            win.flip()

        calibration.collect_data(nx, ny)

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
    mode_label = visual.TextStim(
        win,
        text="DEV MODE – mouse = gaze" if DEV_MODE else "LIVE – Tobii X3-120",
        height=20,
        color="yellow" if DEV_MODE else "lime",
        pos=(-SCREEN_WIDTH // 2 + 10, SCREEN_HEIGHT // 2 - 20),
        anchorHoriz="left", anchorVert="top"
    )
    instructions = visual.TextStim(
        win,
        text="Gaze tracking active  |  ESC to quit",
        height=22, color="white",
        pos=(0, -SCREEN_HEIGHT // 2 + 30),
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
        mode_label.draw()

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

    calibrated = run_calibration(win, eyetracker)
    if not calibrated:
        win.close()
        return

    gaze_collector = GazeCollector(eyetracker, win)
    run_gaze_demo(win, gaze_collector)

    win.close()
    print("[AI TEMPLATE] Done.")


if __name__ == "__main__":
    main()
