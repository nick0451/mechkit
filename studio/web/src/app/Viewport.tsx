// The 3D pane: toolbar, the viewer itself, balloons, the part card and the explode slider.
// Talks to the scene only through the Viewer interface (../viewer/api.ts).
import { useCallback, useEffect, useRef, useState } from "react";
import { actions, clearActiveViewer, getState, setActiveViewer, useStore } from "../state/store";
import type { Manifest, View } from "../types";
import type { Viewer } from "../viewer/api";
import { createViewer } from "../viewer/viewer";
import { Balloons } from "./Balloons";
import { PartCard } from "./PartCard";

type ModelStatus = { kind: "loading" } | { kind: "ready" } | { kind: "error"; message: string };

interface Props {
  manifest: Manifest;
  glbUrl: string;
}

function messageOf(e: unknown): string {
  return e instanceof Error && e.message ? e.message : String(e);
}

export function Viewport({ manifest, glbUrl }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [viewer, setViewer] = useState<Viewer | null>(null); // set once the model is on screen
  const [status, setStatus] = useState<ModelStatus>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const getCanvas = useCallback(() => hostRef.current?.querySelector("canvas") ?? null, []);

  const explode = useStore((s) => s.explode);
  const balloons = useStore((s) => s.balloons);
  const context = useStore((s) => s.context);
  const selectedKey = useStore((s) => s.selectedKey);

  // One viewer per (manifest, model URL, attempt). Each gets its own mount element, removed with it, so a
  // StrictMode double-mount or a project switch never leaves a second canvas or WebGL context behind.
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const mount = document.createElement("div");
    mount.className = "viewer-mount";
    host.appendChild(mount);
    setStatus({ kind: "loading" });

    let v: Viewer;
    try {
      v = createViewer(mount);
    } catch (e) {
      mount.remove();
      setStatus({ kind: "error", message: `The 3D view could not start: ${messageOf(e)}` });
      return;
    }

    let alive = true;
    const offSelect = v.onSelect((key) => actions.select(key));
    const observer = new ResizeObserver(() => {
      if (alive) v.resize();
    });
    observer.observe(mount);

    v.load(manifest, glbUrl).then(
      () => {
        if (!alive) return;
        const s = getState();
        v.showReference(s.context);
        v.setExplode(s.explode);
        v.setSelected(s.selectedKey);
        if (s.explode > 0 || !s.context) v.fit();
        setActiveViewer(v, mount);
        setViewer(v);
        setStatus({ kind: "ready" });
      },
      (e: unknown) => {
        if (!alive) return;
        setStatus({ kind: "error", message: messageOf(e) });
      },
    );

    return () => {
      alive = false;
      observer.disconnect();
      offSelect();
      clearActiveViewer(v);
      setViewer(null);
      try {
        v.dispose();
      } finally {
        mount.remove();
      }
    };
  }, [manifest, glbUrl, attempt]);

  useEffect(() => {
    viewer?.setExplode(explode);
  }, [viewer, explode]);

  useEffect(() => {
    viewer?.showReference(context);
  }, [viewer, context]);

  useEffect(() => {
    viewer?.setSelected(selectedKey);
  }, [viewer, selectedKey]);

  const chooseView = (view: View) => {
    if (!viewer) return;
    const t = view.group === "exploded" ? 1 : 0;
    // Explode first (directly, not waiting for the effect) so the view is fitted to what will be shown.
    viewer.setExplode(t);
    actions.setExplode(t);
    viewer.setView(view);
  };

  const hasReference = manifest.parts.some((p) => p.kind === "reference");
  const ready = viewer !== null && status.kind === "ready";
  const percent = Math.round(explode * 100);
  const selected = selectedKey ? manifest.parts.find((p) => p.key === selectedKey) : undefined;

  return (
    <div className="viewport-pane">
      <div className="toolbar" role="toolbar" aria-label="View">
        {manifest.views.length > 0 && (
          <div className="toolbar-group" role="group" aria-label="Named views">
            {manifest.views.map((view) => (
              <button key={view.name} type="button" className="btn" disabled={!ready} onClick={() => chooseView(view)}>
                {view.name}
              </button>
            ))}
          </div>
        )}
        <div className="toolbar-group">
          <button type="button" className="btn toggle" aria-pressed={balloons} onClick={() => actions.setBalloons(!balloons)}>
            Balloons
          </button>
          {hasReference && (
            <button
              type="button"
              className="btn toggle"
              aria-pressed={context}
              title="Show or hide context parts (shown for reference only)"
              onClick={() => actions.setContext(!context)}
            >
              Context
            </button>
          )}
          <button type="button" className="btn" disabled={!ready} title="Fit the picture to what is shown" onClick={() => viewer?.fit()}>
            Fit
          </button>
        </div>
      </div>

      <div className="viewport">
        {/* React leaves this element empty: the effect above puts the viewer's own mount element in it. */}
        <div className="viewer-host" ref={hostRef} />
        {ready && balloons && <Balloons viewer={viewer} parts={manifest.parts} selectedKey={selectedKey} getCanvas={getCanvas} />}
        {selected && <PartCard manifest={manifest} part={selected} />}
        {status.kind === "loading" && (
          <div className="viewport-note" role="status">
            Preparing the 3D model. The first time a version is opened this takes a few seconds.
          </div>
        )}
        {status.kind === "error" && (
          <div className="viewport-note problem" role="alert">
            <strong>The 3D model could not be shown</strong>
            <span>{status.message}</span>
            <span>The Parts and Guide tabs still work.</span>
            <button type="button" className="btn" onClick={() => setAttempt((n) => n + 1)}>
              Try again
            </button>
          </div>
        )}
      </div>

      <div className="explode-bar">
        <label htmlFor="explode-slider">Explode</label>
        <input
          id="explode-slider"
          type="range"
          min={0}
          max={100}
          step={1}
          value={percent}
          disabled={!ready}
          onChange={(e) => actions.setExplode(Number(e.target.value) / 100)}
        />
        <output htmlFor="explode-slider">{percent} %</output>
      </div>
    </div>
  );
}
