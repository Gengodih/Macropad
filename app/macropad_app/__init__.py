"""Macro Pad app: settings, music info and updates for the ESP32 macro pad."""

VERSION = "1.1.0"

# The GitHub repository that holds the releases ("owner/name"). Filled in by the
# build (GitHub Actions writes _build_info.py); empty = update check is off.
try:
    from ._build_info import UPDATE_REPO  # type: ignore
except Exception:  # running from source
    UPDATE_REPO = ""

APP_NAME = "Macro Pad"
MAKER = "Gengodih"
