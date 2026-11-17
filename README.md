# Macro Pad – App, Firmware & Installer

Die Windows-App für das ESP32-S3 Macro Pad (Design: Gengodih). Sie ersetzt den alten `macropad_helper.py` und kann:

- **Tastenbelegung**: jede Taste frei belegen (F13–F24, alle Tasten, Media, Shortcuts wie Kopieren oder Snipping Tool, eigene Kombinationen, „Nichts“). Licht-Taste und Fun 2 lassen sich auch belegen, sind ohne laufende App aber wieder die Licht-Tasten.
- **Drehknopf**: Lautstärke und Stumm, wahlweise für den ganzen PC oder nur die Musik-App.
- **RGB LED**: alle Lichtmodi, Helligkeit, Farbe, bis zu 10 eigene Schemata mit einer Farbe pro Taste.
- **Sprache**: App und Pad jeweils Deutsch oder Englisch. Die Begrüßung auf dem Pad bleibt Englisch.
- **Display**: Hintergrund (Aquarium oder schlicht), Fische an/aus, Helligkeit, Musik-Player an/aus.
- **Update & Repair**: prüft selbst auf neue Versionen, aktualisiert die App, flasht die Firmware mit Restzeit-Anzeige und Abbrechen-Knopf und prüft die Programmdateien.
- **Anleitung**: Switches und Keycaps tauschen, Tipps zur Fehlersuche.

Deine Einstellungen liegen in `%APPDATA%\MacroPad`, getrennt vom Programm. Updates ändern daran nichts. Das Pad speichert seine Einstellungen außerdem selbst, sie funktionieren also auch ohne App.

## Ordner

| Ordner | Inhalt |
|---|---|
| `app/macropad_app` | die App (Python + PySide6) |
| `firmware/macropad` | die Pad-Firmware (Arduino) |
| `installer` | das Setup (Inno Setup) |
| `.github/workflows` | baut auf GitHub automatisch Firmware, App und Setup |
| `tests` | automatische Tests |
| `tools` | Hilfsskripte für den Build |

## Einmalig: GitHub einrichten

1. Lege auf **github.com** einen kostenlosen Account an.
2. Klicke oben rechts auf **+ → New repository**:
   - Name: `macropad`
   - **Public** auswählen (sonst können die Apps deiner Freunde die Updates nicht abrufen)
   - **Create repository** klicken
3. Lade diesen ganzen Ordner hoch, am einfachsten mit **GitHub Desktop** (desktop.github.com):
   - *File → Add local repository* → diesen Ordner wählen
   - *Publish repository* klicken
   - Alternativ geht es im Browser über *Add file → Upload files*: alle Dateien und Ordner hineinziehen, auch den Ordner `.github`.
4. Gehe im Repository auf **Settings → Actions → General** und prüfe, dass unter *Workflow permissions* **Read and write permissions** ausgewählt ist.

## Eine Version veröffentlichen

1. Öffne im Repository den Tab **Actions**.
2. Wähle links **Release** und klicke **Run workflow**.
3. Nach ca. 10–15 Minuten liegt unter **Releases** die neue Version mit:
   - `MacroPad-Setup-1.1.0.exe`: das Setup für dich und deine Freunde
   - `manifest.json`: wird von der App für Updates und Repair gebraucht
   - `firmware-2.0.0.zip`: die Firmware

Für ein Update erhöhst du zuerst die Version:

- **App**: `VERSION` in `app/macropad_app/__init__.py`
- **Firmware**, falls du sie geändert hast: `FW_VERSION` in `firmware/macropad/macropad.ino`

Danach hochladen und wieder **Run workflow** klicken. Alle installierten Apps finden das Update dann von selbst.

## Erste Installation

1. Das Setup starten. Es fragt nach der Sprache (Englisch ist vorausgewählt), dem Installationsort und ob ein Desktop-Symbol angelegt werden soll.
   - „Nur für mich“ braucht keine Administratorrechte.
   - „Für alle Benutzer“ installiert nach *Programme*. Dafür fragt Windows nach Administratorrechten.
2. Den alten `macropad_helper` beenden und aus dem Autostart entfernen. Er blockiert sonst das Pad.
3. Das Pad hat noch die alte Firmware. Gehe in der App auf **Update & Repair → Firmware flashen**.
   - Falls das Pad nicht in den Update-Modus wechselt: Pad abstecken, den BOOT-Knopf am T-Display gedrückt halten, wieder einstecken und nochmal flashen.

Hinweis: Mit der neuen Firmware sendet der BOOT-Knopf am T-Display **F24** (vorher F18), weil F18 jetzt auf einer der 15 Tasten liegt.

## Ohne GitHub bauen (zum Testen)

`build.bat` doppelklicken. Das Skript installiert bei Bedarf Python 3.12, baut die App und führt die Tests aus. Wenn Inno Setup 6 installiert ist, baut es auch das Setup. Danach liegt die App unter `dist\MacroPad\MacroPad.exe`.

## Für Entwickler

```
pip install -r requirements.txt
python -m unittest discover -s tests -v       # Tests
python tests/native/run_native.py              # Firmware-Parser nativ (braucht g++)
cd app && python -m macropad_app               # App aus dem Quellcode starten
```
