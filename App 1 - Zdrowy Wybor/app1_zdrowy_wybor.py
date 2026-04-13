#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APP 1 - ZDROWY WYBOR

Eksperyment eye-tracking (5 prob):
- Po lewej: produkt + zlozone nazwy skladnikow
- Po prawej: produkt + proste nazwy skladnikow
- Uzytkownik wybiera zdrowsza opcje (strzalka lewo/prawo)
- Na koncu: heatmapy + analiza czynnikow decyzyjnych

Sterowanie:
- Lewo/Prawo: wybor
- Spacja: dalej
- ESC: wyjscie
"""

import csv
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# ============================================================================
# 0. WYBOR TRYBU
# ============================================================================
HERE = Path(__file__).resolve().parent
SDK_PATH = HERE.parent / "x3-120 SDK" / "64"

print()
print("=" * 56)
print("      APP 1 - ZDROWY WYBOR | WYBOR TRYBU")
print("=" * 56)
print("[1] TRYB DEV      (mysz = spojrzenie, bez eye-trackera)")
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
    raise ImportError(
        "Brak PsychoPy. Zainstaluj: pip install psychopy"
    ) from exc

if not DEV_MODE:
    import tobii_research as tr

logging.console.setLevel(logging.ERROR)

# ============================================================================
# 2. PARAMETRY
# ============================================================================
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN = True
N_TRIALS = 5
TRIAL_TIMEOUT = 12.0

LEFT_X = -460
RIGHT_X = 460
PRODUCT_Y = 170
ING_Y = -150

CARD_W = 480
CARD_H = 420
PACK_W = 280
PACK_H = 170

# ============================================================================
# 3. BAZA TRESCI
# ============================================================================
PRODUKTY = [
    "Baton proteinowy",
    "Baton owsiany",
    "Przekaska fitness",
    "Baton energetyczny",
    "Baton zbozowy",
]

SMAKI = ["kakao", "orzech", "wanilia", "kokos", "truskawka", "miod"]

SKLADNIKI_ZLOZONE = [
    "izolat bialek serwatkowych",
    "frakcjonowany blonnik akacjowy",
    "mieszanka tokoferoli",
    "emulgator lecytyny slonecznikowej",
    "koncentrat bialek mleka",
    "hydrolizowany kolagen rybi",
    "inulina z cykorii",
    "regulator kwasowosci: cytryniany sodu",
    "ekstrakt rozmarynu",
    "stabilizator pektyny",
]

SKLADNIKI_PROSTE = [
    "platki owsiane",
    "orzechy ziemne",
    "miod",
    "daktyle",
    "kakao",
    "rodzynki",
    "jablko suszone",
    "migdaly",
    "pestki slonecznika",
    "cynamon",
    "olej rzepakowy",
    "sol morska",
]

KOLORY_PRODUKTU = [
    [0.1, 0.5, 0.9],
    [0.95, 0.55, 0.15],
    [0.2, 0.7, 0.35],
    [0.8, 0.25, 0.3],
    [0.55, 0.4, 0.8],
]


# ============================================================================
# 4. NARZEDZIA GAZE
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


# ============================================================================
# 5. KALIBRACJA
# ============================================================================
CAL_POINTS = [
    (0.5, 0.5),
    (0.1, 0.1),
    (0.9, 0.1),
    (0.9, 0.9),
    (0.1, 0.9),
]


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

    dot = visual.Circle(win, radius=20, fillColor="white", lineColor=None)
    center = visual.Circle(win, radius=4, fillColor="black", lineColor=None)

    instrukcja = visual.TextStim(
        win,
        text="Patrz na kolejne punkty kalibracyjne. Nacisnij SPACJE, aby zaczac.",
        color="white",
        height=30,
        wrapWidth=1300,
        pos=(0, 0),
    )
    instrukcja.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        calibration.leave_calibration_mode()
        return False

    for nx, ny in CAL_POINTS:
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
# 6. GENEROWANIE PROB
# ============================================================================
def generuj_probe(n_trials):
    proby = []
    for idx in range(n_trials):
        produkt = random.choice(PRODUKTY)
        smak = random.choice(SMAKI)
        kolor = random.choice(KOLORY_PRODUKTU)

        left_ing = random.sample(SKLADNIKI_ZLOZONE, 3)
        right_ing = random.sample(SKLADNIKI_PROSTE, 3)

        proby.append(
            {
                "trial": idx + 1,
                "nazwa": f"{produkt} {smak}",
                "kolor": kolor,
                "left_ingredients": left_ing,
                "right_ingredients": right_ing,
            }
        )
    return proby


def stworz_stymulusy_proby(win, trial):
    title = visual.TextStim(
        win,
        text=(
            f"PROBA {trial['trial']}/{N_TRIALS}  |  "
            "Ktora opcja jest zdrowsza? (strzalka LEWO / PRAWO)"
        ),
        color="white",
        height=28,
        pos=(0, 470),
    )

    left_card = visual.Rect(
        win,
        width=CARD_W,
        height=CARD_H,
        pos=(LEFT_X, 40),
        fillColor=[-0.55, -0.55, -0.55],
        lineColor=[0.2, 0.2, 0.2],
    )
    right_card = visual.Rect(
        win,
        width=CARD_W,
        height=CARD_H,
        pos=(RIGHT_X, 40),
        fillColor=[-0.55, -0.55, -0.55],
        lineColor=[0.2, 0.2, 0.2],
    )

    pack_left = visual.Rect(
        win,
        width=PACK_W,
        height=PACK_H,
        pos=(LEFT_X, PRODUCT_Y),
        fillColor=trial["kolor"],
        lineColor="black",
    )
    pack_right = visual.Rect(
        win,
        width=PACK_W,
        height=PACK_H,
        pos=(RIGHT_X, PRODUCT_Y),
        fillColor=trial["kolor"],
        lineColor="black",
    )

    left_label = visual.TextStim(
        win,
        text=trial["nazwa"] + "\nWersja A",
        color="white",
        height=24,
        pos=(LEFT_X, PRODUCT_Y),
        wrapWidth=PACK_W - 20,
        alignText="center",
    )
    right_label = visual.TextStim(
        win,
        text=trial["nazwa"] + "\nWersja B",
        color="white",
        height=24,
        pos=(RIGHT_X, PRODUCT_Y),
        wrapWidth=PACK_W - 20,
        alignText="center",
    )

    left_ing_text = visual.TextStim(
        win,
        text="Sklad:\n- " + "\n- ".join(trial["left_ingredients"]),
        color="white",
        height=25,
        pos=(LEFT_X, ING_Y),
        wrapWidth=CARD_W - 70,
        alignText="left",
    )
    right_ing_text = visual.TextStim(
        win,
        text="Sklad:\n- " + "\n- ".join(trial["right_ingredients"]),
        color="white",
        height=25,
        pos=(RIGHT_X, ING_Y),
        wrapWidth=CARD_W - 70,
        alignText="left",
    )

    footer = visual.TextStim(
        win,
        text="ESC = wyjscie",
        color=[0.8, 0.8, 0.8],
        height=20,
        pos=(0, -500),
    )

    aoi = {
        "left_img": [LEFT_X - PACK_W / 2, LEFT_X + PACK_W / 2, PRODUCT_Y - PACK_H / 2, PRODUCT_Y + PACK_H / 2],
        "right_img": [RIGHT_X - PACK_W / 2, RIGHT_X + PACK_W / 2, PRODUCT_Y - PACK_H / 2, PRODUCT_Y + PACK_H / 2],
        "left_ing": [LEFT_X - (CARD_W - 70) / 2, LEFT_X + (CARD_W - 70) / 2, ING_Y - 150, ING_Y + 90],
        "right_ing": [RIGHT_X - (CARD_W - 70) / 2, RIGHT_X + (CARD_W - 70) / 2, ING_Y - 150, ING_Y + 90],
    }

    stims = [
        title,
        left_card,
        right_card,
        pack_left,
        pack_right,
        left_label,
        right_label,
        left_ing_text,
        right_ing_text,
        footer,
    ]
    return stims, aoi


# ============================================================================
# 7. ANALIZA GAZE
# ============================================================================
def policz_metryki_z_gaze(samples, aoi, choice_side, rt):
    if len(samples) < 2:
        return {
            "left_total": 0.0,
            "right_total": 0.0,
            "left_img": 0.0,
            "right_img": 0.0,
            "left_ing": 0.0,
            "right_ing": 0.0,
            "first_fix_side": "brak",
            "choice": choice_side,
            "rt": rt,
            "samples": samples,
        }

    metryki = {
        "left_img": 0.0,
        "right_img": 0.0,
        "left_ing": 0.0,
        "right_ing": 0.0,
    }

    first_fix_side = "brak"

    for i in range(len(samples) - 1):
        x = samples[i]["x"]
        y = samples[i]["y"]
        dt = max(0.0, samples[i + 1]["t"] - samples[i]["t"])

        in_left_img = rect_contains(aoi["left_img"], x, y)
        in_right_img = rect_contains(aoi["right_img"], x, y)
        in_left_ing = rect_contains(aoi["left_ing"], x, y)
        in_right_ing = rect_contains(aoi["right_ing"], x, y)

        if first_fix_side == "brak":
            if in_left_img or in_left_ing:
                first_fix_side = "left"
            elif in_right_img or in_right_ing:
                first_fix_side = "right"

        if in_left_img:
            metryki["left_img"] += dt
        if in_right_img:
            metryki["right_img"] += dt
        if in_left_ing:
            metryki["left_ing"] += dt
        if in_right_ing:
            metryki["right_ing"] += dt

    left_total = metryki["left_img"] + metryki["left_ing"]
    right_total = metryki["right_img"] + metryki["right_ing"]

    metryki.update(
        {
            "left_total": left_total,
            "right_total": right_total,
            "first_fix_side": first_fix_side,
            "choice": choice_side,
            "rt": rt,
            "samples": samples,
        }
    )
    return metryki


def zrob_heatmape(samples, width=192, height=108):
    img = np.zeros((height, width), dtype=np.float32)
    if not samples:
        return np.zeros((height, width, 3), dtype=np.float32)

    xs = np.array([s["x"] for s in samples], dtype=np.float32)
    ys = np.array([s["y"] for s in samples], dtype=np.float32)

    # Konwersja pikseli PsychoPy -> indeksy macierzy
    xi = ((xs + SCREEN_WIDTH / 2) / SCREEN_WIDTH * (width - 1)).astype(int)
    yi = ((SCREEN_HEIGHT / 2 - ys) / SCREEN_HEIGHT * (height - 1)).astype(int)

    mask = (xi >= 0) & (xi < width) & (yi >= 0) & (yi < height)
    xi = xi[mask]
    yi = yi[mask]

    for x_idx, y_idx in zip(xi, yi):
        img[y_idx, x_idx] += 1.0

    # Proste wygladzenie
    for _ in range(6):
        img = (
            img
            + np.roll(img, 1, axis=0)
            + np.roll(img, -1, axis=0)
            + np.roll(img, 1, axis=1)
            + np.roll(img, -1, axis=1)
        ) / 5.0

    # Mocniejsze podbicie kontrastu, aby hotspoty byly bardziej wyrazne
    img = np.power(img, 0.6)

    m = np.max(img)
    if m > 0:
        img = img / m

    rgb = np.zeros((height, width, 3), dtype=np.float32)
    rgb[:, :, 0] = np.clip(img * 1.35, 0.0, 1.0)
    rgb[:, :, 1] = np.clip(img * 0.75, 0.0, 1.0)
    rgb[:, :, 2] = np.clip(img * 0.08, 0.0, 0.5)
    return rgb


def analiza_koncowa(wyniki):
    if not wyniki:
        return {
            "mean_rt": 0.0,
            "right_choice_rate": 0.0,
            "look_choice_match": 0.0,
            "first_fix_right": 0.0,
            "top_factors": [],
        }

    n = len(wyniki)
    sr_rt = float(np.mean([w["rt"] for w in wyniki]))
    right_choices = sum(1 for w in wyniki if w["choice"] == "right")
    first_fix_right = sum(1 for w in wyniki if w["first_fix_side"] == "right")

    zgodnosc_spojrzenie_wybor = 0
    for w in wyniki:
        bardziej_ogl = "right" if w["right_total"] >= w["left_total"] else "left"
        if bardziej_ogl == w["choice"]:
            zgodnosc_spojrzenie_wybor += 1

    avg_left_ing = float(np.mean([w["left_ing"] for w in wyniki]))
    avg_right_ing = float(np.mean([w["right_ing"] for w in wyniki]))
    avg_left_img = float(np.mean([w["left_img"] for w in wyniki]))
    avg_right_img = float(np.mean([w["right_img"] for w in wyniki]))

    # Heurystyczna sila czynnikow (0-100)
    scores = {
        "Czas na prostych skladnikach (prawa strona)": max(0.0, avg_right_ing - avg_left_ing),
        "Przewaga czasu spojrzen na prawa strone": float(np.mean([w["right_total"] - w["left_total"] for w in wyniki])),
        "Pierwsza fiksacja na prawej stronie": first_fix_right / n,
        "Uwaznosc na opakowanie (obrazy)": avg_left_img + avg_right_img,
        "Zgodnosc: dluzej patrzylem -> to wybralem": zgodnosc_spojrzenie_wybor / n,
    }

    min_val = min(scores.values())
    shifted = {k: (v - min_val) for k, v in scores.items()}
    max_val = max(shifted.values()) if shifted else 1.0
    if max_val <= 0:
        max_val = 1.0

    top_factors = sorted(
        [(k, 100.0 * v / max_val) for k, v in shifted.items()],
        key=lambda x: x[1],
        reverse=True,
    )[:3]

    return {
        "mean_rt": sr_rt,
        "right_choice_rate": 100.0 * right_choices / n,
        "look_choice_match": 100.0 * zgodnosc_spojrzenie_wybor / n,
        "first_fix_right": 100.0 * first_fix_right / n,
        "avg_left_ing": avg_left_ing,
        "avg_right_ing": avg_right_ing,
        "avg_left_img": avg_left_img,
        "avg_right_img": avg_right_img,
        "top_factors": top_factors,
    }


# ============================================================================
# 8. PREZENTACJA WYNIKOW
# ============================================================================
def ekran_startowy(win):
    tekst = visual.TextStim(
        win,
        text=(
            "APP 1: ZDROWY WYBOR\n\n"
            "Na ekranie pojawia sie 5 par produktow (lewa i prawa strona).\n"
            "Lewa strona ma bardziej zlozone nazwy skladnikow, prawa prostsze.\n"
            "Wybierz strzalka, ktora opcja WG CIEBIE jest zdrowsza.\n"
            "To badanie preferencji - nie ma poprawnych ani blednych odpowiedzi.\n\n"
            "LEWO/PRAWO = odpowiedz, ESC = wyjscie, SPACJA = start badania"
        ),
        color="white",
        height=30,
        wrapWidth=1600,
    )
    tekst.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    return "escape" not in keys


def feedback_po_probie(win, trial_idx, choice_side, rt):
    msg = (
        f"Proba {trial_idx}/{N_TRIALS}\n"
        f"Wybor zapisany: {'LEWO' if choice_side == 'left' else 'PRAWO'}\n"
        f"Czas reakcji: {rt:.2f} s"
    )
    stim = visual.TextStim(win, text=msg, color="lightgray", height=34)
    stim.draw()
    win.flip()
    core.wait(0.35)


def ekran_raportu(win, wyniki, podsumowanie):
    heatmaps = [zrob_heatmape(w["samples"], width=200, height=120) for w in wyniki]

    title = visual.TextStim(
        win,
        text="RAPORT KONCOWY - CZYNNIKI DECYZJI",
        color="white",
        height=34,
        pos=(0, 500),
    )

    summary_lines = [
        "To badanie nie posiada poprawnych odpowiedzi.",
        f"Sredni czas reakcji: {podsumowanie['mean_rt']:.2f} s",
        f"Odsetek wyborow PRAWO: {podsumowanie['right_choice_rate']:.1f}%",
        f"Zgodnosc: dluzsze patrzenie -> wybrana strona: {podsumowanie['look_choice_match']:.1f}%",
        f"Pierwsza fiksacja na PRAWO: {podsumowanie['first_fix_right']:.1f}%",
        "Czerwony hotspot = najwiecej fiksacji (najczestsze patrzenie).",
        "",
        "Najsilniejsze czynniki decyzji:",
    ]

    for idx, (name, score) in enumerate(podsumowanie["top_factors"], start=1):
        summary_lines.append(f"{idx}. {name} ({score:.1f}/100)")

    summary = visual.TextStim(
        win,
        text="\n".join(summary_lines),
        color="white",
        height=25,
        alignText="left",
        wrapWidth=900,
        pos=(-500, 120),
    )

    labels = []
    images = []
    gaze_markers = []
    slots = [(-250, -120), (100, -120), (450, -120), (-75, -360), (275, -360)]

    for i, hm in enumerate(heatmaps):
        pos = slots[i]
        images.append(
            visual.ImageStim(
                win,
                image=hm,
                units="pix",
                size=(300, 180),
                pos=pos,
                interpolate=True,
            )
        )
        labels.append(
            visual.TextStim(
                win,
                text=f"Heatmapa proba {i + 1}",
                color="white",
                height=20,
                pos=(pos[0], pos[1] + 110),
            )
        )

        # Dodatkowe znaczniki: tor spojrzen + ostatnia fiksacja przed decyzja
        samples = wyniki[i]["samples"]
        if samples:
            # Redukcja liczby punktow dla czytelnosci (max ~35 punktow)
            step = max(1, len(samples) // 35)
            sampled = samples[::step]
            pts = []
            for s in sampled:
                x_local = ((s["x"] + SCREEN_WIDTH / 2) / SCREEN_WIDTH - 0.5) * 300 + pos[0]
                y_local = (0.5 - (s["y"] + SCREEN_HEIGHT / 2) / SCREEN_HEIGHT) * 180 + pos[1]
                pts.append((x_local, y_local))

            if len(pts) > 1:
                gaze_markers.append(
                    visual.ShapeStim(
                        win,
                        vertices=pts,
                        closeShape=False,
                        lineColor="cyan",
                        lineWidth=1.8,
                    )
                )

            last = pts[-1]
            gaze_markers.append(
                visual.Circle(
                    win,
                    radius=6,
                    pos=last,
                    fillColor="yellow",
                    lineColor="black",
                    lineWidth=1.0,
                )
            )
            labels.append(
                visual.TextStim(
                    win,
                    text="zolta kropka = wzrok przy decyzji",
                    color="yellow",
                    height=14,
                    pos=(pos[0], pos[1] - 104),
                )
            )

    footer = visual.TextStim(
        win,
        text="SPACJA = zakoncz | ESC = wyjscie",
        color=[0.8, 0.8, 0.8],
        height=22,
        pos=(0, -515),
    )

    while True:
        title.draw()
        summary.draw()
        for stim in images:
            stim.draw()
        for lbl in labels:
            lbl.draw()
        for marker in gaze_markers:
            marker.draw()
        footer.draw()
        win.flip()

        keys = event.getKeys(["space", "escape"])
        if keys:
            break


def zapisz_csv(wyniki, podsumowanie):
    out_file = HERE / f"wyniki_app1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    fields = [
        "trial",
        "choice",
        "rt",
        "left_total",
        "right_total",
        "left_img",
        "right_img",
        "left_ing",
        "right_ing",
        "first_fix_side",
    ]

    with open(out_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for idx, row in enumerate(wyniki, start=1):
            row_out = {k: row.get(k, "") for k in fields}
            row_out["trial"] = idx
            w.writerow(row_out)

        w.writerow({})
        w.writerow({"trial": "PODSUMOWANIE"})
        w.writerow({"trial": "sredni_rt_s", "choice": f"{podsumowanie['mean_rt']:.3f}"})
        w.writerow({"trial": "wybor_prawo_%", "choice": f"{podsumowanie['right_choice_rate']:.2f}"})
        w.writerow({"trial": "zgodnosc_spojrzenie_wybor_%", "choice": f"{podsumowanie['look_choice_match']:.2f}"})

    print(f"Zapisano wyniki: {out_file}")


# ============================================================================
# 9. PRZEBIEG PROBY
# ============================================================================
def run_trial(win, collector, trial):
    stims, aoi = stworz_stymulusy_proby(win, trial)
    start = core.MonotonicClock()
    samples = []
    choice = None
    rt = TRIAL_TIMEOUT

    while start.getTime() < TRIAL_TIMEOUT:
        keys = event.getKeys(["left", "right", "escape"])
        if "escape" in keys:
            return None
        if "left" in keys:
            choice = "left"
            rt = start.getTime()
            break
        if "right" in keys:
            choice = "right"
            rt = start.getTime()
            break

        gaze = collector.get_gaze_pix()
        if gaze is not None:
            samples.append({"t": start.getTime(), "x": float(gaze[0]), "y": float(gaze[1])})

        for stim in stims:
            stim.draw()
        win.flip()

    if choice is None:
        choice = "left" if random.random() < 0.5 else "right"

    wynik = policz_metryki_z_gaze(samples, aoi, choice, rt)
    return wynik


# ============================================================================
# 10. MAIN
# ============================================================================
def main():
    et = connect_eyetracker()

    win = visual.Window(
        size=(SCREEN_WIDTH, SCREEN_HEIGHT),
        fullscr=FULLSCREEN,
        color="black",
        units="pix",
    )

    if et is None:
        msg = visual.TextStim(
            win,
            text=(
                "Nie znaleziono eye-trackera Tobii.\n\n"
                "Podlacz urzadzenie lub uruchom ponownie w TRYBIE DEV.\n"
                "Nacisnij dowolny klawisz, aby wyjsc."
            ),
            color="orange",
            height=32,
            wrapWidth=1500,
        )
        msg.draw()
        win.flip()
        event.waitKeys()
        win.close()
        return

    if not run_calibration(win, et):
        fail = visual.TextStim(
            win,
            text="Kalibracja nieudana lub przerwana. Koniec.",
            color="orange",
            height=34,
        )
        fail.draw()
        win.flip()
        core.wait(1.5)
        win.close()
        return

    if not ekran_startowy(win):
        win.close()
        return

    collector = GazeCollector(et, win=win)
    collector.start()

    proby = generuj_probe(N_TRIALS)
    wyniki = []

    for trial in proby:
        wynik = run_trial(win, collector, trial)
        if wynik is None:
            collector.stop()
            win.close()
            return

        wyniki.append(wynik)
        feedback_po_probie(
            win,
            trial_idx=trial["trial"],
            choice_side=wynik["choice"],
            rt=wynik["rt"],
        )

    collector.stop()

    podsumowanie = analiza_koncowa(wyniki)
    zapisz_csv(wyniki, podsumowanie)
    ekran_raportu(win, wyniki, podsumowanie)

    win.close()


if __name__ == "__main__":
    main()
