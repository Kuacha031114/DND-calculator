import { cp, mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(here, "..");
const pyodideSource = join(webRoot, "node_modules", "pyodide");
const pyodideTarget = join(webRoot, "public", "pyodide");
const wheelSource = resolve(webRoot, "..", "dist-web");
const wheelTarget = join(webRoot, "public", "python");

await mkdir(pyodideTarget, { recursive: true });
await mkdir(wheelTarget, { recursive: true });

const runtimeExtensions = [".js", ".mjs", ".wasm", ".zip", ".json"];
for (const name of await readdir(pyodideSource)) {
  if (runtimeExtensions.some((extension) => name.endsWith(extension))) {
    await cp(join(pyodideSource, name), join(pyodideTarget, name));
  }
}

const wheels = (await readdir(wheelSource)).filter((name) => name.endsWith(".whl"));
if (wheels.length !== 1) {
  throw new Error(`dist-web 中应有且仅有一个 wheel，实际为 ${wheels.length} 个`);
}
await cp(join(wheelSource, wheels[0]), join(wheelTarget, wheels[0]));
await writeFile(
  join(wheelTarget, "wheel.json"),
  JSON.stringify({ file: wheels[0] }, null, 2) + "\n",
  "utf8",
);

const packageJson = JSON.parse(await readFile(join(webRoot, "package.json"), "utf8"));
console.log(`Prepared Pyodide ${packageJson.dependencies.pyodide} and ${wheels[0]}`);
