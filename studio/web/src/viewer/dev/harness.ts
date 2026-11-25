// Browser harness for the viewer (development only; not imported by the app, not part of the build).
// To run: copy a project's manifest.json and its model.glb next to this file (do not leave them here), start
// `npx vite --port 5199 --strictPort`, open /src/viewer/dev/harness.html, read the PASS / FAIL list; stop vite.
import * as THREE from "three";
import type { Manifest, Vec3 } from "../../types";
import { worldToKit, type Frame } from "../frame";
import { createViewer } from "../viewer";

const out = document.getElementById("out")!;
const lines: string[] = [];
let failed = 0;
function check(name: string, ok: boolean, detail = ""): void {
  if (!ok) failed++;
  lines.push(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  [" + detail + "]" : ""}`);
  out.textContent = lines.join("\n");
}
const nextFrame = () => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));

function decode(url: string): Promise<HTMLImageElement> {
  return new Promise((res, rej) => {
    const img = new Image();
    img.onload = () => res(img);
    img.onerror = () => rej(new Error("image did not decode"));
    img.src = url;
  });
}
function inkFraction(img: HTMLImageElement, bg: [number, number, number]): number {
  const c = document.createElement("canvas");
  c.width = img.naturalWidth;
  c.height = img.naturalHeight;
  const g = c.getContext("2d")!;
  g.drawImage(img, 0, 0);
  const d = g.getImageData(0, 0, c.width, c.height).data;
  let n = 0;
  for (let i = 0; i < d.length; i += 4) {
    if (Math.abs(d[i] - bg[0]) + Math.abs(d[i + 1] - bg[1]) + Math.abs(d[i + 2] - bg[2]) > 24) n++;
  }
  return n / (d.length / 4);
}
function pixel(img: HTMLImageElement, x: number, y: number): [number, number, number] {
  const c = document.createElement("canvas");
  c.width = img.naturalWidth;
  c.height = img.naturalHeight;
  const g = c.getContext("2d")!;
  g.drawImage(img, 0, 0);
  const d = g.getImageData(Math.round(x), Math.round(y), 1, 1).data;
  return [d[0], d[1], d[2]];
}
function show(url: string, title: string): void {
  const img = document.createElement("img");
  img.src = url;
  img.title = title;
  document.getElementById("imgs")!.appendChild(img);
}

async function main(): Promise<void> {
  const manifest = (await (await fetch("./manifest.json")).json()) as Manifest;
  const glb = "./model.glb";
  const container = document.getElementById("view")!;
  const viewer = createViewer(container);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const dbg = () => (viewer as any).__debug() as { scene: THREE.Scene; camera: THREE.OrthographicCamera; renderer: THREE.WebGLRenderer; frame: Frame; items: { key: string; node: THREE.Object3D; meshes: THREE.Mesh[] }[] };

  let frames = 0;
  viewer.onFrame(() => frames++);
  const selections: (string | null)[] = [];
  viewer.onSelect((k) => selections.push(k));

  await viewer.load(manifest, glb);
  check("load resolves; 19 item nodes found", dbg().items.length === 19, `${dbg().items.length}`);
  check("frame is rigid, 1 world unit = 1 mm", dbg().frame.rigid && Math.abs(dbg().frame.scale - 1) < 1e-6, `scale ${dbg().frame.scale}`);
  check("17 anchors (non-reference, count > 0), all inside the picture after load", viewer.anchors().length === 17 && viewer.anchors().every((a) => a.visible), `${viewer.anchors().length}`);

  // Real geometry against the manifest's exact boxes, assembled and exploded.
  function worstBoxError(t: number): { err: number; key: string } {
    let worst = { err: 0, key: "" };
    const { frame, items, scene } = dbg();
    scene.updateMatrixWorld(true);
    for (const it of items) {
      const part = manifest.parts.find((p) => p.key === it.key)!;
      const box = new THREE.Box3();
      for (const m of it.meshes) {
        const pos = m.geometry.getAttribute("position");
        const v = new THREE.Vector3();
        for (let i = 0; i < pos.count; i++) {
          v.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld);
          const k = worldToKit(frame, [v.x, v.y, v.z]);
          box.expandByPoint(new THREE.Vector3(k[0], k[1], k[2]));
        }
      }
      const lo = part.bbox[0].map((n, i) => n + part.explode[i] * t);
      const hi = part.bbox[1].map((n, i) => n + part.explode[i] * t);
      const e = Math.max(
        Math.abs(box.min.x - lo[0]), Math.abs(box.min.y - lo[1]), Math.abs(box.min.z - lo[2]),
        Math.abs(box.max.x - hi[0]), Math.abs(box.max.y - hi[1]), Math.abs(box.max.z - hi[2]),
      );
      if (e > worst.err) worst = { err: e, key: it.key };
    }
    return worst;
  }
  let w = worstBoxError(0);
  check("assembled: every mesh box matches the manifest bbox (kit frame) within 0.1 mm", w.err < 0.1, `worst ${w.err.toFixed(4)} mm at ${w.key}`);
  viewer.setExplode(1);
  w = worstBoxError(1);
  check("explode 1: every mesh box = manifest bbox + explode within 0.1 mm", w.err < 0.1, `worst ${w.err.toFixed(4)} mm at ${w.key}`);
  viewer.setExplode(0.5);
  w = worstBoxError(0.5);
  check("explode 0.5: halfway within 0.1 mm", w.err < 0.1, `worst ${w.err.toFixed(4)} mm at ${w.key}`);
  viewer.setExplode(0);
  viewer.setExplodeMap({ Knob: 1, Bezel: 0.5 });
  {
    const { items } = dbg();
    const knob = items.find((i) => i.key === "Knob")!.node.position;
    const bezel = items.find((i) => i.key === "Bezel")!.node.position;
    const pod = items.find((i) => i.key === "Pod")!.node.position;
    check("explode map: Knob at 1, Bezel at 0.5, Pod follows the global 0", Math.abs(knob.y + 0.072) < 1e-9 && Math.abs(bezel.y - 0.0492403876506104) < 1e-9 && pod.length() < 1e-12, `${knob.y} ${bezel.y} ${pod.length()}`);
  }
  viewer.setExplodeMap(null);
  w = worstBoxError(0);
  check("explode map cleared: back to assembled", w.err < 0.1, `worst ${w.err.toFixed(4)}`);

  // onFrame
  await nextFrame();
  frames = 0;
  viewer.setExplode(0.3);
  viewer.setExplode(0.6);
  await nextFrame();
  check("onFrame fires once for a burst of explode changes", frames === 1, `${frames}`);
  frames = 0;
  viewer.setSelected("Knob");
  viewer.setHighlighted(["Knob"]);
  await nextFrame();
  check("onFrame does not fire for select / highlight", frames === 0, `${frames}`);
  await nextFrame();
  check("idle: no frames", frames === 0, `${frames}`);
  viewer.setSelected(null);
  viewer.setHighlighted([]);
  viewer.setExplode(0);

  // Pure projection against the real three camera, in several views.
  function worstProjectionError(): number {
    const { camera, frame, scene } = dbg();
    scene.updateMatrixWorld(true);
    const rect = container.getBoundingClientRect();
    let worst = 0;
    for (const a of viewer.anchors()) {
      const part = manifest.parts.find((p) => p.key === a.key)!;
      const m = frame.m;
      const c = part.centre;
      const t = 1; // called at explode 1
      const k: Vec3 = [c[0] + part.explode[0] * t, c[1] + part.explode[1] * t, c[2] + part.explode[2] * t];
      const wv = new THREE.Vector3(
        m[0] * k[0] + m[4] * k[1] + m[8] * k[2] + m[12],
        m[1] * k[0] + m[5] * k[1] + m[9] * k[2] + m[13],
        m[2] * k[0] + m[6] * k[1] + m[10] * k[2] + m[14],
      ).project(camera);
      const x = ((wv.x + 1) / 2) * Math.floor(rect.width - 2);
      const y = ((1 - wv.y) / 2) * Math.floor(rect.height - 2);
      worst = Math.max(worst, Math.abs(x - a.x), Math.abs(y - a.y));
    }
    return worst;
  }
  viewer.setExplode(1);
  for (const v of manifest.views) {
    viewer.setView(v);
    await nextFrame();
    const e = worstProjectionError();
    const all = viewer.anchors().every((a) => a.visible);
    check(`view "${v.name}": anchors equal three's own projection (< 0.01 px), all inside after fit`, e < 0.01 && all, `worst ${e.toExponential(2)} px`);
  }

  // Camera round trip
  const camA = viewer.getCamera();
  viewer.setCamera({ eye: [123.25, -45.5, 67.125], target: [1, 2, 3], up: [0, 0, 1], height: 77.5 });
  const camB = viewer.getCamera();
  check("setCamera -> getCamera is exact", JSON.stringify(camB) === JSON.stringify({ eye: [123.25, -45.5, 67.125], target: [1, 2, 3], up: [0, 0, 1], height: 77.5 }));
  viewer.setCamera(camA);
  check("getCamera -> setCamera -> getCamera is exact", JSON.stringify(viewer.getCamera()) === JSON.stringify(camA));

  // fit keeps direction
  viewer.setExplode(0);
  viewer.fit();
  const camC = viewer.getCamera();
  const dirOf = (s: { eye: Vec3; target: Vec3 }) => {
    const d = [s.target[0] - s.eye[0], s.target[1] - s.eye[1], s.target[2] - s.eye[2]];
    const n = Math.hypot(d[0], d[1], d[2]);
    return d.map((x) => x / n);
  };
  const dd = dirOf(camA).map((x, i) => Math.abs(x - dirOf(camC)[i]));
  check("fit() keeps the direction, changes the picture height after un-exploding, everything inside", Math.max(...dd) < 1e-9 && camC.height !== camA.height && viewer.anchors().every((a) => a.visible), `height ${camA.height.toFixed(1)} -> ${camC.height.toFixed(1)}`);

  // Context toggle
  const front = manifest.views[0];
  viewer.setView(front);
  const hWith = viewer.getCamera().height;
  viewer.showReference(false);
  viewer.fit();
  const hWithout = viewer.getCamera().height;
  check("showReference(false) hides the monitor (fit gets tighter)", hWithout < hWith, `${hWith.toFixed(1)} -> ${hWithout.toFixed(1)}`);
  viewer.showReference(true);
  viewer.setView(front);
  await nextFrame();

  // Picking with real pointer events at a part's anchor
  function clickAt(x: number, y: number, dragBy = 0): void {
    const canvas = container.querySelector("canvas")!;
    const r = canvas.getBoundingClientRect();
    const base = { bubbles: true, cancelable: true, pointerId: 77, button: 0, clientX: r.left + x, clientY: r.top + y };
    canvas.dispatchEvent(new PointerEvent("pointerdown", { ...base, buttons: 1 }));
    if (dragBy) canvas.dispatchEvent(new PointerEvent("pointermove", { ...base, buttons: 1, clientX: base.clientX + dragBy }));
    canvas.dispatchEvent(new PointerEvent("pointerup", { ...base, clientX: base.clientX + dragBy }));
  }
  viewer.setExplode(1);
  const expl = manifest.views.find((v) => v.group === "exploded")!;
  viewer.setView(expl);
  await nextFrame();
  let picked = 0;
  const wrong: string[] = [];
  for (const a of viewer.anchors()) {
    selections.length = 0;
    clickAt(a.x, a.y);
    const got = selections[0];
    const part = manifest.parts.find((p) => p.key === a.key)!;
    const gotPart = manifest.parts.find((p) => p.key === got);
    if (got === a.key || (gotPart && gotPart.label === part.label)) picked++;
    else wrong.push(`${a.key}->${got}`);
  }
  // A centre of mass can sit in a ring's hole (Bezel, Pod) or inside / behind another part, so not all 17 can hit.
  check("exploded view: clicking a part's anchor picks that part where the centre is on show (>= 10 of 17, Knob among them)", picked >= 10 && !wrong.some((x) => x.startsWith("Knob->")), `${picked}/17; other: ${wrong.join(", ")}`);
  viewer.setSelected("Knob");
  selections.length = 0;
  await nextFrame();
  check("setSelected does not call onSelect", selections.length === 0);
  viewer.setSelected(null);
  selections.length = 0;
  clickAt(3, 3);
  check("clicking empty space reports null", selections.length === 1 && selections[0] === null, JSON.stringify(selections));
  selections.length = 0;
  const before = JSON.stringify(viewer.getCamera());
  const some = viewer.anchors()[0];
  clickAt(some.x, some.y, 40);
  check("a drag is not a click, and it orbits", selections.length === 0 && JSON.stringify(viewer.getCamera()) !== before, JSON.stringify(selections));
  {
    const canvas = container.querySelector("canvas")!;
    const r = canvas.getBoundingClientRect();
    const h0 = viewer.getCamera().height;
    canvas.dispatchEvent(new WheelEvent("wheel", { bubbles: true, cancelable: true, deltaY: -200, clientX: r.left + 100, clientY: r.top + 100 }));
    check("wheel up zooms in", viewer.getCamera().height < h0, `${h0.toFixed(1)} -> ${viewer.getCamera().height.toFixed(1)}`);
    const c0 = viewer.getCamera();
    const base = { bubbles: true, cancelable: true, pointerId: 78, button: 2, clientX: r.left + 200, clientY: r.top + 200 };
    canvas.dispatchEvent(new PointerEvent("pointerdown", { ...base, buttons: 2 }));
    canvas.dispatchEvent(new PointerEvent("pointermove", { ...base, buttons: 2, clientX: base.clientX + 50 }));
    canvas.dispatchEvent(new PointerEvent("pointerup", { ...base, clientX: base.clientX + 50 }));
    const c1 = viewer.getCamera();
    const moved = Math.hypot(c1.target[0] - c0.target[0], c1.target[1] - c0.target[1], c1.target[2] - c0.target[2]);
    check("right-drag pans (target moves, direction kept)", moved > 1 && Math.max(...dirOf(c0).map((x, i) => Math.abs(x - dirOf(c1)[i]))) < 1e-9, `moved ${moved.toFixed(2)} mm`);
  }

  // Capture from the on-screen viewer
  viewer.setView(expl);
  await nextFrame();
  const canvas = container.querySelector("canvas")!;
  const sizeBefore = `${canvas.width}x${canvas.height}`;
  const cap = await viewer.capture({ width: 1600, height: 900, background: "#ffffff" });
  const img = await decode(cap.dataUrl);
  check("capture: PNG of exactly the requested size", img.naturalWidth === 1600 && img.naturalHeight === 900 && cap.dataUrl.startsWith("data:image/png"), `${img.naturalWidth}x${img.naturalHeight}`);
  check("capture: on-screen canvas size restored", `${canvas.width}x${canvas.height}` === sizeBefore, `${sizeBefore} -> ${canvas.width}x${canvas.height}`);
  check("capture: white corner, model drawn", pixel(img, 2, 2).every((n) => n === 255) && inkFraction(img, [255, 255, 255]) > 0.03, `ink ${(inkFraction(img, [255, 255, 255]) * 100).toFixed(1)} %`);
  check("capture: 17 anchors, all inside the image", cap.anchors.length === 17 && cap.anchors.every((a) => a.visible && a.x >= 0 && a.x <= 1600 && a.y >= 0 && a.y <= 900));
  {
    // the pixel at an anchor of a big solid part should be near that part's colour, not background
    const a = cap.anchors.find((x) => x.key === "Knob")!;
    const px = pixel(img, a.x, a.y);
    check("capture: the pixel at the Knob's anchor is red (anchor lands on the part)", px[0] > 110 && px[0] > px[1] * 1.6 && px[0] > px[2] * 1.6, `rgb ${px.join(",")}`);
  }
  show(cap.dataUrl, "on-screen viewer, exploded, white");
  await nextFrame();
  const shotAfter = await decode(canvas.toDataURL());
  void shotAfter;

  // Hidden, non-interactive viewer (what the print module does)
  const hidden = document.getElementById("hidden")!;
  const pv = createViewer(hidden, { background: "#ffffff", interactive: false });
  await pv.load(manifest, glb);
  pv.showReference(false);
  const stepKeys = manifest.steps[2]?.add ?? ["Knob"];
  const soFar = manifest.steps.slice(0, 3).flatMap((s) => s.add);
  pv.setVisible(soFar);
  pv.setHighlighted(stepKeys);
  pv.setExplodeMap(Object.fromEntries(stepKeys.map((k) => [k, 1])));
  pv.setView(expl);
  const cap2 = await pv.capture({ width: 1400, height: 1000 });
  const img2 = await decode(cap2.dataUrl);
  const ink2 = inkFraction(img2, [255, 255, 255]);
  check("hidden viewer: capture has the requested size and is not blank", img2.naturalWidth === 1400 && img2.naturalHeight === 1000 && ink2 > 0.02, `ink ${(ink2 * 100).toFixed(1)} %`);
  check("hidden viewer: anchors only for the shown parts, all inside (fitted to the image shape)", cap2.anchors.length > 0 && cap2.anchors.every((a) => soFar.includes(a.key) && a.visible), `${cap2.anchors.length} anchors`);
  show(cap2.dataUrl, "hidden viewer, step 3 style");
  pv.setVisible(null);
  pv.setHighlighted([]);
  pv.setExplodeMap(null);
  pv.showReference(true);
  pv.setView(manifest.views[0]);
  const cap3 = await pv.capture({ width: 1400, height: 1000 });
  show(cap3.dataUrl, "hidden viewer, assembled front, white");
  const cap4 = await pv.capture({ width: 700, height: 500, background: "#0b0e13" });
  show(cap4.dataUrl, "hidden viewer, assembled front, dark");
  const hiddenCanvas = hidden.querySelector("canvas")!;
  const gl = (pv as unknown as { __debug: () => { renderer: THREE.WebGLRenderer } }).__debug().renderer.getContext();
  pv.dispose();
  check("dispose: canvas removed and context lost", !hiddenCanvas.isConnected && gl.isContextLost());

  // Create / dispose many viewers: no context leak warnings expected (see console)
  for (let i = 0; i < 20; i++) {
    const tmp = createViewer(hidden, { interactive: false });
    tmp.dispose();
  }
  await nextFrame();
  const glMain = dbg().renderer.getContext();
  check("after 20 create/dispose cycles the main viewer's context is still alive", !glMain.isContextLost());

  // Resize
  container.style.width = "500px";
  container.style.height = "300px";
  viewer.resize();
  await nextFrame();
  const dpr = Math.min(Math.max(window.devicePixelRatio, 1), 2);
  check("resize: canvas follows the container", canvas.width === Math.floor(500 * dpr) && canvas.height === Math.floor(300 * dpr), `${canvas.width}x${canvas.height} dpr ${dpr}`);
  container.style.width = "760px";
  container.style.height = "480px";
  viewer.resize();
  viewer.setExplode(0);
  viewer.setView(manifest.views[0]);
  viewer.setSelected("Knob");
  await nextFrame();

  lines.push("", failed === 0 ? "ALL PASS" : `${failed} FAILED`);
  out.textContent = lines.join("\n");
  document.title = failed === 0 ? "HARNESS ALL PASS" : `HARNESS ${failed} FAILED`;
}

main().catch((err) => {
  lines.push(`ERROR ${err instanceof Error ? err.stack || err.message : String(err)}`);
  out.textContent = lines.join("\n");
  document.title = "HARNESS ERROR";
});
