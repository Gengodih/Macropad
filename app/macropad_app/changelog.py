"""What changed in each version (newest first), shown in "Update & Repair"
and put into the release, so the app can show what an update brings."""

CHANGES = {
    "1.6.1": {
        "en": ["Pad firmware 2.3.1: the screen now always comes back after the PC was shut down or asleep "
               "(please flash it once under Pad firmware)",
               "A key press turns the pad's screen on for a minute, even while the PC sleeps"],
        "de": ["Pad-Firmware 2.3.1: Das Display geht jetzt immer wieder an, nachdem der PC aus war oder geschlafen hat "
               "(bitte einmal unter Pad-Firmware flashen)",
               "Ein Tastendruck schaltet das Display für eine Minute ein, auch wenn der PC schläft"],
    },
    "1.6.0": {
        "en": ["Music app volume: the pad now shows what you hear (Windows volume × the app's level)",
               "Layer 2 removed",
               "\"What's new\" box in Update & Repair"],
        "de": ["Lautstärke der Musik-App: Das Pad zeigt jetzt, was du hörst (Windows-Lautstärke × Stufe der App)",
               "Ebene 2 entfernt",
               "\"Was ist neu\"-Box unter Update & Repair"],
    },
    "1.5.0": {
        "en": ["Screen widgets: clock, PC stats, focus timer",
               "Own picture or GIF on the pad's screen",
               "Small timer on every background while the focus timer runs"],
        "de": ["Display-Widgets: Uhr, PC-Werte, Fokus-Timer",
               "Eigenes Bild oder GIF auf dem Display des Pads",
               "Kleiner Timer auf jedem Hintergrund, solange der Fokus-Timer läuft"],
    },
    "1.4.0": {
        "en": ["Macros: shortcuts, text, open programs or websites, pauses",
               "Tap / hold / double-tap keys",
               "Profiles that switch the keys per program",
               "Microphone key that glows red when muted",
               "Sleep when the PC is locked or idle, backup to a file, welcome name, statistics"],
        "de": ["Makros: Shortcuts, Text, Programme oder Webseiten öffnen, Pausen",
               "Tippen-/Halten-/Doppeltippen-Tasten",
               "Profile, die die Tasten je nach Programm wechseln",
               "Mikrofon-Taste, die bei stummem Mikro rot leuchtet",
               "Ruhezustand bei gesperrtem oder unbenutztem PC, Sicherung in eine Datei, Name in der Begrüßung, Statistik"],
    },
    "1.3.0": {
        "en": ["7 new pad backgrounds with live previews in the app",
               "Sleepy fox by the campfire"],
        "de": ["7 neue Pad-Hintergründe mit Live-Vorschau in der App",
               "Schläfriger Fuchs am Lagerfeuer"],
    },
}


def notes(version: str, lang: str = "en") -> list[str]:
    entry = CHANGES.get(version, {})
    return list(entry.get(lang) or entry.get("en") or [])


def as_dict(version: str) -> dict:
    """For the release manifest: {"en": [...], "de": [...]}."""
    return {lang: notes(version, lang) for lang in ("en", "de")}
