import type { AnalysisConfig, AnalysisRollMode, BuildProfile } from "./types";

export interface BuildResult {
  id: string;
  name: string;
  included_in_party: boolean;
  hit_probability: number;
  normal_hit_probability: number;
  critical_probability: number;
  at_least_one_hit_probability: number;
  at_least_one_critical_probability: number;
  expected_hits: number;
  damage_per_attack: number;
  rider_damage: number;
  guaranteed_damage: number;
  dpr: number;
}

export interface EncounterResult {
  builds: BuildResult[];
  party_build_count: number;
  raw_party_dpr: number;
  adjusted_party_dpr: number;
  total_monster_hp: number;
  estimated_rounds: number;
  suggested_hp_each: number;
  suggested_monster_count: number;
}

function integer(value: string, label: string, minimum: number, maximum: number): number {
  if (!/^-?\d+$/.test(value.trim())) throw new Error(`${label} 必须是整数`);
  const parsed = Number(value);
  if (parsed < minimum || parsed > maximum) throw new Error(`${label} 必须在 ${minimum} 到 ${maximum} 之间`);
  return parsed;
}

function decimal(value: string, label: string, minimum: number, maximum: number): number {
  if (value.trim() === "" || !Number.isFinite(Number(value))) throw new Error(`${label} 必须是数字`);
  const parsed = Number(value);
  if (parsed < minimum || parsed > maximum) throw new Error(`${label} 必须在 ${minimum} 到 ${maximum} 之间`);
  return parsed;
}

const D20_DISTRIBUTIONS = new Map<AnalysisRollMode, number[]>();

function selectedD20Distribution(mode: AnalysisRollMode): number[] {
  const cached = D20_DISTRIBUTIONS.get(mode);
  if (cached) return cached;
  const dice = mode === "elven_accuracy" ? 3 : mode === "normal" ? 1 : 2;
  const probabilities = Array(21).fill(0) as number[];
  const outcomes = 20 ** dice;
  function visit(values: number[]) {
    if (values.length === dice) {
      const selected = mode === "disadvantage" ? Math.min(...values) : Math.max(...values);
      probabilities[selected] += 1 / outcomes;
      return;
    }
    for (let face = 1; face <= 20; face += 1) visit([...values, face]);
  }
  visit([]);
  D20_DISTRIBUTIONS.set(mode, probabilities);
  return probabilities;
}

export function attackProbabilities(
  targetAc: number, attackBonus: number, mode: AnalysisRollMode, critRange: number,
): { normal: number; critical: number; hit: number } {
  const distribution = selectedD20Distribution(mode);
  let normal = 0;
  let critical = 0;
  for (let d20 = 1; d20 <= 20; d20 += 1) {
    const probability = distribution[d20];
    if (d20 === 1) continue;
    if (d20 >= critRange) critical += probability;
    else if (d20 + attackBonus >= targetAc) normal += probability;
  }
  return { normal, critical, hit: normal + critical };
}

/** Exact E[max(0, dice total + flat)], including negative flat modifiers. */
export function expectedDamage(count: number, sides: number, flat: number): number {
  if (flat >= 0) return count * (sides + 1) / 2 + flat;
  if (count === 0) return Math.max(0, flat);
  let distribution = [1];
  for (let die = 0; die < count; die += 1) {
    const next = Array(distribution.length + sides).fill(0) as number[];
    for (let sum = 0; sum < distribution.length; sum += 1) {
      for (let face = 1; face <= sides; face += 1) next[sum + face] += distribution[sum] / sides;
    }
    distribution = next;
  }
  return distribution.reduce((total, probability, sum) => total + probability * Math.max(0, sum + flat), 0);
}

export function analyzeBuild(profile: BuildProfile, targetAc: number): BuildResult {
  const attackBonus = integer(profile.attack_bonus, `${profile.name}的命中加值`, -99, 99) - (profile.power_attack ? 5 : 0);
  const attacks = integer(profile.attacks_per_round, `${profile.name}的每轮攻击次数`, 1, 100);
  const critRange = integer(profile.crit_range, `${profile.name}的重击下限`, 2, 20);
  const diceCount = integer(profile.damage_dice_count, `${profile.name}的伤害骰数量`, 0, 50);
  const dieSides = integer(profile.damage_die_sides, `${profile.name}的伤害骰面数`, 2, 100);
  const damageBonus = integer(profile.damage_bonus, `${profile.name}的伤害加值`, -100, 500) + (profile.power_attack ? 10 : 0);
  const critExtraDice = integer(profile.crit_extra_dice, `${profile.name}的重击额外骰`, 0, 50);
  const riderDice = integer(profile.rider_dice_count, `${profile.name}的首次命中附伤骰`, 0, 50);
  const riderSides = integer(profile.rider_die_sides, `${profile.name}的附伤骰面数`, 2, 100);
  const riderBonus = integer(profile.rider_bonus, `${profile.name}的附伤加值`, -100, 500);
  const guaranteed = decimal(profile.guaranteed_damage, `${profile.name}的每轮固定伤害`, 0, 10000);
  const probabilities = attackProbabilities(targetAc, attackBonus, profile.roll_mode, critRange);
  const normalDamage = expectedDamage(diceCount, dieSides, damageBonus);
  const criticalDamage = expectedDamage(diceCount * 2 + critExtraDice, dieSides, damageBonus);
  const perAttack = probabilities.normal * normalDamage + probabilities.critical * criticalDamage;
  const miss = 1 - probabilities.hit;
  const firstHitFactor = probabilities.hit === 0 ? 0 : (1 - miss ** attacks) / probabilities.hit;
  const normalRider = expectedDamage(riderDice, riderSides, riderBonus);
  const criticalRider = expectedDamage(profile.rider_doubles_on_crit ? riderDice * 2 : riderDice, riderSides, riderBonus);
  const riderDamage = firstHitFactor * (
    probabilities.normal * normalRider + probabilities.critical * criticalRider
  );
  return {
    id: profile.id, name: profile.name, included_in_party: profile.enabled, hit_probability: probabilities.hit,
    normal_hit_probability: probabilities.normal, critical_probability: probabilities.critical,
    at_least_one_hit_probability: 1 - miss ** attacks,
    at_least_one_critical_probability: 1 - (1 - probabilities.critical) ** attacks,
    expected_hits: attacks * probabilities.hit, damage_per_attack: perAttack,
    rider_damage: riderDamage, guaranteed_damage: guaranteed,
    dpr: attacks * perAttack + riderDamage + guaranteed,
  };
}

export function analyzeEncounter(config: AnalysisConfig, targetAcOverride?: number): EncounterResult {
  const targetAc = targetAcOverride ?? integer(config.target_ac, "目标 AC", 1, 99);
  const monsterCount = integer(config.monster_count, "怪物数量", 1, 100);
  const hpEach = decimal(config.hp_each, "每只怪物 HP", 1, 100000);
  const uptime = decimal(config.party_uptime_percent, "队伍输出在线率", 1, 100) / 100;
  const multiplier = decimal(config.damage_multiplier, "伤害结算倍率", 0.01, 10);
  const desiredRounds = decimal(config.desired_rounds, "目标战斗轮数", 0.1, 100);
  const builds = config.builds.map((profile) => analyzeBuild(profile, targetAc));
  const partyBuilds = builds.filter((build) => build.included_in_party);
  const rawPartyDpr = partyBuilds.reduce((total, build) => total + build.dpr, 0);
  const adjustedPartyDpr = rawPartyDpr * uptime * multiplier;
  const totalMonsterHp = monsterCount * hpEach;
  return {
    builds, party_build_count: partyBuilds.length, raw_party_dpr: rawPartyDpr, adjusted_party_dpr: adjustedPartyDpr,
    total_monster_hp: totalMonsterHp,
    estimated_rounds: adjustedPartyDpr > 0 ? totalMonsterHp / adjustedPartyDpr : Number.POSITIVE_INFINITY,
    suggested_hp_each: adjustedPartyDpr * desiredRounds / monsterCount,
    suggested_monster_count: adjustedPartyDpr * desiredRounds / hpEach,
  };
}
