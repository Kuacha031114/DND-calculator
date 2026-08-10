import type { AppConfig, EntryConfig, QuickConfig, TargetConfig } from "./types";

export const STORAGE_KEY = "chizhong-dnd-calculator:web:config-v1";
export const ABILITIES = ["力量", "敏捷", "体质", "智力", "感知", "魅力"] as const;
export const DAMAGE_TYPES = ["强酸", "钝击", "寒冷", "火焰", "力场", "闪电", "黯蚀", "穿刺", "毒素", "心灵", "光耀", "挥砍", "雷鸣"];

export const QUICK_DEFAULTS: QuickConfig = {
  target_ac: "15", attack_bonus: "5", attack_count: "1", roll_mode: "普通",
  crit_range: "20", power_attack: false, damage_dice_count: "1", damage_die_sides: "8",
  damage_bonus: "3", manual_hits: false, manual_hit_count: "1", manual_critical_count: "0",
};

export function id(prefix: string): string {
  const random = globalThis.crypto?.randomUUID?.().replaceAll("-", "").slice(0, 8)
    ?? Math.random().toString(16).slice(2, 10);
  return `${prefix}-${random}`;
}

export function defaultTarget(index = 1): TargetConfig {
  return {
    id: id("target"), name: `目标 ${index}`, ac: "15",
    saves: Object.fromEntries(ABILITIES.map((ability) => [ability, "0"])),
    resistances: "", vulnerabilities: "", immunities: "", nonmagical_resistances: "",
    crit_immune: false, fixed_reduction: "0",
  };
}

export function normalizeTarget(value: Partial<TargetConfig>, index = 1): TargetConfig {
  const defaults = defaultTarget(index);
  return {
    ...defaults,
    ...value,
    saves: { ...defaults.saves, ...(value.saves ?? {}) },
  } as TargetConfig;
}

export function defaultEntry(index = 1): EntryConfig {
  return {
    id: id("entry"), name: `攻击 ${index}`, mode: "attack", target_id: "", all_targets: false,
    count: "1", attack_bonus: "5", manual_hits: false, manual_hit_count: "1",
    manual_critical_count: "0", dc: "15", save_ability: "敏捷", save_outcome: "成功半伤",
    damage_name: "武器", dice_count: "1", dice_sides: "8", flat_bonus: "3",
    damage_type: "挥砍", advantage: "0", disadvantage: "0", crit_range: "20",
    elven_accuracy: false, halfling_lucky: false, power_attack: false, power_indices: "",
    weapon_die: true, magical: false, great_weapon_fighting: false, bless: false, bane: false,
    preset: "无", rider: "无", rider_dice: "1", rider_sides: "6",
  };
}

export function normalizeEntry(value: Partial<EntryConfig>, index = 1): EntryConfig {
  return { ...defaultEntry(index), ...value } as EntryConfig;
}

export function defaultConfig(): AppConfig {
  const target = defaultTarget();
  const entry = defaultEntry();
  entry.target_id = target.id;
  return {
    config_version: 1,
    quick: { ...QUICK_DEFAULTS },
    targets: [target], entries: [entry], custom_presets: {},
    onboarding_seen: false, help_expanded: false, web: { active_view: "quick" },
  };
}

export function normalizeConfig(value: unknown): AppConfig {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("配置根节点必须是对象");
  const source = value as Record<string, unknown>;
  const version = source.config_version ?? 1;
  if (version !== 1) throw new Error(`不支持配置版本 ${String(version)}，当前仅支持版本 1`);
  const rawTargets = Array.isArray(source.targets) ? source.targets : [];
  const targets = rawTargets.length
    ? rawTargets.map((target, index) => normalizeTarget(target as Partial<TargetConfig>, index + 1))
    : [defaultTarget()];
  const rawEntries = Array.isArray(source.entries) ? source.entries : [];
  const entries = rawEntries.length
    ? rawEntries.map((entry, index) => normalizeEntry(entry as Partial<EntryConfig>, index + 1))
    : [defaultEntry()];
  const targetIds = new Set(targets.map((target) => target.id));
  for (const entry of entries) if (!targetIds.has(entry.target_id)) entry.target_id = targets[0].id;
  return {
    ...source,
    config_version: 1,
    quick: { ...QUICK_DEFAULTS, ...((source.quick as Partial<QuickConfig>) ?? {}) },
    targets,
    entries,
    custom_presets: source.custom_presets && typeof source.custom_presets === "object"
      ? structuredClone(source.custom_presets as AppConfig["custom_presets"]) : {},
    web: { active_view: "quick", ...((source.web as Partial<AppConfig["web"]>) ?? {}) },
  } as AppConfig;
}

export function loadConfig(storage: Storage = localStorage): { config: AppConfig; warning?: string } {
  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) return { config: defaultConfig() };
  try {
    return { config: normalizeConfig(JSON.parse(raw)) };
  } catch (error) {
    storage.setItem(`${STORAGE_KEY}:corrupt:${new Date().toISOString()}`, raw);
    storage.removeItem(STORAGE_KEY);
    return {
      config: defaultConfig(),
      warning: `本地配置损坏，已备份并恢复默认值：${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

export function saveConfig(config: AppConfig, storage: Storage = localStorage): void {
  storage.setItem(STORAGE_KEY, JSON.stringify(config));
}

export function exportConfig(config: AppConfig): Blob {
  const payload = { ...config };
  delete payload.window;
  return new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
}

export async function importConfig(file: File): Promise<AppConfig> {
  return normalizeConfig(JSON.parse(await file.text()));
}
