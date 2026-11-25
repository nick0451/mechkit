// Numbered balloons over the 3D view. React renders one button per item once; positions are then written straight
// to the elements on every viewer frame, so orbiting does not re-render anything.
import { useEffect, useMemo, useRef } from "react";
import { balloonParts } from "../state/logic";
import { actions } from "../state/store";
import type { Part } from "../types";
import type { Viewer } from "../viewer/api";
import { forwardToCanvas } from "./forward";

interface Props {
  viewer: Viewer;
  parts: Part[];
  selectedKey: string | null;
  /** The 3D canvas under the balloons: drags and wheel turns that start on a balloon are passed on to it. */
  getCanvas: () => HTMLCanvasElement | null;
}

export function Balloons({ viewer, parts, selectedKey, getCanvas }: Props) {
  const items = useMemo(() => balloonParts(parts), [parts]);
  const elements = useRef(new Map<string, HTMLButtonElement>());
  const layer = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = layer.current;
    return el ? forwardToCanvas(el, getCanvas) : undefined;
  }, [getCanvas]);

  useEffect(() => {
    const els = elements.current;
    const update = () => {
      const shown = new Set<string>();
      for (const a of viewer.anchors()) {
        const el = els.get(a.key);
        if (!el || !a.visible) continue;
        shown.add(a.key);
        el.style.transform = `translate(${a.x.toFixed(1)}px, ${a.y.toFixed(1)}px) translate(-50%, -50%)`;
        el.style.display = "flex";
      }
      for (const [key, el] of els) if (!shown.has(key)) el.style.display = "none";
    };
    const off = viewer.onFrame(update);
    update();
    return off;
  }, [viewer, items]);

  return (
    <div className="balloons" ref={layer}>
      {items.map((p) => (
        <button
          key={p.key}
          type="button"
          tabIndex={-1} // the tree gives keyboard access to the same items
          className={p.key === selectedKey ? "balloon selected" : "balloon"}
          title={p.name}
          aria-label={`${p.label}: ${p.name}`}
          ref={(el) => {
            if (el) elements.current.set(p.key, el);
            else elements.current.delete(p.key);
          }}
          onClick={() => actions.select(p.key)}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
