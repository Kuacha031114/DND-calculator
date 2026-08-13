import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { defaultAnalysis } from "../config";
import type { AnalysisBundle, AnalysisConfig, BridgeMethods, BuildResult } from "../types";
import { DamageAnalysis } from "./DamageAnalysis";

function bundleFor(config: AnalysisConfig, acs: number[]): AnalysisBundle {
  const builds: BuildResult[] = config.builds.map((build, index) => ({
    id: build.id, name: build.name, included_in_party: build.enabled,
    hit_probability: 0.55, normal_hit_probability: 0.5, critical_probability: 0.05,
    at_least_one_hit_probability: 0.7975, at_least_one_critical_probability: 0.0975,
    expected_hits: 1.1, damage_per_attack: index === 0 ? 5.75 : 5.775,
    rider_damage: 0, guaranteed_damage: 0, dpr: index === 0 ? 11.5 : 11.55,
  }));
  const raw = builds.filter((build) => build.included_in_party).reduce((sum, build) => sum + build.dpr, 0);
  const result = {
    builds, party_build_count: builds.filter((build) => build.included_in_party).length,
    raw_party_dpr: raw, adjusted_party_dpr: raw * 0.85, total_monster_hp: 40,
    estimated_rounds: raw ? 40 / (raw * 0.85) : null,
    suggested_hp_each: raw * 0.85 * 4, suggested_monster_count: raw * 0.85 * 4 / 40,
  };
  return { result, sensitivity: acs.map((ac) => ({ ac, result })) };
}

function mockBridge(): BridgeMethods {
  return {
    resolveAnalysis: vi.fn(async (config: AnalysisConfig, acs: number[]) => {
      if (!/^-?\d+$/.test(config.target_ac)) throw new Error("目标 AC 必须是整数");
      if (!/^-?\d+$/.test(config.monster_count)) throw new Error("怪物数量 必须是整数");
      return bundleFor(config, acs);
    }),
  } as unknown as BridgeMethods;
}

describe("DamageAnalysis", () => {
  it("shows async build comparison and DM duration recommendations", async () => {
    render(<DamageAnalysis config={defaultAnalysis()} onChange={() => undefined} bridge={mockBridge()} ready />);
    expect(screen.getByRole("heading", { name: "命中率与期望伤害比较器" })).toBeInTheDocument();
    expect(await screen.findByText(/队伍原始 DPR 11.5/)).toBeInTheDocument();
    expect(screen.getByText("当前预计战斗时长")).toBeInTheDocument();
    expect(screen.getByText(/每只约 39 HP/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AC 敏感性" })).toBeInTheDocument();
  });

  it("updates a build through controlled inputs", () => {
    let current = defaultAnalysis();
    const bridge = mockBridge();
    const rendered = render(<DamageAnalysis config={current} onChange={(next) => { current = next; }} bridge={bridge} ready />);
    fireEvent.change(screen.getByLabelText("方案 1 名称"), { target: { value: "战士长剑" } });
    expect(current.builds[0].name).toBe("战士长剑");
    rendered.rerender(<DamageAnalysis config={current} onChange={() => undefined} bridge={bridge} ready />);
    expect(screen.getByDisplayValue("战士长剑")).toBeInTheDocument();
  });

  it("surfaces invalid numeric input without discarding the editor", async () => {
    const config = { ...defaultAnalysis(), target_ac: "abc" };
    render(<DamageAnalysis config={config} onChange={() => undefined} bridge={mockBridge()} ready />);
    expect(await screen.findByRole("alert")).toHaveTextContent("目标 AC 必须是整数");
    expect(screen.getByRole("alert")).toHaveTextContent("所有编辑内容都已保留");
    expect(screen.getAllByText("构筑方案").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "怪物与实战修正" })).toBeInTheDocument();
    expect(screen.getByLabelText("怪物数量")).toHaveValue("1");
    expect(screen.getByText("修正输入后，这里会自动恢复结果。")).toBeInTheDocument();
  });

  it("keeps the invalid DM field mounted so it can be corrected", async () => {
    const config = { ...defaultAnalysis(), monster_count: "" };
    render(<DamageAnalysis config={config} onChange={() => undefined} bridge={mockBridge()} ready />);
    expect(await screen.findByRole("alert")).toHaveTextContent("怪物数量 必须是整数");
    expect(screen.getByLabelText("怪物数量")).toHaveValue("");
    expect(screen.queryByRole("heading", { name: "方案输出排名" })).not.toBeInTheDocument();
  });

  it("discards a stale worker response after the inputs change", async () => {
    const pending: Array<(bundle: AnalysisBundle) => void> = [];
    const bridge = { resolveAnalysis: vi.fn((config: AnalysisConfig, acs: number[]) => new Promise<AnalysisBundle>((resolve) => pending.push(() => resolve(bundleFor(config, acs))))) } as unknown as BridgeMethods;
    const first = defaultAnalysis();
    const rendered = render(<DamageAnalysis config={first} onChange={() => undefined} bridge={bridge} ready />);
    await waitFor(() => expect(bridge.resolveAnalysis).toHaveBeenCalledTimes(1));
    const second = { ...first, builds: first.builds.map((build, index) => index ? build : { ...build, name: "新方案" }) };
    rendered.rerender(<DamageAnalysis config={second} onChange={() => undefined} bridge={bridge} ready />);
    await waitFor(() => expect(bridge.resolveAnalysis).toHaveBeenCalledTimes(2));
    pending[1](bundleFor(second, [15]));
    expect(await screen.findByText("新方案")).toBeInTheDocument();
    pending[0](bundleFor(first, [15]));
    await waitFor(() => expect(screen.queryByText("常规攻击")).not.toBeInTheDocument());
  });
});
