"""Manifest of a build, for "Repair" and for the update check.

    python tools/make_manifest.py files <dist folder> <app version> <firmware version>
        -> writes <dist folder>/manifest.json (every file's SHA-256, used offline by Repair)
    python tools/make_manifest.py release <dist folder> <setup.exe> <out manifest.json>
        -> the release asset: the same list plus the installer's name, size and SHA-256
"""

import hashlib
import json
import sys
from pathlib import Path


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def files_manifest(dist, version, firmware):
    dist = Path(dist)
    files = {}
    for p in sorted(dist.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            files[p.relative_to(dist).as_posix()] = sha(p)
    data = {"version": version, "firmware": firmware, "files": files}
    (dist / "manifest.json").write_text(json.dumps(data, indent=1), "utf-8")
    print(f"manifest: {len(files)} files")


def release_manifest(dist, setup, out):
    data = json.loads((Path(dist) / "manifest.json").read_text("utf-8"))
    setup = Path(setup)
    data["setup"] = {"name": setup.name, "size": setup.stat().st_size, "sha256": sha(setup)}
    # what this version brings (shown by the installed apps before they update)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from macropad_app import changelog
    data["notes"] = changelog.as_dict(data["version"])
    Path(out).write_text(json.dumps(data, indent=1, ensure_ascii=False), "utf-8")
    lines = [f"- {n}" for n in data["notes"]["en"]] + [""] + [f"- {n}" for n in data["notes"]["de"]]
    (Path(out).parent / "release-notes.md").write_text("\n".join(lines) + "\n", "utf-8")
    print("release manifest:", data["setup"])


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "files":
        files_manifest(*sys.argv[2:])
    elif len(sys.argv) == 5 and sys.argv[1] == "release":
        release_manifest(*sys.argv[2:])
    else:
        sys.exit(__doc__)
