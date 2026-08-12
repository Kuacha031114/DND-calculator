import { useEffect, useMemo, useRef, useState } from "react";
import { EngineBridge } from "./bridge";
import { defaultEntry, defaultTarget, exportConfig, id, importConfig, loadConfig, saveConfig } from "./config";
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
  function download() {
    const url = URL.createObjectURL(exportConfig(config));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = "config-v3.json"; anchor.click();
    URL.revokeObjectURL(url);
  }
  async function upload(file?: File) {
    if (!file) return;
    try { const next = await importConfig(file); setConfig(next); setViewState(next.web.active_view ?? "quick"); setWarning("配置导入成功，原配置已由导出文件替换。"); }
    catch (error) { setWarning(`导入失败，当前配置未改变：${error instanceof Error ? error.message : String(error)}`); }
    if (importInput.current) importInput.current.value = "";
  }
  function continueAdvanced() {
    const target = defaultTarget(config.targets.length + 1);
    target.name = "快速计算目标"; target.ac = config.quick.target_ac;
    const entry = defaultEntry(config.entries.length + 1);
    entry.id = id("entry"); entry.name = "快速攻击"; entry.target_id = target.id;
    entry.count = config.quick.attack_count; entry.attack_bonus = config.quick.attack_bonus;
    entry.crit_range = config.quick.crit_range; entry.power_attack = config.quick.power_attack;
    entry.dice_count = config.quick.damage_dice_count; entry.dice_sides = config.quick.damage_die_sides;
    entry.flat_bonus = config.quick.damage_bonus; entry.manual_hits = config.quick.manual_hits;
    entry.manual_hit_count = config.quick.manual_hit_count; entry.manual_critical_count = config.quick.manual_critical_count;
    entry.advantage = config.quick.roll_mode === "优势" ? "1" : "0";
    entry.disadvantage = config.quick.roll_mode === "劣势" ? "1" : "0";
    setConfig({ ...config, targets: [...config.targets, target], entries: [...config.entries, entry], web: { ...config.web, active_view: "advanced" } });
    setViewState("advanced"); setWarning("快速设置已追加到高级工作台，原有数据未被覆盖。");
  }

  return <div className="app-shell">
    <header className="app-header"><div className="brand"><span>⚔</span><div><strong>池中社 DND 战斗计算器</strong><small>2014 规则 · 网页离线版</small></div></div>
      <nav aria-label="主导航"><button className={view === "quick" ? "active" : ""} onClick={() => setView("quick")}>快速计算</button><button className={view === "advanced" ? "active" : ""} onClick={() => setView("advanced")}>高级工作台</button><button className={view === "analysis" ? "active" : ""} onClick={() => setView("analysis")}>强度与时长</button></nav>
      <div className="header-actions"><button onClick={() => importInput.current?.click()}>导入配置</button><button onClick={download}>导出配置</button><input ref={importInput} hidden type="file" accept="application/json,.json" onChange={(event) => upload(event.target.files?.[0])}/></div>
    </header>
    <div className={`engine-status ${engineState}`}><span className="status-dot"/>{engineMessage}{engineState === "error" && <button onClick={initialize}>重试</button>}</div>
    {warning && <div className="global-notice"><span>{warning}</span><button aria-label="关闭提示" onClick={() => setWarning("")}>×</button></div>}
    {view === "quick" ? <QuickCalculator config={config.quick} onChange={(quick) => setConfig({ ...config, quick })} bridge={bridge} ready={engineState === "ready"} onContinueAdvanced={continueAdvanced}/>
      : view === "advanced" ? <AdvancedWorkspace config={config} onChange={setConfig} bridge={bridge} ready={engineState === "ready"}/>
        : <DamageAnalysis config={config.analysis} onChange={(analysis) => setConfig({ ...config, analysis })}/>}
    <footer><span>所有数据和投骰均留在你的浏览器中</span><span>·</span><a href="https://github.com/Kuacha031114/DND-calculator">GitHub 源码</a></footer>
  </div>;
}
