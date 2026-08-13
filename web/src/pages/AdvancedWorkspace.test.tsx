import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { defaultConfig } from "../config";
import type { AdvancedResult, BridgeMethods } from "../types";
import { AdvancedWorkspace } from "./AdvancedWorkspace";

describe("AdvancedWorkspace", () => {
  function result(sessionId: string): AdvancedResult {
    return {
      session_id: sessionId,
      attack_modifiers_resolved: true,
      selectable_attack_modifiers: [],
      selectable_riders: [],
      sessions: [{ mode: "attack", attack_results: [], save_results: [], damage_results: [] }],
    };
  }

  it("always offers attack damage resolution when there are no riders", async () => {
    const started = result("session");
    const bridge = {
      startAdvanced: vi.fn().mockResolvedValue(started),
      resolveAttackDamage: vi.fn().mockResolvedValue(started),
      disposeSession: vi.fn().mockResolvedValue({ disposed: true }),
    } as unknown as BridgeMethods;
    render(<AdvancedWorkspace config={defaultConfig()} onChange={() => undefined} bridge={bridge} ready />);
    fireEvent.click(screen.getByRole("button", { name: "① 投掷检定" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "④ 结算攻击伤害" })).toBeInTheDocument());
    expect(screen.getByText(/没有需要选择的附加伤害/)).toBeInTheDocument();
  });

  it("adds dynamic hit modifiers and keeps the last damage component", () => {
    const config = defaultConfig();
    const onChange = vi.fn();
    render(<AdvancedWorkspace config={config} onChange={onChange} bridge={{} as BridgeMethods} ready={false} />);
    fireEvent.click(screen.getByRole("button", { name: "选择一次 +1d4" }));
    const changed = onChange.mock.calls.at(-1)?.[0];
    expect(changed.entries[0].attack_modifiers[0]).toMatchObject({ scope: "once_selectable", dice_sides: "4" });
    expect(screen.getAllByRole("button", { name: "删除" }).some((button) => button.hasAttribute("disabled"))).toBe(true);
  });

  it("resolves selectable attack modifiers before showing damage riders", async () => {
    const started = result("session");
    started.attack_modifiers_resolved = false;
    started.selectable_attack_modifiers = [{
      modifier_id: "bond", name: "勇气联结", dice: { count: 1, sides: 4, sign: 1 },
      attacks: [{ attack_id: "g:0", group_id: "g", group_name: "攻击", index: 0, target_id: "t", d20_rolls: [], selected_d20: 10, total: 12, hit: false, critical: false, power_attack: false, explanation: "" }],
    }];
    const resolved = result("session");
    const bridge = {
      startAdvanced: vi.fn().mockResolvedValue(started),
      resolveAttackModifiers: vi.fn().mockResolvedValue(resolved),
      disposeSession: vi.fn().mockResolvedValue({ disposed: true }),
    } as unknown as BridgeMethods;
    render(<AdvancedWorkspace config={defaultConfig()} onChange={() => undefined} bridge={bridge} ready />);
    fireEvent.click(screen.getByRole("button", { name: "① 投掷检定" }));
    await screen.findByText(/勇气联结/);
    fireEvent.change(screen.getByLabelText(/勇气联结/), { target: { value: "g:0" } });
    fireEvent.click(screen.getByRole("button", { name: "提交命中修正" }));
    await waitFor(() => expect(bridge.resolveAttackModifiers).toHaveBeenCalledWith("session", { bond: "g:0" }));
    expect(await screen.findByRole("button", { name: "④ 结算攻击伤害" })).toBeInTheDocument();
  });

  it("disposes the previous session before starting another one", async () => {
    const bridge = {
      startAdvanced: vi.fn()
        .mockResolvedValueOnce(result("first"))
        .mockResolvedValueOnce(result("second")),
      disposeSession: vi.fn().mockResolvedValue({ disposed: true }),
    } as unknown as BridgeMethods;
    render(<AdvancedWorkspace config={defaultConfig()} onChange={() => undefined} bridge={bridge} ready />);

    fireEvent.click(screen.getByRole("button", { name: "① 投掷检定" }));
    await waitFor(() => expect(bridge.startAdvanced).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "④ 结算攻击伤害" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "① 投掷检定" }));

    await waitFor(() => expect(bridge.disposeSession).toHaveBeenCalledWith("first"));
    await waitFor(() => expect(bridge.startAdvanced).toHaveBeenCalledTimes(2));
  });

  it("disposes the active session when unmounted", async () => {
    const bridge = {
      startAdvanced: vi.fn().mockResolvedValue(result("active")),
      disposeSession: vi.fn().mockResolvedValue({ disposed: true }),
    } as unknown as BridgeMethods;
    const rendered = render(<AdvancedWorkspace config={defaultConfig()} onChange={() => undefined} bridge={bridge} ready />);
    fireEvent.click(screen.getByRole("button", { name: "① 投掷检定" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "④ 结算攻击伤害" })).toBeInTheDocument());

    rendered.unmount();

    expect(bridge.disposeSession).toHaveBeenCalledWith("active");
  });

  it("disposes a session returned after unmount without updating state", async () => {
    let resolveStart!: (value: AdvancedResult) => void;
    const pending = new Promise<AdvancedResult>((resolve) => { resolveStart = resolve; });
    const bridge = {
      startAdvanced: vi.fn().mockReturnValue(pending),
      disposeSession: vi.fn().mockResolvedValue({ disposed: true }),
    } as unknown as BridgeMethods;
    const rendered = render(<AdvancedWorkspace config={defaultConfig()} onChange={() => undefined} bridge={bridge} ready />);
    fireEvent.click(screen.getByRole("button", { name: "① 投掷检定" }));
    rendered.unmount();

    resolveStart(result("late"));

    await waitFor(() => expect(bridge.disposeSession).toHaveBeenCalledWith("late"));
  });
});
