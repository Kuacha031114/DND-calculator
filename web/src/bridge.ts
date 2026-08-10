import type { AdvancedResult, AppConfig, BridgeMethods, QuickSummary } from "./types";

type Pending = { resolve(value: unknown): void; reject(reason: Error): void };

export class EngineBridge implements BridgeMethods {
  private readonly worker: Worker;
  private readonly pending = new Map<number, Pending>();
  private sequence = 0;

  constructor(worker = new Worker(new URL("./engine.worker.ts", import.meta.url), { type: "module" })) {
    this.worker = worker;
    this.worker.onmessage = (event: MessageEvent<{ id: number; ok: boolean; data?: unknown; error?: string }>) => {
      const current = this.pending.get(event.data.id);
      if (!current) return;
      this.pending.delete(event.data.id);
      if (event.data.ok) current.resolve(event.data.data);
      else current.reject(new Error(event.data.error || "规则引擎调用失败"));
    };
    this.worker.onerror = (event) => {
      const error = new Error(event.message || "规则引擎 Worker 加载失败");
      for (const current of this.pending.values()) current.reject(error);
      this.pending.clear();
    };
  }

  private call<T>(method: string, payload: Record<string, unknown> = {}): Promise<T> {
    const id = ++this.sequence;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (value: unknown) => void, reject });
      this.worker.postMessage({ id, method, payload });
    });
  }

  init() { return this.call<{ version: string; config_version: number; methods: string[] }>("init"); }
  resolveQuick(payload: Record<string, unknown>) { return this.call<QuickSummary>("resolveQuick", payload); }
  startAdvanced(payload: AppConfig) { return this.call<AdvancedResult>("startAdvanced", payload); }
  resolveAttackDamage(sessionId: string, selections: Record<string, string[]>) {
    return this.call<AdvancedResult>("resolveAttackDamage", { session_id: sessionId, selections });
  }
  reroll(sessionId: string, references: Array<[string, string, number]>) {
    return this.call<AdvancedResult>("reroll", { session_id: sessionId, references });
  }
  disposeSession(sessionId: string) {
    return this.call<{ disposed: boolean }>("disposeSession", { session_id: sessionId });
  }
  terminate() { this.worker.terminate(); }
}
