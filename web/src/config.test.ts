import { beforeEach, describe, expect, it } from "vitest";
import { STORAGE_KEY, defaultConfig, loadConfig, normalizeConfig, saveConfig } from "./config";

describe("web configuration", () => {
  beforeEach(() => localStorage.clear());

  it("round trips without losing advanced data", () => {
    const config = defaultConfig();
    config.targets[0].name = "巨龙";
    config.entries[0].rider = "偷袭";
    config.future = { keep: true };
    saveConfig(config);
    const loaded = loadConfig().config;
    expect(loaded.targets[0].name).toBe("巨龙");
    expect(loaded.entries[0].rider).toBe("偷袭");
    expect(loaded.future).toEqual({ keep: true });
  });

  it("normalizes old optional fields", () => {
    const loaded = normalizeConfig({ config_version: 1, targets: [{ id: "t", name: "目标", ac: "17" }], entries: [{ id: "e", target_id: "t" }] });
    expect(loaded.entries[0].manual_hits).toBe(false);
    expect(loaded.targets[0].saves.敏捷).toBe("0");
  });

  it("rejects unsupported versions without replacing current data", () => {
    const config = defaultConfig(); saveConfig(config);
    expect(() => normalizeConfig({ config_version: 99 })).toThrow("不支持配置版本");
    expect(localStorage.getItem(STORAGE_KEY)).toBeTruthy();
  });

  it("backs up corrupt local data", () => {
    localStorage.setItem(STORAGE_KEY, "{broken");
    const loaded = loadConfig();
    expect(loaded.warning).toContain("本地配置损坏");
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(Object.keys(localStorage).some((key) => key.startsWith(`${STORAGE_KEY}:corrupt:`))).toBe(true);
  });
});
