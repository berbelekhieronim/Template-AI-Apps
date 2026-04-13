#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
APP 3 - WYKRYWACZ KLAMSTW (PROTOTYP)

Szybki protokol (ok. 3-4 min):
1) Kalibracja
2) Trening: badany etykietuje intencje strzalkami (LEWO=KLAMIE, PRAWO=PRAWDA)
3) Follow-up: model przewiduje etykiete z gaze data i porownuje z odpowiedzia badanego

Uwaga metodologiczna:
To jest model stylu zachowania konkretnej osoby, nie uniwersalny detector klamstwa.
"""

import csv
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# ============================================================================
# 0. TRYB URUCHOMIENIA
# ============================================================================
HERE = Path(__file__).resolve().parent
SDK_PATH = HERE.parent / "x3-120 SDK" / "64"

print()
print("=" * 64)
print(" APP 3 - WYKRYWACZ KLAMSTW | WYBOR TRYBU")
print("=" * 64)
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
# 2. PARAMETRY
# ============================================================================
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
FULLSCREEN = True

N_TRAIN = 16
N_TEST = 10
TRIAL_TIMEOUT = 5.0

LEFT_X = -430
RIGHT_X = 430
IMG_Y = 80
IMG_W = 420
IMG_H = 300

# ============================================================================
# 3. NARZEDZIA GAZE + KURSOR
# ============================================================================
def norm_to_pix(nx, ny):
    px = (nx - 0.5) * SCREEN_WIDTH
    py = (0.5 - ny) * SCREEN_HEIGHT
    return px, py


def rect_contains(rect, x, y):
    return rect[0] <= x <= rect[1] and rect[2] <= y <= rect[3]


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
# 4. KALIBRACJA
# ============================================================================
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
    return result.status == tr.CALIBRATION_STATUS_SUCCESS


# ============================================================================
# 5. STYMULY
# ============================================================================
BODZCE = [
    ("Samochod sportowy", [0.7, 0.1, 0.1]),
    ("Dom nad jeziorem", [0.1, 0.4, 0.7]),
    ("Wakacje Bali", [0.8, 0.45, 0.1]),
    ("Nowy smartfon", [0.3, 0.3, 0.3]),
    ("Luksusowy zegarek", [0.55, 0.35, 0.1]),
    ("Bilet VIP", [0.45, 0.1, 0.55]),
]


def losuj_triale(n):
    trials = []
    for idx in range(n):
        left = random.choice(BODZCE)
        right = random.choice(BODZCE)
        while right[0] == left[0]:
            right = random.choice(BODZCE)

        trials.append(
            {
                "trial": idx + 1,
                "left_name": left[0],
                "left_color": left[1],
                "right_name": right[0],
                "right_color": right[1],
            }
        )
    return trials


def draw_trial_scene(win, trial, phase_name, phase_idx, phase_total):
    title = visual.TextStim(
        win,
        text=(
            f"{phase_name}  {phase_idx}/{phase_total} | "
            "Obejrzyj oba obrazy i odpowiedz sobie na pytanie z dolu ekranu"
        ),
        color="white",
        height=26,
        pos=(0, 460),
        wrapWidth=1800,
    )

    left_img = visual.Rect(
        win,
        width=IMG_W,
        height=IMG_H,
        pos=(LEFT_X, IMG_Y),
        fillColor=trial["left_color"],
        lineColor="white",
        lineWidth=2,
    )
    right_img = visual.Rect(
        win,
        width=IMG_W,
        height=IMG_H,
        pos=(RIGHT_X, IMG_Y),
        fillColor=trial["right_color"],
        lineColor="white",
        lineWidth=2,
    )

    left_txt = visual.TextStim(
        win,
        text=trial["left_name"],
        color="white",
        height=32,
        pos=(LEFT_X, IMG_Y),
        wrapWidth=IMG_W - 20,
    )
    right_txt = visual.TextStim(
        win,
        text=trial["right_name"],
        color="white",
        height=32,
        pos=(RIGHT_X, IMG_Y),
        wrapWidth=IMG_W - 20,
    )

    q = visual.TextStim(
        win,
        text=(
            "Pytanie: Ktora z dwoch rzeczy Ci sie bardziej podoba?\n"
            "Nastepnie oznacz intencje odpowiedzi: LEWO = KLAMIE, PRAWO = MOWIE PRAWDE"
        ),
        color="yellow",
        height=27,
        pos=(0, -250),
        wrapWidth=1700,
    )

    foot = visual.TextStim(
        win,
        text="ESC = wyjscie",
        color=[0.8, 0.8, 0.8],
        height=20,
        pos=(0, -500),
    )

    aoi = {
        "left_img": [LEFT_X - IMG_W / 2, LEFT_X + IMG_W / 2, IMG_Y - IMG_H / 2, IMG_Y + IMG_H / 2],
        "right_img": [RIGHT_X - IMG_W / 2, RIGHT_X + IMG_W / 2, IMG_Y - IMG_H / 2, IMG_Y + IMG_H / 2],
    }

    return [title, left_img, right_img, left_txt, right_txt, q, foot], aoi


# ============================================================================
# 6. CECHY + MODEL
# ============================================================================
def features_from_samples(samples, aoi, rt):
    if len(samples) < 2:
        return np.zeros(8, dtype=np.float32)

    left_dwell = 0.0
    right_dwell = 0.0
    switches = 0
    first_side = 0
    last_side = "none"
    first_hit_t = None

    xs = [s["x"] for s in samples]
    ys = [s["y"] for s in samples]

    for i in range(len(samples) - 1):
        x = samples[i]["x"]
        y = samples[i]["y"]
        dt = max(0.0, samples[i + 1]["t"] - samples[i]["t"])

        in_left = rect_contains(aoi["left_img"], x, y)
        in_right = rect_contains(aoi["right_img"], x, y)

        now_side = "none"
        if in_left:
            left_dwell += dt
            now_side = "left"
        elif in_right:
            right_dwell += dt
            now_side = "right"

        if first_hit_t is None and now_side != "none":
            first_hit_t = samples[i]["t"]
            first_side = 1 if now_side == "right" else 0

        if last_side != "none" and now_side != "none" and now_side != last_side:
            switches += 1
        if now_side != "none":
            last_side = now_side

    total_dwell = left_dwell + right_dwell
    if total_dwell > 0:
        left_ratio = left_dwell / total_dwell
        right_ratio = right_dwell / total_dwell
    else:
        left_ratio = 0.0
        right_ratio = 0.0

    ttf = first_hit_t if first_hit_t is not None else rt
    mean_x = float(np.mean(xs)) if xs else 0.0
    std_x = float(np.std(xs)) if xs else 0.0

    feat = np.array(
        [
            rt,
            left_dwell,
            right_dwell,
            right_ratio - left_ratio,
            float(switches),
            float(first_side),
            ttf,
            std_x,
        ],
        dtype=np.float32,
    )
    return feat


FEATURE_NAMES = [
    "czas_reakcji",
    "dwell_lewo",
    "dwell_prawo",
    "roznica_ratio_prawo_minus_lewo",
    "liczba_przelaczen",
    "pierwsza_fiksacja_prawo",
    "czas_do_pierwszej_fiksacji",
    "zmiennosc_pozioma_wzroku",
]


def fit_logreg(X, y, lr=0.08, n_iter=500):
    eps = 1e-6
    mu = X.mean(axis=0)
    sigma = X.std(axis=0) + eps
    Xn = (X - mu) / sigma

    w = np.zeros(Xn.shape[1], dtype=np.float32)
    b = 0.0

    for _ in range(n_iter):
        z = Xn @ w + b
        p = 1.0 / (1.0 + np.exp(-z))
        err = p - y

        grad_w = (Xn.T @ err) / len(y)
        grad_b = float(np.mean(err))

        w -= lr * grad_w
        b -= lr * grad_b

    return {"mu": mu, "sigma": sigma, "w": w, "b": b}


def predict_prob(model, x):
    xn = (x - model["mu"]) / model["sigma"]
    z = float(np.dot(xn, model["w"]) + model["b"])
    return 1.0 / (1.0 + np.exp(-z))


def explain_prediction(model, x, top_k=3):
    xn = (x - model["mu"]) / model["sigma"]
    contrib = xn * model["w"]
    idxs = np.argsort(-np.abs(contrib))[:top_k]

    explain = []
    for idx in idxs:
        direction = "w strone KLAMSTWA" if contrib[idx] >= 0 else "w strone PRAWDY"
        explain.append(
            {
                "name": FEATURE_NAMES[idx],
                "contribution": float(contrib[idx]),
                "direction": direction,
                "value": float(x[idx]),
            }
        )
    return explain


# ============================================================================
# 7. PRZEBIEG PROBY
# ============================================================================
def run_one_trial(win, collector, trial, phase_name, phase_idx, phase_total, model=None):
    stims, aoi = draw_trial_scene(win, trial, phase_name, phase_idx, phase_total)
    ready = visual.TextStim(
        win,
        text=(
            f"{phase_name} {phase_idx}/{phase_total}\n\n"
            "Za chwile zobaczysz dwie opcje.\n"
            "Zastanow sie: Ktora z dwoch rzeczy Ci sie bardziej podoba?\n"
            "Gdy bedziesz gotow_a, nacisnij SPACJE."
        ),
        color="white",
        height=30,
        wrapWidth=1500,
    )
    ready.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    if "escape" in keys:
        return None

    clock = core.MonotonicClock()
    samples = []
    label = None

    while True:
        reveal_cursor_if_moved(win)

        keys = event.getKeys(["left", "right", "escape"])
        if "escape" in keys:
            return None
        if "left" in keys:
            label = 1  # klamie
            break
        if "right" in keys:
            label = 0  # prawda
            break

        gaze = collector.get_gaze_pix()
        if gaze is not None:
            samples.append({"t": clock.getTime(), "x": float(gaze[0]), "y": float(gaze[1])})

        for s in stims:
            s.draw()
        win.flip()

    rt = clock.getTime()
    feat = features_from_samples(samples, aoi, rt)

    pred_label = None
    pred_prob = None
    evidence = []
    if model is not None:
        pred_prob = predict_prob(model, feat)
        pred_label = 1 if pred_prob >= 0.5 else 0
        evidence = explain_prediction(model, feat)

    wynik = {
        "trial": trial["trial"],
        "phase": phase_name,
        "left_name": trial["left_name"],
        "right_name": trial["right_name"],
        "label": label,
        "label_text": "KLAMSTWO" if label == 1 else "PRAWDA",
        "rt": rt,
        "pred_label": pred_label,
        "pred_prob": pred_prob,
        "samples_n": len(samples),
        "features": feat,
        "evidence": evidence,
    }
    return wynik


# ============================================================================
# 8. RAPORT
# ============================================================================
def licz_metryki_test(test_rows):
    if not test_rows:
        return {
            "acc": 0.0,
            "tp": 0,
            "tn": 0,
            "fp": 0,
            "fn": 0,
        }

    tp = tn = fp = fn = 0
    for r in test_rows:
        y = r["label"]
        p = r["pred_label"]
        if p == 1 and y == 1:
            tp += 1
        elif p == 0 and y == 0:
            tn += 1
        elif p == 1 and y == 0:
            fp += 1
        elif p == 0 and y == 1:
            fn += 1

    acc = 100.0 * (tp + tn) / max(1, len(test_rows))
    return {"acc": acc, "tp": tp, "tn": tn, "fp": fp, "fn": fn}


def pokaz_raport(win, train_rows, test_rows, model):
    m = licz_metryki_test(test_rows)

    top_feat = []
    if model is not None:
        w_abs = np.abs(model["w"])
        idxs = np.argsort(-w_abs)[:4]
        for i in idxs:
            top_feat.append((FEATURE_NAMES[i], float(w_abs[i])))

    lines = [
        "RAPORT: WYKRYWACZ KLAMSTW (PROTOTYP)",
        "",
        f"Proby treningowe: {len(train_rows)}",
        f"Proby follow-up: {len(test_rows)}",
        f"Skutecznosc modelu (follow-up): {m['acc']:.1f}%",
        f"Macierz pomylek: TP={m['tp']}  TN={m['tn']}  FP={m['fp']}  FN={m['fn']}",
        "",
        "Najmocniejsze cechy wzroku dla tej osoby:",
    ]

    if top_feat:
        norm = max(v for _, v in top_feat) or 1.0
        for i, (name, val) in enumerate(top_feat, start=1):
            lines.append(f"{i}. {name}  ({100.0 * val / norm:.1f}/100)")

    lines.extend(
        [
            "",
            "Wniosek: model jest osobniczy (na ta osobe, w tej sesji).",
            "SPACJA = zakoncz",
        ]
    )

    panel = visual.Rect(
        win,
        width=1600,
        height=860,
        pos=(0, 0),
        fillColor=[-0.88, -0.9, -0.95],
        lineColor=[-0.3, -0.3, -0.1],
        lineWidth=2,
    )

    txt = visual.TextStim(
        win,
        text="\n".join(lines),
        color=[-0.2, -0.2, -0.2],
        height=29,
        wrapWidth=1450,
        alignText="left",
        pos=(0, 40),
    )

    while True:
        reveal_cursor_if_moved(win)
        panel.draw()
        txt.draw()
        win.flip()
        keys = event.getKeys(["space", "escape"])
        if keys:
            return


def zapisz_csv(rows, model):
    out_file = HERE / f"wyniki_app3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    fieldnames = [
        "trial",
        "phase",
        "left_name",
        "right_name",
        "label",
        "label_text",
        "pred_label",
        "pred_prob",
        "evidence_1",
        "evidence_2",
        "evidence_3",
        "rt",
        "samples_n",
    ] + [f"feat_{name}" for name in FEATURE_NAMES]

    with open(out_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for r in rows:
            row = {k: r.get(k, "") for k in fieldnames}
            evidence = r.get("evidence", [])
            for idx in range(3):
                if idx < len(evidence):
                    ev = evidence[idx]
                    row[f"evidence_{idx + 1}"] = (
                        f"{ev['name']} | wartosc={ev['value']:.3f} | {ev['direction']} | sila={ev['contribution']:.3f}"
                    )
            for i, name in enumerate(FEATURE_NAMES):
                row[f"feat_{name}"] = f"{float(r['features'][i]):.6f}"
            if r["pred_prob"] is not None:
                row["pred_prob"] = f"{r['pred_prob']:.6f}"
            w.writerow(row)

        if model is not None:
            w.writerow({})
            w.writerow({"trial": "MODEL_WEIGHTS"})
            for i, name in enumerate(FEATURE_NAMES):
                w.writerow({"trial": name, "phase": f"{float(model['w'][i]):.6f}"})

    print(f"Zapisano wyniki: {out_file}")


# ============================================================================
# 9. UI POMOCNICZE
# ============================================================================
def pokaz_wstep(win):
    txt = visual.TextStim(
        win,
        text=(
            "APP 3: WYKRYWACZ KLAMSTW (PROTOTYP)\n\n"
            "Instrukcja: patrz na dwa obrazy i odpowiedz sobie na pytanie:\n"
            "Ktora z dwoch rzeczy Ci sie bardziej podoba?\n\n"
            "Nastepnie deklaruj intencje strzalka:\n"
            "LEWO = klamie, PRAWO = mowie prawde.\n\n"
            "Faza 1: model uczy sie Twojego wzorca z danych wzroku.\n"
            "Faza 2: model sam przewiduje, czy klamiesz.\n\n"
            "Czas calkowity: okolo 3-4 min\n"
            "SPACJA = start, ESC = wyjscie"
        ),
        color="white",
        height=30,
        wrapWidth=1600,
    )
    txt.draw()
    win.flip()
    keys = event.waitKeys(keyList=["space", "escape"])
    return "escape" not in keys


def pokaz_predykcje(win, pred_label, pred_prob, true_label, evidence):
    color = "lime" if pred_label == true_label else "orange"
    evidence_lines = []
    for idx, ev in enumerate(evidence[:3], start=1):
        evidence_lines.append(
            f"{idx}. {ev['name']}: {ev['value']:.2f} -> {ev['direction']}"
        )

    txt = visual.TextStim(
        win,
        text=(
            f"Model przewidzial: {'KLAMSTWO' if pred_label == 1 else 'PRAWDA'}\n"
            f"Prawdopodobienstwo klamstwa: {100.0 * pred_prob:.1f}%\n"
            f"Twoja etykieta: {'KLAMSTWO' if true_label == 1 else 'PRAWDA'}\n\n"
            "Dowody z gaze data:\n"
            + "\n".join(evidence_lines)
            + "\n\nSPACJA = dalej"
        ),
        color=color,
        height=28,
        wrapWidth=1300,
    )
    while True:
        reveal_cursor_if_moved(win)
        txt.draw()
        win.flip()
        keys = event.getKeys(["space", "escape"])
        if keys:
            return


# ============================================================================
# 10. MAIN
# ============================================================================
def main():
    eyetracker = connect_eyetracker()

    win = visual.Window(
        size=(SCREEN_WIDTH, SCREEN_HEIGHT),
        fullscr=FULLSCREEN,
        color="black",
        units="pix",
    )
    init_hidden_cursor(win)

    if eyetracker is None:
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

    if not run_calibration(win, eyetracker):
        fail = visual.TextStim(
            win,
            text="Kalibracja nieudana lub przerwana. Koniec.",
            color="orange",
            height=34,
        )
        fail.draw()
        win.flip()
        core.wait(1.2)
        win.close()
        return

    if not pokaz_wstep(win):
        win.close()
        return

    collector = GazeCollector(eyetracker, win=win)
    collector.start()

    train_trials = losuj_triale(N_TRAIN)
    test_trials = losuj_triale(N_TEST)

    train_rows = []
    for i, t in enumerate(train_trials, start=1):
        r = run_one_trial(win, collector, t, "TRENING", i, N_TRAIN, model=None)
        if r is None:
            collector.stop()
            win.close()
            return
        train_rows.append(r)

    X_train = np.array([r["features"] for r in train_rows], dtype=np.float32)
    y_train = np.array([r["label"] for r in train_rows], dtype=np.float32)

    # Zabezpieczenie: jesli badany zaznaczyl tylko jedna klase, model bylby niestabilny.
    if len(np.unique(y_train)) < 2:
        # Wymuszenie minimalnej roznorodnosci, by model mogl dzialac.
        y_train[0] = 1.0 - y_train[0]

    model = fit_logreg(X_train, y_train)

    test_rows = []
    for i, t in enumerate(test_trials, start=1):
        r = run_one_trial(win, collector, t, "FOLLOW-UP", i, N_TEST, model=model)
        if r is None:
            collector.stop()
            win.close()
            return
        test_rows.append(r)
        pokaz_predykcje(win, r["pred_label"], r["pred_prob"], r["label"], r["evidence"])

    collector.stop()

    all_rows = train_rows + test_rows
    zapisz_csv(all_rows, model)
    pokaz_raport(win, train_rows, test_rows, model)

    win.close()


if __name__ == "__main__":
    main()
