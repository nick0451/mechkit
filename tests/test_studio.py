"""MechKit Studio backend: project list, manifest, model.glb (structure, cache), web app files, path safety, the command.

    uv run python tests/test_studio.py

Runs real servers on free 127.0.0.1 ports (uvicorn in a thread, and once the real command as a subprocess) and talks
to them with http.client; everything is stopped at the end. Fusion is not involved. For the real Monitor weather
display (if its folder exists) the server builds exports/<version>/presentation/model.glb there, as it does in use.
"""

import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import quote

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
import build123d as bd  # noqa: E402
import numpy as np  # noqa: E402
import uvicorn  # noqa: E402

from mechkit import studio  # noqa: E402
from mechkit.present import manifest  # noqa: E402
from mechkit.studio import app as studio_app  # noqa: E402
from mechkit.studio import glb  # noqa: E402

def _example():
    """The worked example: your own working copy beside the kit if there is one, else the copy in examples/."""
    for p in (KIT.parent / "Monitor weather display", KIT / "examples" / "monitor-weather-display"):
        if (p / "exports").is_dir():
            return p
    return KIT / "examples" / "monitor-weather-display"


MWD = _example()
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %-4s %s  %s" % ("ok" if cond else "FAIL", name, detail))


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Running:
    """A Studio server in a thread: with Running(root, dist) as get: status, headers, body = get('/api/health')."""

    def __init__(self, projects_root=None, dist_dir=None):
        self.port = free_port()
        self.config = studio.server_config(self.port, projects_root, dist_dir)
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        end = time.time() + 20
        while not self.server.started and time.time() < end:
            time.sleep(0.02)
        if not self.server.started:
            raise RuntimeError("the test server did not start")
        return self.get

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=20)

    def get(self, path, timeout=180):
        return fetch(self.port, path, timeout)


def fetch(port, path, timeout=180, host="127.0.0.1", host_header=None):
    """GET a RAW path (nothing is normalised on the way out). Returns (status, {lower-case header: value}, body bytes).
    host_header: send this Host header instead of the address connected to."""
    c = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        if host_header is None:
            c.request("GET", path)
        else:
            c.putrequest("GET", path, skip_host=True)
            c.putheader("Host", host_header)
            c.endheaders()
        r = c.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
    finally:
        c.close()


def as_json(body):
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError:
        return None


def is_404_json(reply):
    status, headers, body = reply
    data = as_json(body)
    return status == 404 and headers.get("content-type", "").startswith("application/json") and isinstance(data, dict) and isinstance(data.get("detail"), str)


def sample_items():
    plate = bd.Box(40, 30, 4)
    lid = bd.Pos(0, 0, 4) * bd.Box(40, 30, 2)
    screws = [bd.Pos(x, 0, 3) * bd.Cylinder(1.5, 8) for x in (-12, 12)]
    table = bd.Pos(0, 0, -7) * bd.Box(120, 90, 10)
    return [manifest.item("Plate", plate, 1, "printed", "The base plate.", "#2b2d31", material="PETG", part_number="T-1"),
            manifest.item("Lid", lid, 2, "printed", "The lid.", "#c8ccd2", material="PETG", explode=(0, 0, 20)),
            manifest.item("Screw_A", screws[0], 3, "hardware", "M3 screw.", "#9aa0a8", part="Screw M3", explode=(0, 0, 45)),
            manifest.item("Screw_B", screws[1], 3, "hardware", "M3 screw.", "#9aa0a8", part="Screw M3", explode=(0, 0, 45)),
            manifest.item("Table", table, 0, "reference", "The desk.", "#3a3d42", opacity=0.3)]


# ---- reading a GLB -------------------------------------------------------------------------------------------------

def quat_matrix(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def local_matrix(node):
    m = np.eye(4)
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape(4, 4).T
    m[:3, :3] = quat_matrix(node.get("rotation", [0, 0, 0, 1])) @ np.diag(node.get("scale", [1, 1, 1]))
    m[:3, 3] = node.get("translation", [0, 0, 0])
    return m


def positions(doc, binary, accessor_index):
    acc = doc["accessors"][accessor_index]
    view = doc["bufferViews"][acc["bufferView"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", 12)
    raw = np.frombuffer(binary, dtype=np.uint8, count=(acc["count"] - 1) * stride + 12, offset=start)
    if stride == 12:
        return raw.view("<f4").reshape(-1, 3).astype(float)
    return np.stack([raw[i * stride:i * stride + 12].view("<f4") for i in range(acc["count"])]).astype(float)


def points_below(doc, binary, index, parent=None):
    """Every vertex under node `index`, in that node's PARENT frame when parent is given, else in the node's own frame."""
    node = doc["nodes"][index]
    here = np.eye(4) if parent is None else parent @ local_matrix(node)
    found = []
    if "mesh" in node:
        for prim in doc["meshes"][node["mesh"]]["primitives"]:
            p = positions(doc, binary, prim["attributes"]["POSITION"])
            found.append(p @ here[:3, :3].T + here[:3, 3])
    for child in node.get("children", []):
        found.extend(points_below(doc, binary, child, here))
    return found


def materials_below(doc, index):
    node = doc["nodes"][index]
    found = set()
    if "mesh" in node:
        found |= {prim.get("material") for prim in doc["meshes"][node["mesh"]]["primitives"]}
    for child in node.get("children", []):
        found |= materials_below(doc, child)
    return found


def linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def check_glb(tag, raw, data):
    """The contract's GLB facts, re-measured on `raw` (the bytes served) against the manifest dict `data`."""
    try:
        doc, binary = glb.read(raw)
    except ValueError as e:
        check("%s: is a glTF 2 binary" % tag, False, str(e))
        return
    check("%s: is a glTF 2 binary" % tag, doc["asset"]["version"] == "2.0" and len(binary) > 0, "%d bytes" % len(raw))
    keys = [e["key"] for e in data["parts"]]
    roots = doc["scenes"][doc.get("scene", 0)]["nodes"]
    root = doc["nodes"][roots[0]]
    check("%s: one root node named model" % tag, len(roots) == 1 and root.get("name") == "model", str(root.get("name")))
    turned = quat_matrix(root.get("rotation", [0, 0, 0, 1])) @ np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]).T
    check("%s: the root turns kit Z-up into glTF Y-up (kit +Y = front comes out as -Z, X stays)" % tag,
          np.allclose(turned[:, 0], [0, 1, 0], atol=1e-6) and np.allclose(turned[:, 1], [0, 0, -1], atol=1e-6) and np.allclose(turned[:, 2], [1, 0, 0], atol=1e-6)
          and "translation" not in root and "scale" not in root and "matrix" not in root, str(root.get("rotation")))
    kids = root.get("children", [])
    names = [doc["nodes"][i].get("name") for i in kids]
    check("%s: the root's children are the manifest items, named by key, one each (%d)" % (tag, len(keys)), sorted(names) == sorted(keys) and len(names) == len(keys),
          "%d nodes" % len(names))
    all_names = [n.get("name") for n in doc["nodes"]]
    check("%s: no key names a second node anywhere" % tag, all(all_names.count(k) == 1 for k in keys))
    plain = [doc["nodes"][i].get("name") for i in kids if any(t in doc["nodes"][i] for t in ("translation", "rotation", "scale", "matrix"))]
    check("%s: no item node has a transform of its own" % tag, plain == [], str(plain))
    by_key = {e["key"]: e for e in data["parts"]}
    worst, empty = 0.0, []
    for i in kids:
        e = by_key.get(doc["nodes"][i].get("name"))
        pts = points_below(doc, binary, i)
        if e is None or not pts:
            empty.append(doc["nodes"][i].get("name"))
            continue
        pts = np.concatenate(pts) * 1000.0                                    # metres -> mm, in the item node's own frame
        worst = max(worst, float(np.abs(np.array([pts.min(axis=0), pts.max(axis=0)]) - np.array(e["bbox"])).max()))
    check("%s: every item node holds a mesh" % tag, empty == [], str(empty))
    check("%s: metres, and an item node's frame is the kit frame (mesh boxes x 1000 = manifest boxes, mm)" % tag, not empty and worst < 0.1, "worst %.4f mm" % worst)
    wanted = {(e["colour"].lower(), round(e["opacity"], 4)) for e in data["parts"]}
    mats = doc.get("materials", [])
    check("%s: one material per colour (%d)" % (tag, len(wanted)), len(mats) == len(wanted), "%d materials" % len(mats))
    off = []
    for i in kids:
        e = by_key.get(doc["nodes"][i].get("name"))
        used = materials_below(doc, i)
        if e is None or len(used) != 1 or None in used:
            off.append(doc["nodes"][i].get("name"))
            continue
        got = mats[used.pop()]["pbrMetallicRoughness"]["baseColorFactor"]
        want = [linear(c) for c in glb.colour(e["colour"])[:3]] + [e["opacity"]]
        if max(abs(got[k] - want[k]) for k in range(4)) > 0.01:
            off.append("%s %s" % (e["key"], [round(c, 3) for c in got]))
    check("%s: each item's material is its manifest colour (linear) and opacity" % tag, off == [], str(off))


# ---- the tests -----------------------------------------------------------------------------------------------------

def make_sample(tmp):
    root = tmp / "root"
    items = sample_items()
    views = [manifest.view("Front", (120, 200, 60), (0, 0, 0)), manifest.view("Exploded", (160, 160, 110), (0, 0, 20), group="exploded")]
    steps = [manifest.step("Base", "Put the plate down.", ["Plate"]), manifest.step("Close", "Lid on, two screws.", ["Lid", "Screw_A", "Screw_B"])]
    old = manifest.write(root / "Sample box", "v1", "Sample", items, views)
    new = manifest.write(root / "Sample box", "v2", "Sample", items, views, steps=steps)
    mid = manifest.write(root / "Sample box", "v1b", "Sample", items[:2], views)
    now = time.time()
    for path, age in ((old, 3000), (mid, 2000), (new, 1000)):               # v2 newest, then v1b, then v1 (not name order)
        for f in path.parent.iterdir():
            os.utime(f, (now - age, now - age))
    manifest.write(root / "Another", "v1", "Another thing", items[:1], views[:1])
    (root / "No exports here").mkdir()
    (root / "Half" / "exports" / "v1").mkdir(parents=True)                  # a version folder without a manifest
    (root / "notes.txt").write_text("not a project", encoding="utf-8")
    secret = manifest.write(tmp / "outside" / "Secret", "v1", "Secret", items[:1], views[:1])     # NOT under the root
    dist = tmp / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>studio test index</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("export const x = 1;\n", encoding="utf-8")
    (tmp / "secret.txt").write_text("TOP-SECRET-TEXT", encoding="utf-8")
    return root, dist, new, secret


def test_sample(tmp):
    root, dist, new, secret = make_sample(tmp)
    folder = new.parent
    with Running(root, dist) as get:
        print("health and project list (temporary projects root)")
        status, headers, body = get("/api/health")
        check("health", status == 200 and as_json(body) == {"status": "ok", "kit": str(KIT)}, body.decode()[:80])
        status, headers, body = get("/api/projects")
        listing = as_json(body)
        ids = [p["id"] for p in listing["projects"]] if listing else None
        check("projects: only folders with a manifest, each with id, name, versions", status == 200 and ids == ["Another", "Sample box"]
              and all(sorted(p) == ["id", "name", "versions"] for p in listing["projects"]), str(ids))
        sample = listing["projects"][1]
        check("project name comes from the manifest, id is the folder name", sample["name"] == "Sample" and listing["projects"][0]["name"] == "Another thing")
        check("versions newest first by manifest time (not by name)", sample["versions"] == ["v2", "v1b", "v1"], str(sample["versions"]))

        print("manifest")
        base = "/api/projects/%s" % quote("Sample box")
        status, headers, body = get(base + "/v2/manifest")
        data = as_json(body)
        check("manifest: 200 JSON", status == 200 and headers.get("content-type", "").startswith("application/json") and isinstance(data, dict))
        need = ["project", "version", "up", "assembled_bbox", "exploded_bbox", "exploded_offset", "parts", "views", "table", "steps"]
        check("manifest: every field the web app's Manifest type names", all(k in data for k in need), str([k for k in need if k not in data]))
        check("manifest: the server-side folder key is stripped", "folder" not in data and str(tmp) not in body.decode("utf-8"))
        part_keys = ["key", "label", "kind", "name", "part", "description", "part_number", "material", "colour", "opacity", "explode", "count",
                     "volume_mm3", "bbox", "centre", "bodies", "step"]
        check("manifest: parts carry every field of the Part type", len(data["parts"]) == 5 and all(k in e for e in data["parts"] for k in part_keys))
        check("manifest: steps in order with their items", [(s["title"], s["add"]) for s in data["steps"]] == [("Base", ["Plate"]), ("Close", ["Lid", "Screw_A", "Screw_B"])])
        check("manifest: table rows and quantities", [(r["label"], r["qty"]) for r in data["table"]] == [(1, 1), (2, 1), (3, 2)])
        check("manifest: views", [(v["name"], v["group"]) for v in data["views"]] == [("Front", "assembled"), ("Exploded", "exploded")])
        status, headers, body = get(base + "/v1/manifest")
        check("a manifest without steps is served with steps = []", status == 200 and as_json(body)["steps"] == [])

        print("model.glb")
        out = folder / "model.glb"
        check("no model.glb before the first request", not out.exists())
        t0 = time.time()
        status, headers, raw = get(base + "/v2/model.glb")
        check("GLB: 200, content type model/gltf-binary", status == 200 and headers.get("content-type") == "model/gltf-binary",
              "%s %s in %.1f s" % (status, headers.get("content-type"), time.time() - t0))
        check("GLB: cached beside the manifest, same bytes as served", out.is_file() and out.read_bytes() == raw and headers.get("x-studio-model") == "built")
        check_glb("sample", raw, data)
        made = out.stat().st_mtime_ns
        time.sleep(0.05)
        status, headers, again = get(base + "/v2/model.glb")
        check("cache: a second request does not rebuild (same file time, same bytes)", status == 200 and out.stat().st_mtime_ns == made and again == raw
              and headers.get("x-studio-model") == "cached")
        m_time = new.stat().st_mtime
        os.utime(out, (m_time - 60, m_time - 60))                           # the model is now older than its manifest
        status, headers, third = get(base + "/v2/model.glb")
        rebuilt = out.stat().st_mtime_ns
        check("cache: rebuilt when the manifest is newer than the model", status == 200 and headers.get("x-studio-model") == "built" and rebuilt > new.stat().st_mtime_ns,
              headers.get("x-studio-model", ""))
        time.sleep(0.05)
        os.utime(folder / "Lid.step", None)                                 # one STEP file touched after the model was made
        status, headers, fourth = get(base + "/v2/model.glb")
        check("cache: rebuilt when a STEP file is newer than the model", status == 200 and headers.get("x-studio-model") == "built" and out.stat().st_mtime_ns > rebuilt)
        status, headers, fifth = get(base + "/v2/model.glb")
        check("cache: and reused again afterwards", status == 200 and headers.get("x-studio-model") == "cached")
        out.unlink()
        replies = [None] * 4

        def grab(i):
            replies[i] = get(base + "/v2/model.glb")

        threads = [threading.Thread(target=grab, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        built = [r[1].get("x-studio-model") for r in replies]
        check("four requests at once: all get the same complete file, built once", all(r[0] == 200 and r[2] == replies[0][2] for r in replies)
              and built.count("built") == 1 and replies[0][2] == out.read_bytes(), str(built))
        try:
            glb.read(replies[0][2])
            whole = True
        except ValueError:
            whole = False
        left = sorted(f.name for f in folder.iterdir() if f.suffix not in (".step", ".json") and f.name != "model.glb")
        check("the file is whole and no temporary file is left behind", whole and left == [], str(left))
        (folder / "Lid.step").rename(folder / "Lid.away")
        os.utime(out, (m_time - 60, m_time - 60))
        status, headers, body = get(base + "/v2/model.glb")
        (folder / "Lid.away").rename(folder / "Lid.step")
        check("a missing STEP file gives a 500 with a JSON reason, and the old model is left alone", status == 500 and "Lid.step" in (as_json(body) or {}).get("detail", "")
              and out.is_file(), body.decode()[:90])

        print("host header (DNS rebinding)")
        port = get.__self__.port
        refused = [fetch(port, p, host_header=h)[0] for h in ("evil.example", "evil.example:%d" % port, "127.0.0.1.evil.example")
                   for p in ("/api/health", "/api/projects", base + "/v2/manifest", base + "/v2/model.glb", "/")]
        check("a request under any other host name is refused with 400 (API, model and web app alike)", all(s == 400 for s in refused), str(sorted(set(refused))))
        leak = fetch(port, "/api/projects", host_header="evil.example")[2]
        check("and the refusal carries no project data", b"Sample" not in leak, leak.decode(errors="replace")[:60])
        allowed = [fetch(port, "/api/health", host_header=h)[0] for h in ("127.0.0.1", "127.0.0.1:%d" % port, "localhost", "localhost:%d" % port)]
        check("127.0.0.1 and localhost, with or without the port, are served", allowed == [200] * 4, str(allowed))

        print("unknown things and path safety")
        check("unknown project: 404 JSON", is_404_json(get("/api/projects/Nope/v1/manifest")) and is_404_json(get("/api/projects/Nope/v1/model.glb")))
        check("unknown version: 404 JSON", is_404_json(get(base + "/v9/manifest")) and is_404_json(get(base + "/v9/model.glb")))
        check("a folder without a manifest is not a project", is_404_json(get("/api/projects/Half/v1/manifest")) and is_404_json(get("/api/projects/%s/v1/manifest" % quote("No exports here"))))
        check("unknown API route: 404 JSON, not the web app", is_404_json(get("/api/nothing")) and is_404_json(get("/api")) and is_404_json(get(base + "/v2/other")))
        check("the outside manifest really exists (so a leak would show)", secret.is_file() and not secret.is_relative_to(root))
        sb = quote("Sample box")
        attempts = [
            "/api/projects/../outside/Secret/v1/manifest",
            "/api/projects/..%2Foutside%2FSecret/v1/manifest",
            "/api/projects/..%5Coutside%5CSecret/v1/manifest",
            "/api/projects/..\\outside\\Secret/v1/manifest",
            "/api/projects/%2E%2E%2Foutside%2FSecret/v1/manifest",
            "/api/projects/../outside/Secret/v1/model.glb",
            "/api/projects/..%5Coutside%5CSecret/v1/model.glb",
            "/api/projects/../../outside/Secret/v1/manifest",
            "/api/projects/%2E%2E/v1/manifest",
            "/api/projects/../v1/manifest",
            "/api/projects/./v2/manifest",
            "/api/projects/%2E/v2/manifest",
            "/api/projects/" + quote(str(tmp / "outside" / "Secret"), safe="") + "/v1/manifest",
            "/api/projects/" + quote((tmp / "outside" / "Secret").as_posix(), safe="") + "/v1/manifest",
            "/api/projects/" + quote(str(root / "Sample box"), safe="") + "/v2/manifest",
            "/api/projects/%s/../v2/manifest" % sb,
            "/api/projects/%s/%%2E%%2E/manifest" % sb,
            "/api/projects/%s/..%%2Fv2/manifest" % sb,
            "/api/projects/%s/v2%%2F..%%2Fv2/manifest" % sb,
            "/api/projects/%s/v2%%5C..%%5Cv2/manifest" % sb,
            "/api/projects/%s/..%%5C..%%5C..%%5Coutside%%5CSecret%%5Cexports%%5Cv1/manifest" % sb,
            "/api/projects/%s/..%%2F..%%2F..%%2Foutside%%2FSecret%%2Fexports%%2Fv1/model.glb" % sb,
            "/api/projects/%s/%s/manifest" % (sb, quote(str(tmp / "outside" / "Secret" / "exports" / "v1"), safe="")),
            "/api/projects/%s%%2Fexports/v2/manifest" % sb,
            "/api/projects/%s%%00/v2/manifest" % sb,
            "/api/projects/%s/v2%%00/manifest" % sb,
            "/api/projects/%s./v2/manifest" % sb,
            "/api/projects/%s/v2./manifest" % sb,
            "/api/projects/%s%%20/v2/manifest" % sb,
            "/api/projects/%s/V2/manifest" % sb,
            "/api/projects/%s/v2/manifest" % quote("sample box"),
        ]
        leaks = []
        for a in attempts:
            status, headers, body = get(a)
            if status != 404 or b"volume_mm3" in body or b"The base plate" in body or body[:4] == b"glTF":      # the 404 text may echo the id
                leaks.append("%s -> %s" % (a, status))
        check("%d traversal / absolute-path / look-alike requests: every one a 404, nothing read" % len(attempts), leaks == [], str(leaks))
        check("no model.glb appeared outside the root", not (secret.parent / "model.glb").exists())
        check("find_manifest only matches names that exist", studio_app.find_manifest(root, "..", "v1") is None
              and studio_app.find_manifest(root, "Sample box", "..") is None and studio_app.find_manifest(root, str(tmp / "outside" / "Secret"), "v1") is None
              and studio_app.find_manifest(root, "Sample box/", "v2") is None and studio_app.find_manifest(root, "Sample box", "v2") == new)

        print("the web app's files")
        status, headers, body = get("/")
        check("/ is the built index.html", status == 200 and b"studio test index" in body and headers.get("content-type", "").startswith("text/html"))
        status, headers, body = get("/assets/app.js")
        check("a built file is served with a script content type", status == 200 and body.startswith(b"export const x") and "javascript" in headers.get("content-type", ""),
              headers.get("content-type", ""))
        status, headers, body = get("/some/page/in/the/app")
        check("an unknown non-API path gets index.html", status == 200 and b"studio test index" in body)
        leaks = []
        for a in ("/../secret.txt", "/..%2Fsecret.txt", "/..%5Csecret.txt", "/assets/..%2F..%2Fsecret.txt", "/assets/../../secret.txt", "/..\\secret.txt",
                  "/" + quote(str(tmp / "secret.txt"), safe=""), "/" + quote((tmp / "secret.txt").as_posix(), safe=""), "//" + (tmp / "secret.txt").as_posix()):
            status, headers, body = get(a)
            if b"TOP-SECRET" in body:
                leaks.append(a)
        check("files outside dist are never served", leaks == [], str(leaks))

    with Running(root, tmp / "no_dist_here") as get:
        status, headers, body = get("/")
        text = body.decode("utf-8")
        check("dist missing: a clear plain-text message naming the folder and the build command", headers.get("content-type", "").startswith("text/plain")
              and "not been built" in text and "npm run build" in text and str(tmp / "no_dist_here") in text and status == 503, "status %s" % status)
        check("dist missing: the API still answers", get("/api/health")[0] == 200 and is_404_json(get("/api/nothing")))


def test_cache_rules(tmp):
    """glb.ensure called directly (no server): what file times alone would miss."""
    print("model cache: sources that change during a build, restored files, settings")
    path = tmp / "root" / "Another" / "exports" / "v1" / "presentation" / "manifest.json"
    folder = path.parent
    out = folder / glb.NAME
    step = folder / "Plate.step"
    real_build, calls = glb.build, []

    def rewrite_step():                                                     # as `mechkit present` would, mid-build
        raw = step.read_bytes()
        time.sleep(0.02)
        step.write_bytes(raw)

    def counting(data, where, target):
        calls.append(1)
        real_build(data, where, target)

    def rewritten_during_first_build(data, where, target):
        counting(data, where, target)
        if len(calls) == 1:
            rewrite_step()

    def always_rewritten(data, where, target):
        counting(data, where, target)
        rewrite_step()

    wait = glb.RETRY_WAIT
    glb.RETRY_WAIT = 0.0
    try:
        glb.build = rewritten_during_first_build
        got, built = glb.ensure(path)
        check("sources rewritten during a build: that build is thrown away and made again", got == out and built and len(calls) == 2, "%d builds" % len(calls))
        _, files = glb.sources(path)
        check("the stored note matches the sources as they are now, and the model is not older than them",
              glb.read_stamp(out) == glb.signature(files) and all(out.stat().st_mtime_ns >= f.stat().st_mtime_ns for f in files))
        glb.build = counting
        del calls[:]
        check("then it is fresh: no build", glb.ensure(path) == (out, False) and calls == [])

        old = step.stat().st_mtime - 5000
        os.utime(step, (old, old))                                          # e.g. restored from a backup with its old time
        check("a source whose time moved BACKWARDS still means a rebuild", glb.ensure(path) == (out, True) and len(calls) == 1, "%d builds" % len(calls))

        keep = glb.LINEAR_DEFLECTION
        glb.LINEAR_DEFLECTION = keep * 2
        try:
            del calls[:]
            check("a change of tessellation settings means a rebuild", glb.ensure(path) == (out, True) and len(calls) == 1, "%d builds" % len(calls))
        finally:
            glb.LINEAR_DEFLECTION = keep
        del calls[:]
        check("and back again: rebuilt once, then fresh", glb.ensure(path) == (out, True) and glb.ensure(path) == (out, False) and len(calls) == 1, "%d builds" % len(calls))

        (folder / glb.STAMP).unlink()
        del calls[:]
        check("a model with no note beside it (made by an older Studio) is rebuilt once", glb.ensure(path) == (out, True) and glb.ensure(path) == (out, False)
              and len(calls) == 1, "%d builds" % len(calls))

        glb.build = always_rewritten
        os.utime(step, None)
        before = out.read_bytes()
        del calls[:]
        try:
            glb.ensure(path)
            gave_up = False
        except RuntimeError as e:
            gave_up = "kept changing" in str(e)
        left = sorted(f.name for f in folder.iterdir() if ".tmp." in f.name)
        check("sources that never hold still: a clear error after %d tries, the old model untouched, no temporary files" % glb.BUILD_TRIES,
              gave_up and len(calls) == glb.BUILD_TRIES and out.read_bytes() == before and left == [], "%d builds, left %s" % (len(calls), left))
        glb.build = counting
        del calls[:]
        check("and once they hold still it builds", glb.ensure(path) == (out, True) and len(calls) == 1)
    finally:
        glb.build = real_build
        glb.RETRY_WAIT = wait


def test_real():
    print("monitor weather display (the real project, default projects root)")
    with Running() as get:
        status, headers, body = get("/api/projects")
        listing = as_json(body) or {"projects": []}
        mine = [p for p in listing["projects"] if p["id"] == MWD.name]
        check("listed by default (beside the kit, or in its examples)", status == 200 and len(mine) == 1 and "v0p9" in mine[0]["versions"], str(mine))
        if not mine:
            return
        version = "v0p9"
        base = "/api/projects/%s/%s" % (quote(MWD.name), version)
        status, headers, body = get(base + "/manifest")
        data = as_json(body)
        check("manifest: 19 items, 13 table rows, 5 views, 7 steps, no folder key", status == 200 and len(data["parts"]) == 19 and len(data["table"]) == 13
              and len(data["views"]) == 5 and len(data["steps"]) == 7 and "folder" not in data,
              "%d items, %d rows, %d views, %d steps" % (len(data["parts"]), len(data["table"]), len(data["views"]), len(data["steps"])))
        qty = {r["part"]: r["qty"] for r in data["table"]}
        check("parts table quantities 3 / 3 / 1", qty.get("Bolt M3 x 10, socket head") == 3 and qty.get("Heat-set insert M3") == 3 and qty.get("Round display GC9A01 1.28 in") == 1)
        t0 = time.time()
        status, headers, raw = get(base + "/model.glb")
        check("GLB: 200, model/gltf-binary", status == 200 and headers.get("content-type") == "model/gltf-binary",
              "%s, %d bytes, %.1f s (%s)" % (status, len(raw), time.time() - t0, headers.get("x-studio-model")))
        if status == 200:
            check_glb("monitor", raw, data)
            doc = glb.read_json(raw)
            check("monitor: 19 item nodes under the root", len(doc["nodes"][doc["scenes"][0]["nodes"][0]].get("children", [])) == 19)
            out = MWD / "exports" / version / "presentation" / "model.glb"
            made = out.stat().st_mtime_ns
            status, headers, again = get(base + "/model.glb")
            check("monitor: second request served from the cache", out.stat().st_mtime_ns == made and again == raw and headers.get("x-studio-model") == "cached")
        check("the default dist folder is the kit's studio/web/dist", get.__self__.config.app.state.dist_dir == KIT / "studio" / "web" / "dist")


def test_command():
    print("the command")
    cfg = studio.server_config(free_port())
    check("the command's server configuration binds 127.0.0.1", cfg.host == "127.0.0.1" and studio.HOST == "127.0.0.1", cfg.host)
    source = (KIT / "mechkit" / "studio" / "app.py").read_text(encoding="utf-8")
    check("no other bind address in the server code", "0.0.0.0" not in source and '"::"' not in source and "host=HOST" in source)
    port = free_port()
    cmd = [sys.executable, "-m", "mechkit", "studio", "--port", str(port), "--no-browser"]
    proc = subprocess.Popen(cmd, cwd=str(KIT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        reply, end = None, time.time() + 60
        while time.time() < end and proc.poll() is None:
            try:
                reply = fetch(port, "/api/health", timeout=2)
                break
            except OSError:
                time.sleep(0.2)
        check("python -m mechkit studio --no-browser starts and answers /api/health", reply is not None and reply[0] == 200
              and as_json(reply[2]) == {"status": "ok", "kit": str(KIT)}, "port %d" % port)
        try:
            other = [a for a in socket.gethostbyname_ex(socket.gethostname())[2] if not a.startswith("127.")]
        except OSError:
            other = []
        if other and reply is not None:
            try:
                fetch(port, "/api/health", timeout=2, host=other[0])
                reached = True
            except OSError:
                reached = False
            check("not reachable on this machine's network address", not reached, other[0])
        else:
            print("       (no non-loopback address found: the outside-reachability check was skipped)")
        if reply is not None:
            second = subprocess.run(cmd, cwd=str(KIT), capture_output=True, timeout=60)
            check("a second start on the same port stops with a clear message", second.returncode == 1 and b"in use" in second.stdout, second.stdout.decode(errors="replace").strip()[:80])
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=15)
    try:
        fetch(port, "/api/health", timeout=1)
        alive = True
    except OSError:
        alive = False
    check("the command's server is stopped again", proc.poll() is not None and not alive)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="mk_studio_")).resolve()
    try:
        test_sample(tmp)
        test_cache_rules(tmp)
        if (MWD / "exports").is_dir():
            test_real()
        test_command()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d checks, %d failed" % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)


if __name__ == "__main__":
    main()
