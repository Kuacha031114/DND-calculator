import { useMemo } from "react";
import { analyzeEncounter } from "../analysis";
import { defaultBuild, id } from "../config";
import { Check, Field, SelectInput, TextInput } from "../components/Field";
import type { AnalysisConfig, BuildProfile } from "../types";

function fixed(value: number, digits = 1): string {
  return Number.isFinite(value) ? value.toFixed(digits) : "—";
}

function percent(value: number): string {
  return `${fixed(value * 100, 1)}%`;
}

export function DamageAnalysis({ config, onChange }: {
  config: AnalysisConfig;
  onChange(config: AnalysisConfig): void;
}) {
  const calculation = useMemo(() => {
    try { return { result: analyzeEncounter(config), error: "" }; }
    catch (error) { return { result: null, error: error instanceof Error ? error.message : String(error) }; }
  }, [config]);

  function update<K extends keyof AnalysisConfig>(key: K, value: AnalysisConfig[K]) {
    onChange({ ...config, [key]: value });
  }

  function updateBuild<K extends keyof BuildProfile>(buildId: string, key: K, value: BuildProfile[K]) {
    update("builds", config.builds.map((build) => build.id === buildId ? { ...build, [key]: value } : build));
  }

  function duplicateBuild(build: BuildProfile) {
    update("builds", [...config.builds, { ...build, id: id("build"), name: `${build.name}副本`, enabled: false }]);
  }

  function addBuild() {
    update("builds", [...config.builds, defaultBuild(config.builds.length + 1)]);
  }

  function removeBuild(buildId: string) {
    if (config.builds.length <= 1) return;
    update("builds", config.builds.filter((build) => build.id !== buildId));
  }

  const resultById = new Map(calculation.result?.builds.map((result) => [result.id, result]) ?? []);
  const maxDpr = Math.max(1, ...Array.from(resultById.values(), (result) => result.dpr));
  const targetAc = Number(config.target_ac);
  const sensitivity = calculation.result && Number.isInteger(targetAc)
    ? Array.from({ length: 9 }, (_, index) => Math.max(1, Math.min(99, targetAc - 4 + index)))
      .filter((ac, index, values) => values.indexOf(ac) === index)
      .map((ac) => {
        try { return { ac, result: analyzeEncounter(config, ac) }; } catch { return null; }
      }).filter((row): row is NonNullable<typeof row> => row !== null)
    : [];

  return <main className="page analysis-page">
    <section className="hero analysis-hero"><div><span className="eyebrow">D&D 5e 2014 · 构筑与备团</span>
      <h1>命中率与期望伤害比较器</h1>
      <p>比较玩家构筑的稳定输出，再把队伍 DPR 换算成怪物总 HP 和预计战斗轮数。</p></div><div className="d20 analysis-d20">%</div></section>

    <section className="panel analysis-overview">
      <div><h2>共同假想目标</h2><p>所有方案先对同一 AC 计算，便于公平比较。DM 区域会复用这个 AC。</p></div>
      <Field label="目标 AC"><TextInput aria-label="分析目标 AC" inputMode="numeric" value={config.target_ac} onChange={(event) => update("target_ac", event.target.value)} /></Field>
    </section>

    <section className="analysis-heading"><div><span className="section-kicker">玩家与审卡</span><h2>构筑方案</h2>
      <p>一个方案代表一名角色的一整轮输出。所有方案都会比较，只有勾选项才计入 DM 队伍 DPR。</p></div>
      <button className="secondary" onClick={addBuild}>新增构筑</button></section>

    <div className="build-list">
      {config.builds.map((build, index) => {
        const result = resultById.get(build.id);
        return <article className={`panel build-card ${build.enabled ? "" : "comparison-only-card"}`} key={build.id}>
          <header className="build-card-header"><div className="build-title"><span className="build-index">{index + 1}</span>
            <TextInput aria-label={`方案 ${index + 1} 名称`} value={build.name} onChange={(event) => updateBuild(build.id, "name", event.target.value)} /></div>
            <div className="mini-actions"><Check label="计入 DM 队伍" checked={build.enabled} onChange={(event) => updateBuild(build.id, "enabled", event.target.checked)} />
              <button onClick={() => duplicateBuild(build)}>复制</button><button disabled={config.builds.length <= 1} onClick={() => removeBuild(build.id)}>删除</button></div></header>

          <div className="build-fields">
            <fieldset><legend>攻击</legend><div className="analysis-field-grid">
              <Field label="命中加值" hint="填写使用减5前的加值"><TextInput inputMode="numeric" value={build.attack_bonus} onChange={(event) => updateBuild(build.id, "attack_bonus", event.target.value)} /></Field>
              <Field label="每轮攻击次数"><TextInput inputMode="numeric" value={build.attacks_per_round} onChange={(event) => updateBuild(build.id, "attacks_per_round", event.target.value)} /></Field>
              <Field label="投骰方式"><SelectInput value={build.roll_mode} onChange={(event) => updateBuild(build.id, "roll_mode", event.target.value as BuildProfile["roll_mode"])}><option value="normal">普通</option><option value="advantage">优势</option><option value="disadvantage">劣势</option><option value="elven_accuracy">三骰取高（精灵精准）</option></SelectInput></Field>
              <Field label="重击下限"><TextInput inputMode="numeric" value={build.crit_range} onChange={(event) => updateBuild(build.id, "crit_range", event.target.value)} /></Field>
            </div><Check label="减 5 命中、命中后加 10 伤害" checked={build.power_attack} onChange={(event) => updateBuild(build.id, "power_attack", event.target.checked)} /></fieldset>

            <fieldset><legend>每次命中伤害</legend><div className="analysis-field-grid damage-inputs">
              <Field label="骰子数量"><TextInput inputMode="numeric" value={build.damage_dice_count} onChange={(event) => updateBuild(build.id, "damage_dice_count", event.target.value)} /></Field>
              <Field label="骰子面数"><TextInput inputMode="numeric" value={build.damage_die_sides} onChange={(event) => updateBuild(build.id, "damage_die_sides", event.target.value)} /></Field>
              <Field label="固定加值"><TextInput inputMode="numeric" value={build.damage_bonus} onChange={(event) => updateBuild(build.id, "damage_bonus", event.target.value)} /></Field>
              <Field label="重击额外骰颗数" hint="半兽人凶蛮攻击等，不含常规翻倍"><TextInput inputMode="numeric" value={build.crit_extra_dice} onChange={(event) => updateBuild(build.id, "crit_extra_dice", event.target.value)} /></Field>
            </div></fieldset>

            <fieldset><legend>每轮一次附伤</legend><div className="analysis-field-grid damage-inputs">
              <Field label="首次命中附伤骰"><TextInput inputMode="numeric" value={build.rider_dice_count} onChange={(event) => updateBuild(build.id, "rider_dice_count", event.target.value)} /></Field>
              <Field label="附伤骰面数"><TextInput inputMode="numeric" value={build.rider_die_sides} onChange={(event) => updateBuild(build.id, "rider_die_sides", event.target.value)} /></Field>
              <Field label="附伤固定加值"><TextInput inputMode="numeric" value={build.rider_bonus} onChange={(event) => updateBuild(build.id, "rider_bonus", event.target.value)} /></Field>
              <Field label="每轮固定伤害" hint="持续伤害或已经单独算好的期望"><TextInput inputMode="decimal" value={build.guaranteed_damage} onChange={(event) => updateBuild(build.id, "guaranteed_damage", event.target.value)} /></Field>
            </div><Check label="附伤骰在触发重击时翻倍" checked={build.rider_doubles_on_crit} onChange={(event) => updateBuild(build.id, "rider_doubles_on_crit", event.target.checked)} /></fieldset>
          </div>

          {result && <div className="build-result" aria-label={`${build.name}计算结果`}>
            <div><span>单次命中率</span><strong>{percent(result.hit_probability)}</strong><small>其中重击 {percent(result.critical_probability)}</small></div>
            <div><span>本轮至少命中一次</span><strong>{percent(result.at_least_one_hit_probability)}</strong><small>期望命中 {fixed(result.expected_hits, 2)} 次</small></div>
            <div><span>每次攻击期望</span><strong>{fixed(result.damage_per_attack)}</strong><small>已计未命中与重击</small></div>
            <div className="dpr-result"><span>每轮期望伤害 DPR</span><strong>{fixed(result.dpr)}</strong><small>附伤贡献 {fixed(result.rider_damage)}</small></div>
          </div>}
        </article>;
      })}
    </div>

    {calculation.error && <div className="error analysis-error" role="alert">{calculation.error}</div>}

    {calculation.result && <>
      <section className="panel comparison-panel"><div className="analysis-heading compact"><div><span className="section-kicker">横向比较</span><h2>方案输出排名</h2></div><strong className="party-dpr">队伍原始 DPR {fixed(calculation.result.raw_party_dpr)}</strong></div>
        <div className="comparison-bars">{calculation.result.builds.slice().sort((a, b) => b.dpr - a.dpr).map((build) => <div className="comparison-row" key={build.id}>
          <span>{build.name}{!build.included_in_party && <small>仅比较</small>}</span><div><i style={{ width: `${build.dpr / maxDpr * 100}%` }} /></div><strong>{fixed(build.dpr)}</strong>
        </div>)}</div>
      </section>

      <section className="dm-section"><div className="analysis-heading"><div><span className="section-kicker">DM 审卡与备团</span><h2>战斗时长规划</h2>
        <p>将所有“计入 DM 队伍”的构筑视为同时完整行动的角色；未勾选的备选方案只参与比较，不参与合计。</p></div></div>
        {calculation.result.party_build_count === 0 && <div className="warning">请至少勾选一个“计入 DM 队伍”的构筑；横向比较仍然有效，但暂时无法估算战斗时长。</div>}
        <div className="dm-grid">
          <article className="panel dm-controls"><h3>怪物与实战修正</h3><div className="form-grid">
            <Field label="怪物数量"><TextInput inputMode="numeric" value={config.monster_count} onChange={(event) => update("monster_count", event.target.value)} /></Field>
            <Field label="每只怪物 HP"><TextInput inputMode="decimal" value={config.hp_each} onChange={(event) => update("hp_each", event.target.value)} /></Field>
            <Field label="队伍输出在线率" hint="移动、控制、倒地等造成的损失，建议 70%–90%"><div className="input-suffix"><TextInput inputMode="decimal" value={config.party_uptime_percent} onChange={(event) => update("party_uptime_percent", event.target.value)} /><span>%</span></div></Field>
            <Field label="伤害结算倍率" hint="普遍抗性填 0.5，易伤填 2"><SelectInput value={config.damage_multiplier} onChange={(event) => update("damage_multiplier", event.target.value)}><option value="0.5">0.5× 普遍抗性</option><option value="0.75">0.75× 部分受限</option><option value="1">1× 正常</option><option value="1.25">1.25× 部分易伤</option><option value="2">2× 普遍易伤</option></SelectInput></Field>
            <Field label="希望战斗持续轮数"><TextInput inputMode="decimal" value={config.desired_rounds} onChange={(event) => update("desired_rounds", event.target.value)} /></Field>
          </div></article>
          <article className="panel duration-card"><span>当前预计战斗时长</span><strong>{fixed(calculation.result.estimated_rounds, 2)}<small>轮</small></strong>
            <p>总 HP {fixed(calculation.result.total_monster_hp, 0)} ÷ 有效队伍 DPR {fixed(calculation.result.adjusted_party_dpr)}</p>
            <div className="duration-meter" aria-label="预计战斗轮数"><i style={{ width: `${Math.min(100, calculation.result.estimated_rounds / Math.max(1, Number(config.desired_rounds)) * 50)}%` }} /></div>
            <small>这是无治疗、无增援、无溢出浪费的基线估算。</small></article>
        </div>

        {calculation.result.party_build_count > 0 && <><div className="recommendation-grid">
          <article className="panel recommendation"><span>保持 {config.monster_count} 只怪物</span><strong>每只约 {fixed(calculation.result.suggested_hp_each, 0)} HP</strong><p>对应约 {config.desired_rounds} 轮的目标时长。</p></article>
          <article className="panel recommendation"><span>保持每只 {config.hp_each} HP</span><strong>约 {fixed(calculation.result.suggested_monster_count, 1)} 只</strong><p>实际使用整数只数后，时长会相应上下浮动。</p></article>
        </div>

        <article className="panel sensitivity-panel"><h3>AC 敏感性</h3><p>观察只改 AC 时，队伍命中率、有效 DPR 与战斗轮数如何变化。</p>
          <div className="table-scroll"><table><thead><tr><th>目标 AC</th><th>队伍原始 DPR</th><th>有效 DPR</th><th>预计轮数</th></tr></thead><tbody>
            {sensitivity.map((row) => <tr className={row.ac === targetAc ? "selected-row" : ""} key={row.ac}><td>{row.ac}</td><td>{fixed(row.result.raw_party_dpr)}</td><td>{fixed(row.result.adjusted_party_dpr)}</td><td>{fixed(row.result.estimated_rounds, 2)}</td></tr>)}
          </tbody></table></div></article></>}
      </section>
    </>}

    <aside className="analysis-notes"><h2>这个估算能说明什么</h2><ul>
      <li>适合比较同一假想目标下的构筑强弱，以及粗调怪物 AC、数量和 HP。</li>
      <li>每轮一次附伤按“第一次命中时使用”精确计入，触发重击时可选择是否翻倍骰。</li>
      <li>它不会自动计算范围伤害、控制收益、治疗、召唤物、传奇动作或击杀导致的集火溢出；这些应通过输出在线率保守修正。</li>
      <li>预计轮数是备团基线，不是遭遇难度或团灭概率评级。怪物输出仍需由 DM 单独审核。</li>
    </ul></aside>
  </main>;
}
