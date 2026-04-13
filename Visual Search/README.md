# Visual Search Demo - Dni Otwarte

Demonstracja różnicy między **Pop-out Search** a **Conjunction Search** z śledzeniem ruchu oczu.

## 🎯 Cel eksperymentu

Pokazać studentom różnicę między:
- **Bottom-up attention** (pop-out) - automatyczne, szybkie
- **Top-down attention** (conjunction) - świadome, wolne

## 📋 Warunki eksperymentalne

### 1. POP-OUT Search
**Zadanie:** Znajdź CZERWONE KÓŁKO wśród zielonych kółek

**Dlaczego jest łatwe:**
- Target różni się jedną cechą (kolor)
- Uwaga jest przyciągana automatycznie (bottom-up)
- Szybkie znalezienie (~1-2 fixacje)
- Nie zależy od liczby distractorów

### 2. CONJUNCTION Search
**Zadanie:** Znajdź CZERWONE KÓŁKO wśród:
- Czerwonych kwadratów (ten sam kolor, inny kształt)
- Zielonych kółek (ten sam kształt, inny kolor)

**Dlaczego jest trudne:**
- Target wymaga kombinacji cech (kolor + kształt)
- Wymaga świadomego poszukiwania (top-down)
- Wiele fixacji
- Czas rośnie z liczbą distractorów

## 🔬 Teoria psychologiczna

**Feature Integration Theory** (Treisman & Gelade, 1980)
- Pojedyncze cechy są przetwarzane równolegle i automatycznie
- Kombinacje cech wymagają sekwencyjnej uwagi
- Pop-out = preattentive processing
- Conjunction = attentive processing

## 📊 Co śledzimy

1. **Czas do pierwszej fixacji na targecie** - jak szybko oko znajduje cel
2. **Liczba fixacji** - ile razy trzeba spojrzeć
3. **Struktura ścieżki** - czy systematyczna czy chaotyczna
4. **Czas reakcji** - kiedy użytkownik nacisnął SPACE

## ✨ Funkcje

- ✅ Fullscreen (ukryty pasek Windows)
- ✅ 2 warunki: Pop-out + Conjunction
- ✅ 12 distractorów + 1 target (łącznie 13 elementów)
- ✅ Losowe rozmieszczenie w każdym trial
- ✅ Gradient scanpath (🔴 start → 🟢 koniec)
- ✅ Żółte zaznaczenie pierwszej fixacji na targecie
- ✅ Automatyczna detekcja fixacji (I-DT algorithm)
- ✅ Countdown 3-2-1 przed każdym trial
- ✅ Statystyki: liczba fixacji, czas do znalezienia

## 🎮 Jak używać

1. Upewnij się że eye tracker jest podłączony i skalibrowany
2. Uruchom `run_experiment.bat`
3. Instrukcja dla uczestnika:
   - Znajdź CZERWONE KÓŁKO
   - Naciśnij SPACJĘ gdy je znajdziesz
4. Po każdym zadaniu - SPACJA aby zobaczyć scanpath
5. Całość trwa ~2 minuty

## 📈 Typowe wyniki

**Pop-out:**
- Czas znalezienia: 0.5-1.5s
- Fixacji: 1-3
- Ścieżka: Bezpośrednia do targetu

**Conjunction:**
- Czas znalezienia: 2-5s
- Fixacji: 5-15
- Ścieżka: Systematyczne skanowanie lub losowe przeszukiwanie

## ⚙️ Konfiguracja

W pliku `visual_search_experiment.py`:

```python
SEARCH_DURATION = 10.0  # Max czas (sekundy)
SET_SIZE = 12           # Liczba distractorów (więcej = trudniej)
ITEM_RADIUS = 40        # Wielkość kółek/kwadratów
TARGET_DETECTION_RADIUS = 80  # Jak blisko = "znaleziony"
```

## 🎓 Dla prowadzącego

**Co pokazać studentom:**
1. Różnicę w czasie między pop-out a conjunction
2. Różnicę w liczbie fixacji
3. Różnicę w strukturze ścieżki (prosta vs. chaotyczna)
4. Że pop-out jest "automatyczny" - oko idzie od razu do targetu
5. Że conjunction wymaga "pracy" - systematyczne przeszukiwanie

**Pytania do dyskusji:**
- Dlaczego pop-out jest łatwiejszy?
- Co się dzieje gdy dodamy więcej distractorów?
- Jak mózg wie gdzie patrzeć w pop-out?
- Jaka strategia jest używana w conjunction search?

## 🐛 Troubleshooting

**Eye tracker nie znaleziony:**
- Sprawdź kabel USB
- Uruchom Tobii Eye Tracker Manager
- Zrób kalibrację

**Nie zbiera danych gaze:**
- Problem z `as_dictionary=True` (już naprawiony w kodzie)
- Sprawdź czy SDK jest w `../x3-120 SDK/64/`

**Zawieszanie się:**
- Wszystkie obiekty visual są tworzone raz na początku
- Nie powinno się zawieszać

## 📝 Rozszerzenia (opcjonalne)

Możesz dodać:
- Więcej poziomów trudności (różne SET_SIZE)
- Warunek z 24 distractorami
- Heatmapa zamiast/oprócz scanpath
- Zapis danych do CSV
- Randomizacja kolejności warunków
- Więcej prób każdego typu
