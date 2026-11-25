"""The Studio server: a read-only API over your projects, plus the built web app.

Projects are looked for in the folders named by MECHKIT_PROJECTS (several, separated like PATH) or, when that is not
set, beside the kit (its parent folder) and in the kit's own examples/ folder. An example is hidden when one of your
own projects has the same name.

    GET /api/health                                  {"status": "ok", "kit": "<path>"}
    GET /api/projects                                {"projects": [{"id", "name", "versions": [newest first]}]}
    GET /api/projects/{id}/{version}/manifest        the presentation manifest (without the server-side "folder" key)
    GET /api/projects/{id}/{version}/model.glb       model/gltf-binary, built once and cached beside the manifest
    anything else                                    studio/web/dist (index.html for unknown non-API paths)

A project is a direct child folder of a projects root that has exports/<version>/presentation/manifest.json.
`id` and `version` are never joined into a path as given: they are looked up among the folder names that exist, so
`..`, slashes, backslashes and absolute paths simply match nothing (404).
Requests whose Host header is not 127.0.0.1 or localhost are refused (400): see ALLOWED_HOSTS.
"""

import json
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ..present import manifest as manifest_mod
from . import glb

KIT = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
DEFAULT_PORT = 8765
# The only names a browser may have used to reach this server (the Host header, port ignored). Anything else gets a
# 400: a web page that points its own domain at 127.0.0.1 (DNS rebinding) must not be able to read the projects.
ALLOWED_HOSTS = ("127.0.0.1", "localhost")

# Set here because Python's own table reads the Windows registry, where .js is often text/plain (a browser then
# refuses to run the module).
MEDIA = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json", ".map": "application/json", ".svg": "image/svg+xml",
         ".png": "image/png", ".jpg": "image/jpeg", ".ico": "image/x-icon", ".woff2": "font/woff2", ".wasm": "application/wasm",
         ".glb": "model/gltf-binary", ".txt": "text/plain; charset=utf-8"}

NO_DIST = ("MechKit Studio: the web app has not been built yet.\n\n"
           "Expected the built files in:\n  %s\n\n"
           "Build them once with:\n  cd \"%s\"\n  npm run build\n\n"
           "The API is running (try /api/health and /api/projects).\n")


def _child_dirs(folder):
    """Names of the folders directly inside `folder` (empty if it cannot be read)."""
    try:
        return {p.name: p for p in Path(folder).iterdir() if p.is_dir()}
    except OSError:
        return {}


def versions_of(project_dir):
    """[(version, manifest path)] of one project folder, newest manifest first."""
    found = []
    for name, d in _child_dirs(Path(project_dir) / "exports").items():
        m = d / "presentation" / "manifest.json"
        if m.is_file():
            found.append((m.stat().st_mtime_ns, name, m))
    found.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [(name, m) for _, name, m in found]


def _title(manifest_path, fallback):
    try:
        name = json.loads(Path(manifest_path).read_text(encoding="utf-8")).get("project")
    except (OSError, ValueError, AttributeError):
        return fallback
    return name if isinstance(name, str) and name.strip() else fallback


PROJECTS_ENV = "MECHKIT_PROJECTS"


def default_roots():
    """Where projects are looked for: $MECHKIT_PROJECTS (folders separated like PATH), else beside the kit and in its examples."""
    env = os.environ.get(PROJECTS_ENV, "").strip()
    if env:
        return [Path(p).resolve() for p in env.split(os.pathsep) if p.strip()]
    return [KIT.parent, KIT / "examples"]


def _roots(root):
    """One folder or several, as a list of resolved paths."""
    if root is None:
        return default_roots()
    if isinstance(root, (str, Path)):
        return [Path(root).resolve()]
    return [Path(r).resolve() for r in root]


def _projects(root):
    """{id: (folder, name, versions)} over all roots, in listing order. Earlier roots win: a later folder with an id or a
    project name that is already taken is left out (so your own project hides the example of the same name)."""
    found, names = {}, set()
    for r in _roots(root):
        for folder_name, d in sorted(_child_dirs(r).items(), key=lambda kv: kv[0].lower()):
            versions = versions_of(d)
            if not versions or folder_name in found:
                continue
            title = _title(versions[0][1], folder_name)
            if title.strip().lower() in names:
                continue
            names.add(title.strip().lower())
            found[folder_name] = (d, title, versions)
    return found


def list_projects(root):
    return [{"id": pid, "name": title, "versions": [v for v, _ in versions]} for pid, (_, title, versions) in _projects(root).items()]


def find_manifest(root, project_id, version):
    """The manifest path for a project id and version, or None. Only names that exist as folders can match."""
    entry = _projects(root).get(project_id)
    if entry is None:
        return None
    for name, m in entry[2]:
        if name == version:
            return m
    return None


def create_app(projects_root=None, dist_dir=None):
    """The FastAPI app. projects_root: a folder (or a list of folders) whose children are projects; default: see
    default_roots(). dist_dir: the built web app (default: <kit>/studio/web/dist)."""
    roots = _roots(projects_root)
    root = roots if len(roots) > 1 else roots[0]
    dist = Path(dist_dir).resolve() if dist_dir else KIT / "studio" / "web" / "dist"
    app = FastAPI(title="MechKit Studio", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(ALLOWED_HOSTS), www_redirect=False)
    app.state.projects_root = roots[0]
    app.state.projects_roots = roots
    app.state.dist_dir = dist

    def manifest_or_404(project_id, version):
        m = find_manifest(root, project_id, version)
        if m is None:
            raise HTTPException(status_code=404, detail="no project %r with version %r" % (project_id, version))
        return m

    @app.get("/api/health")
    def health():
        return {"status": "ok", "kit": str(KIT)}

    @app.get("/api/projects")
    def projects():
        return {"projects": list_projects(root)}

    @app.get("/api/projects/{project_id}/{version}/manifest")
    def get_manifest(project_id: str, version: str):
        path = manifest_or_404(project_id, version)
        try:
            data = manifest_mod.load(path)
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(status_code=500, detail="manifest cannot be used: %s" % e)
        data.pop("folder", None)
        return JSONResponse(data, headers={"Cache-Control": "no-cache"})

    @app.get("/api/projects/{project_id}/{version}/model.glb")
    def get_model(project_id: str, version: str):
        path = manifest_or_404(project_id, version)
        try:
            out, built = glb.ensure(path)
            body = out.read_bytes()
        except Exception as e:                                               # the CAD kernel raises many kinds
            raise HTTPException(status_code=500, detail="model could not be built: %s: %s" % (type(e).__name__, e))
        return Response(body, media_type="model/gltf-binary",
                        headers={"Cache-Control": "no-cache", "X-Studio-Model": "built" if built else "cached"})

    @app.api_route("/api", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/api/{rest:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def no_such_api(rest: str = ""):
        raise HTTPException(status_code=404, detail="no such API route: /api/%s" % rest)

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def web_app(path: str = ""):
        index = dist / "index.html"
        if not index.is_file():
            return PlainTextResponse(NO_DIST % (dist, dist.parent), status_code=503)
        if path:
            try:
                target = (dist / path).resolve()
                inside = target.is_relative_to(dist) and target.is_file()
            except (OSError, ValueError):
                inside = False
            if inside and target != index:
                return FileResponse(target, media_type=MEDIA.get(target.suffix.lower()))
        return FileResponse(index, media_type=MEDIA[".html"], headers={"Cache-Control": "no-cache"})

    return app


def server_config(port=DEFAULT_PORT, projects_root=None, dist_dir=None):
    """The uvicorn configuration the command uses: always bound to 127.0.0.1."""
    import uvicorn

    return uvicorn.Config(create_app(projects_root, dist_dir), host=HOST, port=int(port), log_level="warning")


def serve(port=DEFAULT_PORT, open_browser=True, projects_root=None, dist_dir=None):
    """Run the server until Ctrl+C. Returns an exit code."""
    import uvicorn

    port = int(port)
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((HOST, port))
    except OSError as e:
        print("MechKit Studio NOT started: port %d on %s is in use (%s). Try --port with another number." % (port, HOST, e))
        return 1
    finally:
        probe.close()
    config = server_config(port, projects_root, dist_dir)
    url = "http://%s:%d/" % (HOST, port)
    app = config.app
    print("MechKit Studio: %s   (Ctrl+C stops it)" % url)
    for r in app.state.projects_roots:
        print("  projects from: %s" % r)
    if not (app.state.dist_dir / "index.html").is_file():
        print("  note: the web app is not built (%s is missing): only the API will answer." % (app.state.dist_dir / "index.html"))
    sys.stdout.flush()
    if open_browser:
        timer = threading.Timer(1.0, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    uvicorn.Server(config).run()
    return 0
