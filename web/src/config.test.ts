import { beforeEach, describe, expect, it } from "vitest";
import fixtures from "../../tests/fixtures/config_compatibility.json";
import {
  IMPORT_BACKUP_PREFIX,
  STORAGE_KEY,
  backupBeforeImport,
  defaultConfig,
  exportConfig,
  loadConfig,
  normalizeConfig,
  saveConfig,
} from "./config";

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
    config.entries[0].damage_components.push({
      id: "sneak", name: "偷袭", dice_count: "3", dice_sides: "6", flat_bonus: "0",
      damage_type: "穿刺", scope: "once_selectable", crit_behavior: "double_dice", weapon_die: false, magical: false,
    });
    config.future = { keep: true };
    saveConfig(config);
    const loaded = loadConfig().config;
    expect(loaded.targets[0].name).toBe("巨龙");
    expect(loaded.entries[0].damage_components[1].name).toBe("偷袭");
    expect(loaded.future).toEqual({ keep: true });
  });

  it("normalizes old optional fields", () => {
    const loaded = normalizeConfig({ config_version: 1, targets: [{ id: "t", name: "目标", ac: "17" }], entries: [{ id: "e", target_id: "t" }] });
    expect(loaded.entries[0].manual_hits).toBe(false);
    expect(loaded.targets[0].saves.敏捷).toBe("0");
    expect(loaded.analysis.builds).toHaveLength(2);
    expect(loaded.analysis.target_ac).toBe("15");
  });

  it("migrates v1 hit dice and riders to config version 2", () => {
    const loaded = normalizeConfig({
      config_version: 1,
      entries: [{ id: "legacy", bless: true, preset: "祝福术 +1d4", rider: "至圣斩", rider_dice: "2", rider_sides: "8" }],
    });
    expect(loaded.config_version).toBe(2);
    expect(loaded.entries[0].attack_modifiers.map((item) => item.name)).toEqual(["祝福术", "祝福术（预设）"]);
    expect(loaded.entries[0].damage_components[1]).toMatchObject({ name: "至圣斩", scope: "selected_hits", damage_type: "光耀" });
    expect(loaded.entries[0]).not.toHaveProperty("bless");
    expect(loaded.entries[0]).not.toHaveProperty("rider");
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

  it("creates a timestamped import backup without changing the active config", () => {
    const config = defaultConfig();
    config.future = { keep: true };
    saveConfig(config);
    const key = backupBeforeImport(config, localStorage, new Date("2026-08-13T02:03:04.000Z"));
    expect(key).toBe(`${IMPORT_BACKUP_PREFIX}2026-08-13T02:03:04.000Z`);
    expect(JSON.parse(localStorage.getItem(key)!)).toMatchObject({ future: { keep: true } });
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toMatchObject({ future: { keep: true } });
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
