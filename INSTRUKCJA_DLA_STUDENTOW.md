# Instrukcja dla studentow (krok po kroku)

Ta instrukcja pokazuje jak:
1. zalogowac sie w VS Code,
2. sklonowac repozytorium,
3. uruchomic aplikacje szablonowa,
4. edytowac kod,
5. testowac lokalnie w trybie DEV,
6. zapisac zmiany i wyslac je na GitHub.

## 1) Co trzeba miec na komputerze

Przed startem upewnij sie, ze masz:
- konto GitHub,
- VS Code,
- Git,
- Python 3.10+ (albo nowszy 3.x).

## 2) Pierwsze logowanie w VS Code

1. Otworz VS Code.
2. Kliknij ikonke konta w prawym gornym rogu.
3. Wybierz `Sign in with GitHub`.
4. Dokoncz logowanie w przegladarce.
5. Wroc do VS Code (powinno pokazac, ze jestes zalogowany).

## 3) Sklonowanie repozytorium na swoj komputer

### Opcja A (najprostsza, przez VS Code)

1. Wcisnij `Ctrl+Shift+P`.
2. Wpisz: `Git: Clone` i wybierz ta komende.
3. Wklej adres repo, np.:
   `https://github.com/berbelekhieronim/Template-AI-Apps.git`
4. Wybierz folder docelowy na komputerze.
5. Kliknij `Open` gdy VS Code zapyta, czy otworzyc projekt.

### Opcja B (przez terminal)

W terminalu wpisz:

```bash
git clone https://github.com/berbelekhieronim/Template-AI-Apps.git
cd Template-AI-Apps
code .
```

## 4) Instalacja bibliotek (jednorazowo)

W projekcie uruchom:

### Windows (polecane)

```bat
install_deps.bat
```

### Albo recznie (gdy skrypt nie dziala)

```bash
py -3 -m pip install -r requirements-students.txt
```

## 5) Uruchomienie aplikacji szablonowej w trybie DEV

1. Otworz folder `AI Template App`.
2. Uruchom:

```bat
AI Template App\run_app.bat
```

3. Na ekranie startowym wybierz tryb `DEV`.
4. W trybie DEV zamiast eyetrackera uzywana jest myszka.

To oznacza, ze mozesz budowac i testowac aplikacje bez urzadzenia Tobii.

## 6) Jak edytowac aplikacje szablonowa

1. Otworz plik:
   `AI Template App/ai_template_app.py`
2. Zmieniaj tylko male fragmenty na raz.
3. Po kazdej zmianie uruchom aplikacje ponownie w trybie DEV i sprawdz czy dziala.
4. Jezeli pojawi sie blad, cofnij ostatnia zmiane i popraw kod.

Dobra praktyka:
- najpierw zmiana tekstow i kolorow,
- potem nowa logika,
- na koncu zapis wynikow i raport.

## 7) Szybki cykl pracy (najlepszy na zajecia)

1. Zmien fragment kodu.
2. Zapisz plik (`Ctrl+S`).
3. Uruchom aplikacje w DEV.
4. Sprawdz czy dziala.
5. Powtorz.

## 8) Zapis zmian do GitHub

Po zakonczeniu pracy:

```bash
git add .
git commit -m "Opis co zostalo zmienione"
git push
```

Jesli pracujecie na forkach, wysylajcie zmiany do swojego forka.

## 9) Najczestsze problemy i szybkie rozwiazania

1. `python` lub `py` nie dziala:
- zainstaluj Pythona i zaznacz opcje dodania do PATH.

2. `git` nie dziala:
- doinstaluj Git i uruchom ponownie VS Code.

3. Brak bibliotek:
- uruchom jeszcze raz `install_deps.bat`.

4. Aplikacja nie laczy sie z eyetrackerem:
- do testow wybierz tryb DEV.
- tryb TEACHER uruchamiaj tylko na komputerze z Tobii i SDK.

## 10) Co oddajecie prowadzacemu

Na koniec oddajecie:
1. link do swojego repo/forka,
2. kod dzialajacej aplikacji,
3. krotki opis: co aplikacja robi i jak ja uruchomic w DEV.

Powodzenia i pracujcie iteracyjnie: mala zmiana -> test -> kolejna zmiana.
