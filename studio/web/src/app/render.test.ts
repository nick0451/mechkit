// Renders the data-only panels to HTML (no browser, no 3D) against the worked example's manifest
// (examples/monitor-weather-display), to check counts and wording.
import { existsSync, readFileSync } from "node:fs";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Manifest } from "../types";
import { GuideTab } from "./GuideTab";
import { PartCard } from "./PartCard";
import { PartsTab } from "./PartsTab";
import { Tree } from "./Tree";

// src/app/ -> src -> web -> studio -> the kit's folder
const path = new URL("../../../../examples/monitor-weather-display/exports/v0p9/presentation/manifest.json", import.meta.url);
const real = existsSync(path);
const manifest: Manifest = real ? JSON.parse(readFileSync(path, "utf-8")) : ({} as Manifest);

const count = (html: string, needle: string) => html.split(needle).length - 1;

describe.skipIf(!real)("panels against the monitor display manifest", () => {
  it("tree lists all 19 items with a legend of the four kinds", () => {
    const html = renderToStaticMarkup(createElement(Tree, { manifest }));
    expect(count(html, 'class="tree-row"')).toBe(19);
    expect(html).toContain("19 items");
    expect(count(html, 'class="legend-item"')).toBe(4);
  });

  it("parts table has 13 rows with quantities 3 / 3 / 1 for bolts, inserts, display", () => {
    const html = renderToStaticMarkup(createElement(PartsTab, { manifest }));
    expect(count(html, "<tr tabindex")).toBe(13);
    const qty = (label: number) => manifest.table.find((r) => r.label === label)?.qty;
    expect([qty(7), qty(6), qty(3)]).toEqual([3, 3, 1]);
    for (const row of manifest.table) expect(html).toContain(`<td class="num">${row.qty}</td>`);
  });

  it("guide shows 7 steps in order, each with parts", () => {
    const html = renderToStaticMarkup(createElement(GuideTab, { manifest }));
    expect(count(html, 'class="guide-step"')).toBe(7);
    expect(html).toContain("Step 1 of 7");
    expect(html).toContain("Step 7 of 7");
    expect(html.indexOf("Step 1 of 7")).toBeLessThan(html.indexOf("Step 2 of 7"));
    expect(count(html, 'class="guide-parts"')).toBe(7);
    expect(html).toContain("x 2"); // two M3 inserts go into the pod in step 1
  });

  it("guide without steps shows a calm message", () => {
    const html = renderToStaticMarkup(createElement(GuideTab, { manifest: { ...manifest, steps: [] } }));
    expect(html).toContain("no assembly order yet");
    expect(html).not.toContain("guide-step");
  });

  it("part card shows size, volume, number and step", () => {
    const part = manifest.parts.find((p) => p.key === "Bezel")!;
    const html = renderToStaticMarkup(createElement(PartCard, { manifest, part }));
    expect(html).toContain("48.0 x 11.4 x 47.6 mm");
    expect(html).toContain("2,388 mm³ (2.39 cm³)");
    expect(html).toContain("3D printed");
    expect(html).toContain("MWD-P1");
    expect(html).toMatch(/Step \d of 7: /);
  });

  it("part card for a context part says it is not part of the build", () => {
    const part = manifest.parts.find((p) => p.kind === "reference")!;
    const html = renderToStaticMarkup(createElement(PartCard, { manifest, part }));
    expect(html).toContain("shown for context");
  });
});
