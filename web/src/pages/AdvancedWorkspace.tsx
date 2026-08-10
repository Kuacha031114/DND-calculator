import { useEffect, useMemo, useState } from "react";
import { AdvancedResults } from "../components/Results";
import { Check, Field, SelectInput, TextInput } from "../components/Field";
import { ABILITIES, DAMAGE_TYPES, defaultEntry, defaultTarget, id } from "../config";
import type { AdvancedResult, AppConfig, BridgeMethods, EntryConfig, TargetConfig } from "../types";

const modeLabels = { attack: "攻击检定", save: "豁免检定", auto: "自动伤害" } as const;
const builtInPresets = ["无", "神射手 -5/+10", "巨武器大师 -5/+10", "重武器战斗风格", "祝福术 +1d4", "灾祸术 -1d4", "精灵精准", "半身人幸运", "咒剑诅咒 19–20", "勇士精通重击 19–20", "勇士卓越重击 18–20"];

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
  const target = config.targets[Math.min(targetIndex, config.targets.length - 1)];
  const entry = config.entries[Math.min(entryIndex, config.entries.length - 1)];

  useEffect(() => { if (targetIndex >= config.targets.length) setTargetIndex(0); }, [config.targets.length, targetIndex]);
  useEffect(() => { if (entryIndex >= config.entries.length) setEntryIndex(0); }, [config.entries.length, entryIndex]);

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
    try {
      setBusy(true); setError("");
      if (result) await bridge.disposeSession(result.session_id).catch(() => undefined);
      const next = await bridge.startAdvanced(config);
      setResult(next); setStale(false); setRiderSelections({}); setRerolls(new Set());
    } catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); }
    finally { setBusy(false); }
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
      <aside className="panel navigator"><h2>目标</h2><div className="item-list">{config.targets.map((item, index) => <button className={index === targetIndex ? "selected" : ""} onClick={() => setTargetIndex(index)} key={item.id}><strong>{item.name}</strong><span>AC {item.ac}</span></button>)}</div>
        <div className="mini-actions"><button onClick={addTarget}>新增</button><button onClick={duplicateTarget}>复制</button><button onClick={deleteTarget}>删除</button></div>
        <hr/><h2>结算条目</h2><div className="item-list">{config.entries.map((item, index) => <button className={index === entryIndex ? "selected" : ""} onClick={() => setEntryIndex(index)} key={item.id}><strong>{item.name}</strong><span>{modeLabels[item.mode]}</span></button>)}</div>
        <div className="mini-actions"><button onClick={addEntry}>新增</button><button onClick={duplicateEntry}>复制</button><button onClick={deleteEntry}>删除</button><button onClick={() => moveEntry(-1)}>↑</button><button onClick={() => moveEntry(1)}>↓</button></div>
      </aside>
      <section className="editor-column">
        <details className="panel editor" open><summary>目标防御 · {target.name}</summary>
          <div className="form-grid"><Field label="目标名称"><TextInput value={target.name} onChange={(event) => patchTarget({ name: event.target.value })}/></Field><Field label="AC"><TextInput inputMode="numeric" value={target.ac} onChange={(event) => patchTarget({ ac: event.target.value })}/></Field></div>
          <h3>豁免加值</h3><div className="ability-grid">{ABILITIES.map((ability) => <Field label={ability} key={ability}><TextInput inputMode="numeric" value={target.saves[ability]} onChange={(event) => patchTarget({ saves: { ...target.saves, [ability]: event.target.value } })}/></Field>)}</div>
          <div className="form-grid"><Field label="抗性" hint="用逗号分隔伤害类型"><TextInput value={target.resistances} onChange={(event) => patchTarget({ resistances: event.target.value })}/></Field><Field label="易伤"><TextInput value={target.vulnerabilities} onChange={(event) => patchTarget({ vulnerabilities: event.target.value })}/></Field><Field label="免疫"><TextInput value={target.immunities} onChange={(event) => patchTarget({ immunities: event.target.value })}/></Field><Field label="非魔法抗性"><TextInput value={target.nonmagical_resistances} onChange={(event) => patchTarget({ nonmagical_resistances: event.target.value })}/></Field><Field label="固定减伤"><TextInput inputMode="numeric" value={target.fixed_reduction} onChange={(event) => patchTarget({ fixed_reduction: event.target.value })}/></Field><Check label="重击免疫" checked={target.crit_immune} onChange={(event) => patchTarget({ crit_immune: event.target.checked })}/></div>
        </details>
        <details className="panel editor" open><summary>编辑条目 · {entry.name}</summary>
          <div className="form-grid"><Field label="条目名称"><TextInput value={entry.name} onChange={(event) => patchEntry({ name: event.target.value })}/></Field><Field label="结算方式"><SelectInput value={entry.mode} onChange={(event) => patchEntry({ mode: event.target.value as EntryConfig["mode"] })}><option value="attack">攻击检定</option><option value="save">豁免检定</option><option value="auto">自动伤害</option></SelectInput></Field><Field label="目标"><SelectInput value={entry.target_id} onChange={(event) => patchEntry({ target_id: event.target.value })}>{config.targets.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</SelectInput></Field>{entry.mode !== "attack" && <Check label="应用到全部目标" checked={entry.all_targets} onChange={(event) => patchEntry({ all_targets: event.target.checked })}/>}</div>
          {entry.mode === "attack" && <><h3>攻击规则</h3><div className="form-grid"><Field label="攻击次数"><TextInput inputMode="numeric" value={entry.count} onChange={(event) => patchEntry({ count: event.target.value })}/></Field><Field label="命中加值"><TextInput inputMode="numeric" value={entry.attack_bonus} onChange={(event) => patchEntry({ attack_bonus: event.target.value })}/></Field><Field label="优势来源数"><TextInput inputMode="numeric" value={entry.advantage} onChange={(event) => patchEntry({ advantage: event.target.value })}/></Field><Field label="劣势来源数"><TextInput inputMode="numeric" value={entry.disadvantage} onChange={(event) => patchEntry({ disadvantage: event.target.value })}/></Field><Field label="重击下限"><TextInput inputMode="numeric" value={entry.crit_range} onChange={(event) => patchEntry({ crit_range: event.target.value })}/></Field><Field label="减 5 加 10 序号"><TextInput value={entry.power_indices} onChange={(event) => patchEntry({ power_indices: event.target.value })}/></Field></div>
            <div className="check-grid"><Check label="AC 未知，手动指定命中" checked={entry.manual_hits} onChange={(event) => patchEntry({ manual_hits: event.target.checked })}/><Check label="全部攻击减 5 加 10" checked={entry.power_attack} onChange={(event) => patchEntry({ power_attack: event.target.checked })}/><Check label="精灵精准" checked={entry.elven_accuracy} onChange={(event) => patchEntry({ elven_accuracy: event.target.checked })}/><Check label="半身人幸运" checked={entry.halfling_lucky} onChange={(event) => patchEntry({ halfling_lucky: event.target.checked })}/><Check label="祝福术" checked={entry.bless} onChange={(event) => patchEntry({ bless: event.target.checked })}/><Check label="灾祸术" checked={entry.bane} onChange={(event) => patchEntry({ bane: event.target.checked })}/></div>
            {entry.manual_hits && <div className="form-grid"><Field label="命中次数"><TextInput inputMode="numeric" value={entry.manual_hit_count} onChange={(event) => patchEntry({ manual_hit_count: event.target.value })}/></Field><Field label="其中重击"><TextInput inputMode="numeric" value={entry.manual_critical_count} onChange={(event) => patchEntry({ manual_critical_count: event.target.value })}/></Field></div>}</>}
          {entry.mode === "save" && <><h3>豁免规则</h3><div className="form-grid"><Field label="豁免 DC"><TextInput inputMode="numeric" value={entry.dc} onChange={(event) => patchEntry({ dc: event.target.value })}/></Field><Field label="豁免属性"><SelectInput value={entry.save_ability} onChange={(event) => patchEntry({ save_ability: event.target.value })}>{ABILITIES.map((ability) => <option key={ability}>{ability}</option>)}</SelectInput></Field><Field label="成功效果"><SelectInput value={entry.save_outcome} onChange={(event) => patchEntry({ save_outcome: event.target.value })}><option>成功半伤</option><option>成功无伤</option><option>成功全伤</option></SelectInput></Field></div></>}
          <h3>伤害</h3><div className="form-grid"><Field label="伤害名称"><TextInput value={entry.damage_name} onChange={(event) => patchEntry({ damage_name: event.target.value })}/></Field><Field label="骰子数量"><TextInput inputMode="numeric" value={entry.dice_count} onChange={(event) => patchEntry({ dice_count: event.target.value })}/></Field><Field label="骰子面数"><TextInput inputMode="numeric" value={entry.dice_sides} onChange={(event) => patchEntry({ dice_sides: event.target.value })}/></Field><Field label="固定加值"><TextInput inputMode="numeric" value={entry.flat_bonus} onChange={(event) => patchEntry({ flat_bonus: event.target.value })}/></Field><Field label="伤害类型"><SelectInput value={entry.damage_type} onChange={(event) => patchEntry({ damage_type: event.target.value })}>{DAMAGE_TYPES.map((type) => <option key={type}>{type}</option>)}</SelectInput></Field></div>
          <div className="check-grid"><Check label="武器骰" checked={entry.weapon_die} onChange={(event) => patchEntry({ weapon_die: event.target.checked })}/><Check label="魔法伤害" checked={entry.magical} onChange={(event) => patchEntry({ magical: event.target.checked })}/><Check label="重武器战斗风格" checked={entry.great_weapon_fighting} onChange={(event) => patchEntry({ great_weapon_fighting: event.target.checked })}/></div>
          {entry.mode === "attack" && <><h3>预设与附加伤害</h3><div className="form-grid"><Field label="规则预设"><SelectInput value={entry.preset} onChange={(event) => patchEntry({ preset: event.target.value })}>{builtInPresets.map((preset) => <option key={preset}>{preset}</option>)}</SelectInput></Field><Field label="命中后附加"><SelectInput value={entry.rider} onChange={(event) => patchEntry({ rider: event.target.value })}><option>无</option><option>偷袭</option><option>至圣斩</option><option>凶蛮攻击</option><option>野蛮重击</option></SelectInput></Field><Field label="附加骰数量"><TextInput inputMode="numeric" value={entry.rider_dice} onChange={(event) => patchEntry({ rider_dice: event.target.value })}/></Field><Field label="附加骰面数"><TextInput inputMode="numeric" value={entry.rider_sides} onChange={(event) => patchEntry({ rider_sides: event.target.value })}/></Field></div></>}
          <div className="preset-row"><button onClick={savePreset}>保存当前为自定义预设</button>{Object.keys(config.custom_presets).map((name) => <span className="preset-chip" key={name}><button onClick={() => loadPreset(name)}>{name}</button><button aria-label={`删除预设 ${name}`} onClick={() => deletePreset(name)}>×</button></span>)}</div>
        </details>
      </section>
    </div>
    {result && result.sessions.some((session) => session.mode === "attack") && <section className="panel rider-panel"><h2>② 命中后附加</h2>{result.selectable_riders.length === 0 && <p>当前攻击没有需要选择的附加伤害，可以直接结算。</p>}{result.selectable_riders.map((rider) => <fieldset key={rider.component_id}><legend>{rider.name}</legend>{rider.attacks.map((attack) => <Check key={attack.attack_id} label={`${attack.group_name} · 第 ${attack.index + 1} 次${attack.critical ? "（重击）" : ""}`} checked={(riderSelections[rider.component_id] ?? []).includes(attack.attack_id)} onChange={(event) => toggleRider(rider.component_id, attack.attack_id, event.target.checked, rider.scope === "once_selectable")}/>)}</fieldset>)}<button className="primary" disabled={stale || busy} onClick={resolveDamage}>③ 结算攻击伤害</button></section>}
    {result && <AdvancedResults result={result} />}
    {diceReferences.length > 0 && <section className="panel reroll-panel"><h2>手动重骰</h2><div className="check-grid">{diceReferences.map((item) => <Check key={item.key} label={item.label} checked={rerolls.has(item.key)} onChange={(event) => setRerolls((current) => { const next = new Set(current); if (event.target.checked) next.add(item.key); else next.delete(item.key); return next; })}/>)}</div><button className="secondary" disabled={stale || busy || rerolls.size === 0} onClick={rerollSelected}>重骰选中骰子</button></section>}
  </main>;
}
