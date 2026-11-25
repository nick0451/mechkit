// Builds the printed pages as DOM. All text goes in through textContent; the only markup inserted as a string is the
// balloon SVG, which holds numbers only (see balloons.ts).
import type { Manifest, TableRow } from "../types";
import type { Capture } from "../viewer/api";
import { balloonSvg, layoutBalloons } from "./balloons";
import type { PageHeader } from "./pages";
import { qtyText } from "./pages";
import type { NeedRow } from "./steps";

export interface Picture {
  capture: Capture;
  width: number; // px, as captured
  height: number;
  /** Parts that get a balloon: a list of keys, "all", or "none". */
  balloons: readonly string[] | "all" | "none";
  alt: string;
}

/** Designed print sizes (mm). The CSS in print.css uses the same column widths: keep the two in step. */
const SHEET_PICTURE_WIDTH_MM = 155;
const SHEET_PICTURE_MAX_HEIGHT_MM = 105;
const COVER_PICTURE_MAX_HEIGHT_MM = 92; // lower: in portrait the title, this picture and 13 table rows share one page
const STEP_PICTURE_WIDTH_MM = 175;
const STEP_PICTURE_MAX_HEIGHT_MM = 135;
/** Above this many rows the parts table is set smaller and tighter (print.css, .pr-table-dense) to stay on its page:
 *  the pages are laid out for the 13 rows of the first project, with room for about 3 more lines. */
export const DENSE_TABLE_ROWS = 14;

export function tableClass(rowCount: number): string {
  return rowCount > DENSE_TABLE_ROWS ? "pr-table pr-table-dense" : "pr-table";
}

export function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function headerEl(h: PageHeader): HTMLElement {
  const head = el("header", "pr-header");
  const left = el("div", "pr-header-left");
  left.append(el("span", "pr-project", h.project), el("span", "pr-version", h.version));
  head.append(left, el("div", "pr-header-title", h.title), el("div", "pr-header-page", h.page));
  return head;
}

export function pageEl(kind: string, h: PageHeader): HTMLElement {
  const page = el("section", `pr-page pr-${kind}`);
  page.append(headerEl(h));
  return page;
}

/** The image with its balloon overlay. The box keeps the captured aspect ratio; the SVG shares the image's viewBox. */
function pictureEl(pic: Picture, printedWidthMm: number, maxHeightMm: number, caption?: string): HTMLElement {
  const fig = el("figure", "pr-figure");
  const box = el("div", "pr-pic");
  box.style.aspectRatio = `${pic.width} / ${pic.height}`;
  box.style.maxWidth = `${((maxHeightMm * pic.width) / pic.height).toFixed(1)}mm`;
  const img = el("img");
  img.alt = pic.alt;
  img.width = pic.width;
  img.height = pic.height;
  img.decoding = "sync";
  img.src = pic.capture.dataUrl;
  box.append(img);
  if (pic.balloons !== "none") {
    const layout = layoutBalloons(pic.capture.anchors, {
      width: pic.width,
      height: pic.height,
      printedWidthMm,
      keys: pic.balloons === "all" ? undefined : pic.balloons,
    });
    if (layout.balloons.length > 0) box.insertAdjacentHTML("beforeend", balloonSvg(layout));
  }
  fig.append(box);
  if (caption) fig.append(el("figcaption", "pr-caption", caption));
  return fig;
}

/** No., Part, Qty, Made, Material, Part number on a row's first line; the description on its second. */
function partsTableEl(rows: TableRow[]): HTMLElement {
  const table = el("table", tableClass(rows.length));
  const cols = el("colgroup");
  for (const c of ["no", "part", "qty", "made", "material", "pn"]) cols.append(el("col", `pr-col-${c}`));
  table.append(cols);

  const thead = el("thead");
  const h1 = el("tr");
  const no = el("th", "pr-no", "No.");
  no.rowSpan = 2;
  h1.append(no, el("th", undefined, "Part"), el("th", "pr-qty", "Qty"), el("th", undefined, "Made"), el("th", undefined, "Material"), el("th", undefined, "Part number"));
  const h2 = el("tr");
  const hd = el("th", "pr-desc", "Description");
  hd.colSpan = 5;
  h2.append(hd);
  thead.append(h1, h2);
  table.append(thead);

  for (const r of rows) {
    const body = el("tbody", "pr-row");
    const a = el("tr");
    const num = el("td", "pr-no", String(r.label));
    num.rowSpan = 2;
    a.append(
      num,
      el("td", "pr-part", r.part),
      el("td", "pr-qty", String(r.qty)),
      el("td", undefined, r.made),
      el("td", undefined, r.material || "-"),
      el("td", "pr-pn", r.part_number || "-"),
    );
    const b = el("tr");
    const d = el("td", "pr-desc", r.description);
    d.colSpan = 5;
    b.append(d);
    body.append(a, b);
    table.append(body);
  }
  return table;
}

function splitEl(figure: HTMLElement, side: HTMLElement): HTMLElement {
  const split = el("div", "pr-split");
  side.classList.add("pr-side");
  split.append(figure, side);
  return split;
}

export function sheetPage(manifest: Manifest, header: PageHeader, pic: Picture): HTMLElement {
  const page = pageEl("sheet", header);
  const side = el("div");
  side.append(partsTableEl(manifest.table));
  page.append(splitEl(pictureEl(pic, SHEET_PICTURE_WIDTH_MM, SHEET_PICTURE_MAX_HEIGHT_MM, "Numbers match the parts table."), side));
  return page;
}

export function guideCoverPage(manifest: Manifest, header: PageHeader, pic: Picture): HTMLElement {
  const page = pageEl("cover", header);
  const title = el("div", "pr-title");
  title.append(el("h1", undefined, manifest.project), el("p", undefined, `Assembly guide, version ${manifest.version}. ${manifest.steps.length} steps.`));
  page.append(title);
  const side = el("div");
  side.append(el("h2", undefined, "Parts"), partsTableEl(manifest.table));
  page.append(splitEl(pictureEl(pic, SHEET_PICTURE_WIDTH_MM, COVER_PICTURE_MAX_HEIGHT_MM, "The finished assembly."), side));
  return page;
}

export interface StepPageData {
  header: PageHeader;
  heading: string; // "Step 3 of 7: Wire and seat the display"
  text: string;
  need: NeedRow[];
  pic: Picture;
  last: boolean;
  /** Replaces the closing line on the last step (e.g. when a commissioning page follows). */
  doneText?: string;
}

export function guideStepPage(data: StepPageData): HTMLElement {
  const page = pageEl("step", data.header);
  page.append(el("h1", "pr-step-heading", data.heading));

  const side = el("div");
  side.append(el("h2", undefined, "You need"));
  const list = el("table", "pr-need");
  for (const row of data.need) {
    const tr = el("tr");
    const num = el("td", "pr-need-no");
    num.append(el("span", "pr-chip", String(row.label)));
    tr.append(num, el("td", "pr-need-part", row.part), el("td", "pr-need-qty", qtyText(row.qty)));
    list.append(tr);
  }
  side.append(list);
  side.append(el("h2", undefined, "Do this"));
  side.append(el("p", "pr-step-text", data.text));
  if (data.last) side.append(el("p", "pr-done", data.doneText ?? "Done: that was the last step."));

  const caption = "This step's parts are in full colour and pulled out along the way they go on. Parts fitted earlier are pale.";
  page.append(splitEl(pictureEl(data.pic, STEP_PICTURE_WIDTH_MM, STEP_PICTURE_MAX_HEIGHT_MM, caption), side));
  return page;
}

/** Resolves when every image in the pages can be painted; rejects with a clear message when one cannot. */
export async function imagesReady(root: HTMLElement): Promise<void> {
  const imgs = Array.from(root.querySelectorAll("img"));
  await Promise.all(
    imgs.map(async (img) => {
      try {
        await img.decode();
      } catch {
        if (!(img.complete && img.naturalWidth > 0)) throw new Error("A picture for the printed pages could not be decoded.");
      }
    }),
  );
}
