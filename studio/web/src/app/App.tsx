// MechKit Studio: the whole screen. Header (project, version, print), assembly tree, and the three tabs.
import { useEffect, useMemo } from "react";
import { glbUrl } from "../api/client";
import type { Problem } from "../state/logic";
import { actions, useStore, type Tab } from "../state/store";
import { GuideTab } from "./GuideTab";
import { PartsTab } from "./PartsTab";
import { PrintButtons } from "./PrintButtons";
import { Tree } from "./Tree";
import { Viewport } from "./Viewport";
import "./app.css";

const TABS: { id: Tab; name: string }[] = [
  { id: "assembly", name: "Assembly" },
  { id: "parts", name: "Parts" },
  { id: "guide", name: "Guide" },
];

function ProblemPanel({ problem, onRetry }: { problem: Problem; onRetry: () => void }) {
  return (
    <div className="message problem" role="alert">
      <h2>{problem.title}</h2>
      <p>{problem.hint}</p>
      {problem.detail && <p className="detail">Details: {problem.detail}</p>}
      <button type="button" className="btn primary" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export default function App() {
  const projects = useStore((s) => s.projects);
  const projectsStatus = useStore((s) => s.projectsStatus);
  const projectsProblem = useStore((s) => s.projectsProblem);
  const projectId = useStore((s) => s.projectId);
  const version = useStore((s) => s.version);
  const manifest = useStore((s) => s.manifest);
  const manifestStatus = useStore((s) => s.manifestStatus);
  const manifestProblem = useStore((s) => s.manifestProblem);
  const tab = useStore((s) => s.tab);

  useEffect(() => {
    void actions.init();
  }, []);

  const project = projects.find((p) => p.id === projectId);
  const modelUrl = useMemo(() => (projectId && version ? glbUrl(projectId, version) : ""), [projectId, version]);

  useEffect(() => {
    document.title = manifest ? `${manifest.project} ${manifest.version} - MechKit Studio` : "MechKit Studio";
  }, [manifest]);

  let body;
  if (projectsStatus === "error" && projectsProblem) {
    body = <ProblemPanel problem={projectsProblem} onRetry={() => void actions.retryProjects()} />;
  } else if (projectsStatus !== "ready") {
    body = (
      <div className="message" role="status">
        Looking for projects...
      </div>
    );
  } else if (projects.every((p) => p.versions.length === 0)) {
    body = (
      <div className="message">
        <h2>No projects to show yet</h2>
        <p>
          A project appears here once it has a presentation: a file exports/&lt;version&gt;/presentation/manifest.json in a folder
          beside the mechkit folder.
        </p>
        <p>Make one from the mechkit folder with: uv run python -m mechkit present "&lt;project folder&gt;"</p>
        <button type="button" className="btn primary" onClick={() => void actions.retryProjects()}>
          Look again
        </button>
      </div>
    );
  } else if (manifestStatus === "error" && manifestProblem) {
    body = <ProblemPanel problem={manifestProblem} onRetry={actions.retryManifest} />;
  } else if (!manifest || !projectId || !version) {
    body = (
      <div className="message" role="status">
        Loading {project?.name ?? "project"}...
      </div>
    );
  } else {
    body = (
      <div className="workspace">
        <Tree manifest={manifest} />
        <div className="main">
          <div className="tabs" role="tablist" aria-label="Sections">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                id={`tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls={`panel-${t.id}`}
                className="tab"
                onClick={() => actions.setTab(t.id)}
              >
                {t.name}
                {t.id === "parts" && <span className="tab-count">{manifest.table.length}</span>}
                {t.id === "guide" && manifest.steps.length > 0 && <span className="tab-count">{manifest.steps.length}</span>}
              </button>
            ))}
          </div>
          <div className="panels">
            {/* The 3D pane stays mounted under the other tabs: the viewer keeps its camera, and the sheet print needs it. */}
            <div
              id="panel-assembly"
              role="tabpanel"
              aria-labelledby="tab-assembly"
              className={tab === "assembly" ? "panel panel-assembly" : "panel panel-assembly covered"}
            >
              <Viewport manifest={manifest} glbUrl={modelUrl} />
            </div>
            {tab === "parts" && (
              <div id="panel-parts" role="tabpanel" aria-labelledby="tab-parts" className="panel panel-over">
                <PartsTab manifest={manifest} />
              </div>
            )}
            {tab === "guide" && (
              <div id="panel-guide" role="tabpanel" aria-labelledby="tab-guide" className="panel panel-over">
                <GuideTab manifest={manifest} />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="brand">MechKit Studio</h1>
        {projects.length > 0 && (
          <div className="pickers">
            <label>
              <span>Project</span>
              <select value={projectId ?? ""} onChange={(e) => actions.chooseProject(e.target.value)}>
                {projects.map((p) => (
                  <option key={p.id} value={p.id} disabled={p.versions.length === 0}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Version</span>
              <select value={version ?? ""} onChange={(e) => actions.chooseVersion(e.target.value)} disabled={!project}>
                {(project?.versions ?? []).map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
        <div className="spacer" />
        {manifest && projectId && version && <PrintButtons manifest={manifest} projectId={projectId} version={version} />}
      </header>
      {body}
    </div>
  );
}
