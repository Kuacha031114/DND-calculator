import { useEffect, useMemo, useRef, useState } from "react";
import { EngineBridge } from "./bridge";
import {
  backupBeforeImport,
  defaultEntry,
  defaultTarget,
  exportConfig,
  id,
  importConfig,
  loadConfig,
  saveConfig,
} from "./config";
import { AdvancedWorkspace } from "./pages/AdvancedWorkspace";
import { DamageAnalysis } from "./pages/DamageAnalysis";
import { QuickCalculator } from "./pages/QuickCalculator";
import type { AppConfig, ViewName } from "./types";

export default function App() {
  const initial = useMemo(() => loadConfig(), []);
  const [config, setConfig] = useState<AppConfig>(initial.config);
  const [view, setViewState] = useState<ViewName>(initial.config.web.active_view ?? "quick");
  const [engineState, setEngineState] = useState<"loading" | "ready" | "error">("loading");
  const [engineMessage, setEngineMessage] = useState("正在下载离线规则引擎，首次加载需要一点时间…");
  const [warning, setWarning] = useState(initial.warning ?? "");
  const [undoImport, setUndoImport] = useState<AppConfig | null>(null);
  const bridge = useMemo(() => new EngineBridge(), []);
  const importInput = useRef<HTMLInputElement>(null);

  function initialize() {
    setEngineState("loading"); setEngineMessage("正在下载离线规则引擎，首次加载需要一点时间…");
    bridge.init().then((data) => { setEngineState("ready"); setEngineMessage(`规则引擎 v${data.version} 已就绪 · 计算只在本机进行`); })
      .catch((error) => { setEngineState("error"); setEngineMessage(error instanceof Error ? error.message : String(error)); });
  }
  useEffect(() => { initialize(); return () => bridge.terminate(); }, [bridge]);
  useEffect(() => { const handle = window.setTimeout(() => saveConfig(config), 300); return () => window.clearTimeout(handle); }, [config]);

  function setView(next: ViewName) {
    setViewState(next); setConfig((current) => ({ ...current, web: { ...current.web, active_view: next } }));
  }
  function patchWeb(values: Partial<AppConfig["web"]>) {
    setConfig((current) => ({ ...current, web: { ...current.web, ...values } }));
  }
  function download() {
    const url = URL.createObjectURL(exportConfig(config));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "config-v3.json"; anchor.click();
    URL.revokeObjectURL(url);
  }
  async function upload(file?: File) {
    if (!file) return;
    try {
      const next = await importConfig(file);
      const confirmed = window.confirm("导入会完整替换当前配置，不会合并。继续前会自动创建本地备份。是否继续？");
      if (!confirmed) {
        setWarning("已取消导入，当前配置未改变。");
        return;
      }
      const previous = structuredClone(config);
      backupBeforeImport(previous);
      setUndoImport(previous);
      setConfig(next);
      setViewState(next.web.active_view ?? "quick");
      setWarning("配置导入成功，原配置已备份并由导入文件完整替换。");
    }
    catch (error) { setWarning(`导入失败，当前配置未改变：${error instanceof Error ? error.message : String(error)}`); }
    finally { if (importInput.current) importInput.current.value = ""; }
  }
  function restoreImport() {
    if (!undoImport) return;
    const previous = structuredClone(undoImport);
    setConfig(previous);
    setViewState(previous.web.active_view ?? "quick");
    setUndoImport(null);
    setWarning("已撤销本次导入，并恢复导入前的完整配置。");
  }
  function continueAdvanced() {
    const target = defaultTarget(config.targets.length + 1);
    target.name = "快速计算目标"; target.ac = config.quick.target_ac;
    const entry = defaultEntry(config.entries.length + 1);
    entry.id = id("entry"); entry.name = "快速攻击"; entry.target_id = target.id;
    entry.count = config.quick.attack_count; entry.attack_bonus = config.quick.attack_bonus;
    entry.crit_range = config.quick.crit_range; entry.power_attack = config.quick.power_attack;
    entry.damage_components[0] = {
      ...entry.damage_components[0], dice_count: config.quick.damage_dice_count,
      dice_sides: config.quick.damage_die_sides, flat_bonus: config.quick.damage_bonus,
    };
    entry.manual_hits = config.quick.manual_hits;
    entry.manual_hit_count = config.quick.manual_hit_count; entry.manual_critical_count = config.quick.manual_critical_count;
    entry.advantage = config.quick.roll_mode === "优势" ? "1" : "0";
    entry.disadvantage = config.quick.roll_mode === "劣势" ? "1" : "0";
    setConfig({ ...config, targets: [...config.targets, target], entries: [...config.entries, entry], web: { ...config.web, active_view: "advanced" } });
    setViewState("advanced"); setWarning("快速设置已追加到高级工作台，原有数据未被覆盖。");
  }

  return <div className="app-shell">
    <header className="app-header"><div className="brand"><span>⚔</span><div><strong>池中社 DND 战斗计算器</strong><small>2014 规则 · 网页离线版</small></div></div>
      <nav aria-label="主导航"><button className={view === "quick" ? "active" : ""} onClick={() => setView("quick")}>快速计算</button><button className={view === "advanced" ? "active" : ""} onClick={() => setView("advanced")}>高级工作台</button><button className={view === "analysis" ? "active" : ""} onClick={() => setView("analysis")}>强度与时长</button></nav>
      <div className="header-actions"><button onClick={() => patchWeb({ help_expanded: true })}>使用帮助</button><button onClick={() => importInput.current?.click()}>导入配置</button><button onClick={download}>导出配置</button><input ref={importInput} hidden type="file" accept="application/json,.json" onChange={(event) => upload(event.target.files?.[0])}/></div>
    </header>
    <div className={`engine-status ${engineState}`}><span className="status-dot"/>{engineMessage}{engineState === "error" && <button onClick={initialize}>重试</button>}</div>
    {warning && <div className="global-notice"><span>{warning}</span>{undoImport && <button className="notice-action" onClick={restoreImport}>撤销本次导入</button>}<button aria-label="关闭提示" onClick={() => setWarning("")}>×</button></div>}
    {!config.web.onboarding_seen && <Onboarding onClose={() => patchWeb({ onboarding_seen: true })} />}
    {Boolean(config.web.help_expanded) && <HelpOverlay view={view} onClose={() => patchWeb({ help_expanded: false })} />}
    {view === "quick" ? <QuickCalculator config={config.quick} onChange={(quick) => setConfig({ ...config, quick })} bridge={bridge} ready={engineState === "ready"} onContinueAdvanced={continueAdvanced}/>
      : view === "advanced" ? <AdvancedWorkspace config={config} onChange={setConfig} bridge={bridge} ready={engineState === "ready"}/>
        : <DamageAnalysis config={config.analysis} onChange={(analysis) => setConfig({ ...config, analysis })} bridge={bridge} ready={engineState === "ready"}/>}
    <footer><span>所有数据和投骰均留在你的浏览器中</span><span>·</span><a href="https://github.com/Kuacha031114/DND-calculator">GitHub 源码</a></footer>
  </div>;
}

function Onboarding({ onClose }: { onClose(): void }) {
  return <div className="modal-backdrop" role="presentation"><section className="help-modal onboarding-modal" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
    <span className="eyebrow">欢迎使用 3.2.0</span><h1 id="onboarding-title">从一次攻击，到整场遭遇</h1>
    <p>三个页面共用同一套 Python 规则。配置和投骰只保存在本机，也可以导出后在桌面版继续。</p>
    <div className="onboarding-grid"><article><strong>快速计算</strong><span>三步完成普通攻击，适合桌边临时结算。</span></article><article><strong>高级工作台</strong><span>处理多命中骰、多伤害组件、抗性和选择性附伤。</span></article><article><strong>强度与时长</strong><span>比较构筑 DPR，并反推怪物数量、HP 和预计轮数。</span></article></div>
    <p className="help-note">导入配置会先备份，再完整替换；导入后可在当前会话一键撤销。</p>
    <button className="primary" autoFocus onClick={onClose}>开始使用</button>
  </section></div>;
}

function HelpOverlay({ view, onClose }: { view: ViewName; onClose(): void }) {
  return <div className="modal-backdrop" role="presentation"><section className="help-modal" role="dialog" aria-modal="true" aria-labelledby="help-title">
    <header><div><span className="eyebrow">规则与操作</span><h1 id="help-title">使用帮助</h1></div><button aria-label="关闭帮助" onClick={onClose}>×</button></header>
    {view === "quick" && <article><h2>快速计算</h2><ol><li>填写目标 AC，或勾选手动命中并直接填写命中、重击次数。</li><li>填写命中加值、攻击次数、优势或劣势；“减 5 加 10”会同时修改命中和伤害。</li><li>填写每次命中的伤害骰与固定值，点击立即结算。修改输入后旧结果会标记为过期。</li></ol><p className="help-note">需要祝福术、勇气联结、至圣斩、抗性或多个目标时，请转到高级工作台。</p></article>}
    {view === "advanced" && <article><h2>高级工作台流程</h2><ol><li>建立目标和结算条目，配置命中修正骰与伤害组件。</li><li>投掷基础检定；“每次攻击”修正自动加入。</li><li>为“结算中选择一次”的命中修正选择某次攻击，或选择不使用，然后提交。</li><li>为至圣斩等选择性伤害指定命中，最后结算并查看逐类型防御链。</li></ol><h3>复杂字段</h3><dl><dt>作用范围</dt><dd>“选择一次”整组最多一个命中，“选择任意命中”可勾选多个，“仅重击”自动加入重击。</dd><dt>重击规则</dt><dd>只决定该组件的伤害骰是否翻倍；固定值永不翻倍。</dd><dt>武器骰 / 魔法伤害</dt><dd>武器骰会受重武器战斗风格影响；魔法伤害可绕过仅针对非魔法伤害的抗性。</dd></dl></article>}
    {view === "analysis" && <article><h2>强度与时长</h2><ol><li>所有构筑对同一 AC 计算，未勾选的构筑只比较、不加入队伍 DPR。</li><li>输出在线率用于估算移动、控制和倒地造成的损失；伤害倍率用于整体近似抗性或易伤。</li><li>预计轮数是备团基线，不代表遭遇难度或团灭概率。</li></ol></article>}
    <article><h2>配置安全</h2><p>导出会保留分析方案、动态列表和未知扩展字段，但去除桌面窗口尺寸。未来版本配置会被明确拒绝，不会覆盖当前数据。</p></article>
    <button className="primary" onClick={onClose}>知道了</button>
  </section></div>;
}
