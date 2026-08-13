import type { AnalysisConfig, AppConfig, AttackModifierConfig, BuildProfile, DamageComponentConfig, EntryConfig, QuickConfig, TargetConfig } from "./types";

export const STORAGE_KEY = "chizhong-dnd-calculator:web:config-v1";
export const IMPORT_BACKUP_PREFIX = `${STORAGE_KEY}:before-import:`;
export const ABILITIES = ["力量", "敏捷", "体质", "智力", "感知", "魅力"] as const;
export const DAMAGE_TYPES = ["强酸", "钝击", "寒冷", "火焰", "力场", "闪电", "黯蚀", "穿刺", "毒素", "心灵", "光耀", "挥砍", "雷鸣"];

export const QUICK_DEFAULTS: QuickConfig = {
  target_ac: "15", attack_bonus: "5", attack_count: "1", roll_mode: "普通",
  crit_range: "20", power_attack: false, damage_dice_count: "1", damage_die_sides: "8",
  damage_bonus: "3", manual_hits: false, manual_hit_count: "1", manual_critical_count: "0",
};

export function defaultBuild(index = 1): BuildProfile {
  return {
    id: id("build"), name: index === 1 ? "常规攻击" : `方案 ${index}`, enabled: true,
    attack_bonus: "7", attacks_per_round: "2", roll_mode: "normal", crit_range: "20",
    damage_dice_count: "1", damage_die_sides: "8", damage_bonus: "4", power_attack: false,
    crit_extra_dice: "0", rider_dice_count: "0", rider_die_sides: "6", rider_bonus: "0",
    rider_doubles_on_crit: true, guaranteed_damage: "0",
  };
}

export function defaultAnalysis(): AnalysisConfig {
  const regular = defaultBuild(1);
  const power = { ...defaultBuild(2), name: "减 5 加 10", enabled: false, power_attack: true };
  return {
    target_ac: "15", monster_count: "1", hp_each: "40", party_uptime_percent: "85",
    damage_multiplier: "1", desired_rounds: "4", builds: [regular, power],
  };
}

export function normalizeAnalysis(value: unknown): AnalysisConfig {
  const defaults = defaultAnalysis();
  if (!value || typeof value !== "object" || Array.isArray(value)) return defaults;
  const source = value as Partial<AnalysisConfig>;
  const builds = Array.isArray(source.builds) && source.builds.length
    ? source.builds.map((build, index) => ({ ...defaultBuild(index + 1), ...build, id: build.id || id("build") }))
    : defaults.builds;
  return { ...defaults, ...source, builds };
}

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
  const entryId = id("entry");
  return {
    id: entryId, name: `攻击 ${index}`, mode: "attack", target_id: "", all_targets: false,
    count: "1", attack_bonus: "5", manual_hits: false, manual_hit_count: "1",
    manual_critical_count: "0", dc: "15", save_ability: "敏捷", save_outcome: "成功半伤",
    attack_modifiers: [], damage_components: [defaultDamageComponent(`${entryId}:damage`)],
    advantage: "0", disadvantage: "0", crit_range: "20",
    elven_accuracy: false, halfling_lucky: false, power_attack: false, power_indices: "",
    great_weapon_fighting: false, preset: "无",
  };
}

export function defaultAttackModifier(prefix = "modifier"): AttackModifierConfig {
  return { id: id(prefix), name: "命中修正", dice_count: "1", dice_sides: "4", sign: "1", scope: "every_attack" };
}

export function defaultDamageComponent(prefix = "damage"): DamageComponentConfig {
  return {
    id: id(prefix), name: "武器", dice_count: "1", dice_sides: "8", flat_bonus: "3",
    damage_type: "挥砍", scope: "every_hit", crit_behavior: "double_dice", weapon_die: true, magical: false,
  };
}

function legacyAttackModifiers(value: Record<string, unknown>, entryId: string): { modifiers: AttackModifierConfig[]; preset: string } {
  const modifiers: AttackModifierConfig[] = [];
  const add = (suffix: string, name: string, sign: "1" | "-1") => modifiers.push({
    ...defaultAttackModifier(), id: `${entryId}:legacy-${suffix}`, name, sign,
  });
  if (value.bless) add("bless", "祝福术", "1");
  if (value.bane) add("bane", "灾祸术", "-1");
  let preset = String(value.preset ?? "无");
  if (preset === "祝福术 +1d4") { add("preset-bless", "祝福术（预设）", "1"); preset = "无"; }
  if (preset === "灾祸术 -1d4") { add("preset-bane", "灾祸术（预设）", "-1"); preset = "无"; }
  return { modifiers, preset };
}

function legacyDamageComponents(value: Record<string, unknown>, entryId: string): DamageComponentConfig[] {
  const damageType = String(value.damage_type ?? "挥砍");
  const output: DamageComponentConfig[] = [{
    ...defaultDamageComponent(), id: `${entryId}:base`, name: String(value.damage_name ?? "伤害"),
    dice_count: String(value.dice_count ?? "1"), dice_sides: String(value.dice_sides ?? "8"),
    flat_bonus: String(value.flat_bonus ?? "0"), damage_type: damageType,
    weapon_die: value.weapon_die === undefined ? true : Boolean(value.weapon_die), magical: Boolean(value.magical),
  }];
  const rider = String(value.rider ?? "无");
  if (rider === "无") return output;
  const critOnly = rider === "凶蛮攻击" || rider === "野蛮重击";
  output.push({
    ...defaultDamageComponent(), id: `${entryId}:legacy-rider`, name: rider,
    dice_count: String(value.rider_dice ?? "1"), dice_sides: String(value.rider_sides ?? "6"), flat_bonus: "0",
    damage_type: rider === "至圣斩" ? "光耀" : damageType,
    scope: critOnly ? "crit_only" : rider === "偷袭" ? "once_selectable" : "selected_hits",
    crit_behavior: critOnly ? "normal" : "double_dice", weapon_die: critOnly,
    magical: rider === "至圣斩" ? true : Boolean(value.magical),
  });
  return output;
}

export function normalizeEntry(value: Partial<EntryConfig> & Record<string, unknown>, index = 1, sourceVersion = 2): EntryConfig {
  const defaults = defaultEntry(index);
  const entryId = String(value.id || defaults.id);
  const legacy = sourceVersion === 1 ? legacyAttackModifiers(value, entryId) : undefined;
  const rawModifiers = sourceVersion === 1 ? legacy!.modifiers : Array.isArray(value.attack_modifiers) ? value.attack_modifiers : [];
  const rawDamages = sourceVersion === 1 ? legacyDamageComponents(value, entryId) : Array.isArray(value.damage_components) && value.damage_components.length ? value.damage_components : defaults.damage_components;
  const normalized = {
    ...defaults, ...value, id: entryId, preset: legacy?.preset ?? String(value.preset ?? "无"),
    attack_modifiers: rawModifiers.map((item) => ({ ...defaultAttackModifier(`${entryId}:modifier`), ...item, id: item.id || id(`${entryId}:modifier`) })),
    damage_components: rawDamages.map((item) => ({ ...defaultDamageComponent(`${entryId}:damage`), ...item, id: item.id || id(`${entryId}:damage`) })),
  } as EntryConfig & Record<string, unknown>;
  for (const key of [
    "bless", "bane", "damage_name", "dice_count", "dice_sides", "flat_bonus",
    "damage_type", "weapon_die", "magical", "rider", "rider_dice", "rider_sides",
  ]) delete normalized[key];
  return normalized;
}

function normalizePreset(value: Record<string, unknown>, name: string, sourceVersion: number): Partial<EntryConfig> {
  const { id: _id, name: _name, target_id: _target, preset: _preset, ...rest } = normalizeEntry({ id: `preset-${name}`, ...value }, 1, sourceVersion);
  return rest;
}

export function defaultConfig(): AppConfig {
  const target = defaultTarget();
  const entry = defaultEntry();
  entry.target_id = target.id;
  return {
    config_version: 2,
    quick: { ...QUICK_DEFAULTS },
    targets: [target], entries: [entry], custom_presets: {}, analysis: defaultAnalysis(),
    onboarding_seen: false, help_expanded: false,
    web: { active_view: "quick", onboarding_seen: false, help_expanded: false },
  };
}

export function normalizeConfig(value: unknown): AppConfig {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("配置根节点必须是对象");
  const source = value as Record<string, unknown>;
  const version = Number(source.config_version ?? 1);
  if (version !== 1 && version !== 2) throw new Error(`不支持配置版本 ${String(version)}，当前仅支持版本 1 或 2`);
  const rawTargets = Array.isArray(source.targets) ? source.targets : [];
  const targets = rawTargets.length
    ? rawTargets.map((target, index) => normalizeTarget(target as Partial<TargetConfig>, index + 1))
    : [defaultTarget()];
  const rawEntries = Array.isArray(source.entries) ? source.entries : [];
  const entries = rawEntries.length
    ? rawEntries.map((entry, index) => normalizeEntry(entry as Partial<EntryConfig> & Record<string, unknown>, index + 1, version))
    : [defaultEntry()];
  const targetIds = new Set(targets.map((target) => target.id));
  for (const entry of entries) if (!targetIds.has(entry.target_id)) entry.target_id = targets[0].id;
  return {
    ...source,
    config_version: 2,
    quick: { ...QUICK_DEFAULTS, ...((source.quick as Partial<QuickConfig>) ?? {}) },
    targets,
    entries,
    custom_presets: source.custom_presets && typeof source.custom_presets === "object"
      ? Object.fromEntries(Object.entries(source.custom_presets as Record<string, Record<string, unknown>>).map(([name, preset]) => [name, normalizePreset(preset, name, version)])) : {},
    analysis: normalizeAnalysis(source.analysis),
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

export function backupBeforeImport(
  config: AppConfig,
  storage: Storage = localStorage,
  now: Date = new Date(),
): string {
  const key = `${IMPORT_BACKUP_PREFIX}${now.toISOString()}`;
  storage.setItem(key, JSON.stringify(config));
  return key;
}

export function exportConfig(config: AppConfig): Blob {
  const payload = portableConfig(config);
  return new Blob([JSON.stringify(payload, null, 2) + "\n"], { type: "application/json" });
}

export function portableConfig(config: AppConfig): AppConfig {
  const payload = structuredClone(config);
  delete payload.window;
  payload.config_version = 2;
  return payload;
}

export async function importConfig(file: File): Promise<AppConfig> {
  const text = typeof file.text === "function" ? await file.text() : await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("无法读取配置文件"));
    reader.readAsText(file);
  });
  return normalizeConfig(JSON.parse(text));
}
