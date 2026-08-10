import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QUICK_DEFAULTS } from "../config";
import type { BridgeMethods } from "../types";
import { QuickCalculator } from "./QuickCalculator";

describe("QuickCalculator", () => {
  it("resolves and marks a changed result stale", async () => {
    const resolveQuick = vi.fn().mockResolvedValue({ attack_count: 1, hit_count: 1, critical_count: 0, total_damage: 9, session: { mode: "attack", attack_results: [], save_results: [], damage_results: [] } });
    const bridge = { resolveQuick } as unknown as BridgeMethods;
    let current = { ...QUICK_DEFAULTS };
    const { rerender } = render(<QuickCalculator config={current} onChange={(next) => { current = next; }} bridge={bridge} ready onContinueAdvanced={() => undefined}/>);
    fireEvent.click(screen.getByRole("button", { name: "立即结算" }));
    await waitFor(() => expect(screen.getByText("9")).toBeInTheDocument());
    current = { ...current, attack_bonus: "6" };
    rerender(<QuickCalculator config={current} onChange={() => undefined} bridge={bridge} ready onContinueAdvanced={() => undefined}/>);
    expect(screen.getByText(/当前结果已过期/)).toBeInTheDocument();
  });

  it("validates manual critical count before calling Python", async () => {
    const resolveQuick = vi.fn();
    const bridge = { resolveQuick } as unknown as BridgeMethods;
    render(<QuickCalculator config={{ ...QUICK_DEFAULTS, manual_hits: true, attack_count: "2", manual_hit_count: "1", manual_critical_count: "2" }} onChange={() => undefined} bridge={bridge} ready onContinueAdvanced={() => undefined}/>);
    fireEvent.click(screen.getByRole("button", { name: "立即结算" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("重击次数必须在 0 到 1 之间");
    expect(resolveQuick).not.toHaveBeenCalled();
  });
});
