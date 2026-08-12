import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { defaultAnalysis } from "../config";
import { DamageAnalysis } from "./DamageAnalysis";

describe("DamageAnalysis", () => {
  it("shows build comparison and DM duration recommendations", () => {
    render(<DamageAnalysis config={defaultAnalysis()} onChange={() => undefined} />);
    expect(screen.getByRole("heading", { name: "命中率与期望伤害比较器" })).toBeInTheDocument();
    expect(screen.getByText(/队伍原始 DPR 11.5/)).toBeInTheDocument();
    expect(screen.getByText("当前预计战斗时长")).toBeInTheDocument();
    expect(screen.getByText(/每只约 39 HP/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AC 敏感性" })).toBeInTheDocument();
  });

  it("updates a build through controlled inputs", () => {
    let current = defaultAnalysis();
    const rendered = render(<DamageAnalysis config={current} onChange={(next) => { current = next; }} />);
    fireEvent.change(screen.getByLabelText("方案 1 名称"), { target: { value: "战士长剑" } });
    expect(current.builds[0].name).toBe("战士长剑");
    rendered.rerender(<DamageAnalysis config={current} onChange={() => undefined} />);
    expect(screen.getByDisplayValue("战士长剑")).toBeInTheDocument();
  });

  it("surfaces invalid numeric input without discarding the editor", () => {
    const config = { ...defaultAnalysis(), target_ac: "abc" };
    render(<DamageAnalysis config={config} onChange={() => undefined} />);
    expect(screen.getByRole("alert")).toHaveTextContent("目标 AC 必须是整数");
    expect(screen.getAllByText("构筑方案").length).toBeGreaterThan(0);
  });
});
