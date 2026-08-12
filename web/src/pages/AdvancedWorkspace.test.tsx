import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { defaultConfig } from "../config";
import type { AdvancedResult, BridgeMethods } from "../types";
import { AdvancedWorkspace } from "./AdvancedWorkspace";

describe("AdvancedWorkspace", () => {
  function result(sessionId: string): AdvancedResult {
    return {
      session_id: sessionId,
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
    await waitFor(() => expect(screen.getByRole("button", { name: "③ 结算攻击伤害" })).toBeInTheDocument());
    expect(screen.getByText(/没有需要选择的附加伤害/)).toBeInTheDocument();
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
    await waitFor(() => expect(screen.getByRole("button", { name: "③ 结算攻击伤害" })).toBeInTheDocument());
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
    await waitFor(() => expect(screen.getByRole("button", { name: "③ 结算攻击伤害" })).toBeInTheDocument());

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
