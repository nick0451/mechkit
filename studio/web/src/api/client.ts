// Talks to the MechKit Studio backend (see ../../../CONTRACT.md, "Backend API"). Same origin: no host in the URLs.
import type { Manifest, ProjectList } from "../types";

const enc = encodeURIComponent;

/** Why a request failed, in a form the screen can explain. */
export class ApiError extends Error {
  /** "network": no answer at all (server not running). "http": the server answered with an error. "format": not the JSON we expect. */
  readonly kind: "network" | "http" | "format";
  readonly status: number;

  constructor(kind: "network" | "http" | "format", message: string, status = 0) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

export function glbUrl(projectId: string, version: string): string {
  return `/api/projects/${enc(projectId)}/${enc(version)}/model.glb`;
}

async function getJson(url: string, signal?: AbortSignal): Promise<unknown> {
  let r: Response;
  try {
    r = await fetch(url, { signal, headers: { Accept: "application/json" } });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError("network", "The server did not answer.");
  }
  if (!r.ok) {
    let detail = "";
    try {
      const body: unknown = await r.json();
      if (body && typeof body === "object" && "detail" in body) detail = String((body as { detail: unknown }).detail);
    } catch {
      // not JSON: keep the status only
    }
    throw new ApiError("http", detail || `The server answered with error ${r.status}.`, r.status);
  }
  try {
    return await r.json();
  } catch {
    throw new ApiError("format", "The server's answer was not JSON.", r.status);
  }
}

export async function fetchProjects(signal?: AbortSignal): Promise<ProjectList> {
  const data = await getJson("/api/projects", signal);
  const list = (data as Partial<ProjectList> | null)?.projects;
  if (!Array.isArray(list)) throw new ApiError("format", "The project list has an unexpected shape.");
  return {
    projects: list
      .filter((p) => p && typeof p.id === "string" && Array.isArray(p.versions))
      .map((p) => ({ id: p.id, name: typeof p.name === "string" && p.name ? p.name : p.id, versions: p.versions })),
  };
}

export async function fetchManifest(projectId: string, version: string, signal?: AbortSignal): Promise<Manifest> {
  const data = await getJson(`/api/projects/${enc(projectId)}/${enc(version)}/manifest`, signal);
  const m = data as Partial<Manifest> | null;
  if (!m || typeof m !== "object" || !Array.isArray(m.parts)) {
    throw new ApiError("format", "The manifest has an unexpected shape (no parts list).");
  }
  // Older manifests may lack the optional lists: the app treats them as empty.
  return { ...(m as Manifest), views: m.views ?? [], table: m.table ?? [], steps: m.steps ?? [] };
}
