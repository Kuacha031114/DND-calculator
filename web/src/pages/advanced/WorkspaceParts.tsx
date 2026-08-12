import { Check, Field, SelectInput, TextInput } from "../../components/Field";
import { ABILITIES, DAMAGE_TYPES } from "../../config";
import type { AdvancedResult, AppConfig, EntryConfig, TargetConfig } from "../../types";

const modeLabels = { attack: "攻击检定", save: "豁免检定", auto: "自动伤害" } as const;
const builtInPresets = ["无", "神射手 -5/+10", "巨武器大师 -5/+10", "重武器战斗风格", "祝福术 +1d4", "灾祸术 -1d4", "精灵精准", "半身人幸运", "咒剑诅咒 19–20", "勇士精通重击 19–20", "勇士卓越重击 18–20"];

export type WorkspaceActions = {
  selectTarget(index: number): void;
  addTarget(): void;
  duplicateTarget(): void;
  deleteTarget(): void;
  selectEntry(index: number): void;
  addEntry(): void;
  duplicateEntry(): void;
  deleteEntry(): void;
  moveEntry(offset: number): void;
};

export function WorkspaceNavigator({ config, targetIndex, entryIndex, actions }: {
  config: AppConfig; targetIndex: number; entryIndex: number; actions: WorkspaceActions;
}) {
  return <aside className="panel navigator"><h2>目标</h2><div className="item-list">{config.targets.map((item, index) => <button className={index === targetIndex ? "selected" : ""} onClick={() => actions.selectTarget(index)} key={item.id}><strong>{item.name}</strong><span>AC {item.ac}</span></button>)}</div>
    <div className="mini-actions"><button onClick={actions.addTarget}>新增</button><button onClick={actions.duplicateTarget}>复制</button><button onClick={actions.deleteTarget}>删除</button></div>
    <hr/><h2>结算条目</h2><div className="item-list">{config.entries.map((item, index) => <button className={index === entryIndex ? "selected" : ""} onClick={() => actions.selectEntry(index)} key={item.id}><strong>{item.name}</strong><span>{modeLabels[item.mode]}</span></button>)}</div>
    <div className="mini-actions"><button onClick={actions.addEntry}>新增</button><button onClick={actions.duplicateEntry}>复制</button><button onClick={actions.deleteEntry}>删除</button><button onClick={() => actions.moveEntry(-1)}>↑</button><button onClick={() => actions.moveEntry(1)}>↓</button></div>
  </aside>;
}

export function TargetEditor({ target, patch }: { target: TargetConfig; patch(value: Partial<TargetConfig>): void }) {
  return <details className="panel editor" open><summary>目标防御 · {target.name}</summary>
    <div className="form-grid"><Field label="目标名称"><TextInput value={target.name} onChange={(event) => patch({ name: event.target.value })}/></Field><Field label="AC"><TextInput inputMode="numeric" value={target.ac} onChange={(event) => patch({ ac: event.target.value })}/></Field></div>
    <h3>豁免加值</h3><div className="ability-grid">{ABILITIES.map((ability) => <Field label={ability} key={ability}><TextInput inputMode="numeric" value={target.saves[ability]} onChange={(event) => patch({ saves: { ...target.saves, [ability]: event.target.value } })}/></Field>)}</div>
    <div className="form-grid"><Field label="抗性" hint="用逗号分隔伤害类型"><TextInput value={target.resistances} onChange={(event) => patch({ resistances: event.target.value })}/></Field><Field label="易伤"><TextInput value={target.vulnerabilities} onChange={(event) => patch({ vulnerabilities: event.target.value })}/></Field><Field label="免疫"><TextInput value={target.immunities} onChange={(event) => patch({ immunities: event.target.value })}/></Field><Field label="非魔法抗性"><TextInput value={target.nonmagical_resistances} onChange={(event) => patch({ nonmagical_resistances: event.target.value })}/></Field><Field label="固定减伤"><TextInput inputMode="numeric" value={target.fixed_reduction} onChange={(event) => patch({ fixed_reduction: event.target.value })}/></Field><Check label="重击免疫" checked={target.crit_immune} onChange={(event) => patch({ crit_immune: event.target.checked })}/></div>
  </details>;
}

export function EntryEditor({ entry, targets, customPresets, patch, savePreset, loadPreset, deletePreset }: {
  entry: EntryConfig; targets: TargetConfig[]; customPresets: AppConfig["custom_presets"];
  patch(value: Partial<EntryConfig>): void; savePreset(): void; loadPreset(name: string): void; deletePreset(name: string): void;
}) {
  return <details className="panel editor" open><summary>编辑条目 · {entry.name}</summary>
    <div className="form-grid"><Field label="条目名称"><TextInput value={entry.name} onChange={(event) => patch({ name: event.target.value })}/></Field><Field label="结算方式"><SelectInput value={entry.mode} onChange={(event) => patch({ mode: event.target.value as EntryConfig["mode"] })}><option value="attack">攻击检定</option><option value="save">豁免检定</option><option value="auto">自动伤害</option></SelectInput></Field><Field label="目标"><SelectInput value={entry.target_id} onChange={(event) => patch({ target_id: event.target.value })}>{targets.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</SelectInput></Field>{entry.mode !== "attack" && <Check label="应用到全部目标" checked={entry.all_targets} onChange={(event) => patch({ all_targets: event.target.checked })}/>}</div>
    {entry.mode === "attack" && <><h3>攻击规则</h3><div className="form-grid"><Field label="攻击次数"><TextInput inputMode="numeric" value={entry.count} onChange={(event) => patch({ count: event.target.value })}/></Field><Field label="命中加值"><TextInput inputMode="numeric" value={entry.attack_bonus} onChange={(event) => patch({ attack_bonus: event.target.value })}/></Field><Field label="优势来源数"><TextInput inputMode="numeric" value={entry.advantage} onChange={(event) => patch({ advantage: event.target.value })}/></Field><Field label="劣势来源数"><TextInput inputMode="numeric" value={entry.disadvantage} onChange={(event) => patch({ disadvantage: event.target.value })}/></Field><Field label="重击下限"><TextInput inputMode="numeric" value={entry.crit_range} onChange={(event) => patch({ crit_range: event.target.value })}/></Field><Field label="减 5 加 10 序号"><TextInput value={entry.power_indices} onChange={(event) => patch({ power_indices: event.target.value })}/></Field></div>
      <div className="check-grid"><Check label="AC 未知，手动指定命中" checked={entry.manual_hits} onChange={(event) => patch({ manual_hits: event.target.checked })}/><Check label="全部攻击减 5 加 10" checked={entry.power_attack} onChange={(event) => patch({ power_attack: event.target.checked })}/><Check label="精灵精准" checked={entry.elven_accuracy} onChange={(event) => patch({ elven_accuracy: event.target.checked })}/><Check label="半身人幸运" checked={entry.halfling_lucky} onChange={(event) => patch({ halfling_lucky: event.target.checked })}/><Check label="祝福术" checked={entry.bless} onChange={(event) => patch({ bless: event.target.checked })}/><Check label="灾祸术" checked={entry.bane} onChange={(event) => patch({ bane: event.target.checked })}/></div>
      {entry.manual_hits && <div className="form-grid"><Field label="命中次数"><TextInput inputMode="numeric" value={entry.manual_hit_count} onChange={(event) => patch({ manual_hit_count: event.target.value })}/></Field><Field label="其中重击"><TextInput inputMode="numeric" value={entry.manual_critical_count} onChange={(event) => patch({ manual_critical_count: event.target.value })}/></Field></div>}</>}
    {entry.mode === "save" && <><h3>豁免规则</h3><div className="form-grid"><Field label="豁免 DC"><TextInput inputMode="numeric" value={entry.dc} onChange={(event) => patch({ dc: event.target.value })}/></Field><Field label="豁免属性"><SelectInput value={entry.save_ability} onChange={(event) => patch({ save_ability: event.target.value })}>{ABILITIES.map((ability) => <option key={ability}>{ability}</option>)}</SelectInput></Field><Field label="成功效果"><SelectInput value={entry.save_outcome} onChange={(event) => patch({ save_outcome: event.target.value })}><option>成功半伤</option><option>成功无伤</option><option>成功全伤</option></SelectInput></Field></div></>}
    <h3>伤害</h3><div className="form-grid"><Field label="伤害名称"><TextInput value={entry.damage_name} onChange={(event) => patch({ damage_name: event.target.value })}/></Field><Field label="骰子数量"><TextInput inputMode="numeric" value={entry.dice_count} onChange={(event) => patch({ dice_count: event.target.value })}/></Field><Field label="骰子面数"><TextInput inputMode="numeric" value={entry.dice_sides} onChange={(event) => patch({ dice_sides: event.target.value })}/></Field><Field label="固定加值"><TextInput inputMode="numeric" value={entry.flat_bonus} onChange={(event) => patch({ flat_bonus: event.target.value })}/></Field><Field label="伤害类型"><SelectInput value={entry.damage_type} onChange={(event) => patch({ damage_type: event.target.value })}>{DAMAGE_TYPES.map((type) => <option key={type}>{type}</option>)}</SelectInput></Field></div>
    <div className="check-grid"><Check label="武器骰" checked={entry.weapon_die} onChange={(event) => patch({ weapon_die: event.target.checked })}/><Check label="魔法伤害" checked={entry.magical} onChange={(event) => patch({ magical: event.target.checked })}/><Check label="重武器战斗风格" checked={entry.great_weapon_fighting} onChange={(event) => patch({ great_weapon_fighting: event.target.checked })}/></div>
    {entry.mode === "attack" && <><h3>预设与附加伤害</h3><div className="form-grid"><Field label="规则预设"><SelectInput value={entry.preset} onChange={(event) => patch({ preset: event.target.value })}>{builtInPresets.map((preset) => <option key={preset}>{preset}</option>)}</SelectInput></Field><Field label="命中后附加"><SelectInput value={entry.rider} onChange={(event) => patch({ rider: event.target.value })}><option>无</option><option>偷袭</option><option>至圣斩</option><option>凶蛮攻击</option><option>野蛮重击</option></SelectInput></Field><Field label="附加骰数量"><TextInput inputMode="numeric" value={entry.rider_dice} onChange={(event) => patch({ rider_dice: event.target.value })}/></Field><Field label="附加骰面数"><TextInput inputMode="numeric" value={entry.rider_sides} onChange={(event) => patch({ rider_sides: event.target.value })}/></Field></div></>}
    <div className="preset-row"><button onClick={savePreset}>保存当前为自定义预设</button>{Object.keys(customPresets).map((name) => <span className="preset-chip" key={name}><button onClick={() => loadPreset(name)}>{name}</button><button aria-label={`删除预设 ${name}`} onClick={() => deletePreset(name)}>×</button></span>)}</div>
  </details>;
}

export function RiderPanel({ result, selections, stale, busy, toggle, resolve }: {
  result: AdvancedResult; selections: Record<string, string[]>; stale: boolean; busy: boolean;
  toggle(componentId: string, attackId: string, checked: boolean, once: boolean): void; resolve(): void;
}) {
  if (!result.sessions.some((session) => session.mode === "attack")) return null;
  return <section className="panel rider-panel"><h2>② 命中后附加</h2>{result.selectable_riders.length === 0 && <p>当前攻击没有需要选择的附加伤害，可以直接结算。</p>}{result.selectable_riders.map((rider) => <fieldset key={rider.component_id}><legend>{rider.name}</legend>{rider.attacks.map((attack) => <Check key={attack.attack_id} label={`${attack.group_name} · 第 ${attack.index + 1} 次${attack.critical ? "（重击）" : ""}`} checked={(selections[rider.component_id] ?? []).includes(attack.attack_id)} onChange={(event) => toggle(rider.component_id, attack.attack_id, event.target.checked, rider.scope === "once_selectable")}/>)}</fieldset>)}<button className="primary" disabled={stale || busy} onClick={resolve}>③ 结算攻击伤害</button></section>;
}

export type DiceReference = { key: string; label: string };

export function RerollPanel({ references, selected, stale, busy, toggle, reroll }: {
  references: DiceReference[]; selected: Set<string>; stale: boolean; busy: boolean;
  toggle(key: string, checked: boolean): void; reroll(): void;
}) {
  if (references.length === 0) return null;
  return <section className="panel reroll-panel"><h2>手动重骰</h2><div className="check-grid">{references.map((item) => <Check key={item.key} label={item.label} checked={selected.has(item.key)} onChange={(event) => toggle(item.key, event.target.checked)}/>)}</div><button className="secondary" disabled={stale || busy || selected.size === 0} onClick={reroll}>重骰选中骰子</button></section>;
}
