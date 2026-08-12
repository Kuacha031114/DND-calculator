import { useEffect, useMemo, useRef, useState } from "react";
import { AdvancedResults } from "../components/Results";
import { defaultEntry, defaultTarget, id } from "../config";
import type { AdvancedResult, AppConfig, BridgeMethods, EntryConfig, TargetConfig } from "../types";
import { EntryEditor, RerollPanel, RiderPanel, TargetEditor, WorkspaceNavigator } from "./advanced/WorkspaceParts";

export function AdvancedWorkspace({ config, onChange, bridge, ready }: {
  config: AppConfig; onChange(config: AppConfig): void; bridge: BridgeMethods; ready: boolean;
}) {
  const [targetIndex, setTargetIndex] = useState(0);
  const [entryIndex, setEntryIndex] = useState(0);
  const [result, setResult] = useState<AdvancedResult | null>(null);
  const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [riderSelections, setRiderSelections] = useState<Record<string, string[]>>({});
  const [rerolls, setRerolls] = useState<Set<string>>(new Set());
  const mountedRef = useRef(true);
  const sessionRef = useRef<string | null>(null);
  const startRequestRef = useRef(0);
  const target = config.targets[Math.min(targetIndex, config.targets.length - 1)];
  const entry = config.entries[Math.min(entryIndex, config.entries.length - 1)];

  useEffect(() => { if (targetIndex >= config.targets.length) setTargetIndex(0); }, [config.targets.length, targetIndex]);
  useEffect(() => { if (entryIndex >= config.entries.length) setEntryIndex(0); }, [config.entries.length, entryIndex]);
  useEffect(() => () => {
    mountedRef.current = false;
    startRequestRef.current += 1;
    const sessionId = sessionRef.current;
    sessionRef.current = null;
    if (sessionId) void bridge.disposeSession(sessionId).catch(() => undefined);
  }, [bridge]);

  function commit(next: AppConfig) {
    onChange(next);
    if (result) setStale(true);
  }
  function patchTarget(patch: Partial<TargetConfig>) {
    const targets = config.targets.map((item, index) => index === targetIndex ? { ...item, ...patch } : item);
    commit({ ...config, targets });
  }
  function patchEntry(patch: Partial<EntryConfig>) {
    const entries = config.entries.map((item, index) => index === entryIndex ? { ...item, ...patch } : item);
    commit({ ...config, entries });
  }
  function addTarget() {
    const next = defaultTarget(config.targets.length + 1);
    commit({ ...config, targets: [...config.targets, next] }); setTargetIndex(config.targets.length);
  }
  function duplicateTarget() {
    const next = { ...structuredClone(target), id: id("target"), name: `${target.name} 副本` };
    commit({ ...config, targets: [...config.targets, next] }); setTargetIndex(config.targets.length);
  }
  function deleteTarget() {
    if (config.targets.length === 1) return setError("至少保留一个目标");
    const targets = config.targets.filter((_, index) => index !== targetIndex);
    const entries = config.entries.map((item) => item.target_id === target.id ? { ...item, target_id: targets[0].id } : item);
    commit({ ...config, targets, entries }); setTargetIndex(0);
  }
  function addEntry() {
    const next = defaultEntry(config.entries.length + 1); next.target_id = config.targets[0].id;
    commit({ ...config, entries: [...config.entries, next] }); setEntryIndex(config.entries.length);
  }
  function duplicateEntry() {
    const next = { ...structuredClone(entry), id: id("entry"), name: `${entry.name} 副本` };
    commit({ ...config, entries: [...config.entries, next] }); setEntryIndex(config.entries.length);
  }
  function deleteEntry() {
    if (config.entries.length === 1) return setError("至少保留一个结算条目");
    commit({ ...config, entries: config.entries.filter((_, index) => index !== entryIndex) }); setEntryIndex(0);
  }
  function moveEntry(offset: number) {
    const nextIndex = Math.max(0, Math.min(config.entries.length - 1, entryIndex + offset));
    if (nextIndex === entryIndex) return;
    const entries = [...config.entries]; [entries[entryIndex], entries[nextIndex]] = [entries[nextIndex], entries[entryIndex]];
    commit({ ...config, entries }); setEntryIndex(nextIndex);
  }
  function savePreset() {
    const name = window.prompt("自定义预设名称"); if (!name?.trim()) return;
    const { id: _id, name: _name, target_id: _target, preset: _preset, ...values } = entry;
    commit({ ...config, custom_presets: { ...config.custom_presets, [name.trim()]: values } });
  }
  function loadPreset(name: string) {
    const values = config.custom_presets[name]; if (!values) return;
    patchEntry({ ...values, preset: "无" });
  }
  function deletePreset(name: string) {
    const custom_presets = { ...config.custom_presets }; delete custom_presets[name];
    commit({ ...config, custom_presets });
  }

  async function startResolution() {
    const requestId = ++startRequestRef.current;
    try {
      setBusy(true); setError("");
      const previousSessionId = sessionRef.current;
      sessionRef.current = null;
      if (previousSessionId) await bridge.disposeSession(previousSessionId).catch(() => undefined);
      const next = await bridge.startAdvanced(config);
      if (!mountedRef.current || requestId !== startRequestRef.current) {
        await bridge.disposeSession(next.session_id).catch(() => undefined);
        return;
      }
      sessionRef.current = next.session_id;
      setResult(next); setStale(false); setRiderSelections({}); setRerolls(new Set());
    } catch (caught) {
      if (mountedRef.current && requestId === startRequestRef.current) {
        setError(caught instanceof Error ? caught.message : String(caught));
      }
    } finally {
      if (mountedRef.current && requestId === startRequestRef.current) setBusy(false);
    }
  }
  async function resolveDamage() {
    if (!result || stale) return setError("输入已经改变，请重新投掷检定");
    try { setBusy(true); setError(""); setResult(await bridge.resolveAttackDamage(result.session_id, riderSelections)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
  }
  async function rerollSelected() {
    if (!result || stale || rerolls.size === 0) return;
    const references = [...rerolls].map((value) => JSON.parse(value) as [string, string, number]);
    try { setBusy(true); setError(""); setResult(await bridge.reroll(result.session_id, references)); setRerolls(new Set()); }
    catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
  }
  function toggleRider(componentId: string, attackId: string, checked: boolean, once: boolean) {
    setRiderSelections((current) => ({
      ...current,
      [componentId]: checked
        ? once ? [attackId] : [...new Set([...(current[componentId] ?? []), attackId])]
        : (current[componentId] ?? []).filter((idValue) => idValue !== attackId),
    }));
  }
  const diceReferences = useMemo(() => result?.sessions.flatMap((session) => session.damage_results.flatMap((damage) =>
    damage.components.flatMap((component) => component.dice.map((die, index) => ({
      key: JSON.stringify([damage.source_id, component.component_id, index]),
      label: `${component.name} d${die.sides}：${die.rerolled ? `${die.original}→` : ""}${die.value}`,
    })))
  )) ?? [], [result]);

  return <main className="page advanced-page">
    <div className="advanced-heading"><div><span className="eyebrow">完整规则工作台</span><h1>目标、攻击与法术</h1></div>
      <button className="primary" disabled={!ready || busy} onClick={startResolution}>{busy ? "处理中…" : "① 投掷检定"}</button></div>
    {error && <div className="error" role="alert">{error}</div>}{stale && <div className="warning">输入已经改变，旧结果已过期。</div>}
    <div className="advanced-grid">
      <WorkspaceNavigator config={config} targetIndex={targetIndex} entryIndex={entryIndex} actions={{ selectTarget: setTargetIndex, addTarget, duplicateTarget, deleteTarget, selectEntry: setEntryIndex, addEntry, duplicateEntry, deleteEntry, moveEntry }} />
      <section className="editor-column">
        <TargetEditor target={target} patch={patchTarget} />
        <EntryEditor entry={entry} targets={config.targets} customPresets={config.custom_presets} patch={patchEntry} savePreset={savePreset} loadPreset={loadPreset} deletePreset={deletePreset} />
      </section>
    </div>
    {result && <RiderPanel result={result} selections={riderSelections} stale={stale} busy={busy} toggle={toggleRider} resolve={resolveDamage} />}
    {result && <AdvancedResults result={result} />}
    <RerollPanel references={diceReferences} selected={rerolls} stale={stale} busy={busy} toggle={(key, checked) => setRerolls((current) => { const next = new Set(current); if (checked) next.add(key); else next.delete(key); return next; })} reroll={rerollSelected} />
  </main>;
}
