"""App texts in English and German.  T("key", name=value) -> text in the app language."""

_lang = "en"

TEXTS = {
    # --- window, sidebar ---
    "app_title": ("Macro Pad", "Macro Pad"),
    "menu_home": ("Main menu", "Hauptmenü"),
    "menu_keys": ("Key mapping", "Tastenbelegung"),
    "menu_leds": ("RGB LED", "RGB LED"),
    "menu_language": ("Language", "Sprache"),
    "menu_update": ("Update & Repair", "Update & Repair"),
    "menu_guide": ("Guide", "Anleitung"),
    "menu_display": ("Display", "Display"),
    "pad_status": ("Macro Pad status:", "Macro Pad Status:"),
    "st_connected": ("Connected", "Verbunden"),
    "st_searching": ("Searching", "Suche..."),
    "st_busy": ("Don't disconnect", "Nicht trennen"),
    "st_disconnected": ("Disconnected", "Getrennt"),
    "autostart": ("Autostart", "Autostart"),
    "version": ("Version: v{v}", "Version: v{v}"),
    "apply": ("Apply", "Anwenden"),
    "applying": ("Changing", "Wird geändert"),
    "unsaved_hint": ("Unsaved changes", "Nicht gespeicherte Änderungen"),
    "tray_open": ("Open Macro Pad", "Macro Pad öffnen"),
    "tray_quit": ("Quit", "Beenden"),
    "tray_running": ("Macro Pad keeps running here. Right-click for Quit.",
                     "Macro Pad läuft hier weiter. Rechtsklick zum Beenden."),

    # --- apply popup ---
    "apply_title": ("Changing settings", "Einstellungen werden geändert"),
    "apply_wait": ("About {s} seconds. Please do not unplug the macro pad.",
                   "Ca. {s} Sekunden. Bitte das Macro Pad nicht abstecken."),
    "apply_done": ("Done - the pad has the new settings.", "Fertig - das Pad hat die neuen Einstellungen."),
    "apply_failed": ("The pad did not take the settings ({why}). They are saved and will be sent again "
                     "when the pad is connected.",
                     "Das Pad hat die Einstellungen nicht übernommen ({why}). Sie sind gespeichert und "
                     "werden erneut gesendet, sobald das Pad verbunden ist."),
    "apply_offline": ("Saved. The macro pad is not connected - the settings are sent as soon as you plug it in.",
                      "Gespeichert. Das Macro Pad ist nicht verbunden - die Einstellungen werden gesendet, "
                      "sobald du es einsteckst."),
    "apply_old_fw": ("Saved. The pad's firmware is too old for settings from the app - "
                     "please update it under Update & Repair.",
                     "Gespeichert. Die Firmware des Pads ist zu alt für Einstellungen aus der App - "
                     "bitte unter Update & Repair aktualisieren."),
    "ok": ("OK", "OK"),
    "cancel": ("Cancel", "Abbrechen"),
    "close": ("Close", "Schließen"),
    "yes": ("Yes", "Ja"),
    "no": ("No", "Nein"),

    # --- home ---
    "home_sub": ("handcrafted by {maker}", "handgefertigt von {maker}"),
    "home_hint": ("Pick a menu on the left. Changes take effect when you press Apply.",
                  "Wähle links ein Menü. Änderungen gelten, sobald du auf Anwenden drückst."),
    "now_playing": ("Now playing", "Läuft gerade"),
    "nothing_playing": ("No music playing", "Keine Musik"),
    "music_off": ("Music info is not available on this PC.", "Musik-Infos sind auf diesem PC nicht verfügbar."),

    # --- keys ---
    "keys_title": ("Key mapping", "Tastenbelegung"),
    "keys_hint": ("Click a key to choose what it does.", "Klicke auf eine Taste, um ihre Funktion zu wählen."),
    "keys_reset": ("Reset all keys", "Alle Tasten zurücksetzen"),
    "keys_reset_q": ("Put every key back to the default layout?", "Alle Tasten auf die Standardbelegung zurücksetzen?"),
    "knob": ("Knob", "Drehknopf"),
    "knob_press": ("Press: mute", "Drücken: Stumm"),
    "knob_turn": ("Turn: volume", "Drehen: Lautstärke"),
    "knob_pc": ("PC", "PC"),
    "knob_app": ("Music app", "Music App"),
    "knob_note": ("Without the app running, the knob always controls the Windows volume.",
                  "Ohne laufende App steuert der Knopf immer die Windows-Lautstärke."),
    "fallback_note": ("Only while the app runs. Without the app this key is the {what} again.",
                      "Nur solange die App läuft. Ohne App ist diese Taste wieder die {what}."),
    "what_lights": ("light key", "Licht-Taste"),
    "what_fun2": ("Fun 2 colour key", "Fun-2-Farbtaste"),
    "pick_title": ("Key {n}: choose an action", "Taste {n}: Funktion wählen"),
    "cat_special": ("Special", "Spezial"),
    "cat_fkeys_high": ("F13 - F24", "F13 - F24"),
    "cat_media": ("Media", "Medien"),
    "cat_shortcuts": ("Shortcuts", "Shortcuts"),
    "cat_fkeys": ("F1 - F12", "F1 - F12"),
    "cat_letters": ("Letters", "Buchstaben"),
    "cat_digits": ("Digits", "Zahlen"),
    "cat_editing": ("Editing", "Bearbeiten"),
    "cat_navigation": ("Navigation", "Navigation"),
    "cat_system": ("System", "System"),
    "cat_symbols": ("Symbols", "Sonderzeichen"),
    "cat_numpad": ("Numpad", "Ziffernblock"),
    "cat_combo": ("Own shortcut", "Eigener Shortcut"),
    "combo_hint": ("Tick the modifier keys and pick the key - or click the box and press the combination.",
                   "Hake die Zusatztasten an und wähle die Taste - oder klicke ins Feld und drücke die Kombination."),
    "combo_record": ("Click here, then press the keys", "Hier klicken, dann die Tasten drücken"),
    "combo_key": ("Key", "Taste"),
    "desc_none": ("The key does nothing.", "Die Taste macht nichts."),
    "desc_lights": ("Tap = next light mode, hold + turn the knob = light brightness.",
                    "Tippen = nächster Lichtmodus, halten + Knopf drehen = Lichthelligkeit."),
    "desc_fun2": ("Tap = F23, hold + turn the knob = light colour.",
                  "Tippen = F23, halten + Knopf drehen = Lichtfarbe."),

    # --- leds ---
    "leds_title": ("RGB LED", "RGB LED"),
    "leds_modes": ("Light modes", "Lichtmodi"),
    "leds_modes_hint": ("The selected mode is active. Ticked modes come up when you tap the light key.",
                        "Der gewählte Modus ist aktiv. Angehakte Modi kommen beim Tippen der Licht-Taste dran."),
    "leds_brightness": ("Brightness", "Helligkeit"),
    "leds_colour": ("Colour for \"Key glow\" and \"One colour\"", "Farbe für \"Tasten-Glühen\" und \"Eine Farbe\""),
    "leds_schemes": ("Own schemes ({n}/10)", "Eigene Schemata ({n}/10)"),
    "leds_new": ("New scheme", "Neues Schema"),
    "leds_rename": ("Rename", "Umbenennen"),
    "leds_delete": ("Delete", "Löschen"),
    "leds_delete_q": ("Delete the scheme \"{name}\"?", "Schema \"{name}\" löschen?"),
    "leds_name_q": ("Name of the scheme (max. 15 characters):", "Name des Schemas (max. 15 Zeichen):"),
    "leds_effect": ("Effect", "Effekt"),
    "fx_static": ("Steady", "Konstant"),
    "fx_breathe": ("Breathing", "Atmen"),
    "fx_glow": ("Glow on press", "Leuchten beim Drücken"),
    "leds_click_key": ("Click a key to give it a colour.", "Klicke auf eine Taste, um ihr eine Farbe zu geben."),
    "leds_fill": ("All keys in one colour", "Alle Tasten in einer Farbe"),
    "leds_max": ("You already have 10 schemes - delete one first.", "Du hast schon 10 Schemata - lösche zuerst eins."),
    "leds_no_scheme": ("No own scheme yet. Create one with \"New scheme\".",
                       "Noch kein eigenes Schema. Erstelle eins mit \"Neues Schema\"."),
    "mode_0": ("Rainbow wave", "Regenbogen"),
    "mode_1": ("Gradient", "Farbverlauf"),
    "mode_2": ("Music colour", "Musikfarbe"),
    "mode_3": ("Music beat", "Musik-Beat"),
    "mode_4": ("Key glow", "Tasten-Glühen"),
    "mode_5": ("One colour", "Eine Farbe"),
    "mode_6": ("Lights off", "Licht aus"),
    "new_scheme_name": ("My scheme {n}", "Mein Schema {n}"),

    # --- language ---
    "lang_title": ("Language", "Sprache"),
    "lang_app": ("App language", "Sprache der App"),
    "lang_pad": ("Macro Pad language", "Sprache des Macro Pads"),
    "lang_note": ("The welcome animation on the pad always stays English.",
                  "Die Begrüßungsanimation auf dem Pad bleibt immer Englisch."),

    # --- display ---
    "disp_title": ("Display", "Display"),
    "disp_bg": ("Background animation", "Hintergrund-Animation"),
    "bg_aquarium": ("Aquarium", "Aquarium"),
    "bg_plain": ("Plain (no animation)", "Schlicht (keine Animation)"),
    "disp_fish": ("Fish in the aquarium", "Fische im Aquarium"),
    "disp_brightness": ("Screen brightness", "Display-Helligkeit"),
    "disp_music": ("Show the music player while music plays", "Musik-Player anzeigen, während Musik läuft"),
    "disp_note": ("The background shows whenever no song is on the screen. The button on the side of the "
                  "display still switches between bright, dim and off.",
                  "Der Hintergrund erscheint immer, wenn kein Song angezeigt wird. Der Knopf seitlich am "
                  "Display schaltet weiterhin zwischen hell, gedimmt und aus."),
    "more_soon": ("More animations will follow with updates.", "Weitere Animationen kommen mit Updates."),

    # --- update & repair ---
    "upd_title": ("Update & Repair", "Update & Repair"),
    "upd_app": ("App", "App"),
    "upd_fw": ("Pad firmware", "Pad-Firmware"),
    "upd_installed": ("Installed: v{v}", "Installiert: v{v}"),
    "upd_check": ("Check for updates", "Nach Updates suchen"),
    "upd_checking": ("Checking...", "Suche..."),
    "upd_auto": ("Check automatically", "Automatisch suchen"),
    "upd_none": ("You have the newest version.", "Du hast die neueste Version."),
    "upd_avail": ("Version v{v} is available.", "Version v{v} ist verfügbar."),
    "upd_now": ("Update now", "Jetzt updaten"),
    "upd_off": ("Updates are not set up in this build (no GitHub repository).",
                "Updates sind in diesem Build nicht eingerichtet (kein GitHub-Repository)."),
    "upd_error": ("Could not check for updates: {e}", "Konnte nicht nach Updates suchen: {e}"),
    "fw_pad": ("On the pad: {v}", "Auf dem Pad: {v}"),
    "fw_bundled": ("In this app: v{v}", "In dieser App: v{v}"),
    "fw_old": ("old (before the app)", "alt (vor der App)"),
    "fw_unknown": ("pad not connected", "Pad nicht verbunden"),
    "fw_flash": ("Flash firmware", "Firmware flashen"),
    "fw_flash_q": ("Flash firmware v{v} onto the pad now? It takes about {s} seconds. Do not unplug the pad "
                   "until it is done. Your keys and lights stay as they are.",
                   "Firmware v{v} jetzt auf das Pad flashen? Das dauert ca. {s} Sekunden. Das Pad bis zum "
                   "Ende nicht abstecken. Tasten und Licht bleiben wie eingestellt."),
    "fw_newer_avail": ("The app has newer firmware for your pad.", "Die App hat neuere Firmware für dein Pad."),
    "fw_missing": ("No firmware files in this app build.", "Keine Firmware-Dateien in diesem App-Build."),
    "repair": ("Repair", "Reparieren"),
    "repair_check": ("Check files", "Dateien prüfen"),
    "repair_ok": ("All {n} files are fine.", "Alle {n} Dateien sind in Ordnung."),
    "repair_bad": ("{n} file(s) are damaged or missing.", "{n} Datei(en) beschädigt oder fehlend."),
    "repair_now": ("Repair now", "Jetzt reparieren"),
    "repair_newer": ("Your app is older than the newest version - an update repairs it too.",
                     "Deine App ist älter als die neueste Version - ein Update repariert sie gleich mit."),
    "repair_source": ("checked against v{v}", "geprüft gegen v{v}"),
    "repair_pad": ("Pad does not start or behaves oddly? Flash the firmware again - it also works when the "
                   "pad hangs in update mode.",
                   "Pad startet nicht oder verhält sich komisch? Firmware erneut flashen - das klappt "
                   "auch, wenn das Pad im Update-Modus hängt."),
    "prog_download": ("Downloading the update", "Update wird geladen"),
    "prog_flash": ("Flashing the firmware", "Firmware wird geflasht"),
    "prog_left": ("About {t} left", "Noch ca. {t}"),
    "prog_starting": ("Starting...", "Startet..."),
    "prog_bootloader": ("Restarting the pad in update mode...", "Pad startet im Update-Modus neu..."),
    "prog_writing": ("Writing to the pad...", "Wird auf das Pad geschrieben..."),
    "prog_reconnect": ("Waiting for the pad to restart...", "Warte auf den Neustart des Pads..."),
    "prog_no_unplug": ("Do not unplug the macro pad.", "Das Macro Pad nicht abstecken."),
    "prog_cancel_q": ("Stop now? The pad then stays in update mode until you flash it again "
                      "(Update & Repair > Flash firmware).",
                      "Jetzt abbrechen? Das Pad bleibt dann im Update-Modus, bis du erneut flashst "
                      "(Update & Repair > Firmware flashen)."),
    "prog_install": ("The installer starts now. The app closes and opens again when it is done.",
                     "Der Installer startet jetzt. Die App schließt sich und öffnet sich danach wieder."),
    "flash_ok": ("Firmware v{v} is on the pad.", "Firmware v{v} ist auf dem Pad."),
    "flash_failed": ("Flashing did not work: {e}", "Flashen hat nicht geklappt: {e}"),
    "cancelled": ("Cancelled.", "Abgebrochen."),
    "sec": ("{n} s", "{n} s"),
    "min": ("{n} min", "{n} min"),

    # --- guide ---
    "guide_title": ("Guide", "Anleitung"),
    "guide_switch_t": ("Changing a switch", "Switch austauschen"),
    "guide_switch": (
        "1. Unplug the pad.\n2. Pull the keycap off with the keycap puller.\n"
        "3. Put the switch puller on the two clips (top and bottom of the switch), squeeze and pull "
        "it straight up.\n4. Check that both metal pins of the new switch are straight.\n"
        "5. Line the pins up with the holes and press the switch straight down until it clicks into the "
        "plate. If it is hard to push, take it out and check the pins - a bent pin is the most common reason "
        "a key does nothing.",
        "1. Pad abstecken.\n2. Keycap mit dem Keycap-Puller abziehen.\n"
        "3. Den Switch-Puller an die zwei Klammern (oben und unten am Switch) setzen, zusammendrücken "
        "und gerade nach oben ziehen.\n4. Prüfen, ob beide Metallpins des neuen Switches gerade sind.\n"
        "5. Pins auf die Löcher ausrichten und den Switch gerade nach unten drücken, bis er in der "
        "Platte einrastet. Geht es schwer: rausnehmen und Pins prüfen - ein verbogener Pin ist der "
        "häufigste Grund, wenn eine Taste nicht reagiert."),
    "guide_cap_t": ("Changing a keycap", "Keycap austauschen"),
    "guide_cap": (
        "Pull the old cap straight up with the keycap puller (pulling by hand can lift the whole switch "
        "out of its socket). Push the new cap straight down onto the cross-shaped stem until it sits firmly. "
        "Any MX-compatible 1U keycap fits; see-through or shine-through caps show the lights best.",
        "Alte Kappe mit dem Keycap-Puller gerade nach oben ziehen (mit den Fingern kann der ganze Switch "
        "aus dem Sockel kommen). Neue Kappe gerade auf den kreuzförmigen Stempel drücken, bis sie "
        "fest sitzt. Jede MX-kompatible 1U-Keycap passt; durchsichtige oder Shine-Through-Kappen zeigen "
        "das Licht am besten."),
    "guide_tips_t": ("Tips & fixing problems", "Tipps & Fehlerbehebung"),
    "guide_tips": (
        "• Status stays \"Searching\": try another USB cable (some only charge) or another USB port.\n"
        "• \"Disconnected\" although plugged in: close the Arduino Serial Monitor and the old "
        "macropad_helper (both block the pad). Remove the old helper from autostart.\n"
        "• A key does nothing: swap its switch with a working one. If the problem moves with the "
        "switch, the switch is bad; if not, check the socket and its solder joints.\n"
        "• One LED stays dark and all after it too: the fault is at the first dark LED.\n"
        "• No song on the screen: start Spotify or Deezer and play a song; music info needs Windows "
        "10 or 11.\n"
        "• Pad hangs or shows nothing after an update: Update & Repair > Flash firmware.\n"
        "• The log file for help requests: {log}",
        "• Status bleibt bei \"Suche...\": anderes USB-Kabel probieren (manche laden nur) oder "
        "anderen USB-Anschluss.\n"
        "• \"Getrennt\", obwohl eingesteckt: Arduino Serial Monitor und den alten macropad_helper "
        "schließen (beide blockieren das Pad). Den alten Helper aus dem Autostart entfernen.\n"
        "• Eine Taste reagiert nicht: ihren Switch mit einem funktionierenden tauschen. Wandert der "
        "Fehler mit, ist der Switch kaputt; sonst Sockel und Lötstellen prüfen.\n"
        "• Eine LED bleibt dunkel und alle danach auch: der Fehler sitzt bei der ersten dunklen LED.\n"
        "• Kein Song auf dem Display: Spotify oder Deezer starten und einen Song abspielen; Musik-Infos "
        "brauchen Windows 10 oder 11.\n"
        "• Pad hängt oder zeigt nichts nach einem Update: Update & Repair > Firmware flashen.\n"
        "• Log-Datei für Hilfeanfragen: {log}"),
    "guide_credit_t": ("Design", "Design"),
    "guide_credit": ("Macro Pad design by {maker}.", "Macro-Pad-Design von {maker}."),

    # --- errors ---
    "err_title": ("Something went wrong", "Etwas ist schiefgelaufen"),
    "err_body": ("The app caught an error and keeps running. Details are in the log file:\n{log}\n\n{e}",
                 "Die App hat einen Fehler abgefangen und läuft weiter. Details stehen in der Log-Datei:\n"
                 "{log}\n\n{e}"),
    "err_port_busy": ("Another program is using the pad ({port}). Close the Arduino Serial Monitor or the "
                      "old macropad_helper.",
                      "Ein anderes Programm benutzt das Pad ({port}). Arduino Serial Monitor oder den alten "
                      "macropad_helper schließen."),
    "err_save": ("Could not save the settings to {path}.", "Konnte die Einstellungen nicht unter {path} speichern."),
    "admin_needed": ("This needs administrator rights - Windows will ask you.",
                     "Dafür sind Administratorrechte nötig - Windows fragt dich gleich."),
}


def set_language(lang: str):
    global _lang
    _lang = "de" if lang == "de" else "en"


def language() -> str:
    return _lang


def T(key: str, **kw) -> str:
    pair = TEXTS.get(key)
    if pair is None:
        return key
    text = pair[1] if _lang == "de" else pair[0]
    try:
        return text.format(**kw) if kw else text
    except (KeyError, IndexError, ValueError):
        return text
