// The project has no @types/node (and adds no packages). render.test.ts reads one file with Node's fs when run by
// vitest; this declares just the two functions it uses. Delete this file if @types/node is ever added.
declare module "node:fs" {
  export function existsSync(path: string | URL): boolean;
  export function readFileSync(path: string | URL, encoding: "utf-8"): string;
}
