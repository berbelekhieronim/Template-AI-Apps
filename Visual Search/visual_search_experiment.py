#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Visual Search Demo - Dni Otwarte
Pop-out vs. Conjunction Search - Feature Integration Theory
"""

import sys
import os
from pathlib import Path
import numpy as np
import time
import random
import math  # Potrzebne do tworzenia gwiazdy
import csv
from datetime import datetime

# Text-to-speech - opcjonalne
TTS_AVAILABLE = False
TTS_METHOD = None

# Próbuj najpierw gTTS (Google TTS - polski)
try:
    from gtts import gTTS
    TTS_AVAILABLE = True
    TTS_METHOD = 'gtts'
    print("✓ Używam gTTS (Google Text-to-Speech) - polski głos")
except ImportError:
    # Fallback na pyttsx3
    try:
        import pyttsx3
        TTS_AVAILABLE = True
        TTS_METHOD = 'pyttsx3'
        print("✓ Używam pyttsx3 (Windows SAPI)")
    except ImportError:
        TTS_AVAILABLE = False
        print("⚠ Brak TTS - triale audio będą pominięte")
        print("   Zainstaluj: pip install gtts")

# ============================================================================
# SDK PATH SETUP - MUST BE BEFORE TOBII IMPORT!
# ============================================================================
HERE = Path(__file__).parent.parent
X3_SDK_PATH = HERE / "x3-120 SDK" / "64"

if X3_SDK_PATH.exists():
    sdk_str = str(X3_SDK_PATH.resolve())
    if sdk_str not in sys.path:
        sys.path.insert(0, sdk_str)
        print(f"✓ Added X3-120 SDK to path: {sdk_str}")
else:
    print(f"⚠ SDK not found in: {X3_SDK_PATH}")

# NOW import tobii_research and PsychoPy
import tobii_research as tr
from psychopy import visual, core, event, logging
from psychopy.hardware import mouse

# Wyłącz zbędne warningi PsychoPy
logging.console.setLevel(logging.ERROR)

# ============================================================================
# DEBUG LOGGING SETUP
# ============================================================================
DEBUG_LOG_FILE = Path(__file__).parent / f"debug_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
RESULTS_CSV_FILE = Path(__file__).parent / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

def log_debug(message):
    """Write to both console and debug file"""
    print(message)
    with open(DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")

log_debug("=" * 50)
log_debug("VISUAL SEARCH EXPERIMENT - DEBUG LOG")
log_debug(f"Started: {datetime.now()}")
log_debug("=" * 50)

# ============================================================================
# KONFIGURACJA
# ============================================================================
SEARCH_DURATION = 10.0  # Max czas na znalezienie targetu
ITEM_RADIUS = 40  # Wielkość kółek/kwadratów
SET_SIZE = 8  # Ile distractorów (zmniejszone z 12 na 8 dla bezpieczeństwa)
FIXATION_THRESHOLD = 100  # Piksele
MIN_FIXATION_DURATION = 0.08  # Sekundy
SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

# Target detection - jak blisko trzeba patrzeć
TARGET_DETECTION_RADIUS = 120  # Piksele (zwiększone z 80)

# Poprawność odpowiedzi - jak długo przed SPACE trzeba patrzeć na target
CORRECT_RESPONSE_WINDOW = 0.8  # Sekundy przed naciśnięciem SPACE (zwiększone z 0.5)

# Poprawność odpowiedzi - jak długo przed SPACE trzeba patrzeć na target
CORRECT_RESPONSE_WINDOW = 0.5  # Sekundy przed naciśnięciem SPACE

# Dostępne kolory i kształty
COLORS = ['red', 'green', 'blue', 'yellow', 'orange', 'purple']
SHAPES = ['circle', 'square', 'triangle', 'polygon']  # polygon = wielokąt/diament
BORDERS = ['white', 'black']

# Mapowanie kolorów na RGB dla pewności (PsychoPy czasem ma problem z nazwami)
COLOR_MAP = {
    'red': 'red',
    'green': 'green', 
    'blue': 'blue',
    'yellow': 'yellow',
    'orange': [1.0, 0.5, 0.0],  # RGB dla pomarańczowego
    'purple': 'purple',
    'white': 'white',
    'black': 'black'
}

# ============================================================================
# FIND EYE TRACKER
# ============================================================================
def find_eyetracker():
    """Znajdź i skonfiguruj eye tracker"""
    print("\n🔍 Szukam eye trackera...")
    eyetrackers = tr.find_all_eyetrackers()
    
    if len(eyetrackers) == 0:
        print("❌ Nie znaleziono eye trackera!")
        return None
    
    eyetracker = eyetrackers[0]
    print(f"✓ Znaleziono: {eyetracker.model}")
    print(f"  Serial: {eyetracker.serial_number}")
    
    return eyetracker

# ============================================================================
# GAZE DATA COLLECTOR
# ============================================================================
class GazeCollector:
    """Zbiera dane z eye trackera"""
    def __init__(self):
        self.gaze_data = []
        self.collecting = False
    
    def callback(self, gaze_data):
        """Callback dla danych gaze"""
        if not self.collecting:
            return
            
        left_valid = gaze_data['left_gaze_point_validity']
        right_valid = gaze_data['right_gaze_point_validity']
        
        if left_valid or right_valid:
            x_coords = []
            y_coords = []
            
            if left_valid:
                x_coords.append(gaze_data['left_gaze_point_on_display_area'][0])
                y_coords.append(gaze_data['left_gaze_point_on_display_area'][1])
            
            if right_valid:
                x_coords.append(gaze_data['right_gaze_point_on_display_area'][0])
                y_coords.append(gaze_data['right_gaze_point_on_display_area'][1])
            
            avg_x = np.mean(x_coords)
            avg_y = np.mean(y_coords)
            timestamp = gaze_data['system_time_stamp'] / 1000000.0
            
            self.gaze_data.append({
                'timestamp': timestamp,
                'x': avg_x,
                'y': avg_y
            })
    
    def start(self):
        """Start zbierania"""
        self.gaze_data = []
        self.collecting = True
    
    def stop(self):
        """Stop zbierania"""
        self.collecting = False
        return self.gaze_data

# ============================================================================
# FIXATION DETECTION
# ============================================================================
def detect_fixations(gaze_data, screen_width, screen_height, 
                     threshold=FIXATION_THRESHOLD, min_duration=MIN_FIXATION_DURATION):
    """I-DT algorithm dla detekcji fixacji"""
    if len(gaze_data) < 2:
        return []
    
    points = []
    for g in gaze_data:
        x_pix = g['x'] * screen_width
        y_pix = g['y'] * screen_height
        points.append({
            'x': x_pix,
            'y': y_pix,
            'time': g['timestamp']
        })
    
    fixations = []
    current_fix = [points[0]]
    
    for i in range(1, len(points)):
        fix_center_x = np.mean([p['x'] for p in current_fix])
        fix_center_y = np.mean([p['y'] for p in current_fix])
        
        dist = np.sqrt((points[i]['x'] - fix_center_x)**2 + 
                      (points[i]['y'] - fix_center_y)**2)
        
        if dist < threshold:
            current_fix.append(points[i])
        else:
            if len(current_fix) > 0:
                duration = current_fix[-1]['time'] - current_fix[0]['time']
                if duration >= min_duration:
                    fixations.append({
                        'x': np.mean([p['x'] for p in current_fix]),
                        'y': np.mean([p['y'] for p in current_fix]),
                        'duration': duration,
                        'start_time': current_fix[0]['time']
                    })
            current_fix = [points[i]]
    
    # Ostatnia fixacja
    if len(current_fix) > 0:
        duration = current_fix[-1]['time'] - current_fix[0]['time']
        if duration >= min_duration:
            fixations.append({
                'x': np.mean([p['x'] for p in current_fix]),
                'y': np.mean([p['y'] for p in current_fix]),
                'duration': duration,
                'start_time': current_fix[0]['time']
            })
    
    return fixations

# ============================================================================
# GENERATE SEARCH DISPLAY
# ============================================================================
def create_shape(win, shape_type, pos, color, border_color, radius=ITEM_RADIUS):
    """Tworzy kształt danego typu"""
    # Użyj mapowania kolorów dla pewności
    fill_color = COLOR_MAP.get(color, color)
    line_color = COLOR_MAP.get(border_color, border_color)
    
    if shape_type == 'circle':
        return visual.Circle(
            win=win,
            radius=radius,
            pos=pos,
            fillColor=fill_color,
            lineColor=line_color,
            lineWidth=2
        )
    elif shape_type == 'square':
        return visual.Rect(
            win=win,
            width=radius*2,
            height=radius*2,
            pos=pos,
            fillColor=fill_color,
            lineColor=line_color,
            lineWidth=2
        )
    elif shape_type == 'triangle':
        return visual.Polygon(
            win=win,
            edges=3,
            radius=radius,
            pos=pos,
            fillColor=fill_color,
            lineColor=line_color,
            lineWidth=2
        )
    elif shape_type == 'polygon':  # Wielokąt (diament/sześciokąt)
        return visual.Polygon(
            win=win,
            edges=6,
            radius=radius,
            pos=pos,
            fillColor=fill_color,
            lineColor=line_color,
            lineWidth=2
        )
    elif shape_type == 'star':  # Gwiazda (5-ramienna)
        # Tworzymy prawdziwą gwiazdę z naprzemiennymi wierzchołkami
        outer_radius = radius
        inner_radius = radius * 0.4
        vertices = []
        for i in range(10):
            angle = (i * 36 - 90) * math.pi / 180  # 36 stopni między wierzchołkami
            if i % 2 == 0:
                # Zewnętrzny wierzchołek
                r = outer_radius
            else:
                # Wewnętrzny wierzchołek
                r = inner_radius
            x = r * math.cos(angle)
            y = r * math.sin(angle)
            vertices.append((x, y))
        
        # CRITICAL FIX: Zapewnij że gwiazda jest widoczna z większą linią
        return visual.ShapeStim(
            win=win,
            vertices=vertices,
            pos=pos,
            fillColor=fill_color,
            lineColor=line_color,
            lineWidth=3,  # Zwiększona grubość dla lepszej widoczności
            closeShape=True,
            opacity=1.0  # Zapewnij pełną nieprzezroczystość
        )

def generate_search_display(win, condition_type, target_spec, set_size=SET_SIZE):
    """
    Generuje display dla visual search
    
    condition_type: 'simple_popout', 'conjunction', 'complex', 'very_complex'
    
    Returns: (elements, target_pos)
    """
    elements = []
    
    # Pozycje na siatce (unikaj zbyt blisko siebie)
    margin = 200
    positions = []
    max_attempts = 500
    attempts = 0
    
    # Generuj losowe pozycje dla wszystkich elementów (distractors + target)
    while len(positions) < set_size + 1 and attempts < max_attempts:
        attempts += 1
        x = random.randint(-SCREEN_WIDTH//2 + margin, SCREEN_WIDTH//2 - margin)
        y = random.randint(-SCREEN_HEIGHT//2 + margin, SCREEN_HEIGHT//2 - margin)
        
        # Sprawdź czy nie za blisko innych
        too_close = False
        for px, py in positions:
            if np.sqrt((x-px)**2 + (y-py)**2) < 150:
                too_close = True
                break
        
        if not too_close:
            positions.append((x, y))
    
    if len(positions) < set_size + 1:
        print(f"⚠ Ostrzeżenie: Udało się umieścić tylko {len(positions)} elementów")
    
    # Wybierz losową pozycję dla targetu
    target_idx = random.randint(0, len(positions) - 1)
    target_pos = positions[target_idx]
    
    # TARGET - zgodnie z target_spec (WAŻNE!)
    log_debug(f"  → Tworzę target: {target_spec['name']} (shape={target_spec['shape']}, color={target_spec['color']}, border={target_spec['border']})")
    target = create_shape(win, target_spec['shape'], target_pos, 
                         target_spec['color'], target_spec['border'])
    
    # CRITICAL VALIDATION: Verify target was created successfully
    if target is None:
        log_debug(f"  ❌ ERROR: Target creation failed!")
        raise ValueError(f"CRITICAL: Target not created for {target_spec['name']}")
    
    log_debug(f"  ✓ Target created at position {target_pos}")
    elements.append({'stim': target, 'is_target': True, 'pos': target_pos})
    
    # DISTRACTORS - zależnie od warunku
    for i, pos in enumerate(positions):
        if i == target_idx:
            continue  # Skip target position
        
        if condition_type == 'simple_popout':
            # Najprostszy - jeden kolor/kształt vs target
            if target_spec['color'] == 'red':
                # Jeśli target czerwony, distractory zielone
                distractor = create_shape(win, target_spec['shape'], pos, 'green', target_spec['border'])
            else:
                # Dla innych kolorów targetu - czerwone distractory
                distractor = create_shape(win, target_spec['shape'], pos, 'red', target_spec['border'])
        
        elif condition_type == 'conjunction':
            # Średni - cechy targetu występują osobno
            if random.random() < 0.5:
                # Ten sam kolor, inny kształt
                shapes = ['circle', 'square', 'triangle']
                other_shapes = [s for s in shapes if s != target_spec['shape']]
                if len(other_shapes) == 0:
                    other_shapes = ['square']  # fallback
                dist_shape = random.choice(other_shapes)
                distractor = create_shape(win, dist_shape, pos, target_spec['color'], target_spec['border'])
            else:
                # Ten sam kształt, inny kolor
                colors = ['red', 'green', 'blue']
                other_colors = [c for c in colors if c != target_spec['color']]
                if len(other_colors) == 0:
                    other_colors = ['green']  # fallback
                dist_color = random.choice(other_colors)
                distractor = create_shape(win, target_spec['shape'], pos, dist_color, target_spec['border'])
        
        elif condition_type == 'complex':
            # Trudny - 3 kolory, 3 kształty, losowe obramowanie
            max_retries = 20
            retries = 0
            color = None
            shape = None
            border = None
            
            while retries < max_retries:
                color = random.choice(['red', 'green', 'blue'])
                shape = random.choice(['circle', 'square', 'triangle'])
                border = random.choice(['white', 'black'])
                # CRITICAL: Musi różnić się przynajmniej JEDNĄ cechą (kolor LUB kształt LUB obramowanie)
                if not (color == target_spec['color'] and shape == target_spec['shape'] and border == target_spec['border']):
                    break
                retries += 1
            
            # FALLBACK: Wymuś różnicę jeśli nie udało się wylosować
            if retries >= max_retries:
                log_debug(f"  ⚠ Complex: forcing difference from target")
                # Zmień kolor na pewno inny
                colors = ['red', 'green', 'blue']
                different_colors = [c for c in colors if c != target_spec['color']]
                color = random.choice(different_colors) if different_colors else 'red'
            
            distractor = create_shape(win, shape, pos, color, border)
        
        elif condition_type == 'very_complex':
            # Bardzo trudny - 4 kolory, 4 kształty, 2 obramowania
            max_retries = 20
            retries = 0
            color = None
            shape = None
            border = None
            
            while retries < max_retries:
                color = random.choice(['red', 'green', 'blue', 'yellow'])
                shape = random.choice(['circle', 'square', 'triangle', 'polygon'])
                border = random.choice(['white', 'black'])
                # CRITICAL: Musi różnić się przynajmniej JEDNĄ cechą
                if not (color == target_spec['color'] and shape == target_spec['shape'] and border == target_spec['border']):
                    break
                retries += 1
            
            # FALLBACK: Wymuś różnicę jeśli nie udało się wylosować
            if retries >= max_retries:
                log_debug(f"  ⚠ Very_complex: forcing difference from target")
                colors = ['red', 'green', 'blue', 'yellow']
                different_colors = [c for c in colors if c != target_spec['color']]
                color = random.choice(different_colors) if different_colors else 'red'
            
            distractor = create_shape(win, shape, pos, color, border)
        
        elif condition_type == 'extreme':
            # Ekstremalnie trudny - 5 kolorów, 5 kształtów, 2 obramowania
            # ZAWSZE generuj coś RÓŻNEGO od targetu - z WYMUSZENIEM
            max_retries = 50
            retries = 0
            color = None
            shape = None
            border = None
            
            while retries < max_retries:
                color = random.choice(['red', 'green', 'blue', 'yellow', 'orange'])
                shape = random.choice(['circle', 'square', 'triangle', 'polygon', 'star'])
                border = random.choice(['white', 'black'])
                # Musi różnić się przynajmniej jedną cechą
                if not (color == target_spec['color'] and shape == target_spec['shape'] 
                       and border == target_spec['border']):
                    break
                retries += 1
            
            # FALLBACK: Jeśli mimo wszystko nie udało się, wymuś różnicę
            if retries >= max_retries:
                log_debug(f"  ⚠ Max retries reached, forcing difference")
                # Zmień kolor na pewno inny
                all_colors = ['red', 'green', 'blue', 'yellow', 'orange']
                different_colors = [c for c in all_colors if c != target_spec['color']]
                color = random.choice(different_colors) if different_colors else 'red'
            
            distractor = create_shape(win, shape, pos, color, border)
        
        elements.append({'stim': distractor, 'is_target': False, 'pos': pos})
    
    # CRITICAL VALIDATION: Verify exactly 1 target exists
    target_count = sum(1 for elem in elements if elem['is_target'])
    if target_count != 1:
        log_debug(f"  ❌ ERROR: Generated {target_count} targets instead of 1!")
        log_debug(f"  Target spec: {target_spec}")
        log_debug(f"  Elements: {[(e['is_target'], e['pos']) for e in elements]}")
        raise ValueError(f"CRITICAL: Generated {target_count} targets, expected 1")
    
    # Dodatkowa walidacja - sprawdź że target ma właściwości
    target_elem = next((e for e in elements if e['is_target']), None)
    if target_elem and target_elem['stim'] is not None:
        log_debug(f"  ✓ Wygenerowano: 1 target + {len(elements)-1} distractors")
        log_debug(f"    Target pos: {target_elem['pos']}, fillColor: {getattr(target_elem['stim'], 'fillColor', 'unknown')}")
    else:
        log_debug(f"  ❌ ERROR: Target element has no stim object!")
        raise ValueError(f"CRITICAL: Target stim is None")
    return elements, target_pos

# ============================================================================
# CHECK CORRECT RESPONSE
# ============================================================================
def check_correct_response(gaze_data, target_pos, space_time, screen_width, screen_height):
    """
    Sprawdza czy SPACE została naciśnięta gdy oko patrzyło na target
    
    Returns: True jeśli poprawne, False jeśli nie
    """
    if len(gaze_data) == 0:
        return False
    
    # Sprawdź ostatnie 0.5s przed naciśnięciem SPACE
    target_x_norm = (target_pos[0] + screen_width/2) / screen_width
    target_y_norm = (screen_height/2 - target_pos[1]) / screen_height
    
    # Filtruj dane z okna czasowego przed SPACE
    relevant_gaze = [g for g in gaze_data 
                     if space_time - CORRECT_RESPONSE_WINDOW <= g['timestamp'] <= space_time]
    
    if len(relevant_gaze) == 0:
        return False
    
    # Sprawdź czy którykolwiek punkt był blisko targetu
    for g in relevant_gaze:
        dist_x = abs(g['x'] - target_x_norm) * screen_width
        dist_y = abs(g['y'] - target_y_norm) * screen_height
        dist = np.sqrt(dist_x**2 + dist_y**2)
        
        if dist < TARGET_DETECTION_RADIUS:
            return True
    
    return False

# ============================================================================
# FIND TARGET IN GAZE DATA
# ============================================================================
def find_target_fixation(fixations, target_pos, screen_width, screen_height):
    """
    Znajduje pierwszą fixację na targecie
    Returns: (fixation_index, time_to_target) lub (None, None)
    """
    target_x = target_pos[0] + screen_width/2
    target_y = screen_height/2 - target_pos[1]
    
    for i, fix in enumerate(fixations):
        dist = np.sqrt((fix['x'] - target_x)**2 + (fix['y'] - target_y)**2)
        if dist < TARGET_DETECTION_RADIUS:
            time_to_target = fix['start_time'] - fixations[0]['start_time']
            return i, time_to_target
    
    return None, None

# ============================================================================
# EXPERIMENT
# ============================================================================
def run_experiment():
    """Główna funkcja eksperymentu"""
    
    # Znajdź eye tracker
    eyetracker = find_eyetracker()
    if not eyetracker:
        print("\n❌ Nie można kontynuować bez eye trackera!")
        print("Sprawdź:")
        print("1. Czy eye tracker jest podłączony (USB)")
        print("2. Czy Tobii Eye Tracker Manager jest uruchomiony")
        print("3. Czy kalibracja została wykonana")
        input("\nNaciśnij Enter aby zakończyć...")
        return
    
    # Testuj połączenie z eye trackerem
    print("🔌 Testuję połączenie z eye trackerem...")
    try:
        # Krótki test subskrypcji
        test_data = []
        def test_callback(gaze_data):
            test_data.append(1)
        
        eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, test_callback, as_dictionary=True)
        core.wait(0.5)
        eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, test_callback)
        
        if len(test_data) == 0:
            print("❌ Eye tracker nie przesyła danych!")
            print("Sprawdź czy kalibracja została wykonana w Tobii Eye Tracker Manager")
            input("\nNaciśnij Enter aby zakończyć...")
            return
        
        print(f"✓ Eye tracker działa poprawnie ({len(test_data)} pakietów w 0.5s)")
    except Exception as e:
        print(f"❌ Błąd połączenia z eye trackerem: {e}")
        input("\nNaciśnij Enter aby zakończyć...")
        return
    
    # Stwórz okno PsychoPy
    print("🖥 Tworzę okno PsychoPy...")
    win = visual.Window(
        size=[SCREEN_WIDTH, SCREEN_HEIGHT],
        fullscr=True,
        units='pix',
        color='gray',
        allowGUI=False
    )
    
    # Ukryj kursor
    mouse_obj = mouse.Mouse(win=win, visible=False)
    
    # Setup gaze collector
    collector = GazeCollector()
    
    # Lista wyników
    all_results = []
    
    # Warunki bazowe - progresywnie coraz trudniejsze
    base_conditions = [
        {
            'name': 'ZADANIE 1',
            'type': 'conjunction',
            'set_size': 15,
            'target': {'shape': 'square', 'color': 'blue', 'border': 'white', 'name': 'niebieski kwadrat'},
            'description': 'Znajdź NIEBIESKI KWADRAT\nz BIAŁYM OBRAMOWANIEM'
        },
        {
            'name': 'ZADANIE 2',
            'type': 'extreme',
            'set_size': 20,
            'target': {'shape': 'star', 'color': 'orange', 'border': 'white', 'name': 'pomarańczowa gwiazda'},
            'description': 'Znajdź POMARAŃCZOWĄ GWIAZDĘ\nz BIAŁYM OBRAMOWANIEM'
        },
        {
            'name': 'ZADANIE 3',
            'type': 'very_complex',
            'set_size': 25,
            'target': {'shape': 'circle', 'color': 'red', 'border': 'black', 'name': 'czerwone kółko z czarnym obramowaniem'},
            'description': 'Znajdź CZERWONE KÓŁKO\nz CZARNYM OBRAMOWANIEM'
        },
        {
            'name': 'ZADANIE 4',
            'type': 'complex',
            'set_size': 30,
            'target': {'shape': 'triangle', 'color': 'green', 'border': 'white', 'name': 'zielony trójkąt'},
            'description': 'Znajdź ZIELONY TRÓJKĄT\nz BIAŁYM OBRAMOWANIEM'
        },
        {
            'name': 'ZADANIE 5',
            'type': 'extreme',
            'set_size': 35,
            'target': {'shape': 'polygon', 'color': 'yellow', 'border': 'black', 'name': 'żółty wielokąt z czarnym obramowaniem'},
            'description': 'Znajdź ŻÓŁTY WIELOKĄT\nz CZARNYM OBRAMOWANIEM'
        }
    ]
    
    # Triale: 5 z tekstem, 5 z wizualizacją, 5 z audio (jeśli TTS dostępne)
    # Twórz 3 GRUPY triali - każda grupa ma 5 triali od łatwych do trudnych
    text_conditions = []
    visual_conditions = []
    audio_conditions = []
    
    # Wersja tekstowa (kolejność od łatwych do trudnych)
    for cond in base_conditions:
        text_cond = cond.copy()
        text_cond['target'] = cond['target'].copy()
        text_cond['instruction_type'] = 'text'
        text_conditions.append(text_cond)
    
    # Wersja wizualna (kolejność od łatwych do trudnych)
    for cond in base_conditions:
        visual_cond = cond.copy()
        visual_cond['target'] = cond['target'].copy()
        visual_cond['instruction_type'] = 'visual'
        visual_conditions.append(visual_cond)
    
    # Wersja audio tylko jeśli TTS jest dostępne (kolejność od łatwych do trudnych)
    if TTS_AVAILABLE:
        for cond in base_conditions:
            audio_cond = cond.copy()
            audio_cond['target'] = cond['target'].copy()
            audio_cond['instruction_type'] = 'audio'
            audio_conditions.append(audio_cond)
    
    # Losuj kolejność GRUP (nie triali wewnątrz grup!)
    groups = [('text', text_conditions), ('visual', visual_conditions)]
    if TTS_AVAILABLE:
        groups.append(('audio', audio_conditions))
    
    random.shuffle(groups)
    log_debug(f"✓ Wylosowano kolejność grup: {' → '.join([g[0] for g in groups])}")
    
    # Złóż triale z grup w wylosowanej kolejności
    conditions = []
    for group_name, group_conditions in groups:
        conditions.extend(group_conditions)
    
    # ========================================================================
    # INITIALIZE CSV FILE FOR REAL-TIME RESULTS
    # ========================================================================
    csv_headers = ['trial_num', 'instruction_type', 'task_name', 'condition_type', 
                   'set_size', 'target_found', 'found_time', 'time_to_target', 
                   'reaction_time', 'num_fixations', 'target_fix_idx']
    
    with open(RESULTS_CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
    
    log_debug(f"✓ Created results CSV: {RESULTS_CSV_FILE.name}")
    
    # Instrukcja - dynamiczna w zależności czy TTS dostępne
    if TTS_AVAILABLE:
        instruction_text = ("VISUAL SEARCH\n\n"
                          "Za chwilę zobaczysz 15 zadań wyszukiwania.\n\n"
                          "5 zadań z TEKSTEM opisującym obiekt\n"
                          "5 zadań z OBRAZEM obiektu\n"
                          "5 zadań z GŁOSEM opisującym obiekt\n\n"
                          "Twoim celem jest:\n"
                          "→ Znaleźć WSKAZANY OBIEKT jak najszybciej\n"
                          "→ Nacisnąć SPACJĘ gdy go znajdziesz\n\n"
                          "Po każdym zadaniu zobaczysz\n"
                          "jak się poruszały Twoje oczy!\n\n"
                          "Naciśnij SPACJĘ aby zacząć")
    else:
        instruction_text = ("VISUAL SEARCH\n\n"
                          "Za chwilę zobaczysz 10 zadań wyszukiwania.\n\n"
                          "5 zadań z TEKSTEM opisującym obiekt\n"
                          "5 zadań z OBRAZEM obiektu\n\n"
                          "Twoim celem jest:\n"
                          "→ Znaleźć WSKAZANY OBIEKT jak najszybciej\n"
                          "→ Nacisnąć SPACJĘ gdy go znajdziesz\n\n"
                          "Po każdym zadaniu zobaczysz\n"
                          "jak się poruszały Twoje oczy!\n\n"
                          "Naciśnij SPACJĘ aby zacząć")
    
    instruction = visual.TextStim(
        win=win,
        text=instruction_text,
        height=26,
        color='white',
        wrapWidth=1000
    )
    
    instruction.draw()
    win.flip()
    keys = event.waitKeys(keyList=['space', 'escape'])
    if 'escape' in keys:
        log_debug("User pressed ESC at instruction screen")
        win.close()
        core.quit()
        return
    
    # ========================================================================
    # PĘTLA PO WARUNKACH
    # ========================================================================
    for trial_num, condition in enumerate(conditions, 1):
        try:
            print(f"\n=== TRIAL {trial_num}/{len(conditions)}: {condition['name']} ===")
        
            # Instrukcja dla tego warunku - RÓŻNA dla text vs visual vs audio
            instruction_type = condition.get('instruction_type', 'text')
        
            if instruction_type == 'visual':
                # Wersja WIZUALNA - pokazujemy przykładowy obiekt
                trial_instruction = visual.TextStim(
                    win=win,
                    text=f"ZADANIE {trial_num}/{len(conditions)}\n\n"
                         "Znajdź taki obiekt:",
                    height=28,
                    color='white',
                    wrapWidth=1000,
                    pos=(0, 150)  # Przesunięcie wyżej
                )
            
                trial_instruction.draw()
                
                # Tworzmy przykładowy obiekt z większym odstępem
                target_spec = condition['target']
                sample_object = create_shape(
                    win,
                    target_spec['shape'],
                    (0, 0),  # Wycentrowany z odstępem od tekstu
                    target_spec['color'],
                    target_spec['border'],
                    radius=70  # Nieco mniejszy
                )
                sample_object.draw()
                
                # Dodaj tekst "naciśnij spację"
                start_text = visual.TextStim(
                    win=win,
                    text="Naciśnij SPACJĘ gdy go znajdziesz!\n\nNaciśnij SPACJĘ aby zacząć...",
                    pos=(0, -180),
                    height=24,
                    color='gray',
                    wrapWidth=1000
                )
                start_text.draw()
                win.flip()
                keys = event.waitKeys(keyList=['space', 'escape'])
                if 'escape' in keys:
                    log_debug("User pressed ESC at visual instruction")
                    win.close()
                    core.quit()
            
            elif instruction_type == 'audio' and TTS_AVAILABLE:
                # Wersja AUDIO - od razu odtwarzanie głosu (BEZ żółtego ekranu)
                
                # Synteza mowy - NATYCHMIAST (bez info screen)
                try:
                    # Przygotuj tekst do wypowiedzenia
                    speech_text = condition['description'].replace('\n', ' ')
                    
                    if TTS_METHOD == 'gtts':
                        # Google TTS - generuj plik audio i odtwórz
                        from gtts import gTTS
                        from psychopy import sound
                        
                        # Utwórz folder tymczasowy
                        temp_dir = Path(__file__).parent / "temp_audio"
                        temp_dir.mkdir(exist_ok=True)
                        
                        # Wygeneruj unikalną nazwę pliku
                        audio_file = temp_dir / f"audio_{trial_num}.mp3"
                        
                        # Generuj tylko jeśli nie istnieje
                        if not audio_file.exists():
                            print(f"  Generuję audio: {speech_text[:50]}...")
                            tts = gTTS(text=speech_text, lang='pl', slow=False)
                            tts.save(str(audio_file))
                            print(f"  ✓ Zapisano: {audio_file.name}")
                        
                        # Odtwórz przez PsychoPy
                        audio = sound.Sound(str(audio_file))
                        audio.play()
                        
                        # Czekaj na zakończenie
                        while audio.status == sound.PLAYING:
                            core.wait(0.1)
                        
                    elif TTS_METHOD == 'pyttsx3':
                        # pyttsx3 - bezpośrednia synteza
                        import pyttsx3
                        engine = pyttsx3.init()
                        engine.setProperty('rate', 150)
                        engine.setProperty('volume', 1.0)
                        engine.say(speech_text)
                        engine.runAndWait()
                        engine.stop()
                        
                except Exception as e:
                    print(f"⚠ Błąd TTS: {e}")
                    import traceback
                    traceback.print_exc()
                
                # Poczekaj na SPACE aby kontynuować (już PO odtworzeniu)
                ready_text = visual.TextStim(
                    win=win,
                    text=f"ZADANIE {trial_num}/{len(conditions)}\n\n"
                         "Naciśnij SPACJĘ aby rozpocząć wyszukiwanie!",
                    height=28,
                    color='white',
                    wrapWidth=1000
                )
                ready_text.draw()
                win.flip()
                keys = event.waitKeys(keyList=['space', 'escape'])
                if 'escape' in keys:
                    log_debug("User pressed ESC after audio")
                    win.close()
                    core.quit()
            
            else:
                # Wersja TEKSTOWA - tradycyjna instrukcja
                trial_instruction = visual.TextStim(
                    win=win,
                    text=f"ZADANIE {trial_num}/{len(conditions)}: {condition['name']}\n\n"
                         f"{condition['description']}\n\n"
                         "Naciśnij SPACJĘ gdy znajdziesz wskazany obiekt!\n\n"
                         "Naciśnij SPACJĘ aby zacząć...",
                    height=26,
                    color='white',
                    wrapWidth=1000
                )
                trial_instruction.draw()
                win.flip()
                keys = event.waitKeys(keyList=['space', 'escape'])
                if 'escape' in keys:
                    log_debug("User pressed ESC at text instruction")
                    win.close()
                    core.quit()
            
            # Krótka przerwa (countdown)
            for i in [3, 2, 1]:
                countdown = visual.TextStim(win=win, text=str(i), height=100, color='white')
                countdown.draw()
                win.flip()
                core.wait(0.5)
            
            # Generuj display
            print(f"🎨 Generuję {condition['type']} search display (set_size={condition['set_size']}, target={condition['target']['name']})...")
            elements, target_pos = generate_search_display(win, condition['type'], condition['target'], condition['set_size'])
            
            # ====================================================================
            # SEARCH TASK + ZBIERANIE DANYCH
            # ====================================================================
            print(f"👁 Zbieranie danych gaze...")
            
            try:
                eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, collector.callback, as_dictionary=True)
            except Exception as e:
                print(f"❌ Błąd subskrypcji: {e}")
                win.close()
                return
            
            collector.start()
            
            # Zapisz start_time dla pomiaru czasu
            start_time = core.getTime()
            found_time = None
            
            # DEBUG: Sprawdź elementy przed rysowaniem
            target_elements = [e for e in elements if e['is_target']]
            log_debug(f"  🎨 Rozpoczynam rysowanie {len(elements)} elementów (w tym {len(target_elements)} target)")
            if target_elements:
                log_debug(f"    Target fillColor: {getattr(target_elements[0]['stim'], 'fillColor', 'N/A')}")
            
            while core.getTime() - start_time < SEARCH_DURATION:
                # Rysuj wszystkie elementy
                for elem in elements:
                    elem['stim'].draw()
                
                win.flip()
                
                keys = event.getKeys()
                if 'space' in keys:
                    found_time = core.getTime() - start_time
                    print(f"✓ Użytkownik nacisnął SPACJĘ po {found_time:.2f}s")
                    break
                if 'escape' in keys:
                    collector.stop()
                    try:
                        eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, collector.callback)
                    except:
                        pass
                    win.close()
                    core.quit()
            
            gaze_data = collector.stop()
            try:
                eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, collector.callback)
            except Exception as e:
                print(f"⚠ Ostrzeżenie przy unsubscribe: {e}")
            
            if found_time is None:
                found_time = SEARCH_DURATION
                print("⏱ Timeout - nie znaleziono w czasie")
            
            print(f"✓ Zebrano {len(gaze_data)} punktów gaze")
            
            if len(gaze_data) == 0:
                print("⚠ BRAK DANYCH - pomijam")
                continue
            
            # Oblicz fixacje
            print(f"🔍 Obliczam fixacje...")
            fixations = detect_fixations(gaze_data, SCREEN_WIDTH, SCREEN_HEIGHT)
            print(f"✓ Znaleziono {len(fixations)} fixacji")
            
            # Znajdź pierwszą fixację na targecie
            target_fix_idx, time_to_target = find_target_fixation(fixations, target_pos, SCREEN_WIDTH, SCREEN_HEIGHT)
            
            # Walidacja: JEŚLI była fixacja na targecie = SUKCES
            # Czas reakcji (found_time - time_to_target) jest mierzony ale nie dyskwalifikuje
            if target_fix_idx is not None:
                is_correct = True
                reaction_time = found_time - time_to_target
                print(f"✓ TRAFIONY - fixacja #{target_fix_idx+1} po {time_to_target:.2f}s, SPACE po {found_time:.2f}s (RT: {reaction_time:.2f}s)")
            else:
                is_correct = False
                reaction_time = None
                print(f"❌ NIETRAFIONY - brak fixacji na targecie, SPACE po {found_time:.2f}s")
            
            # ====================================================================
            # ZAPISZ WYNIKI - PRZED SCANPATH (prevent data loss!)
            # ====================================================================
            # Zapisz wyniki DO PAMIĘCI
            trial_result = {
                'name': condition['name'],
                'type': condition['type'],
                'set_size': condition['set_size'],
                'instruction_type': condition.get('instruction_type', 'text'),
                'num_fixations': len(fixations),
                'found_time': found_time,
                'time_to_target': time_to_target if time_to_target is not None else found_time,
                'reaction_time': reaction_time,
                'is_correct': is_correct,
                'target_fix_idx': target_fix_idx
            }
            all_results.append(trial_result)
            
            # ZAPISZ DO CSV W CZASIE RZECZYWISTYM (prevent memory overload)
            try:
                with open(RESULTS_CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=csv_headers)
                    writer.writerow({
                        'trial_num': trial_num,
                        'instruction_type': trial_result['instruction_type'],
                        'task_name': trial_result['name'],
                        'condition_type': trial_result['type'],
                        'set_size': trial_result['set_size'],
                        'target_found': trial_result['is_correct'],
                        'found_time': f"{trial_result['found_time']:.3f}",
                        'time_to_target': f"{trial_result['time_to_target']:.3f}",
                        'reaction_time': f"{trial_result['reaction_time']:.3f}" if trial_result['reaction_time'] else 'N/A',
                        'num_fixations': trial_result['num_fixations'],
                        'target_fix_idx': trial_result['target_fix_idx'] if trial_result['target_fix_idx'] is not None else 'N/A'
                    })
                log_debug(f"✓ Saved trial {trial_num} to CSV")
            except Exception as csv_error:
                log_debug(f"⚠ CSV write error: {csv_error}")
            
            # ====================================================================
            # POKAŻ SCANPATH - zawsze!
            # ====================================================================
            print("📊 Pokazuję scanpath...")
            
            # Konwertuj współrzędne (jeśli są fixacje)
            for fix in fixations:
                fix['x_win'] = fix['x'] - SCREEN_WIDTH/2
                fix['y_win'] = SCREEN_HEIGHT/2 - fix['y']
                
            # Rysuj display
            for elem in elements:
                elem['stim'].draw()
            
            # Gradient kolorów + linie (tylko jeśli są fixacje)
            if len(fixations) > 1:
                num_fix = len(fixations)
                for i in range(len(fixations) - 1):
                    t = i / max(1, num_fix - 1)
                    
                    if t < 0.5:
                        r = 1.0
                        g = t * 2.0
                        b = 0.0
                    else:
                        r = 1.0 - (t - 0.5) * 2.0
                        g = 1.0
                        b = 0.0
                    
                    line_color = [r, g, b]
                    
                    line = visual.Line(
                        win=win,
                        start=[fixations[i]['x_win'], fixations[i]['y_win']],
                        end=[fixations[i+1]['x_win'], fixations[i+1]['y_win']],
                        lineColor=line_color,
                        lineWidth=3
                    )
                    line.draw()
            
            # Rysuj fixacje (tylko jeśli są)
            if len(fixations) > 0:
                num_fix = len(fixations)
                for i, fix in enumerate(fixations):
                    t = i / max(1, num_fix - 1)
                    
                    if t < 0.5:
                        r = 1.0
                        g = t * 2.0
                        b = 0.0
                    else:
                        r = 1.0 - (t - 0.5) * 2.0
                        g = 1.0
                        b = 0.0
                    
                    color = [r, g, b]
                    radius = min(50, max(15, fix['duration'] * 60))
                    
                    # Oznacz target fixation na żółto
                    if i == target_fix_idx:
                        circle_color = 'yellow'
                        line_width = 5
                    else:
                        circle_color = color
                        line_width = 3
                    
                    circle = visual.Circle(
                        win=win,
                        radius=radius,
                        pos=[fix['x_win'], fix['y_win']],
                        fillColor=circle_color,
                        lineColor='white',
                        lineWidth=line_width,
                        opacity=0.7
                    )
                    circle.draw()
                    
                    number = visual.TextStim(
                        win=win,
                        text=str(i+1),
                        pos=[fix['x_win'], fix['y_win']],
                        height=22,
                        color='black',
                        bold=True
                    )
                    number.draw()
            
            # Info z wynikami
            if target_fix_idx is not None and is_correct:
                result_text = f"✓ POPRAWNE!\n" \
                             f"Fixacja #{target_fix_idx+1} po {time_to_target:.2f}s\n" \
                             f"(SPACE naciśnięte po {found_time:.2f}s)"
                result_color = 'lightgreen'
            elif target_fix_idx is not None and not is_correct:
                result_text = f"❌ BŁĄD!\n" \
                             f"Target w fixacji #{target_fix_idx+1} po {time_to_target:.2f}s\n" \
                             f"Ale SPACE naciśnięte bez patrzenia na target ({found_time:.2f}s)"
                result_color = 'salmon'
            else:
                result_text = f"❌ BŁĄD!\n" \
                             f"Czas: {found_time:.2f}s\n" \
                             f"Target nie znaleziony"
                result_color = 'salmon'
            
            info = visual.TextStim(
                win=win,
                text=f"{condition['name']}\n"
                     f"Fixacji: {len(fixations)}\n"
                     f"{result_text}\n\n"
                     f"🔴 = start | 🟢 = koniec | 🟡 = target\n\n"
                     f"SPACJA = dalej",
                pos=[0, -450],
                height=22,
                color=result_color,
                wrapWidth=1200
            )
            info.draw()
            
            win.flip()
            keys = event.waitKeys(keyList=['space', 'escape'])
            if 'escape' in keys:
                log_debug("User pressed ESC at scanpath")
                win.close()
                core.quit()
        
        except Exception as e:
            print(f"❌ Błąd w trialu {trial_num}: {e}")
            import traceback
            traceback.print_exc()
            # Kontynuuj do następnego trialu
            continue
    
    # ========================================================================
    # PODSUMOWANIE - WYKRES WYNIKÓW
    # ========================================================================
    log_debug(f"\n✓ Zakończono {len(conditions)} trials!")
    log_debug(f"All results collected: {len(all_results)} items")
    
    # Verify data integrity
    if len(all_results) == 0:
        log_debug("❌ ERROR: No results collected!")
        win.close()
        core.quit()
        return
    
    # Podziel wyniki na text vs visual vs audio
    text_results = [r for r in all_results if r['instruction_type'] == 'text']
    visual_results = [r for r in all_results if r['instruction_type'] == 'visual']
    audio_results = [r for r in all_results if r['instruction_type'] == 'audio']
    
    log_debug(f"Results breakdown: Text={len(text_results)}, Visual={len(visual_results)}, Audio={len(audio_results)}")
    
    print("\n" + "="*50)
    print("PODSUMOWANIE WYNIKÓW")
    print("="*50)
    print("\nINSTRUKCJE TEKSTOWE:")
    for result in text_results:
        status = "✓ POPRAWNIE" if result['is_correct'] else "✗ BŁĄD"
        print(f"  {result['name']}: {status} - {result['found_time']:.2f}s")
    
    print("\nINSTRUKCJE WIZUALNE:")
    for result in visual_results:
        status = "✓ POPRAWNIE" if result['is_correct'] else "✗ BŁĄD"
        print(f"  {result['name']}: {status} - {result['found_time']:.2f}s")
    
    print("\nINSTRUKCJE AUDIO (TTS):")
    for result in audio_results:
        status = "✓ POPRAWNIE" if result['is_correct'] else "✗ BŁĄD"
        rt_text = f" (RT: {result['reaction_time']:.3f}s)" if result['reaction_time'] is not None else ""
        print(f"  {result['name']}: {status} - {result['found_time']:.2f}s{rt_text}")
    
    print("\n" + "="*50)
    print("ANALIZA CZASÓW REAKCJI (Reaction Time)")
    print("="*50)
    print("RT = Delta między rozpoczęciem fiksacji na targecie a naciśnięciem SPACE\n")
    
    # TEKST - Reaction Time Analysis
    if text_results:
        text_rts = [r['reaction_time'] for r in text_results if r['reaction_time'] is not None]
        if text_rts:
            text_rt_avg = sum(text_rts) / len(text_rts)
            print(f"TEKST - RT:")
            for i, result in enumerate(text_results, 1):
                if result['reaction_time'] is not None:
                    print(f"  Trial {i}: Fiksacja po {result['time_to_target']:.2f}s → SPACE po {result['found_time']:.2f}s = RT: {result['reaction_time']:.3f}s")
                else:
                    print(f"  Trial {i}: Brak fiksacji na targecie")
            print(f"  📊 Średni RT dla TEKST: {text_rt_avg:.3f}s\n")
    
    # VISUAL - Reaction Time Analysis
    if visual_results:
        visual_rts = [r['reaction_time'] for r in visual_results if r['reaction_time'] is not None]
        if visual_rts:
            visual_rt_avg = sum(visual_rts) / len(visual_rts)
            print(f"OBRAZ - RT:")
            for i, result in enumerate(visual_results, 1):
                if result['reaction_time'] is not None:
                    print(f"  Trial {i}: Fiksacja po {result['time_to_target']:.2f}s → SPACE po {result['found_time']:.2f}s = RT: {result['reaction_time']:.3f}s")
                else:
                    print(f"  Trial {i}: Brak fiksacji na targecie")
            print(f"  📊 Średni RT dla OBRAZ: {visual_rt_avg:.3f}s\n")
    
    # AUDIO - Reaction Time Analysis
    if audio_results:
        audio_rts = [r['reaction_time'] for r in audio_results if r['reaction_time'] is not None]
        if audio_rts:
            audio_rt_avg = sum(audio_rts) / len(audio_rts)
            print(f"GŁOS - RT:")
            for i, result in enumerate(audio_results, 1):
                if result['reaction_time'] is not None:
                    print(f"  Trial {i}: Fiksacja po {result['time_to_target']:.2f}s → SPACE po {result['found_time']:.2f}s = RT: {result['reaction_time']:.3f}s")
                else:
                    print(f"  Trial {i}: Brak fiksacji na targecie")
            print(f"  📊 Średni RT dla GŁOS: {audio_rt_avg:.3f}s\n")
    
    # Statystyki porównawcze
    if text_results:
        text_avg = sum(r['found_time'] for r in text_results) / len(text_results)
        text_correct = sum(1 for r in text_results if r['is_correct'])
        text_errors = len(text_results) - text_correct
        print(f"\n📊 TEKST - Średnia: {text_avg:.2f}s | Poprawne: {text_correct}/{len(text_results)} | Błędy: {text_errors}")
    
    if visual_results:
        visual_avg = sum(r['found_time'] for r in visual_results) / len(visual_results)
        visual_correct = sum(1 for r in visual_results if r['is_correct'])
        visual_errors = len(visual_results) - visual_correct
        print(f"📊 WIZUALIZACJA - Średnia: {visual_avg:.2f}s | Poprawne: {visual_correct}/{len(visual_results)} | Błędy: {visual_errors}")
    
    if audio_results:
        audio_avg = sum(r['found_time'] for r in audio_results) / len(audio_results)
        audio_correct = sum(1 for r in audio_results if r['is_correct'])
        audio_errors = len(audio_results) - audio_correct
        print(f"📊 AUDIO - Średnia: {audio_avg:.2f}s | Poprawne: {audio_correct}/{len(audio_results)} | Błędy: {audio_errors}")
    
    log_debug("="*50)
    log_debug("📊 Pokazuję wykres wyników...")
    
    try:
        # Tytuł - dynamiczny w zależności czy TTS było dostępne
        if TTS_AVAILABLE and audio_results:
            title_text = "PODSUMOWANIE - TEKST vs OBRAZ vs GŁOS"
        else:
            title_text = "PODSUMOWANIE - TEKST vs OBRAZ"
        
        title = visual.TextStim(
            win=win,
            text=title_text,
            pos=[0, 460],
            height=22,
            color='white',
            bold=True
        )
        title.draw()
    
        # Wykres słupkowy - STACKED BARS pokazujące czas szukania + czas reakcji
        # Dynamiczna szerokość w zależności od liczby triali
        num_trials = len(all_results)
        if num_trials <= 10:
            bar_width = 70
            bar_spacing = 90
        else:
            bar_width = 55
            bar_spacing = 62
        max_height = 200
    
        # Znajdź maksymalny czas (dla skalowania)
        max_time = max([r['found_time'] for r in all_results])
    
        for i, result in enumerate(all_results):
            # Pozycja słupka - dynamiczna dla 10 lub 15 słupków
            if num_trials <= 10:
                start_x = -450
            else:
                start_x = -430
            x_pos = start_x + i * bar_spacing
        
            # Całkowita wysokość słupka (found_time)
            total_height = (result['found_time'] / max_time) * max_height
            
            # Jeśli była fixacja na targecie - pokazujemy jako STACKED BAR
            if result['is_correct'] and result['reaction_time'] is not None:
                # Dolna część: czas szukania (do fixacji) - niebieski
                search_time_height = (result['time_to_target'] / max_time) * max_height
                
                search_bar = visual.Rect(
                    win=win,
                    width=bar_width,
                    height=search_time_height,
                    pos=[x_pos, 50 + search_time_height/2],
                    fillColor='dodgerblue',
                    lineColor='white',
                    lineWidth=2
                )
                search_bar.draw()
                
                # Górna część: czas reakcji (od fixacji do SPACE) - żółty/pomarańczowy
                rt_height = (result['reaction_time'] / max_time) * max_height
                
                rt_bar = visual.Rect(
                    win=win,
                    width=bar_width,
                    height=rt_height,
                    pos=[x_pos, 50 + search_time_height + rt_height/2],
                    fillColor='gold',
                    lineColor='white',
                    lineWidth=2
                )
                rt_bar.draw()
            else:
                # Jeśli nie znaleziono targetu - czerwony słupek (timeout)
                bar = visual.Rect(
                    win=win,
                    width=bar_width,
                    height=total_height,
                    pos=[x_pos, 50 + total_height/2],
                    fillColor='red',
                    lineColor='white',
                    lineWidth=2
                )
                bar.draw()
        
            # Całkowity czas nad słupkiem
            time_text = visual.TextStim(
                win=win,
                text=f"{result['found_time']:.1f}",
                pos=[x_pos, 50 + total_height + 12],
                height=11,
                color='white',
                bold=True
            )
            time_text.draw()
        
            # Numer trial pod słupkiem
            trial_num = i + 1
            num_text = visual.TextStim(
                win=win,
                text=f"{trial_num}",
                pos=[x_pos, 10],
                height=10,
                color='white'
            )
            num_text.draw()
        # Separator 1 (po 5 trialu)
        separator1 = visual.Line(
            win=win,
            start=[start_x + 4.5 * bar_spacing, 10],
            end=[start_x + 4.5 * bar_spacing, 320],
            lineColor='yellow',
            lineWidth=2
        )
        separator1.draw()
    
        # Etykiety grup
        text_label = visual.TextStim(
            win=win,
            text='TEKST',
            pos=[start_x + 2 * bar_spacing, 330],
            height=18,
            color='cyan',
            bold=True
        )
        text_label.draw()
    
        visual_label = visual.TextStim(
            win=win,
            text='OBRAZ',
            pos=[start_x + 7 * bar_spacing, 330],
            height=18,
            color='cyan',
            bold=True
        )
        visual_label.draw()
    
        # Separator 2 i etykieta GŁOS tylko jeśli są audio triale
        if TTS_AVAILABLE and audio_results:
            separator2 = visual.Line(
                win=win,
                start=[start_x + 9.5 * bar_spacing, 10],
                end=[start_x + 9.5 * bar_spacing, 320],
                lineColor='yellow',
                lineWidth=2
            )
            separator2.draw()
        
            audio_label = visual.TextStim(
                win=win,
                text='GŁOS',
                pos=[start_x + 12 * bar_spacing, 330],
                height=18,
                color='cyan',
                bold=True
            )
            audio_label.draw()
        
        # LEGENDA dla słupków stacked
        legend_title = visual.TextStim(
            win=win,
            text='Interpretacja słupków:',
            pos=[-600, 380],
            height=16,
            color='white',
            bold=True
        )
        legend_title.draw()
        
        legend_text = visual.TextStim(
            win=win,
            text='🔵 Niebieski = Czas szukania (do fixacji na targecie)\n'
                 '🟡 Żółty = Reakcja (od fixacji do SPACE)\n'
                 '🔴 Czerwony = Błąd (nie znaleziono targetu)',
            pos=[-600, 350],
            height=14,
            color='lightgray',
            wrapWidth=300
        )
        legend_text.draw()
    
        # ====================================================================
        # PORÓWNANIE ŚREDNICH - wykres słupkowy na dole + BŁĘDY + REACTION TIME
        # ====================================================================
        if text_results or visual_results or audio_results:
            comp_title = visual.TextStim(
                win=win,
                text='Porównanie średnich czasów, błędów i RT',
                pos=[0, -100],
                height=20,
                color='white',
                bold=True
            )
            comp_title.draw()
        
            # Zbierz dane
            groups = []
            if text_results:
                text_avg = sum(r['found_time'] for r in text_results) / len(text_results)
                text_correct = sum(1 for r in text_results if r['is_correct'])
                text_errors = len(text_results) - text_correct
                text_rts = [r['reaction_time'] for r in text_results if r['reaction_time'] is not None]
                text_rt_avg = sum(text_rts) / len(text_rts) if text_rts else 0
                groups.append(('Tekst', text_avg, text_correct, text_errors, text_rt_avg, 'orange'))
        
            if visual_results:
                visual_avg = sum(r['found_time'] for r in visual_results) / len(visual_results)
                visual_correct = sum(1 for r in visual_results if r['is_correct'])
                visual_errors = len(visual_results) - visual_correct
                visual_rts = [r['reaction_time'] for r in visual_results if r['reaction_time'] is not None]
                visual_rt_avg = sum(visual_rts) / len(visual_rts) if visual_rts else 0
                groups.append(('Obraz', visual_avg, visual_correct, visual_errors, visual_rt_avg, 'cyan'))
        
            if audio_results:
                audio_avg = sum(r['found_time'] for r in audio_results) / len(audio_results)
                audio_correct = sum(1 for r in audio_results if r['is_correct'])
                audio_errors = len(audio_results) - audio_correct
                audio_rts = [r['reaction_time'] for r in audio_results if r['reaction_time'] is not None]
                audio_rt_avg = sum(audio_rts) / len(audio_rts) if audio_rts else 0
                groups.append(('Głos', audio_avg, audio_correct, audio_errors, audio_rt_avg, 'magenta'))
        
            # Parametry wykresu porównawczego
            comp_bar_width = 100
            comp_max_height = 140
            # CRITICAL FIX: Używaj tej samej skali co indywidualne słupki dla spójności!
            comp_max_time = max_time  # Ta sama skala co indywidualne triale
        
            # Pozycje słupków
            positions = [-250, 0, 250] if len(groups) == 3 else ([-150, 150] if len(groups) == 2 else [0])
        
            for i, (name, avg_time, correct, errors, rt_avg, color) in enumerate(groups):
                x_pos = positions[i]
                comp_height = (avg_time / comp_max_time) * comp_max_height
            
                # Słupek czasu
                comp_bar = visual.Rect(
                    win=win,
                    width=comp_bar_width,
                    height=comp_height,
                    pos=[x_pos, -250 + comp_height/2],
                    fillColor=color,
                    lineColor='white',
                    lineWidth=2
                )
                comp_bar.draw()
            
                # Czas nad słupkiem
                time_text = visual.TextStim(
                    win=win,
                    text=f'{avg_time:.2f}s',
                    pos=[x_pos, -250 + comp_height + 15],
                    height=16,
                    color='white',
                    bold=True
                )
                time_text.draw()
            
                # Nazwa pod słupkiem
                label_text = visual.TextStim(
                    win=win,
                    text=name,
                    pos=[x_pos, -310],
                    height=16,
                    color='white'
                )
                label_text.draw()
            
                # Statystyki błędów i RT
                stats_text = visual.TextStim(
                    win=win,
                    text=f'✓{correct}  ✗{errors}\\nRT: {rt_avg:.2f}s' if rt_avg > 0 else f'✓{correct}  ✗{errors}',
                    pos=[x_pos, -340],
                    height=11,
                    color='lightgray'
                )
                stats_text.draw()
    
        # Legenda poprawności - dynamiczna
        if TTS_AVAILABLE and audio_results:
            legend_text = ("🟢 Zielony = poprawna odpowiedź (oko na targecie)\n"
                          "🔴 Czerwony = błędna odpowiedź (oko nie na targecie)\n"
                          "✓ = poprawne odpowiedzi | ✗ = błędy\n\n"
                          "Porównaj czasy i błędy między TEKSTEM, OBRAZEM a GŁOSEM!\n\n"
                          "SPACJA = koniec")
        else:
            legend_text = ("🟢 Zielony = poprawna odpowiedź (oko na targecie)\n"
                          "🔴 Czerwony = błędna odpowiedź (oko nie na targecie)\n"
                          "✓ = poprawne odpowiedzi | ✗ = błędy\n\n"
                          "Porównaj czasy i błędy między TEKSTEM a OBRAZEM!\n\n"
                          "SPACJA = koniec")
    
        legend = visual.TextStim(
            win=win,
            text=legend_text,
            pos=[0, -390],
            height=14,
            color='white',
            wrapWidth=1400
        )
        legend.draw()
    
        win.flip()
        keys = event.waitKeys(keyList=['space', 'escape'])
        if 'escape' in keys:
            log_debug("User pressed ESC at results screen")
            win.close()
            core.quit()
            return
    
    except Exception as chart_error:
        log_debug(f"❌ CHART RENDERING ERROR: {chart_error}")
        import traceback
        log_debug(traceback.format_exc())
        
        # Show simple error message to user
        error_text = visual.TextStim(
            win=win,
            text=f"Error displaying results chart.\nData saved to CSV: {RESULTS_CSV_FILE.name}\n\nPress SPACE to exit",
            pos=[0, 0],
            height=24,
            color='red',
            wrapWidth=1000
        )
        error_text.draw()
        win.flip()
        event.waitKeys(keyList=['space'])
    
    # Cleanup
    win.close()
    log_debug(f"\n✓ Eksperyment zakończony!")
    log_debug(f"Results saved to: {RESULTS_CSV_FILE}")
    log_debug(f"Debug log saved to: {DEBUG_LOG_FILE}")

# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    try:
        run_experiment()
    except Exception as e:
        print(f"\n❌ Błąd: {e}")
        import traceback
        traceback.print_exc()
        input("\nNaciśnij Enter aby zakończyć...")
