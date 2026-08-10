import { useMemo, useState } from "react";
import type { BridgeMethods, QuickConfig, QuickSummary } from "../types";
import { Check, Field, SelectInput, TextInput } from "../components/Field";
import { QuickResults } from "../components/Results";

const rollModes: Record<string, string> = { "普通": "normal", "优势": "advantage", "劣势": "disadvantage" };

function number(value: string, label: string, minimum: number, maximum: number): number {
  if (!/^-?\d+$/.test(value.trim())) throw new Error(`${label}必须是整数`);
  const parsed = Number(value);
  if (parsed < minimum || parsed > maximum) throw new Error(`${label}必须在 ${minimum} 到 ${maximum} 之间`);
  return parsed;
}

export function QuickCalculator({ config, onChange, bridge, ready, onContinueAdvanced }: {
  config: QuickConfig;
  onChange(config: QuickConfig): void;
  bridge: BridgeMethods;
  ready: boolean;
  onContinueAdvanced(): void;
}) {
  const [summary, setSummary] = useState<QuickSummary | null>(null);
  const [resultConfig, setResultConfig] = useState<string>("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const serialized = useMemo(() => JSON.stringify(config), [config]);
  const stale = Boolean(summary && resultConfig !== serialized);

  function update<K extends keyof QuickConfig>(key: K, value: QuickConfig[K]) {
    onChange({ ...config, [key]: value });
  }

  async function run() {
    try {
      setError("");
      setBusy(true);
      const attackCount = number(config.attack_count, "攻击次数", 1, 100);
      const manualHits = config.manual_hits;
      const manualHitCount = manualHits ? number(config.manual_hit_count, "命中次数", 0, attackCount) : null;
      const manualCriticalCount = manualHits
        ? number(config.manual_critical_count, "重击次数", 0, manualHitCount ?? 0) : 0;
      const payload = {
        target_ac: manualHits ? 10 : number(config.target_ac, "目标 AC", 1, 99),
        attack_bonus: number(config.attack_bonus, "命中加值", -99, 99),
        attack_count: attackCount,
        roll_mode: rollModes[config.roll_mode] ?? "normal",
        crit_range: number(config.crit_range, "重击下限", 2, 20),
        power_attack: config.power_attack,
        damage_dice_count: number(config.damage_dice_count, "伤害骰数量", 0, 100),
        damage_die_sides: number(config.damage_die_sides, "伤害骰面数", 2, 1000),
        damage_bonus: number(config.damage_bonus, "伤害加值", -999, 999),
        manual_hit_count: manualHitCount,
        manual_critical_count: manualCriticalCount,
      };
      const next = await bridge.resolveQuick(payload);
      setSummary(next);
      setResultConfig(serialized);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }

  return <main className="page quick-page">
    <section className="hero"><div><span className="eyebrow">D&D 5e 2014</span><h1>三步完成攻击结算</h1>
      <p>填写目标、攻击和伤害。所有投骰都只在你的浏览器中完成。</p></div><div className="d20">20</div></section>
    <section className="steps-grid">
      <article className="panel step-card"><div className="step-number">1</div><h2>目标</h2>
        <Check label="不知道 AC，手动指定命中" checked={config.manual_hits} onChange={(event) => update("manual_hits", event.target.checked)} />
        {!config.manual_hits ? <Field label="目标 AC"><TextInput inputMode="numeric" value={config.target_ac} onChange={(event) => update("target_ac", event.target.value)} /></Field>
          : <div className="field-grid"><Field label="命中次数"><TextInput inputMode="numeric" value={config.manual_hit_count} onChange={(event) => update("manual_hit_count", event.target.value)} /></Field>
            <Field label="其中重击"><TextInput inputMode="numeric" value={config.manual_critical_count} onChange={(event) => update("manual_critical_count", event.target.value)} /></Field></div>}
      </article>
      <article className="panel step-card"><div className="step-number">2</div><h2>攻击</h2>
        <div className="field-grid"><Field label="命中加值"><TextInput inputMode="numeric" value={config.attack_bonus} onChange={(event) => update("attack_bonus", event.target.value)} /></Field>
          <Field label="攻击次数"><TextInput inputMode="numeric" value={config.attack_count} onChange={(event) => update("attack_count", event.target.value)} /></Field></div>
        <div className="field-grid"><Field label="投骰方式"><SelectInput value={config.roll_mode} onChange={(event) => update("roll_mode", event.target.value)}><option>普通</option><option>优势</option><option>劣势</option></SelectInput></Field>
          <Field label="重击下限"><TextInput inputMode="numeric" value={config.crit_range} onChange={(event) => update("crit_range", event.target.value)} /></Field></div>
        <Check label="减 5 命中并在命中时加 10 伤害" checked={config.power_attack} onChange={(event) => update("power_attack", event.target.checked)} />
      </article>
      <article className="panel step-card"><div className="step-number">3</div><h2>伤害</h2>
        <div className="dice-row"><Field label="骰子数量"><TextInput inputMode="numeric" value={config.damage_dice_count} onChange={(event) => update("damage_dice_count", event.target.value)} /></Field><span>d</span>
          <Field label="骰子面数"><TextInput inputMode="numeric" value={config.damage_die_sides} onChange={(event) => update("damage_die_sides", event.target.value)} /></Field><span>+</span>
          <Field label="伤害加值"><TextInput inputMode="numeric" value={config.damage_bonus} onChange={(event) => update("damage_bonus", event.target.value)} /></Field></div>
      </article>
    </section>
    {error && <div className="error" role="alert">{error}</div>}
    <div className="action-row"><button className="primary" disabled={!ready || busy} onClick={run}>{busy ? "正在投骰…" : ready ? "立即结算" : "正在加载规则引擎…"}</button>
      <button className="secondary" onClick={onContinueAdvanced}>在高级模式继续编辑</button></div>
    {summary && <QuickResults summary={summary} stale={stale} />}
  </main>;
}
