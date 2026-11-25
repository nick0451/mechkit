// What the selected part is: floats over the viewport's lower-left corner.
import { formatSize, formatVolume, madeLabel, stepOfPart } from "../state/logic";
import { actions } from "../state/store";
import type { Manifest, Part } from "../types";

interface Props {
  manifest: Manifest;
  part: Part;
}

export function PartCard({ manifest, part }: Props) {
  const step = stepOfPart(manifest, part.key);
  const volume = formatVolume(part.volume_mm3);
  const rows: [string, string][] = [["Made", madeLabel(part.kind)]];
  if (part.material) rows.push(["Material", part.material]);
  if (part.part_number) rows.push(["Part number", part.part_number]);
  rows.push(["Size", formatSize(part.bbox)]);
  if (volume) rows.push(["Volume", volume]);
  if (part.label > 0) rows.push(["No.", String(part.label)]);
  if (step) rows.push(["Assembly", `Step ${step.number} of ${step.total}: ${step.title}`]);
  else if (part.kind === "reference") rows.push(["Assembly", "Not part of the build; shown for context"]);

  return (
    <aside className="part-card" aria-label="Selected part">
      <header>
        <span className={`marker kind-${part.kind}`} aria-hidden="true" />
        <h2>{part.name}</h2>
        <button type="button" className="btn small" aria-label="Clear selection" title="Clear selection" onClick={() => actions.select(null)}>
          Close
        </button>
      </header>
      {part.part && part.part !== part.name && <p className="table-name">Parts list: {part.part}</p>}
      {part.description && <p className="description">{part.description}</p>}
      <dl>
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}
