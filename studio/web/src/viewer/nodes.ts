// Which node of a loaded model is which manifest item. Pure: no three.js, so it is tested in maths.test.ts.
//
// The GLB (CONTRACT.md) has a root node `model` whose DIRECT children are the items, each named by its key, and each
// with a mesh child called `COMPOUND` or similar. Looking a key up by name anywhere in the file is therefore wrong:
// an item keyed `model` or `COMPOUND` (the manifest allows both) would resolve to the root or to another item's
// mesh. The loader also renames a later duplicate (`model` -> `model_1`) and keeps the file's own name in
// `userData.name`, so that is the name compared.

/** The part of a scene node this needs (a three.js Object3D fits). */
export interface NodeLike<T> {
  name: string;
  userData: Record<string, unknown>;
  children: T[];
}

/** The name the file gave a node: the loader's `userData.name` when present, else the node's (possibly altered) name. */
function matches<T extends NodeLike<T>>(node: T, key: string, sanitised: string): boolean {
  const original = node.userData?.name;
  if (typeof original === "string") return original === key || original === sanitised;
  return node.name === key || node.name === sanitised;
}

/**
 * The item node for each key: the keys are looked up among the direct children of ONE node, the one whose children
 * match the most keys (the shallowest such node on a tie). Keys with no node are simply absent from the result.
 * `sanitise` is the loader's own name clean-up (spaces to underscores and so on), for files without `userData.name`.
 */
export function findItemNodes<T extends NodeLike<T>>(root: T, keys: readonly string[], sanitise: (name: string) => string = (s) => s): Map<string, T> {
  const wanted = keys.map((key) => ({ key, sanitised: sanitise(key) }));
  let best = new Map<string, T>();
  let level: T[] = [root];
  while (level.length > 0) {
    const next: T[] = [];
    for (const parent of level) {
      const found = new Map<string, T>();
      for (const child of parent.children) {
        for (const w of wanted) {
          if (!found.has(w.key) && matches(child, w.key, w.sanitised)) {
            found.set(w.key, child);
            break; // one node is one item
          }
        }
        next.push(child);
      }
      if (found.size > best.size) best = found;
    }
    level = next;
  }
  return best;
}
