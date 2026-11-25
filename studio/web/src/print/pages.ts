// Pure logic: page titles, headers and "page N of M". No DOM. Tested in pages.test.ts.
import type { Manifest } from "../types";

export interface PageHeader {
  project: string;
  version: string;
  title: string;
  /** "page 2 of 8" */
  page: string;
}

export const SHEET_TITLE = "Exploded view and parts";
export const GUIDE_TITLE = "Assembly guide";

export function pageLabel(n: number, of: number): string {
  return `page ${n} of ${of}`;
}

export function stepTitle(manifest: Manifest, index: number): string {
  return `Step ${index + 1} of ${manifest.steps.length}: ${manifest.steps[index].title}`;
}

/** Page titles of the assembly guide, in order: the title page, then one page per step. */
export function guideTitles(manifest: Manifest): string[] {
  return [GUIDE_TITLE, ...manifest.steps.map((_, i) => stepTitle(manifest, i))];
}

/** One header per page, numbered 1..M in the order given. */
export function headers(manifest: Manifest, titles: string[]): PageHeader[] {
  return titles.map((title, i) => ({
    project: manifest.project,
    version: manifest.version,
    title,
    page: pageLabel(i + 1, titles.length),
  }));
}

/** Quantity as printed in lists. 0 = the item is a further piece of something counted elsewhere. */
export function qtyText(qty: number): string {
  return qty > 0 ? `${qty} x` : "-";
}
