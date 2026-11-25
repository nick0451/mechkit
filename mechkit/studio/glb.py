"""model.glb for one presentation manifest: every item's STEP file in one glTF binary, cached beside the manifest.

    path = glb.ensure(manifest_path)      builds it when missing or older than the manifest or any of its STEP files

Freshness has two rules, and both must hold for the cached file to be served:
- model.glb is not older than the manifest or any STEP file (the contract's rule);
- the note beside it, model.glb.json, lists exactly the sources it was made from (name, size, time), the tessellation
  settings and the build123d version. That catches what file times alone miss: sources rewritten WHILE the model was
  being built, files restored with older times, and a change of settings or library.

What build123d 0.13 writes (re-checked by tests/test_studio.py): metres; a root node `model` carrying the Z-up -> Y-up
rotation; one child node per item, named by the item's key, with no transform of its own; a material per colour.
"""

import json
import os
import re
import struct
import threading
import time
import uuid
from pathlib import Path

NAME = "model.glb"
STAMP = "model.glb.json"                      # what the cached model was made from (see signature)
RETRY_WAIT = 0.3                              # seconds before building again after such a change
BUILD_TRIES = 3                               # builds per request when the sources change under a running build
LINEAR_DEFLECTION = 0.05
ANGULAR_DEFLECTION = 0.3

_locks = {}
_locks_guard = threading.Lock()


def _lock_for(path):
    with _locks_guard:
        return _locks.setdefault(str(path).lower(), threading.Lock())


def sources(manifest_path):
    """The files model.glb is made from: the manifest and each item's STEP file. Raises ValueError / FileNotFoundError."""
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = [manifest_path]
    for e in data["parts"]:
        name = e["step"]
        if not re.fullmatch(r"[A-Za-z0-9_\-]+\.step", name):
            raise ValueError("%s: STEP file name is not a plain file name: %r" % (e["key"], name))
        f = manifest_path.parent / name
        if not f.is_file():
            raise FileNotFoundError("STEP file missing: %s" % f)
        files.append(f)
    return data, files


def _library_version():
    try:
        from importlib.metadata import version
        return version("build123d")
    except Exception:                                                        # not installed as a distribution
        return "unknown"


def signature(files):
    """What a model made from `files` right now depends on: each source's name, size and time, plus the settings."""
    return {"settings": {"linear_deflection": LINEAR_DEFLECTION, "angular_deflection": ANGULAR_DEFLECTION},
            "build123d": _library_version(),
            "sources": {f.name: [f.stat().st_size, f.stat().st_mtime_ns] for f in files}}


def read_stamp(glb_path):
    """The signature stored beside a model, or None when there is none or it cannot be read."""
    try:
        return json.loads((Path(glb_path).parent / STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def is_stale(glb_path, files, stamp=None):
    """True when the model must be rebuilt. `stamp`: the signature of `files` (default: taken now)."""
    glb_path = Path(glb_path)
    if not glb_path.is_file() or glb_path.stat().st_size == 0:
        return True
    made = glb_path.stat().st_mtime_ns
    if any(f.stat().st_mtime_ns > made for f in files):
        return True
    return read_stamp(glb_path) != (signature(files) if stamp is None else stamp)


def colour(hex_colour, opacity=1.0):
    """'#rrggbb' -> (r, g, b, a) as 0..1 floats."""
    h = hex_colour.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0, float(opacity))


def build(data, folder, out_path):
    """Write the GLB for a manifest dict whose STEP files are in `folder`. Slow (seconds): tessellates every item."""
    import build123d as bd

    children = []
    for e in data["parts"]:
        shape = bd.import_step(str(Path(folder) / e["step"]))
        shape.label = e["key"]
        shape.color = bd.Color(*colour(e["colour"], e.get("opacity", 1.0)))
        children.append(shape)
    model = bd.Compound(label="model", children=children)
    bd.export_gltf(model, str(out_path), binary=True, linear_deflection=LINEAR_DEFLECTION, angular_deflection=ANGULAR_DEFLECTION)
    if not Path(out_path).is_file() or Path(out_path).stat().st_size == 0:
        raise RuntimeError("build123d wrote no GLB at %s" % out_path)


def _replace(src, dst, tries=40, wait=0.05):
    """os.replace, retried: on Windows it fails while another request still has the old file open for reading."""
    for n in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if n == tries - 1:
                raise
            time.sleep(wait)


def ensure(manifest_path):
    """Path of an up-to-date model.glb beside the manifest, building it if needed. Returns (path, built: bool).

    One build at a time per manifest (a second request waits, then finds the file fresh). The file is written under a
    temporary name and renamed, so a reader never sees half a file.

    The sources are looked at again after each build: if `mechkit present` rewrote them meanwhile, that build is
    thrown away and made again (BUILD_TRIES times at most, then RuntimeError), so a model of old geometry is never
    stored as if it were fresh."""
    manifest_path = Path(manifest_path)
    out = manifest_path.parent / NAME
    stamp_path = manifest_path.parent / STAMP
    with _lock_for(out):
        for attempt in range(BUILD_TRIES):
            data, files = sources(manifest_path)
            stamp = signature(files)
            if not is_stale(out, files, stamp):
                return out, False
            unique = "%d.%s" % (os.getpid(), uuid.uuid4().hex[:8])
            tmp = manifest_path.parent / ("model.%s.tmp.glb" % unique)
            tmp_stamp = manifest_path.parent / ("model.%s.tmp.stamp" % unique)
            try:
                build(data, manifest_path.parent, tmp)
                try:
                    unchanged = signature(sources(manifest_path)[1]) == stamp
                except (OSError, ValueError, KeyError, TypeError):          # caught in the middle of being rewritten
                    unchanged = False
                if not unchanged:
                    time.sleep(RETRY_WAIT)
                    continue
                # The old note goes first: between the two renames below there must be no note that could match.
                try:
                    stamp_path.unlink()
                except FileNotFoundError:
                    pass
                _replace(tmp, out)
                tmp_stamp.write_text(json.dumps(stamp, indent=1), encoding="utf-8", newline="\n")
                _replace(tmp_stamp, stamp_path)
                return out, True
            finally:
                for leftover in (tmp, tmp_stamp):
                    if leftover.exists():
                        try:
                            leftover.unlink()
                        except OSError:
                            pass
        raise RuntimeError("the project's files kept changing while the model was being built (%d tries); try again" % BUILD_TRIES)


def read(path_or_bytes):
    """A GLB file (path or bytes) as (json dict, binary chunk bytes). Raises ValueError if it is not a glTF 2 binary."""
    raw = bytes(path_or_bytes) if isinstance(path_or_bytes, (bytes, bytearray)) else Path(path_or_bytes).read_bytes()
    if len(raw) < 20 or raw[:4] != b"glTF":
        raise ValueError("not a GLB file")
    version, total = struct.unpack_from("<II", raw, 4)
    length, kind = struct.unpack_from("<II", raw, 12)
    if version != 2 or kind != 0x4E4F534A or total != len(raw):
        raise ValueError("not a glTF 2 binary (version %s, first chunk %#x, length %s of %s)" % (version, kind, total, len(raw)))
    data = json.loads(raw[20:20 + length].decode("utf-8"))
    binary = b""
    at = 20 + length
    if at + 8 <= len(raw):
        blen, bkind = struct.unpack_from("<II", raw, at)
        if bkind == 0x004E4942:
            binary = raw[at + 8:at + 8 + blen]
    return data, binary


def read_json(path_or_bytes):
    """The JSON chunk of a GLB file (path or bytes) as a dict."""
    return read(path_or_bytes)[0]
