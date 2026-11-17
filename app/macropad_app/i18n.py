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
    "menu_settings": ("Settings", "Einstellungen"),
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
    "knob_note": ("Music app: the knob only changes the music app, and the pad shows what you hear from it "
                  "(Windows volume × the app's level in the volume mixer). Spotify's own volume slider cannot be "
                  "read by other programs. Without the app running, the knob always controls the Windows volume.",
                  "Music App: Der Drehknopf ändert nur die Musik-App, und das Pad zeigt, was du von ihr hörst "
                  "(Windows-Lautstärke × Stufe der App im Lautstärkemixer). Den eigenen Lautstärkeregler von Spotify "
                  "können andere Programme nicht lesen. Ohne laufende App steuert der Drehknopf immer die Windows-Lautstärke."),
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
    "disp_anim": ("Animated background on the pad's screen", "Animierter Hintergrund auf dem Display des Pads"),
    "disp_anim_off": ("Off: the pad shows its plain screen with the status and the last key.",
                      "Aus: Das Pad zeigt seinen schlichten Bildschirm mit Status und letzter Taste."),
    "disp_try": ("Tip: click the chosen preview again to see how it reacts to a key press.",
                 "Tipp: Klick nochmal auf die gewählte Vorschau, um zu sehen, wie sie auf einen Tastendruck reagiert."),
    "disp_screen": ("Screen", "Bildschirm"),
    "disp_needs_fw": ("Your pad still has the older firmware, which only knows the aquarium. Update it under "
                      "Update & Repair to get this background on the pad.",
                      "Dein Pad hat noch die ältere Firmware, die nur das Aquarium kennt. Aktualisiere sie unter "
                      "Update & Repair, damit dieser Hintergrund auch auf dem Pad erscheint."),
    "bg_aquarium": ("Aquarium", "Aquarium"),
    "bg_synthwave": ("Synthwave", "Synthwave"),
    "bg_lava": ("Lava lamp", "Lavalampe"),
    "bg_space": ("Space", "Weltraum"),
    "bg_fire": ("Campfire", "Lagerfeuer"),
    "bg_matrix": ("Matrix code", "Matrix-Code"),
    "bg_rain": ("Rainy night", "Regennacht"),
    "bg_seasons": ("Seasons", "Jahreszeiten"),
    "bgd_aquarium": ("Fish, plants and bubbles. Every key press drops a little food into the water.",
                     "Fische, Pflanzen und Blasen. Jeder Tastendruck streut etwas Futter ins Wasser."),
    "bgd_synthwave": ("A retro sunset over neon mountains. The grid speeds up when you press a key.",
                      "Ein Retro-Sonnenuntergang über Neon-Bergen. Das Gitter wird bei jedem Tastendruck schneller."),
    "bgd_lava": ("Soft wax rising and sinking. A key press gives one of the blobs a push.",
                 "Weiches Wachs steigt und sinkt. Ein Tastendruck gibt einem Klecks einen Schubs."),
    "bgd_space": ("Drifting stars, shooting stars and a ringed planet.",
                  "Vorbeiziehende Sterne, Sternschnuppen und ein Planet mit Ring."),
    "bgd_fire": ("A crackling pixel campfire. Every key press sends up a shower of sparks.",
                 "Ein knisterndes Pixel-Lagerfeuer. Jeder Tastendruck lässt Funken fliegen."),
    "bgd_matrix": ("Green code raining down the screen.", "Grüner Code, der über den Bildschirm regnet."),
    "bgd_rain": ("A city at night in the rain. Windows light up, drops run down the glass.",
                 "Eine Stadt bei Nacht im Regen. Fenster gehen an und aus, Tropfen laufen die Scheibe herunter."),
    "bgd_seasons": ("A landscape that changes with the time of year: snow, blossoms, fireflies or falling leaves.",
                    "Eine Landschaft, die sich mit der Jahreszeit ändert: Schnee, Blüten, Glühwürmchen oder fallendes Laub."),
    "opt_aquarium_fish": ("Fish in the aquarium", "Fische im Aquarium"),
    "opt_synthwave_beat": ("Pulse with the music", "Im Takt der Musik pulsieren"),
    "opt_lava_light_colour": ("Use the light colour of the keys", "Lichtfarbe der Tasten verwenden"),
    "opt_space_rocket": ("A rocket flies past when you press a key", "Bei Tastendruck fliegt eine Rakete vorbei"),
    "opt_fire_beat": ("Dance to the music", "Zur Musik tanzen"),
    "opt_fire_fox": ("Sleepy fox by the fire (looks up when you press a key)",
                     "Schläfriger Fuchs am Feuer (schaut auf, wenn du eine Taste drückst)"),
    "opt_matrix_key_names": ("Pressed keys fall along as golden words", "Gedrückte Tasten fallen als goldene Wörter mit"),
    "opt_rain_storm": ("Thunderstorm with lightning", "Gewitter mit Blitzen"),
    "season_auto": ("By date", "Nach Datum"),
    "season_winter": ("Winter", "Winter"),
    "season_spring": ("Spring", "Frühling"),
    "season_summer": ("Summer", "Sommer"),
    "season_autumn": ("Autumn", "Herbst"),
    "disp_brightness": ("Screen brightness", "Display-Helligkeit"),
    "disp_music": ("Show the music player while music plays", "Musik-Player anzeigen, während Musik läuft"),
    "disp_note": ("The background shows whenever no song is on the screen. The button on the side of the "
                  "display still switches between bright, dim and off.",
                  "Der Hintergrund erscheint immer, wenn kein Song angezeigt wird. Der Knopf seitlich am "
                  "Display schaltet weiterhin zwischen hell, gedimmt und aus."),

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

    # --- settings ---
    "set_title": ("Settings", "Einstellungen"),
    "set_general": ("General", "Allgemein"),
    "set_minimized": ("Start in the background (only the tray icon)", "Im Hintergrund starten (nur Tray-Symbol)"),
    "set_player": ("Music app", "Musik-App"),
    "player_auto": ("Automatic (Spotify or Deezer)", "Automatisch (Spotify oder Deezer)"),
    "set_player_note": ("A different music app takes effect after the next start of the app.",
                        "Eine andere Musik-App gilt ab dem n\u00e4chsten Start der App."),
    "set_reset_t": ("Reset", "Zur\u00fccksetzen"),
    "set_reset_text": ("Puts keys, lights, display and the other settings back to the defaults. "
                       "Press Apply afterwards to send them to the pad too.",
                       "Setzt Tasten, Licht, Display und die anderen Einstellungen auf Standard zur\u00fcck. "
                       "Danach Anwenden dr\u00fccken, damit das Pad sie auch bekommt."),
    "set_reset": ("Reset all settings", "Alle Einstellungen zur\u00fccksetzen"),
    "set_reset_q": ("Reset all settings to the defaults?", "Alle Einstellungen auf Standard zur\u00fccksetzen?"),
    "set_reset_done": ("Done. Press Apply to keep it and send it to the pad.",
                       "Erledigt. Dr\u00fccke Anwenden, um es zu speichern und ans Pad zu senden."),
    "set_uninst_t": ("Uninstall", "Deinstallieren"),
    "set_uninst_text": ("Removes the app from this PC. The macro pad keeps its settings and keeps working "
                        "(without music info).",
                        "Entfernt die App von diesem PC. Das Macro Pad beh\u00e4lt seine Einstellungen und "
                        "funktioniert weiter (ohne Musik-Infos)."),
    "set_uninst_data": ("Also delete my settings and data (log, downloads)",
                        "Meine Einstellungen und Daten (Log, Downloads) auch l\u00f6schen"),
    "set_uninst": ("Uninstall app", "App deinstallieren"),
    "set_uninst_q": ("Remove the Macro Pad app from this PC now?", "Die Macro-Pad-App jetzt von diesem PC entfernen?"),
    "set_uninst_q_data": ("Remove the Macro Pad app and all your settings from this PC now?",
                          "Die Macro-Pad-App und alle deine Einstellungen jetzt von diesem PC entfernen?"),
    "set_uninst_missing": ("Uninstalling only works in the installed app (not when it runs from the source code).",
                           "Deinstallieren geht nur in der installierten App (nicht beim Start aus dem Quellcode)."),
    "set_uninst_failed": ("Could not start the uninstaller: {e}", "Konnte die Deinstallation nicht starten: {e}"),
    "set_data_where": ("Your settings are stored in: {path}", "Deine Einstellungen liegen in: {path}"),

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

    # --- 1.4: macros, profiles, sleep, backup, statistics ---
    'menu_stats': ('Statistics', 'Statistik'),
    'cat_app': ('Macros & more', 'Makros & mehr'),
    'macro_item': ('Macro: {name}', 'Makro: {name}'),
    'multi_item': ('Tap / hold: {name}', 'Tippen / Halten: {name}'),
    'new_macro': ('New macro…', 'Neues Makro…'),
    'new_open': ('Open a program or website…', 'Programm oder Webseite öffnen…'),
    'new_text': ('Type a text…', 'Text schreiben…'),
    'new_multi': ('New tap / hold key…', 'Neue Tippen-/Halten-Taste…'),
    'desc_mic': ('Switches your microphone on and off (for Discord, Teams, games …). The key glows red while it is off, green while it is on.', 'Schaltet dein Mikrofon an und aus (für Discord, Teams, Spiele …). Die Taste leuchtet rot, solange es aus ist, grün, solange es an ist.'),
    'desc_macro': ('Several steps in a row: keys, text, open a program, pauses. Needs the app running.', 'Mehrere Schritte nacheinander: Tasten, Text, Programm öffnen, Pausen. Braucht die laufende App.'),
    'desc_open': ('Opens a program, file, folder or website. Needs the app running.', 'Öffnet ein Programm, eine Datei, einen Ordner oder eine Webseite. Braucht die laufende App.'),
    'desc_text': ('Types a text for you – with umlauts, emoji and line breaks. Needs the app running.', 'Schreibt einen Text für dich – mit Umlauten, Emoji und Zeilenumbrüchen. Braucht die laufende App.'),
    'desc_multi': ('Up to three jobs on one key: tap, hold, double tap. Needs the app running.', 'Bis zu drei Funktionen auf einer Taste: tippen, halten, doppelt tippen. Braucht die laufende App.'),
    'step_text': ('Type "{text}"', 'Schreibe "{text}"'),
    'step_open': ('Open {target}', 'Öffne {target}'),
    'step_delay': ('Wait {ms} ms', 'Warte {ms} ms'),
    'text_hint': ('The text is typed into whatever window is in front. Line breaks become Enter.', 'Der Text wird in das Fenster geschrieben, das vorne ist. Zeilenumbrüche werden zu Enter.'),
    'open_hint': ('A program, file or folder (Browse…), or a web address such as https://youtube.com.', 'Ein Programm, eine Datei oder ein Ordner (Durchsuchen…) oder eine Webadresse wie https://youtube.com.'),
    'browse': ('Browse…', 'Durchsuchen…'),
    'open_filter': ('Programs (*.exe *.lnk *.bat);;All files (*)', 'Programme (*.exe *.lnk *.bat);;Alle Dateien (*)'),
    'exe_filter': ('Programs (*.exe)', 'Programme (*.exe)'),
    'macro_title': ('Macro', 'Makro'),
    'macro_name': ('Name (shown on the pad when you press the key)', 'Name (wird beim Drücken auf dem Pad angezeigt)'),
    'macro_hint': ('The steps run from top to bottom. New steps go below the selected one.', 'Die Schritte laufen von oben nach unten. Neue Schritte kommen unter den ausgewählten.'),
    'add_keys': ('+ Key / shortcut', '+ Taste / Shortcut'),
    'add_text': ('+ Text', '+ Text'),
    'add_open': ('+ Open', '+ Öffnen'),
    'add_delay': ('+ Pause', '+ Pause'),
    'step_edit': ('Change', 'Ändern'),
    'step_up': ('Up', 'Nach oben'),
    'step_down': ('Down', 'Nach unten'),
    'step_remove': ('Remove', 'Entfernen'),
    'delay_ms': ('Length of a new pause (ms):', 'Länge einer neuen Pause (ms):'),
    'save': ('Save', 'Speichern'),
    'default_open_name': ('Open', 'Öffnen'),
    'default_text_name': ('Text', 'Text'),
    'default_multi_name': ('Copy / paste', 'Kopieren / Einfügen'),
    'macro_full': ('A macro can have at most {n} steps.', 'Ein Makro kann höchstens {n} Schritte haben.'),
    'macros_full': ('You can have at most {n} of these.', 'Du kannst höchstens {n} davon haben.'),
    'macro_need_name': ('Please give it a name.', 'Bitte gib einen Namen ein.'),
    'macro_need_step': ('Please add at least one step.', 'Bitte füge mindestens einen Schritt hinzu.'),
    'multi_title': ('Tap / hold key', 'Tippen-/Halten-Taste'),
    'multi_hint': ('Hold = pressed for longer than 0.4 s. Double tap = two taps quickly one after the other. With no double tap set, a tap happens right away.', 'Halten = länger als 0,4 s gedrückt. Doppelt tippen = zweimal schnell hintereinander. Ist kein Doppeltippen eingestellt, kommt das Tippen sofort.'),
    'multi_tap': ('Tap', 'Tippen'),
    'multi_hold': ('Hold', 'Halten'),
    'multi_double': ('Double tap', 'Doppelt tippen'),
    'profile_title': ('Profile', 'Profil'),
    'profile_name': ('Name', 'Name'),
    'profile_hint': ('Tick the programs this profile is for. While one of them is in front, the keys of this profile are used. Programs that are open right now are listed.', 'Hake die Programme an, für die dieses Profil gilt. Solange eins davon vorne ist, gelten die Tasten dieses Profils. Gerade geöffnete Programme stehen schon in der Liste.'),
    'profile_add_ph': ('Other program, e.g. photoshop.exe', 'Anderes Programm, z. B. photoshop.exe'),
    'profile_add': ('Add', 'Hinzufügen'),
    'profile_need_name': ('Please give the profile a name.', 'Bitte gib dem Profil einen Namen.'),
    'profile_label': ('Layout:', 'Belegung:'),
    'profile_default': ('Normal (all programs)', 'Normal (alle Programme)'),
    'profile_new': ('New profile…', 'Neues Profil…'),
    'profile_programs': ('Programs…', 'Programme…'),
    'profile_delete': ('Delete profile', 'Profil löschen'),
    'profile_delete_q': ('Delete the profile "{name}"?', 'Profil "{name}" löschen?'),
    'profile_no_programs': ('no programs yet', 'noch keine Programme'),
    'profile_for': ('Used while one of these is in front: {programs}. Keys you do not change here do the same as in the normal layout.', 'Gilt, solange eins davon vorne ist: {programs}. Tasten, die du hier nicht änderst, machen dasselbe wie in der normalen Belegung.'),
    'profile_active': ('Profile in use right now: {name}', 'Gerade aktives Profil: {name}'),
    'profile_none_active': ('Profiles change the keys by themselves while a certain program is in front (e.g. Photoshop or a game).', 'Profile ändern die Tasten von selbst, solange ein bestimmtes Programm vorne ist (z. B. Photoshop oder ein Spiel).'),
    'sub_macro': ('Macro', 'Makro'),
    'sub_multi': ('Tap / hold', 'Tippen / Halten'),
    'sub_app': ('App', 'App'),
    'app_keys_note': ('Macros, tap / hold keys and the microphone key need the app running; without it these keys do their default job.', 'Makros, Tippen-/Halten-Tasten und die Mikrofon-Taste brauchen die laufende App; ohne sie machen diese Tasten ihre Standardfunktion.'),
    'macros_title': ('Macros & tap / hold keys', 'Makros & Tippen-/Halten-Tasten'),
    'macros_hint': ('Make them here or straight from a key (Macros & more). One macro can be on several keys.', 'Erstelle sie hier oder direkt bei einer Taste (Makros & mehr). Ein Makro kann auf mehreren Tasten liegen.'),
    'macro_edit': ('Change', 'Ändern'),
    'macro_delete': ('Delete', 'Löschen'),
    'macro_delete_q': ('Delete "{name}"? Keys that use it go back to their default.', '"{name}" löschen? Tasten, die es benutzen, bekommen wieder ihre Standardfunktion.'),
    'sleep_title': ('Sleep', 'Ruhezustand'),
    'sleep_locked': ('Screen and lights off while the PC is locked (Windows + L)', 'Display und Licht aus, solange der PC gesperrt ist (Windows + L)'),
    'sleep_idle': ('Also after no key was pressed for:', 'Außerdem, wenn keine Taste gedrückt wurde seit:'),
    'sleep_never': ('never', 'nie'),
    'sleep_minutes': ('{n} minutes', '{n} Minuten'),
    'sleep_note': ('When the PC goes to sleep, the pad goes dark too. Any key or the knob wakes it up.', 'Wenn der PC in den Energiesparmodus geht, wird das Pad auch dunkel. Jede Taste oder der Drehknopf weckt es auf.'),
    'backup_title': ('Backup', 'Sicherung'),
    'backup_text': ('Save keys, macros, profiles, lights and display settings to a file – to keep them safe or share them with friends.', 'Speichert Tasten, Makros, Profile, Licht und Display-Einstellungen in eine Datei – zum Aufheben oder um sie mit Freunden zu teilen.'),
    'backup_export': ('Save to file…', 'In Datei speichern…'),
    'backup_import': ('Load from file…', 'Aus Datei laden…'),
    'backup_saved': ('Saved to {path}.', 'Gespeichert in {path}.'),
    'backup_failed': ('That did not work: {error}', 'Das hat nicht geklappt: {error}'),
    'backup_not_ours': ('This is not a Macro Pad backup.', 'Das ist keine Macro-Pad-Sicherung.'),
    'backup_loaded': ('Loaded. Look around, then press Apply to send it to the pad.', 'Geladen. Schau dich um und drück dann auf Anwenden, um es zum Pad zu schicken.'),
    'owner_name': ('Name in the welcome:', 'Name in der Begrüßung:'),
    'owner_ph': ('e.g. Lena → "Welcome, Lena!"', 'z. B. Lena → "Welcome, Lena!"'),
    'stats_title': ('Statistics', 'Statistik'),
    'stats_hint': ('How often you press each key – the brighter, the more.', 'Wie oft du jede Taste drückst – je heller, desto öfter.'),
    'stats_today': ('Today', 'Heute'),
    'stats_week': ('Last 7 days', 'Letzte 7 Tage'),
    'stats_month': ('Last 30 days', 'Letzte 30 Tage'),
    'stats_all': ('All time', 'Gesamt'),
    'stats_reset': ('Reset statistics', 'Statistik zurücksetzen'),
    'stats_reset_q': ('Delete all counted key presses?', 'Alle gezählten Tastendrücke löschen?'),
    'stats_note': ('Counted while the app is running. Nothing leaves your PC.', 'Gezählt, während die App läuft. Nichts verlässt deinen PC.'),
    'stats_total': ('{n} key presses', '{n} Tastendrücke'),
    'stats_best': ('Most used: {what} ({n}×)', 'Am meisten benutzt: {what} ({n}×)'),
    'stats_empty': ('Nothing counted yet – press a few keys.', 'Noch nichts gezählt – drück ein paar Tasten.'),

    # --- 1.5: widgets ---
    'disp_widgets': ('Widgets', 'Widgets'),
    'bg_clock': ('Clock', 'Uhr'),
    'bg_stats': ('PC stats', 'PC-Werte'),
    'bg_timer': ('Focus timer', 'Fokus-Timer'),
    'bg_picture': ('Own picture', 'Eigenes Bild'),
    'bgd_clock': ('A big clock with the date, in the colour of your key lights. A key press makes it light up.', 'Eine große Uhr mit Datum, in der Farbe deiner Tastenbeleuchtung. Ein Tastendruck lässt sie aufleuchten.'),
    'bgd_stats': ('CPU, RAM and graphics card use, with the last minute as a graph. GPU numbers need an NVIDIA card.', 'Auslastung von CPU, RAM und Grafikkarte, mit der letzten Minute als Kurve. GPU-Werte brauchen eine NVIDIA-Karte.'),
    'bgd_timer': ('Pomodoro: focus, short break, four rounds, then a long break. Give a key "Focus timer start/pause" (Macros & more). While it runs, a small timer shows on every other background too.', 'Pomodoro: Fokus, kurze Pause, vier Runden, dann eine lange Pause. Gib einer Taste "Fokus-Timer Start/Pause" (Makros & mehr). Solange er läuft, zeigt auch jeder andere Hintergrund einen kleinen Timer.'),
    'bgd_picture': ('Any picture or animated GIF. GIFs use up to 50 frames at half the size. It is sent to the pad when you press Apply.', 'Ein beliebiges Bild oder animiertes GIF. GIFs nutzen bis zu 50 Bilder in halber Größe. Es wird beim Anwenden zum Pad geschickt.'),
    'opt_clock_seconds': ('Bar for the seconds', 'Balken für die Sekunden'),
    'opt_clock_h12': ('12-hour time (AM / PM)', '12-Stunden-Anzeige (AM / PM)'),
    'opt_stats_graph': ('Graph of the last minute', 'Kurve der letzten Minute'),
    'opt_timer_focus': ('Focus:', 'Fokus:'),
    'opt_timer_break': ('Short break:', 'Kurze Pause:'),
    'opt_timer_long': ('Long break:', 'Lange Pause:'),
    'opt_picture_fit': ('Show the whole picture (with black edges) instead of filling the screen', 'Ganzes Bild zeigen (mit schwarzen Rändern) statt den Bildschirm zu füllen'),
    'pic_choose': ('Choose picture…', 'Bild auswählen…'),
    'pic_remove': ('Remove', 'Entfernen'),
    'pic_current': ('{name} ({n} frame(s))', '{name} ({n} Bild(er))'),
    'pic_none': ('No picture chosen yet.', 'Noch kein Bild ausgewählt.'),
    'pic_filter': ('Pictures (*.png *.jpg *.jpeg *.gif *.webp *.bmp)', 'Bilder (*.png *.jpg *.jpeg *.gif *.webp *.bmp)'),
    'pic_failed': ('This picture could not be used: {why}', 'Dieses Bild ließ sich nicht verwenden: {why}'),
    'pic_upload': ('Sending the picture', 'Bild wird gesendet'),
    'pic_upload_stage': ('Sending your picture to the pad … keep it plugged in.', 'Dein Bild wird zum Pad geschickt … bitte eingesteckt lassen.'),
    'pic_sent': ('The picture is on the pad.', 'Das Bild ist auf dem Pad.'),
    'pic_not_sent': ('The picture was not sent: {why}', 'Das Bild wurde nicht gesendet: {why}'),
    'timer_break_now': ('Time for a break!', 'Zeit für eine Pause!'),
    'timer_focus_now': ('Break over – back to focus.', 'Pause vorbei – zurück zum Fokus.'),
    # --- 1.6 ---
    'whats_new': ("What's new", 'Was ist neu'),
    'notes_available': ('– available now', '– jetzt verfügbar'),
    'notes_installed': ('– installed', '– installiert'),
    'notes_none': ('No notes for this version.', 'Keine Notizen zu dieser Version.'),
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
