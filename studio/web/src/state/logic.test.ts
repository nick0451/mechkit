import { describe, expect, it } from "vitest";
import type { Part, Step } from "../types";
import {
  balloonParts,
  cameraForPicture,
  clamp01,
  countOutsideView,
  describeManifestError,
  describeProjectsError,
  firstKeyForLabel,
  formatSize,
  formatVolume,
  groupStepParts,
  madeLabel,
  outsideViewMessage,
  parseChoice,
  pickDefault,
  sameCamera,
  stepOfPart,
} from "./logic";

function part(key: string, label: number, over: Partial<Part> = {}): Part {
  return {
    key,
    label,
    kind: "printed",
    name: key,
    part: key,
    description: "",
    part_number: "",
    material: "",
    colour: "#808080",
    opacity: 1,
    explode: [0, 0, 0],
    count: 1,
    volume_mm3: 1,
    bbox: [
      [0, 0, 0],
      [1, 1, 1],
    ],
    centre: [0, 0, 0],
    bodies: 1,
    step: `${key}.step`,
    ...over,
  };
}

const parts: Part[] = [
  part("Pod", 2),
  part("Display_Board", 3, { kind: "bought", part: "Round display" }),
  part("Display_Screen", 3, { kind: "bought", part: "Round display", count: 0 }),
  part("Insert_L", 6, { kind: "hardware", part: "Insert M3" }),
  part("Insert_R", 6, { kind: "hardware", part: "Insert M3" }),
  part("Insert_cap", 6, { kind: "hardware", part: "Insert M3" }),
  part("Monitor", 0, { kind: "reference" }),
];

const steps: Step[] = [
  { title: "Inserts", text: "", add: ["Pod", "Insert_L", "Insert_R"] },
  { title: "Display", text: "", add: ["Display_Screen", "Display_Board"] },
  { title: "Cap", text: "", add: ["Insert_cap", "Nope"] },
];

describe("pickDefault", () => {
  const projects = [
    { id: "A", name: "A", versions: ["v2", "v1"] },
    { id: "B", name: "B", versions: ["v9"] },
  ];
  it("opens the first project's newest version", () => {
    expect(pickDefault(projects)).toEqual({ projectId: "A", version: "v2" });
  });
  it("keeps a remembered choice that still exists", () => {
    expect(pickDefault(projects, { projectId: "A", version: "v1" })).toEqual({ projectId: "A", version: "v1" });
    expect(pickDefault(projects, { projectId: "B", version: "v9" })).toEqual({ projectId: "B", version: "v9" });
  });
  it("falls back to the newest version when the remembered one is gone", () => {
    expect(pickDefault(projects, { projectId: "B", version: "v3" })).toEqual({ projectId: "B", version: "v9" });
  });
  it("ignores a remembered project that is gone", () => {
    expect(pickDefault(projects, { projectId: "Z", version: "v1" })).toEqual({ projectId: "A", version: "v2" });
  });
  it("skips projects without versions and returns null when nothing is viewable", () => {
    expect(pickDefault([{ id: "E", name: "E", versions: [] }, projects[1]])).toEqual({ projectId: "B", version: "v9" });
    expect(pickDefault([])).toBeNull();
    expect(pickDefault([{ id: "E", name: "E", versions: [] }])).toBeNull();
  });
});

describe("parseChoice", () => {
  it("reads a stored choice", () => {
    expect(parseChoice('{"projectId":"A","version":"v1"}')).toEqual({ projectId: "A", version: "v1" });
  });
  it("gives null for anything else", () => {
    expect(parseChoice(null)).toBeNull();
    expect(parseChoice("")).toBeNull();
    expect(parseChoice("{oops")).toBeNull();
    expect(parseChoice('{"projectId":1}')).toBeNull();
    expect(parseChoice('"text"')).toBeNull();
  });
});

describe("formatting", () => {
  it("formats a size from a box with one decimal", () => {
    expect(
      formatSize([
        [-24, -1.4216, -58.1796],
        [24, 9.9483, -10.5616],
      ]),
    ).toBe("48.0 x 11.4 x 47.6 mm");
  });
  it("formats volumes, adding cm3 from 1000 mm3", () => {
    expect(formatVolume(12.34)).toBe("12.3 mm³");
    expect(formatVolume(640.4)).toBe("640 mm³");
    expect(formatVolume(2387.9)).toBe("2,388 mm³ (2.39 cm³)");
    expect(formatVolume(1234567)).toBe("1,234,567 mm³ (1234.6 cm³)");
    expect(formatVolume(0)).toBe("");
    expect(formatVolume(Number.NaN)).toBe("");
  });
  it("names how a part is made", () => {
    expect(madeLabel("printed")).toBe("3D printed");
    expect(madeLabel("reference")).toBe("Context only");
  });
  it("clamps the explode amount", () => {
    expect(clamp01(-1)).toBe(0);
    expect(clamp01(0.4)).toBe(0.4);
    expect(clamp01(7)).toBe(1);
    expect(clamp01(Number.NaN)).toBe(0);
  });
});

describe("groupStepParts", () => {
  it("groups items sharing a label and sums their counts", () => {
    expect(groupStepParts({ parts }, steps[0])).toEqual([
      { label: 2, part: "Pod", qty: 1, kind: "printed", keys: ["Pod"] },
      { label: 6, part: "Insert M3", qty: 2, kind: "hardware", keys: ["Insert_L", "Insert_R"] },
    ]);
  });
  it("counts a two-piece part once", () => {
    expect(groupStepParts({ parts }, steps[1])).toEqual([
      { label: 3, part: "Round display", qty: 1, kind: "bought", keys: ["Display_Board", "Display_Screen"] },
    ]);
  });
  it("skips keys the manifest does not have", () => {
    expect(groupStepParts({ parts }, steps[2]).map((g) => g.keys)).toEqual([["Insert_cap"]]);
    expect(groupStepParts({ parts }, { title: "", text: "", add: [] })).toEqual([]);
  });
});

describe("lookups", () => {
  it("finds the step an item belongs to", () => {
    expect(stepOfPart({ steps }, "Insert_cap")).toEqual({ number: 3, total: 3, title: "Cap" });
    expect(stepOfPart({ steps }, "Monitor")).toBeNull();
    expect(stepOfPart({ steps: [] }, "Pod")).toBeNull();
  });
  it("finds the first item with a label", () => {
    expect(firstKeyForLabel(parts, 6)).toBe("Insert_L");
    expect(firstKeyForLabel(parts, 99)).toBeNull();
  });
  it("gives balloons to counted, non-reference items only", () => {
    expect(balloonParts(parts).map((p) => p.key)).toEqual(["Pod", "Display_Board", "Insert_L", "Insert_R", "Insert_cap"]);
  });
});

describe("error wording", () => {
  it("says the server is not running when nothing answers", () => {
    const p = describeProjectsError({ kind: "network", message: "The server did not answer." });
    expect(p.title).toMatch(/not running/);
    expect(p.hint).toMatch(/mechkit studio/);
  });
  it("treats a gateway error (dev proxy without backend) the same way", () => {
    expect(describeProjectsError({ kind: "http", status: 502, message: "x" }).title).toMatch(/not running/);
  });
  it("reports other project-list failures with their detail", () => {
    const p = describeProjectsError(new Error("boom"));
    expect(p.title).toMatch(/could not be read/);
    expect(p.detail).toBe("boom");
  });
  it("explains a missing version", () => {
    const p = describeManifestError({ kind: "http", status: 404, message: "unknown version" }, "Clock", "v3");
    expect(p.title).toBe("Clock v3 was not found");
    expect(p.detail).toBe("unknown version");
  });
  it("explains a broken manifest", () => {
    const p = describeManifestError({ kind: "format", message: "no parts list" }, "Clock", "v3");
    expect(p.title).toBe("Clock v3 failed to load");
    expect(p.hint).toMatch(/mechkit present/);
  });
});

describe("cameraForPicture", () => {
  const cam = { eye: [0, -300, 0] as [number, number, number], target: [0, 0, 0] as [number, number, number], up: [0, 0, 1] as [number, number, number], height: 100 };
  it("raises the picture height when the screen is wider than the picture, so the sides are kept", () => {
    const out = cameraForPicture(cam, 2.4, 1.6);
    expect(out.height).toBeCloseTo(150, 9);
    expect(out.height * 1.6).toBeCloseTo(cam.height * 2.4, 9); // same width in mm as on screen
    expect(out.eye).toEqual(cam.eye);
    expect(cam.height).toBe(100); // the input is not changed
  });
  it("leaves the camera alone when the screen is narrower, the same shape, or unknown", () => {
    expect(cameraForPicture(cam, 1.2, 1.6)).toBe(cam);
    expect(cameraForPicture(cam, 1.6, 1.6)).toBe(cam);
    expect(cameraForPicture(cam, 0, 1.6)).toBe(cam);
    expect(cameraForPicture(cam, Number.NaN, 1.6)).toBe(cam);
  });
});

describe("sameCamera (is the screen still showing the fitted view?)", () => {
  type V = [number, number, number];
  const cam = { eye: [330, 320, 310] as V, target: [10, 20, 30] as V, up: [0, 0, 1] as V, height: 240 };
  const copy = () => ({ eye: [...cam.eye] as V, target: [...cam.target] as V, up: [...cam.up] as V, height: cam.height });
  it("is true for an equal camera, and for one that differs only by rounding", () => {
    expect(sameCamera(cam, copy())).toBe(true);
    const c = copy();
    c.eye[0] += 1e-9;
    c.height *= 1 + 1e-12;
    expect(sameCamera(cam, c)).toBe(true);
  });
  it("is false after a zoom, a pan, an orbit or a roll", () => {
    expect(sameCamera(cam, { ...copy(), height: 239 })).toBe(false); // zoom
    const panned = copy();
    panned.eye[0] += 0.5;
    panned.target[0] += 0.5;
    expect(sameCamera(cam, panned)).toBe(false);
    const orbited = copy();
    orbited.eye = [330, 321, 310];
    expect(sameCamera(cam, orbited)).toBe(false);
    expect(sameCamera(cam, { ...copy(), up: [0, 1, 0] })).toBe(false);
  });
});

describe("parts outside the view", () => {
  it("counts the anchors that are not visible", () => {
    expect(countOutsideView([])).toBe(0);
    expect(countOutsideView([{ visible: true }, { visible: true }])).toBe(0);
    expect(countOutsideView([{ visible: true }, { visible: false }, { visible: false }])).toBe(2);
  });
  it("words the warning for one and for several", () => {
    expect(outsideViewMessage(1)).toBe("1 part is outside the view and would be missing from the printed sheet.");
    expect(outsideViewMessage(4)).toBe("4 parts are outside the view and would be missing from the printed sheet.");
  });
});
