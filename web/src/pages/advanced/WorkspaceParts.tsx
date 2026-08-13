import { useEffect, useState } from "react";
import { Check, Field, SelectInput, TextInput } from "../../components/Field";
import { ABILITIES, DAMAGE_TYPES, defaultAttackModifier, defaultDamageComponent, id } from "../../config";
import type { AdvancedResult, AppConfig, AttackModifierConfig, DamageComponentConfig, EntryConfig, TargetConfig } from "../../types";

const modeLabels = { attack: "攻击检定", save: "豁免检定", auto: "自动伤害" } as const;
const builtInPresets = ["无", "神射手 -5/+10", "巨武器大师 -5/+10", "重武器战斗风格", "精灵精准", "半身人幸运", "咒剑诅咒 19–20", "勇士精通重击 19–20", "勇士卓越重击 18–20"];

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
    <div className="form-grid"><Field label="抗性" hint="用逗号分隔伤害类型；与易伤同时存在时抵消"><TextInput value={target.resistances} onChange={(event) => patch({ resistances: event.target.value })}/></Field><Field label="易伤" hint="最终伤害翻倍；免疫优先"><TextInput value={target.vulnerabilities} onChange={(event) => patch({ vulnerabilities: event.target.value })}/></Field><Field label="免疫"><TextInput value={target.immunities} onChange={(event) => patch({ immunities: event.target.value })}/></Field><Field label="非魔法抗性" hint="只影响未勾选“魔法伤害”的组件"><TextInput value={target.nonmagical_resistances} onChange={(event) => patch({ nonmagical_resistances: event.target.value })}/></Field><Field label="固定减伤" hint="先于豁免、抗性和易伤结算"><TextInput inputMode="numeric" value={target.fixed_reduction} onChange={(event) => patch({ fixed_reduction: event.target.value })}/></Field><Check label="重击免疫" checked={target.crit_immune} onChange={(event) => patch({ crit_immune: event.target.checked })}/></div>
  </details>;
}

export function EntryEditor({ entry, targets, customPresets, patch, savePreset, loadPreset, deletePreset }: {
  entry: EntryConfig; targets: TargetConfig[]; customPresets: AppConfig["custom_presets"];
  patch(value: Partial<EntryConfig>): void; savePreset(): void; loadPreset(name: string): void; deletePreset(name: string): void;
}) {
  const [modifierIndex, setModifierIndex] = useState(0);
  const [damageIndex, setDamageIndex] = useState(0);
  useEffect(() => { if (modifierIndex >= entry.attack_modifiers.length) setModifierIndex(Math.max(0, entry.attack_modifiers.length - 1)); }, [entry.attack_modifiers.length, modifierIndex]);
  useEffect(() => { if (damageIndex >= entry.damage_components.length) setDamageIndex(Math.max(0, entry.damage_components.length - 1)); }, [entry.damage_components.length, damageIndex]);
  const modifier = entry.attack_modifiers[modifierIndex];
  const damage = entry.damage_components[damageIndex];
  const patchModifier = (value: Partial<AttackModifierConfig>) => patch({ attack_modifiers: entry.attack_modifiers.map((item, index) => index === modifierIndex ? { ...item, ...value } : item) });
  const patchDamage = (value: Partial<DamageComponentConfig>) => patch({ damage_components: entry.damage_components.map((item, index) => index === damageIndex ? { ...item, ...value } : item) });
  const move = <T,>(items: T[], current: number, offset: number, select: (index: number) => void): T[] => {
    const next = Math.max(0, Math.min(items.length - 1, current + offset));
    if (next === current) return items;
    const output = [...items]; [output[current], output[next]] = [output[next], output[current]]; select(next); return output;
  };
  function addModifier(scope: AttackModifierConfig["scope"] = "every_attack") {
    const next = { ...defaultAttackModifier(), scope, name: scope === "every_attack" ? "每次攻击 +1d4" : "选择一次 +1d4" };
    patch({ attack_modifiers: [...entry.attack_modifiers, next] }); setModifierIndex(entry.attack_modifiers.length);
  }
  function addDamage(scope: DamageComponentConfig["scope"] = "every_hit") {
    const names = { every_hit: "每次命中伤害", once_selectable: "选择一次伤害", selected_hits: "按命中选择伤害", crit_only: "仅重击伤害" };
    const next = { ...defaultDamageComponent(), name: names[scope], scope, weapon_die: false, flat_bonus: "0" };
    patch({ damage_components: [...entry.damage_components, next] }); setDamageIndex(entry.damage_components.length);
  }
  return <details className="panel editor" open><summary>编辑条目 · {entry.name}</summary>
    <div className="form-grid"><Field label="条目名称"><TextInput value={entry.name} onChange={(event) => patch({ name: event.target.value })}/></Field><Field label="结算方式"><SelectInput value={entry.mode} onChange={(event) => patch({ mode: event.target.value as EntryConfig["mode"] })}><option value="attack">攻击检定</option><option value="save">豁免检定</option><option value="auto">自动伤害</option></SelectInput></Field><Field label="目标"><SelectInput value={entry.target_id} onChange={(event) => patch({ target_id: event.target.value })}>{targets.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</SelectInput></Field>{entry.mode !== "attack" && <Check label="应用到全部目标" checked={entry.all_targets} onChange={(event) => patch({ all_targets: event.target.checked })}/>}</div>
    {entry.mode === "attack" && <><h3>攻击规则</h3><div className="form-grid"><Field label="攻击次数"><TextInput inputMode="numeric" value={entry.count} onChange={(event) => patch({ count: event.target.value })}/></Field><Field label="命中加值"><TextInput inputMode="numeric" value={entry.attack_bonus} onChange={(event) => patch({ attack_bonus: event.target.value })}/></Field><Field label="优势来源数" hint="任意优势与任意劣势同时存在时相互抵消"><TextInput inputMode="numeric" value={entry.advantage} onChange={(event) => patch({ advantage: event.target.value })}/></Field><Field label="劣势来源数"><TextInput inputMode="numeric" value={entry.disadvantage} onChange={(event) => patch({ disadvantage: event.target.value })}/></Field><Field label="重击下限" hint="只由选中的 d20 决定；命中修正骰不会制造重击"><TextInput inputMode="numeric" value={entry.crit_range} onChange={(event) => patch({ crit_range: event.target.value })}/></Field><Field label="减 5 加 10 序号" hint="填写 1,3 等攻击序号；留空时由下方总开关控制"><TextInput value={entry.power_indices} onChange={(event) => patch({ power_indices: event.target.value })}/></Field></div>
      <div className="check-grid"><Check label="AC 未知，手动指定命中" checked={entry.manual_hits} onChange={(event) => patch({ manual_hits: event.target.checked })}/><Check label="全部攻击减 5 加 10" checked={entry.power_attack} onChange={(event) => patch({ power_attack: event.target.checked })}/><Check label="精灵精准" checked={entry.elven_accuracy} onChange={(event) => patch({ elven_accuracy: event.target.checked })}/><Check label="半身人幸运" checked={entry.halfling_lucky} onChange={(event) => patch({ halfling_lucky: event.target.checked })}/><Check label="重武器战斗风格" checked={entry.great_weapon_fighting} onChange={(event) => patch({ great_weapon_fighting: event.target.checked })}/></div>
      {entry.manual_hits && <div className="form-grid"><Field label="命中次数"><TextInput inputMode="numeric" value={entry.manual_hit_count} onChange={(event) => patch({ manual_hit_count: event.target.value })}/></Field><Field label="其中重击"><TextInput inputMode="numeric" value={entry.manual_critical_count} onChange={(event) => patch({ manual_critical_count: event.target.value })}/></Field></div>}</>}
    {entry.mode === "save" && <><h3>豁免规则</h3><div className="form-grid"><Field label="豁免 DC"><TextInput inputMode="numeric" value={entry.dc} onChange={(event) => patch({ dc: event.target.value })}/></Field><Field label="豁免属性"><SelectInput value={entry.save_ability} onChange={(event) => patch({ save_ability: event.target.value })}>{ABILITIES.map((ability) => <option key={ability}>{ability}</option>)}</SelectInput></Field><Field label="成功效果"><SelectInput value={entry.save_outcome} onChange={(event) => patch({ save_outcome: event.target.value })}><option>成功半伤</option><option>成功无伤</option><option>成功全伤</option></SelectInput></Field></div></>}
    {entry.mode === "attack" && <><h3>命中修正骰</h3><div className="dynamic-editor"><div className="dynamic-list">{entry.attack_modifiers.map((item, index) => <button className={index === modifierIndex ? "selected" : ""} key={item.id} onClick={() => setModifierIndex(index)}><strong>{item.name}</strong><span>{item.sign === "-1" ? "−" : "+"}{item.dice_count}d{item.dice_sides} · {item.scope === "every_attack" ? "每次攻击" : "选择一次"}</span></button>)}{entry.attack_modifiers.length === 0 && <p>尚未添加命中修正骰。</p>}<div className="mini-actions"><button onClick={() => addModifier("every_attack")}>每次 +1d4</button><button onClick={() => addModifier("once_selectable")}>选择一次 +1d4</button><button onClick={() => addModifier()}>空白</button>{modifier && <><button onClick={() => { const next = { ...modifier, id: id("modifier"), name: `${modifier.name} 副本` }; patch({ attack_modifiers: [...entry.attack_modifiers, next] }); setModifierIndex(entry.attack_modifiers.length); }}>复制</button><button onClick={() => { patch({ attack_modifiers: entry.attack_modifiers.filter((_, index) => index !== modifierIndex) }); setModifierIndex(Math.max(0, modifierIndex - 1)); }}>删除</button><button onClick={() => patch({ attack_modifiers: move(entry.attack_modifiers, modifierIndex, -1, setModifierIndex) })}>↑</button><button onClick={() => patch({ attack_modifiers: move(entry.attack_modifiers, modifierIndex, 1, setModifierIndex) })}>↓</button></>}</div></div>{modifier && <div className="dynamic-fields form-grid"><Field label="名称"><TextInput value={modifier.name} onChange={(event) => patchModifier({ name: event.target.value })}/></Field><Field label="骰子数量"><TextInput inputMode="numeric" value={modifier.dice_count} onChange={(event) => patchModifier({ dice_count: event.target.value })}/></Field><Field label="骰子面数"><TextInput inputMode="numeric" value={modifier.dice_sides} onChange={(event) => patchModifier({ dice_sides: event.target.value })}/></Field><Field label="正负"><SelectInput value={modifier.sign} onChange={(event) => patchModifier({ sign: event.target.value as AttackModifierConfig["sign"] })}><option value="1">加值</option><option value="-1">减值</option></SelectInput></Field><Field label="作用范围"><SelectInput value={modifier.scope} onChange={(event) => patchModifier({ scope: event.target.value as AttackModifierConfig["scope"] })}><option value="every_attack">每次攻击</option><option value="once_selectable">投 d20 后选择一次</option></SelectInput></Field></div>}</div></>}
    <h3>伤害组件</h3><div className="dynamic-editor"><div className="dynamic-list">{entry.damage_components.map((item, index) => <button className={index === damageIndex ? "selected" : ""} key={item.id} onClick={() => setDamageIndex(index)}><strong>{item.name}</strong><span>{item.dice_count}d{item.dice_sides}{Number(item.flat_bonus) >= 0 ? "+" : ""}{item.flat_bonus} · {item.damage_type}</span></button>)}<div className="mini-actions"><button onClick={() => addDamage("every_hit")}>每次命中</button>{entry.mode === "attack" && <><button onClick={() => addDamage("once_selectable")}>选择一次</button><button onClick={() => addDamage("selected_hits")}>选择多个</button><button onClick={() => addDamage("crit_only")}>仅重击</button></>}<button onClick={() => { const next = { ...damage, id: id("damage"), name: `${damage.name} 副本` }; patch({ damage_components: [...entry.damage_components, next] }); setDamageIndex(entry.damage_components.length); }}>复制</button><button disabled={entry.damage_components.length === 1} onClick={() => { patch({ damage_components: entry.damage_components.filter((_, index) => index !== damageIndex) }); setDamageIndex(Math.max(0, damageIndex - 1)); }}>删除</button><button onClick={() => patch({ damage_components: move(entry.damage_components, damageIndex, -1, setDamageIndex) })}>↑</button><button onClick={() => patch({ damage_components: move(entry.damage_components, damageIndex, 1, setDamageIndex) })}>↓</button></div></div><div className="dynamic-fields"><div className="form-grid"><Field label="名称"><TextInput value={damage.name} onChange={(event) => patchDamage({ name: event.target.value })}/></Field><Field label="骰子数量"><TextInput inputMode="numeric" value={damage.dice_count} onChange={(event) => patchDamage({ dice_count: event.target.value })}/></Field><Field label="骰子面数"><TextInput inputMode="numeric" value={damage.dice_sides} onChange={(event) => patchDamage({ dice_sides: event.target.value })}/></Field><Field label="固定值"><TextInput inputMode="numeric" value={damage.flat_bonus} onChange={(event) => patchDamage({ flat_bonus: event.target.value })}/></Field><Field label="伤害类型"><SelectInput value={damage.damage_type} onChange={(event) => patchDamage({ damage_type: event.target.value })}>{DAMAGE_TYPES.map((type) => <option key={type}>{type}</option>)}</SelectInput></Field>{entry.mode === "attack" && <Field label="作用范围"><SelectInput value={damage.scope} onChange={(event) => patchDamage({ scope: event.target.value as DamageComponentConfig["scope"] })}><option value="every_hit">每次命中</option><option value="once_selectable">最多选择一次</option><option value="selected_hits">选择任意命中</option><option value="crit_only">仅重击</option></SelectInput></Field>}<Field label="重击规则"><SelectInput value={damage.crit_behavior} onChange={(event) => patchDamage({ crit_behavior: event.target.value as DamageComponentConfig["crit_behavior"] })}><option value="double_dice">伤害骰翻倍</option><option value="normal">不额外翻倍</option></SelectInput></Field></div><div className="check-grid"><Check label="武器骰" checked={damage.weapon_die} onChange={(event) => patchDamage({ weapon_die: event.target.checked })}/><Check label="魔法伤害" checked={damage.magical} onChange={(event) => patchDamage({ magical: event.target.checked })}/></div></div></div>
    {entry.mode === "attack" && <><h3>规则预设</h3><div className="form-grid"><Field label="攻击预设"><SelectInput value={entry.preset} onChange={(event) => patch({ preset: event.target.value })}>{builtInPresets.map((preset) => <option key={preset}>{preset}</option>)}</SelectInput></Field></div></>}
    <div className="preset-row"><button onClick={savePreset}>保存当前为自定义预设</button>{Object.keys(customPresets).map((name) => <span className="preset-chip" key={name}><button onClick={() => loadPreset(name)}>{name}</button><button aria-label={`删除预设 ${name}`} onClick={() => deletePreset(name)}>×</button></span>)}</div>
  </details>;
}

export function AttackModifierPanel({ result, selections, stale, busy, choose, resolve }: {
  result: AdvancedResult; selections: Record<string, string>; stale: boolean; busy: boolean;
  choose(modifierId: string, attackId: string): void; resolve(): void;
}) {
  if (result.attack_modifiers_resolved || result.selectable_attack_modifiers.length === 0) return null;
  return <section className="panel rider-panel"><h2>② 选择本次命中修正</h2><p>每项最多用于所属攻击组的一次攻击，也可以不使用。提交后结果锁定；如需改选请重新投掷检定。</p>{result.selectable_attack_modifiers.map((modifier) => <Field label={`${modifier.name} · ${modifier.dice.sign < 0 ? "−" : "+"}${modifier.dice.count}d${modifier.dice.sides}`} key={modifier.modifier_id}><SelectInput value={selections[modifier.modifier_id] ?? ""} onChange={(event) => choose(modifier.modifier_id, event.target.value)}><option value="">不使用</option>{modifier.attacks.map((attack) => <option value={attack.attack_id} key={attack.attack_id}>{attack.group_name} · 第 {attack.index + 1} 次 · 基础总值 {attack.total}</option>)}</SelectInput></Field>)}<button className="primary" disabled={stale || busy} onClick={resolve}>提交命中修正</button></section>;
}

export function RiderPanel({ result, selections, stale, busy, toggle, resolve }: {
  result: AdvancedResult; selections: Record<string, string[]>; stale: boolean; busy: boolean;
  toggle(componentId: string, attackId: string, checked: boolean, once: boolean): void; resolve(): void;
}) {
  if (!result.sessions.some((session) => session.mode === "attack")) return null;
  if (!result.attack_modifiers_resolved) return null;
  return <section className="panel rider-panel"><h2>③ 命中后附加</h2>{result.selectable_riders.length === 0 && <p>当前攻击没有需要选择的附加伤害，可以直接结算。</p>}{result.selectable_riders.map((rider) => <fieldset key={rider.component_id}><legend>{rider.name}</legend>{rider.attacks.map((attack) => <Check key={attack.attack_id} label={`${attack.group_name} · 第 ${attack.index + 1} 次${attack.critical ? "（重击）" : ""}`} checked={(selections[rider.component_id] ?? []).includes(attack.attack_id)} onChange={(event) => toggle(rider.component_id, attack.attack_id, event.target.checked, rider.scope === "once_selectable")}/>)}</fieldset>)}<button className="primary" disabled={stale || busy} onClick={resolve}>④ 结算攻击伤害</button></section>;
}

export type DiceReference = { key: string; label: string };

export function RerollPanel({ references, selected, stale, busy, toggle, reroll }: {
  references: DiceReference[]; selected: Set<string>; stale: boolean; busy: boolean;
  toggle(key: string, checked: boolean): void; reroll(): void;
}) {
  if (references.length === 0) return null;
  return <section className="panel reroll-panel"><h2>手动重骰</h2><div className="check-grid">{references.map((item) => <Check key={item.key} label={item.label} checked={selected.has(item.key)} onChange={(event) => toggle(item.key, event.target.checked)}/>)}</div><button className="secondary" disabled={stale || busy || selected.size === 0} onClick={reroll}>重骰选中骰子</button></section>;
}
