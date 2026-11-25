// The assembly steps on screen: number, title, text and the parts each step needs.
import { groupStepParts } from "../state/logic";
import { actions } from "../state/store";
import type { Manifest } from "../types";

export function GuideTab({ manifest }: { manifest: Manifest }) {
  const total = manifest.steps.length;
  if (total === 0) {
    return (
      <p className="calm">
        This project has no assembly order yet, so there is no guide to show. The 3D view and the parts table work as usual.
      </p>
    );
  }

  const show = (key: string) => {
    actions.select(key);
    actions.setTab("assembly");
  };

  const g = manifest.guide ?? null;

  return (
    <div className="guide-wrap">
      {g && (g.tools.length > 0 || g.consumables.length > 0 || g.printing) && (
        <section className="guide-extra">
          <h2>Before you start</h2>
          <div className="guide-extra-cols">
            {g.tools.length > 0 && (
              <div>
                <h3>Tools</h3>
                <ul>
                  {g.tools.map((t) => (
                    <li key={t.name}>
                      <strong>{t.name}</strong>
                      {t.note && <span className="guide-note"> {t.note}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {g.consumables.length > 0 && (
              <div>
                <h3>Consumables</h3>
                <ul>
                  {g.consumables.map((t) => (
                    <li key={t.name}>
                      <strong>{t.name}</strong>
                      {t.note && <span className="guide-note"> {t.note}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {g.printing && (
              <div>
                <h3>Printing the parts</h3>
                <ul>
                  {g.printing.settings.map((x) => (
                    <li key={x.name}>
                      <strong>{x.name}:</strong> {x.value}
                    </li>
                  ))}
                  {g.printing.parts.map((x) => (
                    <li key={x.part}>
                      <strong>{x.part}:</strong> {x.orientation}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          {g.notes.map((note) => (
            <p key={note} className="guide-callout">
              {note}
            </p>
          ))}
        </section>
      )}
      {g?.wiring && (
        <section className="guide-extra">
          <h2>{g.wiring.title}</h2>
          <table className="guide-wires">
            <thead>
              <tr>
                <th>{g.wiring.from}</th>
                <th>{g.wiring.to}</th>
                <th>Carries</th>
              </tr>
            </thead>
            <tbody>
              {g.wiring.wires.map((w) => (
                <tr key={w.from + w.to}>
                  <td>{w.from}</td>
                  <td>{w.to}</td>
                  <td>{w.note ? `${w.signal} (${w.note})` : w.signal}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul>
            {g.wiring.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>
      )}
    <ol className="guide">
      {manifest.steps.map((step, i) => {
        const needs = groupStepParts(manifest, step);
        return (
          <li key={i} className="guide-step">
            <div className="guide-number" aria-hidden="true">
              {i + 1}
            </div>
            <div className="guide-body">
              <h2>
                <span className="guide-of">
                  Step {i + 1} of {total}
                </span>
                {step.title}
              </h2>
              <p>{step.text}</p>
              {needs.length > 0 && (
                <ul className="guide-parts" aria-label="You need">
                  {needs.map((n) => (
                    <li key={n.label}>
                      <button type="button" className="guide-part" title="Show in the 3D view" onClick={() => show(n.keys[0])}>
                        <span className="guide-label">{n.label}</span>
                        <span className="guide-name">{n.part}</span>
                        {n.qty > 0 && <span className="guide-qty">x {n.qty}</span>}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        );
      })}
    </ol>
      {g && g.commissioning.length > 0 && (
        <section className="guide-extra">
          <h2>Commissioning</h2>
          {g.commissioning.map((c, i) => (
            <div key={c.title} className="guide-commission">
              <h3>
                {i + 1}. {c.title}
              </h3>
              {c.text && <p>{c.text}</p>}
              <ul>
                {c.checks.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
