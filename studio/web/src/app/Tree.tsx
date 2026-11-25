// Left panel: the project, then its items in manifest order with a marker coloured by kind.
import { useEffect, useRef } from "react";
import { KIND_ORDER, madeLabel } from "../state/logic";
import { actions, useStore } from "../state/store";
import type { Manifest } from "../types";

export function Tree({ manifest }: { manifest: Manifest }) {
  const selectedKey = useStore((s) => s.selectedKey);
  const listRef = useRef<HTMLUListElement>(null);

  // Selected from the 3D view (or a balloon, or the parts table): bring its row into sight.
  useEffect(() => {
    if (!selectedKey) return;
    const row = listRef.current?.querySelector<HTMLElement>('[aria-current="true"]');
    row?.scrollIntoView({ block: "nearest" });
  }, [selectedKey]);

  const kinds = KIND_ORDER.filter((k) => manifest.parts.some((p) => p.kind === k));

  return (
    <nav className="tree" aria-label="Assembly">
      <div className="tree-root">
        <span className="tree-project">{manifest.project}</span>
        <span className="tree-count">{manifest.parts.length} items</span>
      </div>
      <ul ref={listRef}>
        {manifest.parts.map((p) => {
          const selected = p.key === selectedKey;
          return (
            <li key={p.key}>
              <button
                type="button"
                className={selected ? "tree-row selected" : "tree-row"}
                aria-current={selected ? "true" : undefined}
                title={`${p.name} (${madeLabel(p.kind).toLowerCase()})`}
                onClick={() => {
                  actions.select(selected ? null : p.key);
                  actions.setTab("assembly");
                }}
              >
                <span className={`marker kind-${p.kind}`} aria-hidden="true" />
                <span className="tree-name">{p.name}</span>
                {p.label > 0 && <span className="tree-label">{p.label}</span>}
              </button>
            </li>
          );
        })}
      </ul>
      <div className="legend" aria-label="Legend">
        {kinds.map((k) => (
          <span key={k} className="legend-item">
            <span className={`marker kind-${k}`} aria-hidden="true" />
            {madeLabel(k)}
          </span>
        ))}
      </div>
    </nav>
  );
}
