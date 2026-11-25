// The 3D viewer: implements ./api.ts (Viewer). The only folder that imports three.js.
//
// How it is put together:
// - The GLB is in metres; it is loaded under a wrapper scaled by 1000, so the three.js world is millimetres.
// - The kit frame <-> world conversion (frame.ts) is derived from the item nodes' parent matrix after loading.
// - The camera is kept as a CameraState in the KIT frame (camera.ts does the maths) and applied to an orthographic
//   three camera. Fitting and balloon anchors use the manifest's exact boxes and centres, not the display mesh.
// - Every item has its own materials. See-through states (muted, reference) are drawn with a depth pre-pass so only
//   the nearest see-through surface shows: no sorting artefacts, and solid parts behind stay visible through it.
// - Rendering is on demand: one requestAnimationFrame per burst of changes, nothing while idle.

import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { Manifest, Part, Vec3, View } from "../types";
import type { BalloonAnchor, CameraState, Capture, CreateViewer, Viewer, ViewerOptions } from "./api";
import {
  basisOf,
  clipRange,
  cloneState,
  fitToPoints,
  isValidState,
  orbit,
  pan,
  project,
  viewDirection,
  zoomAt,
  type Size,
} from "./camera";
import { boxCorners, clamp01, explodeAmount, explodeOffset, movedCorners } from "./explode";
import { frameFromParentMatrix, IDENTITY, kitDirToWorld, kitToWorld, type Frame } from "./frame";
import { findItemNodes } from "./nodes";

const DEFAULT_BACKGROUND = "#0b0e13"; // tokens.css --viewport
const ACCENT = "#4cc2ff"; // tokens.css --accent
const MUTED_TOWARD = "#d3d8df";
const MUTED_MIX = 0.65;
const MUTED_OPACITY = 0.3;
const MUTED_EDGE = "#8f98a6";
const MUTED_EDGE_OPACITY = 0.55;
// On a light background (the printed pages) the pale look above nearly vanishes: a 1 px grey line at half strength
// on white paper is the only outline a "fitted earlier" part has. There, muted parts are a little more solid and
// their lines darker and stronger. NOT yet judged on a real print.
const LIGHT_BACKGROUND = 0.5; // linear luminance above which the background counts as light
const MUTED_OPACITY_ON_LIGHT = 0.45;
const MUTED_EDGE_ON_LIGHT = "#5f6875";
const MUTED_EDGE_OPACITY_ON_LIGHT = 0.85;
const EDGE_ANGLE = 30; // degrees: sharper creases get a line
const CLICK_SLOP = 4; // px: more movement than this is a drag, not a click
const ORBIT_SPEED = 0.008; // radians per pixel
const FIT_MARGIN = 0.14;
const DEFAULT_STATE: CameraState = { eye: [300, 300, 200], target: [0, 0, 0], up: [0, 0, 1], height: 200 };

interface Item {
  part: Part;
  node: THREE.Object3D;
  base: THREE.Vector3; // the node's own position in the file (normally 0)
  meshes: THREE.Mesh[];
  prepass: THREE.Mesh[]; // depth-only twins, shown while the item is see-through
  material: THREE.MeshStandardMaterial;
  depthMaterial: THREE.MeshBasicMaterial;
  edges: THREE.LineSegments | null;
  edgeMaterial: THREE.LineBasicMaterial;
  colour: THREE.Color;
  edgeColour: THREE.Color;
  shown: boolean;
}

function luminance(c: THREE.Color): number {
  return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b; // c is linear
}

/** Line colour that reads against the part itself: lighter on dark parts, darker on light ones. */
function edgeColourFor(colour: THREE.Color): THREE.Color {
  const out = colour.clone();
  if (luminance(colour) < 0.18) out.lerp(new THREE.Color("#ffffff"), 0.42);
  else out.lerp(new THREE.Color("#000000"), 0.62);
  return out;
}

export const createViewer: CreateViewer = (container: HTMLElement, options: ViewerOptions = {}): Viewer => {
  const interactive = options.interactive !== false;

  // ---------------------------------------------------------------- renderer, scene, lights
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "default" });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;
  const canvas = renderer.domElement;
  canvas.style.display = "block";
  canvas.style.width = "100%";
  canvas.style.height = "100%";
  canvas.style.outline = "none";
  canvas.style.touchAction = "none";
  container.appendChild(canvas);

  function resolveBackground(): string {
    if (options.background) return options.background;
    try {
      const v = getComputedStyle(container).getPropertyValue("--viewport").trim();
      if (v) return v;
    } catch {
      // not attached to a document: use the default
    }
    return DEFAULT_BACKGROUND;
  }
  function colourOf(css: string, fallback: string): THREE.Color {
    const c = new THREE.Color(fallback);
    try {
      c.set(css as THREE.ColorRepresentation);
    } catch {
      c.set(fallback);
    }
    return c;
  }

  const scene = new THREE.Scene();
  const background = colourOf(resolveBackground(), DEFAULT_BACKGROUND);
  scene.background = background;

  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 1000);
  scene.add(camera);

  // Lights ride with the camera, so every view direction is lit the same way (on screen and on paper).
  // Intensities are for three's physical units (a directional light of pi gives full albedo head-on).
  const hemi = new THREE.HemisphereLight(0xffffff, 0x9aa1ad, 1.7);
  const key = new THREE.DirectionalLight(0xffffff, 2.3);
  key.position.set(-0.55, 0.85, 1); // from the upper left, a little in front
  const fill = new THREE.DirectionalLight(0xffffff, 0.9);
  fill.position.set(0.9, -0.25, 0.6); // from the lower right
  camera.add(key, key.target, fill, fill.target);
  key.target.position.set(0, 0, -1);
  fill.target.position.set(0, 0, -1);
  // The hemisphere light's "sky" follows the picture's up: its position IS its direction, set in applyCamera.
  scene.add(hemi);

  const world = new THREE.Group(); // scaled so one world unit is one millimetre
  world.name = "studio-world";
  world.scale.setScalar(1000);
  scene.add(world);

  // ---------------------------------------------------------------- state
  let disposed = false;
  let loadToken = 0;
  let modelRoot: THREE.Object3D | null = null;
  let manifest: Manifest | null = null;
  let items: Item[] = [];
  let itemByKey = new Map<string, Item>();
  let pickMeshes: THREE.Mesh[] = [];
  let frame: Frame = frameFromParentMatrix(IDENTITY, 1);
  let clipPoints: Vec3[] = []; // every part's box at 0 and at 100 % explode, for near / far

  let explode = 0;
  let explodeMap: Record<string, number> | null = null;
  let offsets: Record<string, Vec3> | null = null; // absolute displacements (setOffsets); win over explode
  let offsetClip: Vec3[] = []; // box corners at those displacements, so near / far still cover them
  let visibleKeys: Set<string> | null = null;
  let highlighted = new Set<string>();
  let selected: string | null = null;
  let referenceOn = true;

  let cam: CameraState = cloneState(DEFAULT_STATE);
  /** Bumped whenever what is shown moves or appears / disappears (explode, visibility). */
  let contentVersion = 0;
  /** Set by setView / fit: the camera is "fitted" for this content version, until the user or setCamera moves it. */
  let fittedAt: number | null = null;

  const selectListeners = new Set<(key: string | null) => void>();
  const frameListeners = new Set<() => void>();
  let rafId = 0;
  let frameChanged = false; // camera / explode / visibility / size changed since the last frame

  let cssSize: Size = { width: 0, height: 0 };

  // ---------------------------------------------------------------- sizes and camera
  function measure(): Size {
    return { width: Math.max(0, Math.floor(container.clientWidth)), height: Math.max(0, Math.floor(container.clientHeight)) };
  }
  /** The size used for maths: a hidden (0 x 0) container still gets a sane picture shape. */
  function mathSize(): Size {
    return cssSize.width > 0 && cssSize.height > 0 ? cssSize : { width: 800, height: 600 };
  }

  /** The screen's pixel ratio, kept between 1 and 2 (more costs a lot and shows little). */
  function wantedPixelRatio(): number {
    return Math.min(Math.max(window.devicePixelRatio || 1, 1), 2);
  }

  function applyRendererSize(): void {
    cssSize = measure();
    renderer.setPixelRatio(wantedPixelRatio());
    renderer.setSize(Math.max(1, cssSize.width), Math.max(1, cssSize.height), false);
  }

  function applyCamera(state: CameraState, size: Size): void {
    const b = basisOf(state);
    const halfH = (state.height * frame.scale) / 2;
    const halfW = (halfH * size.width) / size.height;
    const { near, far } = clipRange(state, clipPts());
    camera.left = -halfW;
    camera.right = halfW;
    camera.top = halfH;
    camera.bottom = -halfH;
    camera.near = near * frame.scale;
    camera.far = far * frame.scale;
    const eye = kitToWorld(frame, state.eye);
    const target = kitToWorld(frame, state.target);
    const up = kitDirToWorld(frame, b.up);
    camera.position.set(eye[0], eye[1], eye[2]);
    camera.up.set(up[0], up[1], up[2]).normalize();
    hemi.position.copy(camera.up);
    camera.lookAt(target[0], target[1], target[2]);
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
  }

  // ---------------------------------------------------------------- render on demand
  function renderNow(): void {
    if (disposed) return;
    applyCamera(cam, mathSize());
    renderer.render(scene, camera);
  }

  function requestRender(changed: boolean): void {
    if (disposed) return;
    if (changed) frameChanged = true;
    if (rafId) return;
    rafId = requestAnimationFrame(() => {
      rafId = 0;
      if (disposed) return;
      renderNow();
      if (frameChanged) {
        frameChanged = false;
        for (const cb of [...frameListeners]) {
          try {
            cb();
          } catch (err) {
            console.error("viewer onFrame listener failed", err);
          }
        }
      }
    });
  }

  // ---------------------------------------------------------------- per-item appearance
  function amountFor(key: string): number {
    return explodeAmount(key, explode, explodeMap);
  }

  function isShown(part: Part): boolean {
    if (visibleKeys && !visibleKeys.has(part.key)) return false;
    if (part.kind === "reference" && !referenceOn) return false;
    return true;
  }

  /** Where a part is drawn relative to its seat, mm, kit frame. */
  function offsetFor(part: Part): Vec3 {
    if (offsets && Object.prototype.hasOwnProperty.call(offsets, part.key)) return offsets[part.key];
    return explodeOffset(part, amountFor(part.key));
  }

  function clipPts(): Vec3[] {
    return offsetClip.length > 0 ? clipPoints.concat(offsetClip) : clipPoints;
  }

  function applyExplode(item: Item): void {
    const o = offsetFor(item.part);
    // Item-local units are metres in kit axes (CONTRACT.md): mm / 1000, no axis juggling.
    item.node.position.set(item.base.x + o[0] / 1000, item.base.y + o[1] / 1000, item.base.z + o[2] / 1000);
    item.node.updateMatrixWorld(true);
  }

  const accent = new THREE.Color(ACCENT);
  const mutedToward = new THREE.Color(MUTED_TOWARD);
  const onLight = luminance(background) > LIGHT_BACKGROUND;
  const mutedEdge = new THREE.Color(onLight ? MUTED_EDGE_ON_LIGHT : MUTED_EDGE);
  const mutedOpacity = onLight ? MUTED_OPACITY_ON_LIGHT : MUTED_OPACITY;
  const mutedEdgeOpacity = onLight ? MUTED_EDGE_OPACITY_ON_LIGHT : MUTED_EDGE_OPACITY;

  function applyAppearance(item: Item): void {
    const { part, material, edgeMaterial } = item;
    item.shown = isShown(part);
    item.node.visible = item.shown;

    const muted = highlighted.size > 0 && !highlighted.has(part.key);
    const isSelected = selected !== null && selected === part.key;
    const baseOpacity = Math.min(1, Math.max(0.05, part.opacity));
    const opacity = muted ? Math.min(baseOpacity, mutedOpacity) : baseOpacity;
    const seeThrough = opacity < 1;

    material.color.copy(item.colour);
    if (muted) material.color.lerp(mutedToward, MUTED_MIX);
    material.opacity = opacity;
    material.transparent = seeThrough;
    material.depthWrite = !seeThrough; // see-through: depth comes from the pre-pass twin
    material.emissive.copy(accent);
    material.emissiveIntensity = isSelected ? 0.38 : 0;
    material.needsUpdate = true;

    for (const m of item.meshes) m.renderOrder = seeThrough ? 2 : 0;
    for (const m of item.prepass) m.visible = seeThrough;

    if (isSelected) edgeMaterial.color.copy(accent);
    else if (muted) edgeMaterial.color.copy(mutedEdge);
    else edgeMaterial.color.copy(item.edgeColour);
    const edgeOpacity = muted ? mutedEdgeOpacity : seeThrough ? Math.max(0.45, opacity) : 1;
    edgeMaterial.opacity = isSelected ? 1 : edgeOpacity;
    edgeMaterial.transparent = edgeMaterial.opacity < 1;
    edgeMaterial.needsUpdate = true;
    if (item.edges) item.edges.renderOrder = seeThrough ? 3 : 0;
  }

  function applyAllAppearance(): void {
    for (const item of items) applyAppearance(item);
  }

  // ---------------------------------------------------------------- model set-up and tear-down
  function disposeModel(): void {
    for (const item of items) {
      for (const m of item.meshes) m.geometry.dispose();
      item.material.dispose();
      item.depthMaterial.dispose();
      item.edges?.geometry.dispose();
      item.edgeMaterial.dispose();
    }
    if (modelRoot) {
      // Anything in the file that is not one of our items (and so was not disposed above).
      modelRoot.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (mesh.isMesh || (o as THREE.LineSegments).isLineSegments) {
          mesh.geometry?.dispose();
          const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
          for (const mat of mats) mat?.dispose();
        }
      });
      world.remove(modelRoot);
    }
    modelRoot = null;
    items = [];
    itemByKey = new Map();
    pickMeshes = [];
    clipPoints = [];
  }

  /** One line set per item: creases sharper than EDGE_ANGLE across the whole item, in the item's own frame (mm). */
  function buildEdges(node: THREE.Object3D, meshes: THREE.Mesh[], material: THREE.LineBasicMaterial): THREE.LineSegments | null {
    node.updateWorldMatrix(true, true);
    const toItem = new THREE.Matrix4().copy(node.matrixWorld).invert();
    const rel = new THREE.Matrix4();
    const v = new THREE.Vector3();
    const out: number[] = [];
    const q = (n: number) => Math.round(n * 1e6) / 1e3; // metres -> mm, snapped to 1 micron so shared edges weld
    for (const mesh of meshes) {
      const pos = mesh.geometry.getAttribute("position");
      if (!pos) continue;
      rel.multiplyMatrices(toItem, mesh.matrixWorld);
      const index = mesh.geometry.getIndex();
      const count = index ? index.count : pos.count;
      for (let i = 0; i + 2 < count; i += 3) {
        for (let k = 0; k < 3; k++) {
          const vi = index ? index.getX(i + k) : i + k;
          v.fromBufferAttribute(pos, vi).applyMatrix4(rel);
          out.push(q(v.x), q(v.y), q(v.z));
        }
      }
    }
    if (out.length === 0) return null;
    const merged = new THREE.BufferGeometry();
    merged.setAttribute("position", new THREE.Float32BufferAttribute(out, 3));
    const edgeGeometry = new THREE.EdgesGeometry(merged, EDGE_ANGLE);
    merged.dispose();
    const lines = new THREE.LineSegments(edgeGeometry, material);
    lines.name = "studio-edges";
    lines.scale.setScalar(0.001); // back to the item's metres
    lines.raycast = () => {}; // never picked
    return lines;
  }

  function buildItems(root: THREE.Object3D, m: Manifest): void {
    root.updateMatrixWorld(true);
    let parentMatrix: THREE.Matrix4 | null = null;
    // Items are the direct children of one node (the file's root, `model`), matched by the name the FILE gave them:
    // see nodes.ts for why a search by name through the whole scene is wrong. The loader "sanitises" node names
    // (spaces -> underscores, a few reserved characters dropped), hence the second argument.
    const nodes = findItemNodes<THREE.Object3D>(
      root,
      m.parts.map((p) => p.key),
      (name) => THREE.PropertyBinding.sanitizeNodeName(name),
    );
    for (const part of m.parts) {
      const node = nodes.get(part.key);
      if (!node) {
        console.warn(`viewer: the model has no node named "${part.key}"; that part is not drawn`);
        continue;
      }
      if (!parentMatrix && node.parent) parentMatrix = node.parent.matrixWorld.clone();

      const colour = new THREE.Color(DEFAULT_BACKGROUND);
      try {
        colour.set(part.colour); // "#rrggbb" is sRGB; three converts to its linear working space
      } catch {
        colour.set("#8a94a6");
      }
      const material = new THREE.MeshStandardMaterial({
        color: colour.clone(),
        roughness: 0.62,
        metalness: 0,
        side: THREE.DoubleSide,
        polygonOffset: true, // push faces back a hair so the edge lines on them are not speckled
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      });
      material.forceSinglePass = true;
      material.name = `studio:${part.key}`;
      const depthMaterial = new THREE.MeshBasicMaterial({
        colorWrite: false,
        depthWrite: true,
        transparent: true, // only to put it in the see-through pass, after the solid parts
        side: THREE.DoubleSide,
        polygonOffset: true,
        polygonOffsetFactor: 1,
        polygonOffsetUnits: 1,
      });
      depthMaterial.forceSinglePass = true;
      const edgeColour = edgeColourFor(colour);
      const edgeMaterial = new THREE.LineBasicMaterial({ color: edgeColour.clone() });

      const meshes: THREE.Mesh[] = [];
      node.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (mesh.isMesh) meshes.push(mesh);
      });
      const prepass: THREE.Mesh[] = [];
      for (const mesh of meshes) {
        const old = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        for (const mat of old) mat?.dispose();
        mesh.material = material;
        if (!mesh.geometry.getAttribute("normal")) mesh.geometry.computeVertexNormals();
        mesh.userData.studioKey = part.key;
        const twin = new THREE.Mesh(mesh.geometry, depthMaterial);
        twin.name = "studio-depth";
        twin.renderOrder = 1;
        twin.visible = false;
        twin.raycast = () => {};
        mesh.add(twin); // same placement as the mesh it shadows
        prepass.push(twin);
      }
      const edges = buildEdges(node, meshes, edgeMaterial);
      if (edges) node.add(edges);

      const item: Item = {
        part,
        node,
        base: node.position.clone(),
        meshes,
        prepass,
        material,
        depthMaterial,
        edges,
        edgeMaterial,
        colour,
        edgeColour,
        shown: true,
      };
      items.push(item);
      itemByKey.set(part.key, item);
      pickMeshes.push(...meshes);
    }
    if (items.length === 0 && m.parts.length > 0) {
      throw new Error("The 3D model does not contain any of the parts listed in the manifest.");
    }
    frame = frameFromParentMatrix(parentMatrix ? parentMatrix.elements : world.matrixWorld.elements, 0.001);
    if (!frame.rigid || Math.abs(frame.scale - 1) > 1e-3) {
      console.warn("viewer: unexpected model frame (not a plain rotation in millimetres); views may be off", frame);
    }
    clipPoints = [];
    for (const part of m.parts) clipPoints.push(...movedCorners(part, 0), ...movedCorners(part, 1));
  }

  // ---------------------------------------------------------------- fitting
  function visiblePoints(): Vec3[] {
    if (!manifest) return [];
    const pts: Vec3[] = [];
    for (const part of manifest.parts) {
      if (!isShown(part)) continue;
      pts.push(...boxCorners(part.bbox, offsetFor(part)));
    }
    if (pts.length === 0) for (const part of manifest.parts) pts.push(...boxCorners(part.bbox, offsetFor(part)));
    return pts;
  }

  function fitted(forward: Vec3, up: Vec3, size: Size): CameraState | null {
    return fitToPoints(visiblePoints(), forward, up, size.width / size.height, FIT_MARGIN);
  }

  function contentChanged(): void {
    contentVersion++;
  }

  // ---------------------------------------------------------------- anchors
  function anchorsFor(state: CameraState, size: Size): BalloonAnchor[] {
    if (!manifest) return [];
    const { near, far } = clipRange(state, clipPts());
    const out: BalloonAnchor[] = [];
    for (const part of manifest.parts) {
      if (part.kind === "reference" || !(part.count > 0)) continue;
      if (!isShown(part) || !itemByKey.has(part.key)) continue;
      const off = offsetFor(part);
      const p = project([part.centre[0] + off[0], part.centre[1] + off[1], part.centre[2] + off[2]], state, size);
      const inside = p.x >= 0 && p.x <= size.width && p.y >= 0 && p.y <= size.height && p.depth >= near && p.depth <= far;
      out.push({ key: part.key, label: part.label, x: p.x, y: p.y, visible: inside });
    }
    return out;
  }

  // ---------------------------------------------------------------- input
  const raycaster = new THREE.Raycaster();
  const cleanups: Array<() => void> = [];

  function pickAt(clientX: number, clientY: number): string | null {
    const rect = canvas.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    applyCamera(cam, mathSize());
    scene.updateMatrixWorld(true);
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, 1 - ((clientY - rect.top) / rect.height) * 2);
    raycaster.setFromCamera(ndc, camera);
    const hits = raycaster.intersectObjects(pickMeshes, false);
    let reference: string | null = null;
    for (const hit of hits) {
      const k = hit.object.userData.studioKey as string | undefined;
      const item = k ? itemByKey.get(k) : undefined;
      if (!item || !item.shown) continue;
      // A see-through context part in front must not swallow clicks meant for the real parts behind it.
      if (item.part.kind === "reference") {
        reference = reference ?? item.part.key;
        continue;
      }
      return item.part.key;
    }
    return reference;
  }

  function emitSelect(key: string | null): void {
    for (const cb of [...selectListeners]) {
      try {
        cb(key);
      } catch (err) {
        console.error("viewer onSelect listener failed", err);
      }
    }
  }

  if (interactive) {
    let drag: { id: number; mode: "orbit" | "pan"; x: number; y: number; startX: number; startY: number; moved: boolean; button: number } | null =
      null;

    const onDown = (e: PointerEvent) => {
      if (drag || (e.button !== 0 && e.button !== 1 && e.button !== 2)) return;
      const mode = e.button === 0 && !e.shiftKey ? "orbit" : "pan";
      drag = { id: e.pointerId, mode, x: e.clientX, y: e.clientY, startX: e.clientX, startY: e.clientY, moved: false, button: e.button };
      try {
        canvas.setPointerCapture(e.pointerId);
      } catch {
        // capture is a nicety
      }
      e.preventDefault();
    };
    const onMove = (e: PointerEvent) => {
      if (!drag || e.pointerId !== drag.id) return;
      if (!drag.moved && Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) <= CLICK_SLOP) return;
      const dx = e.clientX - drag.x;
      const dy = e.clientY - drag.y;
      drag.moved = true;
      drag.x = e.clientX;
      drag.y = e.clientY;
      if (dx === 0 && dy === 0) return;
      cam = drag.mode === "orbit" ? orbit(cam, -dx * ORBIT_SPEED, dy * ORBIT_SPEED) : pan(cam, dx, dy, mathSize());
      fittedAt = null;
      requestRender(true);
    };
    const onUp = (e: PointerEvent) => {
      if (!drag || e.pointerId !== drag.id) return;
      const d = drag;
      drag = null;
      try {
        canvas.releasePointerCapture(e.pointerId);
      } catch {
        // already released
      }
      if (e.type === "pointerup" && !d.moved && d.button === 0 && !e.shiftKey) emitSelect(pickAt(e.clientX, e.clientY));
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const unit = e.deltaMode === 1 ? 33 : e.deltaMode === 2 ? 400 : 1; // lines / pages -> pixels
      const factor = Math.exp(Math.max(-1, Math.min(1, (e.deltaY * unit) / 500)));
      const size = mathSize();
      const px = ((e.clientX - rect.left) / rect.width) * size.width;
      const py = ((e.clientY - rect.top) / rect.height) * size.height;
      cam = zoomAt(cam, factor, px, py, size);
      fittedAt = null;
      requestRender(true);
    };
    const onContext = (e: Event) => e.preventDefault();

    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("contextmenu", onContext);
    cleanups.push(() => {
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointercancel", onUp);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("contextmenu", onContext);
    });
  } else {
    canvas.style.pointerEvents = "none";
  }

  const onContextLost = (e: Event) => e.preventDefault();
  const onContextRestored = () => requestRender(true);
  canvas.addEventListener("webglcontextlost", onContextLost);
  canvas.addEventListener("webglcontextrestored", onContextRestored);
  cleanups.push(() => {
    canvas.removeEventListener("webglcontextlost", onContextLost);
    canvas.removeEventListener("webglcontextrestored", onContextRestored);
  });

  function doResize(): void {
    if (disposed) return;
    const next = measure();
    // The pixel ratio changes without any change of size when the window moves to a screen with another scaling,
    // or the browser zoom changes: the canvas would stay blurred (or oversampled) until the next real resize.
    const sameRatio = Math.abs(renderer.getPixelRatio() - wantedPixelRatio()) < 1e-6;
    if (next.width === cssSize.width && next.height === cssSize.height && sameRatio) return;
    applyRendererSize();
    renderNow(); // straight away: a resized canvas is cleared, and waiting a frame would flicker
    requestRender(true);
  }
  if (typeof ResizeObserver !== "undefined") {
    const ro = new ResizeObserver(() => doResize());
    ro.observe(container);
    cleanups.push(() => ro.disconnect());
  }

  // Nothing reports a change of devicePixelRatio by itself; a media query for the CURRENT ratio stops matching when
  // it changes, and is then set up again for the new one.
  if (typeof window.matchMedia === "function") {
    let query: MediaQueryList | null = null;
    const onRatio = (): void => {
      watchRatio();
      doResize();
    };
    const watchRatio = (): void => {
      query?.removeEventListener("change", onRatio);
      query = window.matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
      query.addEventListener("change", onRatio);
    };
    watchRatio();
    cleanups.push(() => query?.removeEventListener("change", onRatio));
  }

  applyRendererSize();
  renderNow();

  // ---------------------------------------------------------------- the public object
  const viewer: Viewer = {
    async load(m: Manifest, glbUrl: string): Promise<void> {
      if (disposed) throw new Error("The viewer has been closed.");
      const token = ++loadToken;
      const gltf = await new GLTFLoader().loadAsync(glbUrl);
      if (disposed || token !== loadToken) {
        // Closed, or a newer load() started while this one was downloading: drop this model.
        gltf.scene.traverse((o) => {
          const mesh = o as THREE.Mesh;
          if (mesh.isMesh) {
            mesh.geometry.dispose();
            const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
            for (const mat of mats) mat?.dispose();
          }
        });
        return;
      }
      disposeModel();
      manifest = m;
      modelRoot = gltf.scene;
      world.add(modelRoot);
      scene.updateMatrixWorld(true);
      try {
        buildItems(modelRoot, m);
      } catch (err) {
        disposeModel();
        manifest = null;
        renderNow();
        throw err;
      }

      explode = 0;
      explodeMap = null;
      offsets = null;
      offsetClip = [];
      visibleKeys = null;
      highlighted = new Set();
      selected = null;
      for (const item of items) applyExplode(item);
      applyAllAppearance();
      contentChanged();

      const first = m.views.find((v) => v.group === "assembled") ?? m.views[0];
      const forward = (first && viewDirection(first.eye, first.target)) ?? viewDirection(DEFAULT_STATE.eye, DEFAULT_STATE.target)!;
      const up: Vec3 = first ? first.up : [0, 0, 1];
      cam = fitted(forward, up, mathSize()) ?? cloneState(DEFAULT_STATE);
      fittedAt = contentVersion;
      renderNow(); // on screen before the promise resolves
      requestRender(true);
    },

    setExplode(t: number): void {
      const next = clamp01(t);
      if (next === explode) return;
      explode = next;
      for (const item of items) applyExplode(item);
      contentChanged();
      requestRender(true);
    },

    setExplodeMap(map: Record<string, number> | null): void {
      explodeMap = map ? { ...map } : null;
      for (const item of items) applyExplode(item);
      contentChanged();
      requestRender(true);
    },

    setOffsets(map: Record<string, Vec3> | null): void {
      offsets = map ? { ...map } : null;
      offsetClip = [];
      if (offsets && manifest) {
        for (const part of manifest.parts) {
          if (Object.prototype.hasOwnProperty.call(offsets, part.key)) offsetClip.push(...boxCorners(part.bbox, offsets[part.key]));
        }
      }
      for (const item of items) applyExplode(item);
      contentChanged();
      requestRender(true);
    },

    setVisible(keys: string[] | null): void {
      visibleKeys = keys ? new Set(keys) : null;
      applyAllAppearance();
      contentChanged();
      requestRender(true);
    },

    setHighlighted(keys: string[]): void {
      highlighted = new Set(keys);
      applyAllAppearance();
      requestRender(false);
    },

    setSelected(key: string | null): void {
      if (key === selected) return;
      selected = key;
      applyAllAppearance();
      requestRender(false);
    },

    onSelect(cb: (key: string | null) => void): () => void {
      selectListeners.add(cb);
      return () => {
        selectListeners.delete(cb);
      };
    },

    showReference(on: boolean): void {
      if (on === referenceOn) return;
      referenceOn = on;
      applyAllAppearance();
      contentChanged();
      requestRender(true);
    },

    setView(view: View): void {
      const forward = viewDirection(view.eye, view.target);
      if (!forward) {
        console.warn(`viewer: view "${view.name}" has its eye on its target; ignored`);
        return;
      }
      const next = fitted(forward, view.up, mathSize());
      if (!next) return; // nothing loaded yet
      cam = next;
      fittedAt = contentVersion;
      requestRender(true);
    },

    fit(): void {
      const b = basisOf(cam);
      const next = fitted(b.forward, cam.up, mathSize());
      if (!next) return;
      cam = next;
      fittedAt = contentVersion;
      requestRender(true);
    },

    getCamera(): CameraState {
      return cloneState(cam);
    },

    setCamera(state: CameraState): void {
      if (!isValidState(state)) {
        console.warn("viewer: setCamera was given an unusable camera; ignored", state);
        return;
      }
      cam = cloneState(state);
      fittedAt = null;
      requestRender(true);
    },

    anchors(): BalloonAnchor[] {
      return anchorsFor(cam, mathSize());
    },

    onFrame(cb: () => void): () => void {
      frameListeners.add(cb);
      return () => {
        frameListeners.delete(cb);
      };
    },

    async capture(opts: { width: number; height: number; background?: string }): Promise<Capture> {
      if (disposed) throw new Error("The viewer has been closed.");
      const width = Math.round(opts.width);
      const height = Math.round(opts.height);
      if (!(width > 0) || !(height > 0)) throw new Error("capture needs a positive width and height.");
      const max = renderer.capabilities.maxTextureSize || 4096;
      if (width > max || height > max) throw new Error(`capture size ${width} x ${height} is larger than this device can render (${max}).`);

      const size: Size = { width, height };
      // A camera that was fitted (setView / fit) and not moved since is re-fitted for THIS picture's shape, so a
      // viewer in a hidden container still fills the image. A camera the user or setCamera placed is used as it is:
      // same eye, target and picture height; the width follows the requested shape.
      let state = cam;
      if (fittedAt === contentVersion) {
        const b = basisOf(cam);
        state = fitted(b.forward, cam.up, size) ?? cam;
      }

      const savedBackground = background.clone();
      const savedRatio = renderer.getPixelRatio();
      const savedSize = renderer.getSize(new THREE.Vector2());
      let dataUrl: string;
      try {
        if (opts.background) background.copy(colourOf(opts.background, `#${savedBackground.getHexString()}`));
        renderer.setPixelRatio(1);
        renderer.setSize(width, height, false);
        applyCamera(state, size);
        renderer.render(scene, camera);
        dataUrl = canvas.toDataURL("image/png"); // same task as the render: the drawing buffer is still there
      } finally {
        background.copy(savedBackground);
        renderer.setPixelRatio(savedRatio);
        renderer.setSize(savedSize.x, savedSize.y, false);
        renderNow(); // put the on-screen picture back straight away
      }
      return { dataUrl, anchors: anchorsFor(state, size) };
    },

    resize(): void {
      doResize();
    },

    dispose(): void {
      if (disposed) return;
      disposed = true;
      loadToken++;
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
      for (const fn of cleanups.splice(0)) fn();
      selectListeners.clear();
      frameListeners.clear();
      disposeModel();
      manifest = null;
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
    },
  };

  // For the folder's own browser harness only (not part of the Viewer interface; the app must not use it).
  Object.defineProperty(viewer, "__debug", {
    enumerable: false,
    value: () => ({ scene, camera, renderer, frame, items: items.map((i) => ({ key: i.part.key, node: i.node, meshes: i.meshes })) }),
  });

  return viewer;
};
