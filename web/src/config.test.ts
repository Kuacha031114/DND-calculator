import { beforeEach, describe, expect, it } from "vitest";
import fixtures from "../../tests/fixtures/config_compatibility.json";
import { STORAGE_KEY, defaultConfig, exportConfig, loadConfig, normalizeConfig, saveConfig } from "./config";

function expectDeepSubset(actual: unknown, expected: unknown): void {
  if (Array.isArray(expected)) {
    expect(Array.isArray(actual)).toBe(true);
    expected.forEach((value, index) => expectDeepSubset((actual as unknown[])[index], value));
  } else if (expected && typeof expected === "object") {
    expect(actual).toBeTruthy();
    for (const [key, value] of Object.entries(expected)) {
      expectDeepSubset((actual as Record<string, unknown>)[key], value);
    }
  } else {
    expect(actual).toEqual(expected);
  }
}

function blobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

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
    expect(loaded.analysis.builds).toHaveLength(2);
    expect(loaded.analysis.target_ac).toBe("15");
  });

  it("round trips analysis profiles and fills newly added profile fields", () => {
    const config = defaultConfig();
    config.analysis.target_ac = "19";
    config.analysis.builds[0].name = "圣武士长剑";
    config.analysis.builds[0].rider_dice_count = "2";
    saveConfig(config);
    const loaded = loadConfig().config;
    expect(loaded.analysis.target_ac).toBe("19");
    expect(loaded.analysis.builds[0].name).toBe("圣武士长剑");
    expect(loaded.analysis.builds[0].rider_dice_count).toBe("2");

    const partial = normalizeConfig({ config_version: 1, analysis: { builds: [{ id: "old", name: "旧方案" }] } });
    expect(partial.analysis.builds[0].damage_die_sides).toBe("8");
    expect(partial.analysis.builds[0].name).toBe("旧方案");
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

  it("matches the shared compatibility fixtures", async () => {
    for (const current of fixtures.valid_cases) {
      const normalized = normalizeConfig(current.input);
      expectDeepSubset(normalized, current.expected);
      if (current.web_export_omits) {
        const exported = JSON.parse(await blobText(exportConfig(normalized))) as Record<string, unknown>;
        for (const key of current.web_export_omits) expect(exported).not.toHaveProperty(key);
      }
    }
    for (const current of fixtures.invalid_cases) {
      expect(() => normalizeConfig(current.input)).toThrow(current.error);
    }
  });
});
