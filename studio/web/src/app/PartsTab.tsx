// The parts table, straight from manifest.table. A row selects the first item with that number and shows it in 3D.
import { firstKeyForLabel } from "../state/logic";
import { actions } from "../state/store";
import type { Manifest } from "../types";

export function PartsTab({ manifest }: { manifest: Manifest }) {
  if (manifest.table.length === 0) {
    return <p className="calm">This project has no parts table.</p>;
  }

  const open = (label: number) => {
    const key = firstKeyForLabel(manifest.parts, label);
    if (key) actions.select(key);
    actions.setTab("assembly");
  };

  return (
    <div className="parts-tab">
      <table className="parts-table">
        <caption>Parts for {manifest.project} {manifest.version}. Choose a row to see the part in the 3D view.</caption>
        <thead>
          <tr>
            <th scope="col" className="num">No.</th>
            <th scope="col">Part</th>
            <th scope="col" className="num">Qty</th>
            <th scope="col">Made</th>
            <th scope="col">Material</th>
            <th scope="col">Part number</th>
            <th scope="col">Description</th>
          </tr>
        </thead>
        <tbody>
          {manifest.table.map((row) => (
            <tr
              key={`${row.label}-${row.part}`}
              tabIndex={0}
              onClick={() => open(row.label)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  open(row.label);
                }
              }}
            >
              <td className="num">{row.label}</td>
              <th scope="row">
                <span className={`marker kind-${row.kind}`} aria-hidden="true" />
                {row.part}
              </th>
              <td className="num">{row.qty}</td>
              <td>{row.made}</td>
              <td>{row.material}</td>
              <td className="mono">{row.part_number}</td>
              <td>{row.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
