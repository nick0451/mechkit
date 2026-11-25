// The assembly guide's pages besides the cover and the steps: "Before you start" (tools, consumables, print settings),
// the wiring diagram, and commissioning (firmware, tests, inspection). All text goes in through textContent.
import "./extras.css";

import type { Guide, GuideWiring } from "../types";
import type { PageHeader } from "./pages";
import { el, pageEl } from "./render";

export const BEFORE_TITLE = "Before you start";
export const COMMISSIONING_TITLE = "Commissioning";

/** Which of the extra pages a guide has, in print order around the steps. */
export function extraPages(guide: Guide | null | undefined): { before: boolean; wiring: boolean; commissioning: boolean } {
  if (!guide) return { before: false, wiring: false, commissioning: false };
  const before = guide.tools.length > 0 || guide.consumables.length > 0 || !!guide.printing || guide.notes.length > 0;
  return { before, wiring: !!guide.wiring && guide.wiring.wires.length > 0, commissioning: guide.commissioning.length > 0 };
}

function listEl(rows: { name: string; note: string }[]): HTMLElement {
  const ul = el("ul", "pr-checklist");
  for (const r of rows) {
    const li = el("li");
    li.append(el("span", "pr-box"), el("span", "pr-item-name", r.name));
    if (r.note) li.append(el("span", "pr-item-note", r.note));
    ul.append(li);
  }
  return ul;
}

function pairTable(head: [string, string], rows: [string, string][], cls: string): HTMLElement {
  const table = el("table", `pr-pairs ${cls}`);
  const thead = el("thead");
  const tr = el("tr");
  tr.append(el("th", undefined, head[0]), el("th", undefined, head[1]));
  thead.append(tr);
  table.append(thead);
  const body = el("tbody");
  for (const [a, b] of rows) {
    const row = el("tr");
    row.append(el("td", "pr-pair-a", a), el("td", undefined, b));
    body.append(row);
  }
  table.append(body);
  return table;
}

export function guideBeforePage(header: PageHeader, guide: Guide): HTMLElement {
  const page = pageEl("before", header);
  page.append(el("h1", "pr-step-heading", BEFORE_TITLE));
  const cols = el("div", "pr-cols");

  const left = el("div", "pr-col");
  if (guide.tools.length > 0) left.append(el("h2", undefined, "Tools"), listEl(guide.tools));
  if (guide.consumables.length > 0) left.append(el("h2", undefined, "Consumables"), listEl(guide.consumables));
  cols.append(left);

  const right = el("div", "pr-col");
  if (guide.printing) {
    right.append(el("h2", undefined, "Printing the parts"));
    if (guide.printing.settings.length > 0) {
      right.append(pairTable(["Setting", "Value"], guide.printing.settings.map((s) => [s.name, s.value]), "pr-settings"));
    }
    if (guide.printing.parts.length > 0) {
      right.append(pairTable(["Part", "How it lies on the bed"], guide.printing.parts.map((p) => [p.part, p.orientation]), "pr-orient"));
    }
    if (guide.printing.note) right.append(el("p", "pr-small", guide.printing.note));
  }
  for (const note of guide.notes) right.append(el("p", "pr-callout", note));
  cols.append(right);

  page.append(cols);
  return page;
}

// ---- wiring diagram ---------------------------------------------------------------------------------------------

const SVG_NS = "http://www.w3.org/2000/svg";

function svg<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number>, text?: string): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  if (text !== undefined) node.textContent = text;
  return node;
}

/** Line colour by what the wire carries: power red, ground black, everything else a dark blue. */
export function wireColour(signal: string): string {
  const s = signal.toLowerCase();
  if (s === "power" || s.includes("3v3") || s.includes("vcc")) return "#c0392b";
  if (s === "ground" || s.includes("gnd")) return "#111111";
  return "#1f4e8c";
}

/** Geometry of the diagram, in its own units: two boxes with one row per wire. Pure, so it can be tested. */
export function wiringLayout(count: number): { width: number; height: number; rowY: number[]; left: [number, number]; right: [number, number]; top: number } {
  const top = 46;
  const pitch = 30;
  const rowY = Array.from({ length: count }, (_, i) => top + 26 + i * pitch);
  return { width: 640, height: top + 26 + Math.max(0, count - 1) * pitch + 30, rowY, left: [20, 210], right: [430, 620], top };
}

function wiringSvg(w: GuideWiring): SVGSVGElement {
  const L = wiringLayout(w.wires.length);
  const root = svg("svg", { viewBox: `0 0 ${L.width} ${L.height}`, class: "pr-wiring-svg", role: "img", "aria-label": w.title });
  const bottom = L.height - 8;
  for (const [x0, x1] of [L.left, L.right]) {
    root.append(svg("rect", { x: x0, y: L.top, width: x1 - x0, height: bottom - L.top, rx: 6, fill: "#f3f4f6", stroke: "#111", "stroke-width": 1.5 }));
  }
  root.append(svg("text", { x: (L.left[0] + L.left[1]) / 2, y: L.top - 12, "text-anchor": "middle", class: "pr-wiring-title" }, w.from));
  root.append(svg("text", { x: (L.right[0] + L.right[1]) / 2, y: L.top - 12, "text-anchor": "middle", class: "pr-wiring-title" }, w.to));
  w.wires.forEach((wire, i) => {
    const y = L.rowY[i];
    const colour = wireColour(wire.signal);
    root.append(svg("line", { x1: L.left[1], y1: y, x2: L.right[0], y2: y, stroke: colour, "stroke-width": 3, "stroke-linecap": "round" }));
    root.append(svg("circle", { cx: L.left[1], cy: y, r: 5, fill: "#fff", stroke: "#111", "stroke-width": 1.5 }));
    root.append(svg("circle", { cx: L.right[0], cy: y, r: 5, fill: "#fff", stroke: "#111", "stroke-width": 1.5 }));
    root.append(svg("text", { x: L.left[1] - 12, y: y + 5, "text-anchor": "end", class: "pr-wiring-pin" }, wire.from));
    root.append(svg("text", { x: L.right[0] + 12, y: y + 5, "text-anchor": "start", class: "pr-wiring-pin" }, wire.to));
    if (wire.signal) {
      root.append(svg("text", { x: (L.left[1] + L.right[0]) / 2, y: y - 6, "text-anchor": "middle", class: "pr-wiring-signal" }, wire.signal));
    }
  });
  return root;
}

export function guideWiringPage(header: PageHeader, wiring: GuideWiring): HTMLElement {
  const page = pageEl("wiring", header);
  page.append(el("h1", "pr-step-heading", wiring.title));
  const cols = el("div", "pr-cols");

  const left = el("div", "pr-col pr-col-wide");
  const fig = el("div", "pr-wiring");
  fig.append(wiringSvg(wiring));
  left.append(fig);
  cols.append(left);

  const right = el("div", "pr-col");
  right.append(el("h2", undefined, `${wiring.wires.length} wires`));
  const table = el("table", "pr-pairs pr-wires");
  const thead = el("thead");
  const hr = el("tr");
  hr.append(el("th", undefined, wiring.from), el("th", undefined, wiring.to), el("th", undefined, "Carries"), el("th", "pr-done-col", "Done"));
  thead.append(hr);
  table.append(thead);
  const body = el("tbody");
  for (const wire of wiring.wires) {
    const tr = el("tr");
    const carries = wire.note ? `${wire.signal} (${wire.note})` : wire.signal;
    const done = el("td", "pr-done-col");
    done.append(el("span", "pr-box"));
    tr.append(el("td", "pr-pair-a", wire.from), el("td", "pr-pair-a", wire.to), el("td", undefined, carries || "-"), done);
    body.append(tr);
  }
  table.append(body);
  right.append(table);
  if (wiring.notes.length > 0) {
    const ul = el("ul", "pr-notes");
    for (const n of wiring.notes) ul.append(el("li", undefined, n));
    right.append(ul);
  }
  cols.append(right);

  page.append(cols);
  return page;
}

export function guideCommissioningPage(header: PageHeader, guide: Guide): HTMLElement {
  const page = pageEl("commissioning", header);
  page.append(el("h1", "pr-step-heading", COMMISSIONING_TITLE));
  const grid = el("div", "pr-sections");
  guide.commissioning.forEach((section, i) => {
    const box = el("section", "pr-section");
    box.append(el("h2", undefined, `${i + 1}. ${section.title}`));
    if (section.text) box.append(el("p", "pr-section-text", section.text));
    if (section.checks.length > 0) box.append(listEl(section.checks.map((c) => ({ name: c, note: "" }))));
    grid.append(box);
  });
  page.append(grid);
  return page;
}
