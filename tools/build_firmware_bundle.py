"""Packs a compiled firmware into the folder the app flashes from.

    python tools/build_firmware_bundle.py <build dir> <boot_app0.bin> <macropad.ino> <out dir>

<build dir> is PlatformIO's .pio/build/tdisplay_s3 (bootloader.bin,
partitions.bin, firmware.bin). The offsets come from the partition table
itself, so they always match what was built.
"""

import hashlib
import json
import re
import shutil
import struct
import sys
from pathlib import Path


def partitions(table: bytes):
    """Entries of an ESP32 partition table: (name, type, subtype, offset, size)."""
    out = []
    for i in range(0, len(table), 32):
        entry = table[i:i + 32]
        if entry[:2] != b"\xaa\x50":
            break
        ptype, sub, offset, size = struct.unpack_from("<BBII", entry, 2)
        name = entry[12:28].split(b"\0")[0].decode("ascii", "ignore")
        out.append((name, ptype, sub, offset, size))
    return out


def main(build_dir, boot_app0, ino, out_dir):
    build_dir, out_dir = Path(build_dir), Path(out_dir)
    version = re.search(r'FW_VERSION\[\]\s*=\s*"([^"]+)"', Path(ino).read_text("utf-8")).group(1)
    table = (build_dir / "partitions.bin").read_bytes()
    parts = partitions(table)
    app = next(p for p in parts if p[1] == 0 and p[2] in (0x00, 0x10))      # factory or ota_0
    otadata = next((p for p in parts if p[1] == 1 and p[2] == 0x00), None)
    nvs = next((p for p in parts if p[1] == 1 and p[2] == 0x02), None)
    files = [(0x0, build_dir / "bootloader.bin", "bootloader.bin"),
             (0x8000, build_dir / "partitions.bin", "partitions.bin")]
    if otadata:
        files.append((otadata[3], Path(boot_app0), "boot_app0.bin"))
    files.append((app[3], build_dir / "firmware.bin", "app.bin"))
    size = (build_dir / "firmware.bin").stat().st_size
    if size > app[4]:
        sys.exit(f"firmware ({size} bytes) does not fit the app partition ({app[4]} bytes)")
    # nothing may touch the pad's saved settings
    if nvs:
        for offset, f, _ in files:
            end = offset + f.stat().st_size
            if offset < nvs[3] + nvs[4] and end > nvs[3]:
                sys.exit(f"{f.name} would overwrite the settings area")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    meta = {"version": version, "chip": "esp32s3", "parts": []}
    for offset, src, name in files:
        shutil.copyfile(src, out_dir / name)
        digest = hashlib.sha256((out_dir / name).read_bytes()).hexdigest()
        meta["parts"].append({"offset": hex(offset), "file": name, "sha256": digest})
    (out_dir / "firmware.json").write_text(json.dumps(meta, indent=2), "utf-8")
    print(f"firmware {version}: " + ", ".join(f"{p['file']}@{p['offset']}" for p in meta["parts"]))


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
