"""One rule for which revision of a project is the newest: used by requirement checks, the presentation and Studio.

Revision folders under <project>/exports/ are named like v0p9 (= 0.9), v1p10, v26 or export_v26. The number after the
last "v" is compared part by part, with "p" as the separator, so v0p10 is newer than v0p9. Folders whose names carry no
such number come after every numbered one, by name. File times are never used: copying or touching a folder must not
change which revision is newest.
"""

import re
from pathlib import Path

_V = re.compile(r"v(\d+(?:p\d+)*)$", re.IGNORECASE)


def key(name):
    """Sort key of a revision folder name: larger = newer."""
    m = _V.search(name)
    if m:
        return (1, tuple(int(x) for x in m.group(1).lower().split("p")), name)
    return (0, (), name)


def folders(project):
    """[(name, folder)] of a project's folders under exports/, newest first."""
    exports = Path(project) / "exports"
    found = [(p.name, p) for p in exports.iterdir() if p.is_dir()] if exports.is_dir() else []
    return sorted(found, key=lambda t: key(t[0]), reverse=True)


def newest(project):
    """The newest revision folder of a project, or None."""
    f = folders(project)
    return f[0][1] if f else None
