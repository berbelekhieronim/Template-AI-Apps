#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APP 2 - WTYCZKA ANTYIMPULS

Prototyp wtyczki do przegladarki internetowej:
- kalibracja eye-trackera,
- pseudoekran zakupowy z przyciskiem "KUP TERAZ",
- podczas patrzenia na przycisk nastepuje plynne wygaszanie przez 5 s,
- po pelnym wygaszeniu: ekran gratulacyjny.
"""

import sys
from pathlib import Path

# ============================================================================
# 0. TRYB URUCHOMIENIA
# ============================================================================
HERE = Path(__file__).resolve().parent
SDK_PATH = HERE.parent / "x3-120 SDK" / "64"

print()
print("=" * 62)
print(" APP 2 - WTYCZKA ANTYIMPULS | WYBOR TRYBU")
print("=" * 62)
print("[1] TRYB DEV        (mysz = spojrzenie)")
print("[2] TRYB NAUCZYCIELA (realny Tobii X3-120)")
print()

while True:
    wybor = input("Wybierz tryb (1 lub 2): ").strip()
    if wybor in ("1", "2"):
        break
    print("Podaj 1 albo 2.")

DEV_MODE = wybor == "1"
print("Uruchamiam:", "TRYB DEV" if DEV_MODE else "TRYB NAUCZYCIELA")

if not DEV_MODE:
    if not SDK_PATH.exists():
        raise FileNotFoundError(f"Nie znaleziono SDK Tobii: {SDK_PATH}")
    sdk_str = str(SDK_PATH)
    if sdk_str not in sys.path:
        sys.path.insert(0, sdk_str)

# ============================================================================
# 1. IMPORTY
# ============================================================================
try:
    from psychopy import core, event, logging, visual
except ImportError as exc:
    raise ImportError("Brak PsychoPy. Zainstaluj: pip install psychopy") from exc

if not DEV_MODE:
    import tobii_research as tr

logging.console.setLevel(logging.ERROR)

# ============================================================================
# 2. STALE
# ============================================================================
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN = True

FADE_SECONDS = 5.0

# ============================================================================
# 3. GAZE + KALIBRACJA
# ============================================================================
def norm_to_pix(nx, ny):
    px = (nx - 0.5) * SCREEN_WIDTH
    py = (0.5 - ny) * SCREEN_HEIGHT
    return px, py


def rect_contains(rect, x, y):
    return rect[0] <= x <= rect[1] and rect[2] <= y <= rect[3]


class GazeCollector:
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
            return

        self._et.subscribe_to(
            tr.EYETRACKER_GAZE_DATA,
            self._callback,
            as_dictionary=True,
        )
        self.active = True

    def stop(self):
        if not DEV_MODE and self.active:
            self._et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._callback)
        self.active = False

    def _callback(self, data):
        self._last = data

    def get_gaze_pix(self):
        if DEV_MODE:
            if self._mouse is None:
                return None
            return self._mouse.getPos()

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

        return norm_to_pix(sum(xs) / len(xs), sum(ys) / len(ys))


def connect_eyetracker():
    if DEV_MODE:
        return "DEV"

    trackery = tr.find_all_eyetrackers()
    if not trackery:
        return None

    et = trackery[0]
    print(f"Polaczono: {et.model} | SN: {et.serial_number}")
    return et


def run_calibration(win, eyetracker):
    if DEV_MODE:
        info = visual.TextStim(
            win,
            text=(
                "TRYB DEV\n"
                "Kalibracja pomijana (mysz symuluje spojrzenie).\n\n"
                "Nacisnij SPACJE, aby przejsc dalej."
            ),
            color="yellow",
            height=32,
            wrapWidth=1300,
        )
        info.draw()
        win.flip()
        keys = event.waitKeys(keyList=["space", "escape"])
        return "escape" not in keys

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
        return False

    for nx, ny in points:
        px, py = norm_to_pix(nx, ny)
        for frame in range(48):
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
    return result.status == tr.CALIBRATION_STATUS_SUCCESS


# ============================================================================
# 4. EKRANY
# ============================================================================
def pokaz_instrukcje(win):
    txt = visual.TextStim(
        win,
        text=(
            "PROTOTYP WTYCZKI ANTYIMPULS\n\n"
            "Po kalibracji zobaczysz strone zakupowa.\n"
            "Jesli spojrzysz na przycisk KUP TERAZ, zacznie sie plynnie wygaszac.\n"
            "Po 5 sekundach patrzenia przycisk zniknie calkowicie.\n\n"
            "SPACJA = dalej, ESC = wyjscie"
        ),
        color="white",
        height=27,
        font="Verdana",
        wrapWidth=1450,
    )
    txt.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    return "escape" not in keys


def ekran_sukcesu(win):
    panel = visual.Rect(
        win,
        width=1500,
        height=560,
        pos=(0, 0),
        fillColor=[-0.82, -0.92, -0.82],
        lineColor=[-0.35, 0.2, -0.35],
        lineWidth=2,
    )
    txt = visual.TextStim(
        win,
        text=(
            "BRAWO!\n\n"
            "Gratuluje wytrwalosci!\n"
            "Udalo Ci sie opanowac kompulsywne zakupy.\n"
            "Zdobywasz kolejny % w naszym programie rabatowym\n"
            "na uslugi z zakresu dbania o zdrowie psychiczne.\n\n"
            "SPACJA = zakoncz"
        ),
        color=[-0.55, 0.25, -0.55],
        height=34,
        font="Verdana",
        wrapWidth=1500,
    )

    while True:
        panel.draw()
        txt.draw()
        win.flip()
        keys = event.getKeys(["space", "escape"])
        if keys:
            return


def run_browser_mockup(win, collector):
    # Ramka pseudo-przegladarki
    browser = visual.Rect(
        win,
        width=1680,
        height=940,
        pos=(0, 0),
        fillColor=[-0.96, -0.95, -0.93],
        lineColor=[0.1, 0.1, 0.1],
        lineWidth=2,
    )

    topbar = visual.Rect(
        win,
        width=1680,
        height=64,
        pos=(0, 438),
        fillColor=[-0.62, -0.62, -0.62],
        lineColor=[-0.62, -0.62, -0.62],
    )

    address = visual.Rect(
        win,
        width=1180,
        height=42,
        pos=(120, 438),
        fillColor=[-0.98, -0.98, -0.98],
        lineColor=[0.2, 0.2, 0.2],
    )

    address_text = visual.TextStim(
        win,
        text="https://luksus-sale.example/gucci-torebka",
        color=[-0.2, -0.2, -0.2],
        height=18,
        font="Verdana",
        pos=(120, 438),
    )

    # Promo
    hero = visual.Rect(
        win,
        width=1450,
        height=330,
        pos=(0, 170),
        fillColor=[0.15, -0.2, -0.2],
        lineColor=[0.65, 0.2, 0.2],
        lineWidth=2,
    )

    promo_main = visual.TextStim(
        win,
        text="PROMOCJA -70%",
        color="white",
        height=58,
        font="Verdana",
        pos=(0, 250),
    )

    promo_desc = visual.TextStim(
        win,
        text="Torebka Gucci - teraz tylko 2999 zl",
        color="white",
        height=36,
        font="Verdana",
        pos=(0, 165),
    )

    # Pole platnosci
    card_box = visual.Rect(
        win,
        width=1450,
        height=300,
        pos=(0, -175),
        fillColor=[-0.88, -0.88, -0.88],
        lineColor=[0.2, 0.2, 0.2],
        lineWidth=1,
    )

    card_title = visual.TextStim(
        win,
        text="Dane platnosci:",
        color=[-0.2, -0.2, -0.2],
        height=24,
        font="Verdana",
        pos=(-520, -65),
        alignText="left",
    )

    card_num_label = visual.TextStim(
        win,
        text="Numer karty:",
        color=[-0.25, -0.25, -0.25],
        height=20,
        font="Verdana",
        pos=(-520, -130),
        alignText="left",
    )

    card_num_value = visual.TextStim(
        win,
        text="4242 1111 8888 5555",
        color=[-0.1, -0.1, -0.1],
        height=23,
        font="Verdana",
        pos=(-220, -130),
        alignText="left",
    )

    cvv_label = visual.TextStim(
        win,
        text="CVV:",
        color=[-0.25, -0.25, -0.25],
        height=20,
        font="Verdana",
        pos=(-520, -190),
        alignText="left",
    )

    cvv_value = visual.TextStim(
        win,
        text="731",
        color=[-0.1, -0.1, -0.1],
        height=23,
        font="Verdana",
        pos=(-420, -190),
        alignText="left",
    )

    exp_label = visual.TextStim(
        win,
        text="Waznosc:",
        color=[-0.25, -0.25, -0.25],
        height=20,
        font="Verdana",
        pos=(-250, -190),
        alignText="left",
    )

    exp_value = visual.TextStim(
        win,
        text="03/29",
        color=[-0.1, -0.1, -0.1],
        height=23,
        font="Verdana",
        pos=(-120, -190),
        alignText="left",
    )

    # Przycisk kup teraz
    button_w = 360
    button_h = 110
    button_pos = (470, -170)
    aoi_scale = 1.2
    aoi_half_w = (button_w * aoi_scale) / 2
    aoi_half_h = (button_h * aoi_scale) / 2
    button_rect = [
        button_pos[0] - aoi_half_w,
        button_pos[0] + aoi_half_w,
        button_pos[1] - aoi_half_h,
        button_pos[1] + aoi_half_h,
    ]

    buy_button_shadow = visual.Rect(
        win,
        width=button_w,
        height=button_h,
        pos=(button_pos[0] + 6, button_pos[1] - 6),
        fillColor=[0.18, -0.1, -0.1],
        lineColor=None,
        opacity=0.45,
    )

    buy_button = visual.Rect(
        win,
        width=button_w,
        height=button_h,
        pos=button_pos,
        fillColor=[0.95, 0.22, 0.22],
        lineColor=[0.55, 0.05, 0.05],
        lineWidth=2,
        opacity=1.0,
    )

    buy_text = visual.TextStim(
        win,
        text="KUP TERAZ",
        color="white",
        height=31,
        font="Verdana",
        pos=button_pos,
        opacity=1.0,
    )

    status_text = visual.TextStim(
        win,
        text="",
        color=[0.95, 0.78, -0.2],
        height=23,
        font="Verdana",
        pos=(460, -280),
        wrapWidth=480,
    )

    hint_text = visual.TextStim(
        win,
        text="Patrz na przycisk, aby uruchomic wygaszanie impulsu zakupowego.",
        color=[-0.15, -0.15, -0.15],
        height=19,
        font="Verdana",
        pos=(0, -365),
        wrapWidth=1450,
    )

    fade_progress = 0.0  # 0..1
    clock = core.Clock()
    prev_t = clock.getTime()

    collector.start()

    while True:
        now_t = clock.getTime()
        dt = max(0.0, now_t - prev_t)
        prev_t = now_t

        keys = event.getKeys(["escape"])
        if "escape" in keys:
            collector.stop()
            return False

        gaze = collector.get_gaze_pix()
        gaze_on_button = False
        if gaze is not None:
            gaze_on_button = rect_contains(button_rect, gaze[0], gaze[1])

        if gaze_on_button and fade_progress < 1.0:
            fade_progress = min(1.0, fade_progress + (dt / FADE_SECONDS))

        alpha = max(0.0, 1.0 - fade_progress)
        buy_button.opacity = alpha
        buy_text.opacity = alpha

        if fade_progress < 1.0:
            if gaze_on_button:
                remaining = max(0.0, FADE_SECONDS * (1.0 - fade_progress))
                status_text.text = f"Przycisk zniknie za {remaining:.1f} sekund"
            else:
                status_text.text = "Skieruj wzrok na KUP TERAZ, aby rozpoczac wygaszanie"
        else:
            status_text.text = ""

        browser.draw()
        topbar.draw()
        address.draw()
        address_text.draw()

        hero.draw()
        promo_main.draw()
        promo_desc.draw()

        card_box.draw()
        card_title.draw()
        card_num_label.draw()
        card_num_value.draw()
        cvv_label.draw()
        cvv_value.draw()
        exp_label.draw()
        exp_value.draw()
        hint_text.draw()

        if alpha > 0.0:
            buy_button_shadow.opacity = alpha * 0.45
            buy_button_shadow.draw()
            buy_button.draw()
            buy_text.draw()

        status_text.draw()
        win.flip()

        if fade_progress >= 1.0:
            collector.stop()
            return True


# ============================================================================
# 5. MAIN
# ============================================================================
def main():
    eyetracker = connect_eyetracker()

    win = visual.Window(
        size=(SCREEN_WIDTH, SCREEN_HEIGHT),
        fullscr=FULLSCREEN,
        color="black",
        units="pix",
    )

    if eyetracker is None:
        msg = visual.TextStim(
            win,
            text=(
                "Nie znaleziono eye-trackera Tobii.\n\n"
                "Podlacz urzadzenie lub uruchom aplikacje w TRYBIE DEV.\n"
                "Nacisnij dowolny klawisz, aby wyjsc."
            ),
            color="orange",
            height=32,
            wrapWidth=1400,
        )
        msg.draw()
        win.flip()
        event.waitKeys()
        win.close()
        return

    if not run_calibration(win, eyetracker):
        fail = visual.TextStim(
            win,
            text="Kalibracja nieudana lub przerwana.",
            color="orange",
            height=36,
        )
        fail.draw()
        win.flip()
        core.wait(1.2)
        win.close()
        return

    if not pokaz_instrukcje(win):
        win.close()
        return

    ok = run_browser_mockup(win, GazeCollector(eyetracker, win=win))
    if ok:
        ekran_sukcesu(win)

    win.close()


if __name__ == "__main__":
    main()
