// Shared data shapes. FOUNDATION FILE: owned by the main session. Agents read it; they do not edit it.
// These mirror what mechkit/present/manifest.py writes and what the backend serves (see ../../CONTRACT.md).

export type Vec3 = [number, number, number];
export type Box = [Vec3, Vec3]; // [min, max], mm, kit frame

/** printed = 3D printed; bought = purchased part; hardware = screws, inserts; reference = context only (e.g. the monitor). */
export type Kind = "printed" | "bought" | "hardware" | "reference";

/** One physical thing in its assembled position. Items that are the same kind of thing share `label` and `part`. */
export interface Part {
  key: string; // unique, file-safe; also the name of this item's node in the GLB
  label: number; // balloon number (0 for reference items)
  kind: Kind;
  name: string; // shown in the tree, e.g. "Bolt M3 x 10 (pod, left)"
  part: string; // parts-table name, e.g. "Bolt M3 x 10, socket head"
  description: string;
  part_number: string;
  material: string;
  colour: string; // "#rrggbb"
  opacity: number; // 1 = solid; reference items may be see-through
  explode: Vec3; // how far the item moves at 100 % explode, mm, kit frame
  count: number; // how many this item adds to its table row (0 = second piece of something already counted)
  volume_mm3: number; // exact, from the CAD kernel
  bbox: Box; // exact, assembled position
  centre: Vec3; // centre of mass, assembled position
  bodies: number;
  step: string; // STEP file name (not used by the web app)
}

export interface View {
  name: string;
  eye: Vec3; // mm, kit frame; only the DIRECTION eye -> target matters, the viewer fits the picture itself
  target: Vec3;
  up: Vec3;
  group: "assembled" | "exploded"; // exploded views are meant to be shown with the explode slider at 100 %
}

export interface TableRow {
  label: number;
  part: string;
  qty: number;
  kind: Kind;
  made: string; // "3D printed" | "bought" | "hardware"
  material: string;
  part_number: string;
  description: string;
}

/** One assembly step: the items that go on in this step. Every non-reference item is in exactly one step. */
export interface Step {
  title: string;
  text: string;
  add: string[]; // item keys
  /** Where this step's picture is taken from (direction only). Absent: the first "exploded" view. */
  view?: { eye: Vec3; target: Vec3; up: Vec3 } | null;
  /** How far items are drawn away from their seats in this step's picture, mm, kit frame, along the way they go on.
   *  May name items of earlier steps too. Items not named stay seated. Absent: derived from the explode vectors. */
  pull?: Record<string, Vec3> | null;
}

export interface GuideItem {
  name: string;
  note: string;
}

export interface GuideWire {
  from: string; // pin on the `from` board
  to: string; // pad on the `to` board
  signal: string;
  note: string;
}

export interface GuideWiring {
  title: string;
  from: string;
  to: string;
  wires: GuideWire[];
  notes: string[];
}

/** The assembly guide's pages besides the steps. Every part of it may be empty. */
export interface Guide {
  tools: GuideItem[];
  consumables: GuideItem[];
  printing: { settings: { name: string; value: string }[]; parts: { part: string; orientation: string }[]; note: string } | null;
  wiring: GuideWiring | null;
  commissioning: { title: string; text: string; checks: string[] }[];
  notes: string[];
}

export interface Manifest {
  project: string;
  version: string;
  up: Vec3; // always [0, 0, 1]: the kit frame is Z up, +Y toward the user, X along the width
  assembled_bbox: Box;
  exploded_bbox: Box;
  exploded_offset: Vec3; // only used by the Fusion sender; ignore
  parts: Part[];
  views: View[];
  table: TableRow[];
  steps: Step[]; // may be empty: then there is no assembly guide
  guide?: Guide | null; // tools, consumables, print settings, wiring, commissioning
}

export interface ProjectInfo {
  id: string; // folder name; URL-encode it in paths
  name: string;
  versions: string[]; // newest first
}

export interface ProjectList {
  projects: ProjectInfo[];
}
