"""MechKit Studio: a local web viewer for kit-built projects (see studio/CONTRACT.md).

    uv run python -m mechkit studio [--port 8765] [--no-browser]

    app.py   the FastAPI app: project list, manifest, model.glb, and the built web app from studio/web/dist
    glb.py   model.glb from a manifest's STEP files (build123d), cached beside the manifest

The server listens on 127.0.0.1 only. Nothing here talks to Fusion.
"""

from .app import HOST, create_app, serve, server_config  # noqa: F401
