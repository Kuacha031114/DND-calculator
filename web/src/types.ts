export type ViewName = "quick" | "advanced" | "analysis";
export type RollMode = "normal" | "advantage" | "disadvantage";

export type AnalysisRollMode = RollMode | "elven_accuracy";

export interface BuildProfile {
  id: string;
  name: string;
  enabled: boolean;
  attack_bonus: string;
  attacks_per_round: string;
  roll_mode: AnalysisRollMode;
  crit_range: string;
  damage_dice_count: string;
  damage_die_sides: string;
  damage_bonus: string;
  power_attack: boolean;
  crit_extra_dice: string;
  rider_dice_count: string;
  rider_die_sides: string;
  rider_bonus: string;
  rider_doubles_on_crit: boolean;
  guaranteed_damage: string;
}

export interface AnalysisConfig {
  target_ac: string;
  monster_count: string;
  hp_each: string;
  party_uptime_percent: string;
  damage_multiplier: string;
  desired_rounds: string;
  builds: BuildProfile[];
}

export interface BuildResult {
  id: string; name: string; included_in_party: boolean;
  hit_probability: number; normal_hit_probability: number; critical_probability: number;
  at_least_one_hit_probability: number; at_least_one_critical_probability: number;
  expected_hits: number; damage_per_attack: number; rider_damage: number;
  guaranteed_damage: number; dpr: number;
}

export interface EncounterResult {
  builds: BuildResult[]; party_build_count: number; raw_party_dpr: number;
  adjusted_party_dpr: number; total_monster_hp: number; estimated_rounds: number | null;
  suggested_hp_each: number; suggested_monster_count: number;
}

export interface AnalysisBundle {
  result: EncounterResult;
  sensitivity: Array<{ ac: number; result: EncounterResult }>;
}

export interface QuickConfig {
  target_ac: string;
  attack_bonus: string;
  attack_count: string;
  roll_mode: string;
  crit_range: string;
  power_attack: boolean;
  damage_dice_count: string;
  damage_die_sides: string;
  damage_bonus: string;
  manual_hits: boolean;
  manual_hit_count: string;
  manual_critical_count: string;
}

export interface TargetConfig {
  id: string;
  name: string;
  ac: string;
  saves: Record<string, string>;
  resistances: string;
  vulnerabilities: string;
  immunities: string;
  nonmagical_resistances: string;
  crit_immune: boolean;
  fixed_reduction: string;
  [key: string]: unknown;
}

export interface EntryConfig {
  id: string;
  name: string;
  mode: "attack" | "save" | "auto";
  target_id: string;
  all_targets: boolean;
  count: string;
  attack_bonus: string;
  manual_hits: boolean;
  manual_hit_count: string;
  manual_critical_count: string;
  dc: string;
  save_ability: string;
  save_outcome: string;
  attack_modifiers: AttackModifierConfig[];
  damage_components: DamageComponentConfig[];
  advantage: string;
  disadvantage: string;
  crit_range: string;
  elven_accuracy: boolean;
  halfling_lucky: boolean;
  power_attack: boolean;
  power_indices: string;
  great_weapon_fighting: boolean;
  preset: string;
  [key: string]: unknown;
}

export interface AttackModifierConfig {
  id: string; name: string; dice_count: string; dice_sides: string;
  sign: "1" | "-1"; scope: "every_attack" | "once_selectable";
}

export interface DamageComponentConfig {
  id: string; name: string; dice_count: string; dice_sides: string; flat_bonus: string;
  damage_type: string; scope: "every_hit" | "once_selectable" | "selected_hits" | "crit_only";
  crit_behavior: "double_dice" | "normal"; weapon_die: boolean; magical: boolean;
}

export interface AppConfig {
  config_version: 2;
  quick: QuickConfig;
  targets: TargetConfig[];
  entries: EntryConfig[];
  custom_presets: Record<string, Partial<EntryConfig>>;
  analysis: AnalysisConfig;
  onboarding_seen?: boolean;
  help_expanded?: boolean;
  web: {
    active_view: ViewName;
    onboarding_seen?: boolean;
    help_expanded?: boolean;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface D20Roll { original: number; value: number; rerolled: boolean }
export interface AttackResult {
  attack_id: string; group_id: string; group_name: string; index: number; target_id: string;
  d20_rolls: D20Roll[]; selected_d20: number; total: number; hit: boolean;
  critical: boolean; power_attack: boolean; explanation: string;
}
export interface RolledDie { sides: number; value: number; original: number | null; rerolled: boolean }
export interface ComponentRoll {
  component_id: string; name: string; damage_type: string; magical: boolean;
  dice: RolledDie[]; flat_bonus: number; raw_total: number;
}
export interface DamageResult {
  source_id: string; target_id: string; critical: boolean; components: ComponentRoll[];
  by_type: Array<{ damage_type: string; raw: number; after_reduction: number; after_save: number; final: number; note: string }>;
  total: number;
}
export interface SaveResult { target_id: string; d20: number; bonus: number; total: number; succeeded: boolean }
export interface RuleTarget { target_id: string; name: string; ac: number }
export interface ResolutionSession {
  mode: "attack" | "save" | "auto";
  targets?: RuleTarget[];
  attack_results: AttackResult[];
  save_results: SaveResult[];
  damage_results: DamageResult[];
  attack_modifiers_resolved?: boolean;
}
export interface QuickSummary {
  attack_count: number; hit_count: number; critical_count: number; total_damage: number;
  session: ResolutionSession;
}
export interface RiderChoice {
  component_id: string; name: string; scope: "once_selectable" | "selected_hits";
  attacks: AttackResult[];
}
export interface AttackModifierChoice {
  modifier_id: string; name: string;
  dice: { count: number; sides: number; sign: number };
  attacks: AttackResult[];
}
export interface AdvancedResult {
  session_id: string;
  sessions: ResolutionSession[];
  attack_modifiers_resolved: boolean;
  selectable_attack_modifiers: AttackModifierChoice[];
  selectable_riders: RiderChoice[];
}

export interface BridgeMethods {
  init(): Promise<{ version: string; config_version: number; methods: string[] }>;
  resolveQuick(payload: Record<string, unknown>): Promise<QuickSummary>;
  resolveAnalysis(config: AnalysisConfig, sensitivityAcs: number[]): Promise<AnalysisBundle>;
  startAdvanced(payload: AppConfig): Promise<AdvancedResult>;
  resolveAttackModifiers(sessionId: string, selections: Record<string, string>): Promise<AdvancedResult>;
  resolveAttackDamage(sessionId: string, selections: Record<string, string[]>): Promise<AdvancedResult>;
  reroll(sessionId: string, references: Array<[string, string, number]>): Promise<AdvancedResult>;
  disposeSession(sessionId: string): Promise<{ disposed: boolean }>;
}
