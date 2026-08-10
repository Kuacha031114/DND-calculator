import type { AdvancedResult, DamageResult, QuickSummary, ResolutionSession } from "../types";

function Dice({ damage }: { damage: DamageResult }) {
  return <div className="damage-detail">
    {damage.components.map((component) => <span key={component.component_id}>
      {component.name}（{component.dice.map((die) => die.rerolled ? `${die.original}→${die.value}` : die.value).join("，") || "固定值"}）
    </span>)}
    <strong>= {damage.total}</strong>
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
