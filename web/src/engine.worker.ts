/// <reference lib="webworker" />

type RequestMessage = { id: number; method: string; payload: Record<string, unknown> };
type BridgeEnvelope = { ok: boolean; data?: unknown; error?: { message: string } };
type PyodideInterface = {
  loadPackage(name: string): Promise<void>;
  runPythonAsync(code: string): Promise<unknown>;
  globals: { set(name: string, value: unknown): void };
};
type PyodideModule = { loadPyodide(options: { indexURL: string }): Promise<PyodideInterface> };

let pyodide: PyodideInterface | null = null;
let initialization: Promise<void> | null = null;

async function initialize(): Promise<void> {
  if (pyodide) return;
  if (initialization) return initialization;
  initialization = (async () => {
    const base = import.meta.env.BASE_URL;
    const moduleUrl = `${self.location.origin}${base}pyodide/pyodide.mjs`;
    const pyodideModule = await import(/* @vite-ignore */ moduleUrl) as PyodideModule;
    pyodide = await pyodideModule.loadPyodide({ indexURL: `${self.location.origin}${base}pyodide/` });
    const manifest = await fetch(`${base}python/wheel.json`).then((response) => {
      if (!response.ok) throw new Error("无法读取 Python 规则包清单");
      return response.json() as Promise<{ file: string }>;
    });
    await pyodide.loadPackage(`${self.location.origin}${base}python/${manifest.file}`);
    await pyodide.runPythonAsync("from dnd_calculator.web_bridge import dispatch_json");
  })();
  try {
    await initialization;
  } catch (error) {
    initialization = null;
    pyodide = null;
    throw error;
  }
}

async function dispatch(method: string, payload: Record<string, unknown>): Promise<unknown> {
  await initialize();
  if (!pyodide) throw new Error("Python 规则引擎尚未就绪");
  pyodide.globals.set("_web_method", method);
  pyodide.globals.set("_web_payload", JSON.stringify(payload));
  const raw = await pyodide.runPythonAsync("dispatch_json(_web_method, _web_payload)");
  const envelope = JSON.parse(String(raw)) as BridgeEnvelope;
  if (!envelope.ok) throw new Error(envelope.error?.message || "规则引擎返回未知错误");
  return envelope.data;
}

self.onmessage = async (event: MessageEvent<RequestMessage>) => {
  const { id, method, payload } = event.data;
  try {
    const data = await dispatch(method, payload);
    self.postMessage({ id, ok: true, data });
  } catch (error) {
    self.postMessage({
      id,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};

export {};
