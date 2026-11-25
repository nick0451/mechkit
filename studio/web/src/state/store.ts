// The app's one small store: plain object + listeners, read from React with useSyncExternalStore.
// Components subscribe to the slice they need (useStore(selector)), so a slider drag does not re-render the tree.
import { useSyncExternalStore } from "react";
import { fetchManifest, fetchProjects } from "../api/client";
import type { Manifest, ProjectInfo } from "../types";
import type { Viewer } from "../viewer/api";
import { clamp01, describeManifestError, describeProjectsError, parseChoice, pickDefault, type Problem } from "./logic";

export type Tab = "assembly" | "parts" | "guide";
export type Status = "idle" | "loading" | "ready" | "error";

export interface AppState {
  projects: ProjectInfo[];
  projectsStatus: Status;
  projectsProblem: Problem | null;

  projectId: string | null;
  version: string | null;

  manifest: Manifest | null;
  manifestStatus: Status;
  manifestProblem: Problem | null;

  /** True while the on-screen viewer has this manifest's model loaded (the sheet print needs its camera). */
  modelReady: boolean;

  selectedKey: string | null;
  /** 0 (assembled) .. 1 (fully apart). */
  explode: number;
  balloons: boolean;
  /** Context (reference) parts shown. */
  context: boolean;
  tab: Tab;
}

const initial: AppState = {
  projects: [],
  projectsStatus: "idle",
  projectsProblem: null,
  projectId: null,
  version: null,
  manifest: null,
  manifestStatus: "idle",
  manifestProblem: null,
  modelReady: false,
  selectedKey: null,
  explode: 0,
  balloons: true,
  context: true,
  tab: "assembly",
};

let state: AppState = initial;
const listeners = new Set<() => void>();

export function getState(): AppState {
  return state;
}

function set(patch: Partial<AppState>): void {
  let changed = false;
  for (const k of Object.keys(patch) as (keyof AppState)[]) {
    if (!Object.is(state[k], patch[k])) {
      changed = true;
      break;
    }
  }
  if (!changed) return;
  state = { ...state, ...patch };
  for (const l of [...listeners]) l();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

/** Selectors must return a value that is stable while the state is unchanged (a field, or a primitive). */
export function useStore<T>(selector: (s: AppState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(state),
    () => selector(state),
  );
}

// ---- remembering the last project -------------------------------------------------------------------------------

const STORAGE_KEY = "mechkit-studio.last";

function recall() {
  try {
    return parseChoice(window.localStorage.getItem(STORAGE_KEY));
  } catch {
    return null; // storage blocked: just start from the default
  }
}

function remember(projectId: string, version: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ projectId, version }));
  } catch {
    // storage blocked: nothing to do
  }
}

// ---- the on-screen viewer (not state: components that need it take it from here at click time) -------------------

let activeViewer: Viewer | null = null;
let activeElement: HTMLElement | null = null;

/** `element` is the one the viewer draws in: its shape is the shape of the on-screen picture. */
export function setActiveViewer(v: Viewer | null, element: HTMLElement | null = null): void {
  activeViewer = v;
  activeElement = v ? element : null;
  set({ modelReady: v !== null });
}

/** Clears the active viewer only if it is still `v` (a newer one may already have taken its place). */
export function clearActiveViewer(v: Viewer): void {
  if (activeViewer === v) setActiveViewer(null);
}

export function getActiveViewer(): Viewer | null {
  return activeViewer;
}

/** Width / height of the on-screen 3D picture; 0 when there is none (or it has no size). */
export function getActiveViewAspect(): number {
  const w = activeElement?.clientWidth ?? 0;
  const h = activeElement?.clientHeight ?? 0;
  return w > 0 && h > 0 ? w / h : 0;
}

// ---- actions ----------------------------------------------------------------------------------------------------

let projectsRun = 0;
let manifestRun = 0;

async function loadProjects(): Promise<void> {
  const run = ++projectsRun;
  set({ projectsStatus: "loading", projectsProblem: null });
  try {
    const { projects } = await fetchProjects();
    if (run !== projectsRun) return;
    set({ projects, projectsStatus: "ready" });
    const choice = pickDefault(projects, state.projectId && state.version ? { projectId: state.projectId, version: state.version } : recall());
    if (choice) void openProject(choice.projectId, choice.version);
    else set({ projectId: null, version: null, manifest: null, manifestStatus: "idle", manifestProblem: null });
  } catch (e) {
    if (run !== projectsRun) return;
    set({ projectsStatus: "error", projectsProblem: describeProjectsError(e) });
  }
}

async function openProject(projectId: string, version: string): Promise<void> {
  const run = ++manifestRun;
  const sameModel = state.projectId === projectId && state.version === version && state.manifest !== null;
  set({
    projectId,
    version,
    manifestStatus: "loading",
    manifestProblem: null,
    // A different model: nothing from the old one applies.
    ...(sameModel ? {} : { manifest: null, selectedKey: null, explode: 0 }),
  });
  const name = state.projects.find((p) => p.id === projectId)?.name ?? projectId;
  try {
    const manifest = await fetchManifest(projectId, version);
    if (run !== manifestRun) return;
    const keep = state.selectedKey !== null && manifest.parts.some((p) => p.key === state.selectedKey);
    set({ manifest, manifestStatus: "ready", selectedKey: keep ? state.selectedKey : null });
    remember(projectId, version);
  } catch (e) {
    if (run !== manifestRun) return;
    set({ manifest: null, manifestStatus: "error", manifestProblem: describeManifestError(e, name, version), selectedKey: null });
  }
}

export const actions = {
  /** Fetch the project list and open the remembered (or first) project. Safe to call twice. */
  init: loadProjects,
  retryProjects: loadProjects,

  /** Switch project: opens its newest version. */
  chooseProject(projectId: string): void {
    const p = state.projects.find((x) => x.id === projectId);
    if (!p || p.versions.length === 0) return;
    void openProject(p.id, p.versions[0]);
  },

  chooseVersion(version: string): void {
    if (state.projectId) void openProject(state.projectId, version);
  },

  retryManifest(): void {
    if (state.projectId && state.version) void openProject(state.projectId, state.version);
  },

  select(key: string | null): void {
    set({ selectedKey: key });
  },

  setExplode(t: number): void {
    set({ explode: clamp01(t) });
  },

  setBalloons(on: boolean): void {
    set({ balloons: on });
  },

  setContext(on: boolean): void {
    set({ context: on });
  },

  setTab(tab: Tab): void {
    set({ tab });
  },
};
