import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { defaultConfig } from "../config";
import type { AdvancedResult, BridgeMethods } from "../types";
import { AdvancedWorkspace } from "./AdvancedWorkspace";

describe("AdvancedWorkspace", () => {
  it("always offers attack damage resolution when there are no riders", async () => {
    const started: AdvancedResult = {
      session_id: "session",
      selectable_riders: [],
      sessions: [{ mode: "attack", attack_results: [], save_results: [], damage_results: [] }],
    };
    const bridge = {
      startAdvanced: vi.fn().mockResolvedValue(started),
      resolveAttackDamage: vi.fn().mockResolvedValue(started),
    } as unknown as BridgeMethods;
    render(<AdvancedWorkspace config={defaultConfig()} onChange={() => undefined} bridge={bridge} ready />);
    fireEvent.click(screen.getByRole("button", { name: "① 投掷检定" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "③ 结算攻击伤害" })).toBeInTheDocument());
    expect(screen.getByText(/没有需要选择的附加伤害/)).toBeInTheDocument();
  });
});
