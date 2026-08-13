import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { QuickSummary } from "../types";
import { QuickResults } from "./Results";

describe("detailed damage results", () => {
  it("shows every component and the complete defense chain", () => {
    const summary: QuickSummary = {
      attack_count: 1, hit_count: 1, critical_count: 0, total_damage: 5,
      session: {
        mode: "attack", save_results: [],
        attack_results: [{
          attack_id: "a", group_id: "g", group_name: "攻击", index: 0, target_id: "t",
          d20_rolls: [{ original: 15, value: 15, rerolled: false }], selected_d20: 15,
          total: 20, hit: true, critical: false, power_attack: false, explanation: "15 + 5 = 20，命中",
        }],
        damage_results: [{
          source_id: "a", target_id: "t", critical: false, total: 5,
          components: [
            { component_id: "weapon", name: "长剑", damage_type: "挥砍", magical: false, dice: [{ sides: 8, value: 6, original: null, rerolled: false }], flat_bonus: 3, raw_total: 9 },
            { component_id: "smite", name: "至圣斩", damage_type: "光耀", magical: true, dice: [{ sides: 8, value: 4, original: 1, rerolled: true }], flat_bonus: 0, raw_total: 4 },
          ],
          by_type: [
            { damage_type: "挥砍", raw: 9, after_reduction: 7, after_save: 7, final: 3, note: "固定减伤 2、抗性" },
            { damage_type: "光耀", raw: 4, after_reduction: 4, after_save: 2, final: 2, note: "豁免成功半伤、魔法" },
          ],
        }],
      },
    };
    render(<QuickResults summary={summary} stale={false} />);
    screen.getByText("查看每次投掷明细").click();
    expect(screen.getByText("长剑")).toBeInTheDocument();
    expect(screen.getByText(/1d8 \[6\] \+ 3 = 9/)).toBeInTheDocument();
    expect(screen.getByText(/1d8 \[1→4\] = 4/)).toBeInTheDocument();
    expect(screen.getByText("固定减伤后")).toBeInTheDocument();
    expect(screen.getByText("豁免后")).toBeInTheDocument();
    expect(screen.getByText("固定减伤 2、抗性")).toBeInTheDocument();
    expect(screen.getByText("豁免成功半伤、魔法")).toBeInTheDocument();
  });
});
