# App 4 - Malowanie Glosem i Wzrokiem

Artsy app do tworzenia obrazow impressionistycznych:
- spojrzenie steruje polozeniem pedzla,
- glos (cechy dzwieku) steruje kolorem, pulsem i energia sladu,
- w trybie DEV dziala bez eye-trackera (mysz = spojrzenie).

## Uruchomienie

### Windows

```bat
run_app4.bat
```

### macOS/Linux

```bash
bash run_app4.sh
```

## Sterowanie

- `SPACE`: zakoncz i zapisz obraz
- `C`: wyczysc plotno
- `S`: zapisz obraz od razu
- `ESC`: wyjdz

## Uwagi

- Tryb `DEV` jest do budowania na laptopach studentow.
- Tryb `NAUCZYCIELA` wymaga Tobii X3-120 i lokalnego SDK.
- Jezeli `sounddevice` nie jest dostepny, aplikacja przechodzi na proceduralna symulacje audio, aby sesja nadal byla estetyczna i plynna.
