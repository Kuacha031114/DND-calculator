import type { AdvancedResult, DamageResult, QuickSummary, ResolutionSession } from "../types";

function Dice({ damage }: { damage: DamageResult }) {
  return <div className="damage-breakdown">
    <div className="damage-components">
      {damage.components.map((component) => {
        const dice = component.dice.map((die) => die.rerolled ? `${die.original}→${die.value}` : String(die.value));
        const flat = component.flat_bonus ? ` ${component.flat_bonus >= 0 ? "+" : "−"} ${Math.abs(component.flat_bonus)}` : "";
        return <div className="component-result" key={component.component_id}>
          <div><strong>{component.name}</strong><span>{component.damage_type}{component.magical ? " · 魔法" : " · 非魔法"}</span></div>
          <code>{dice.length ? `${dice.length}d${component.dice[0].sides} [${dice.join("，")}]${flat}` : `固定值 ${component.flat_bonus}`} = {component.raw_total}</code>
        </div>;
      })}
    </div>
    <div className="defense-chain" aria-label="伤害防御结算链">
      <div className="defense-header"><span>伤害类型</span><span>原始</span><span>固定减伤后</span><span>豁免后</span><span>最终</span></div>
      {damage.by_type.map((item, index) => <div className="defense-row" key={`${item.damage_type}-${index}`}>
        <span><strong>{item.damage_type}</strong>{item.note && <small>{item.note}</small>}</span>
        <span>{item.raw}</span><span>{item.after_reduction}</span><span>{item.after_save}</span><strong>{item.final}</strong>
      </div>)}
    </div>
    <div className="damage-total"><span>本次最终伤害</span><strong>{damage.total}</strong></div>
  </div>;
}

function SessionResult({ session }: { session: ResolutionSession }) {
  const damageBySource = new Map(session.damage_results.map((result) => [result.source_id, result]));
  const targetName = (targetId: string) => session.targets?.find((target) => target.target_id === targetId)?.name ?? targetId;
  if (session.mode === "attack") return <div className="result-list">
    {session.attack_results.map((attack) => <article className="roll-row" key={attack.attack_id}>
      <div><strong>第 {attack.index + 1} 次</strong><span className={attack.critical ? "crit" : attack.hit ? "hit" : "miss"}>
        {attack.critical ? "★ 重击" : attack.hit ? "✔ 命中" : "✘ 未命中"}
      </span></div>
      <p>{attack.explanation}</p>
      {damageBySource.has(attack.attack_id) && <Dice damage={damageBySource.get(attack.attack_id)!} />}
    </article>)}
  </div>;
  if (session.mode === "save") return <div className="result-list">
    {session.save_results.map((save) => {
      const damage = session.damage_results.find((item) => item.target_id === save.target_id);
      return <article className="roll-row" key={save.target_id}>
        <div><strong>{targetName(save.target_id)}</strong><span className={save.succeeded ? "hit" : "miss"}>{save.succeeded ? "豁免成功" : "豁免失败"}</span></div>
        <p>d20 {save.d20} {save.bonus >= 0 ? "+" : ""}{save.bonus} = {save.total}</p>
        {damage && <Dice damage={damage} />}
      </article>;
    })}
  </div>;
  return <div className="result-list">{session.damage_results.map((damage) => <article className="roll-row" key={damage.source_id}>
    <strong>{targetName(damage.target_id)}</strong><Dice damage={damage} />
  </article>)}</div>;
}

export function QuickResults({ summary, stale }: { summary: QuickSummary; stale: boolean }) {
  return <section className={`panel results-panel ${stale ? "stale" : ""}`} aria-live="polite">
    {stale && <div className="warning">输入已经改变，当前结果已过期，请重新结算。</div>}
    <div className="summary-grid">
      <div><span>命中</span><strong>{summary.hit_count}/{summary.attack_count}</strong></div>
      <div><span>重击</span><strong>{summary.critical_count}</strong></div>
      <div><span>总伤害</span><strong>{summary.total_damage}</strong></div>
    </div>
    <details><summary>查看每次投掷明细</summary><SessionResult session={summary.session} /></details>
  </section>;
}

export function AdvancedResults({ result }: { result: AdvancedResult }) {
  return <section className="panel results-panel"><h2>结算结果</h2>
    {result.sessions.map((session, index) => <SessionResult session={session} key={`${session.mode}-${index}`} />)}
  </section>;
}
