import { describe, expect, it } from "vitest";
import { analyzeBuild, analyzeEncounter, attackProbabilities, expectedDamage } from "./analysis";
import { defaultAnalysis, defaultBuild } from "./config";

describe("damage expectation engine", () => {
  it("computes exact normal, advantage, disadvantage and elven accuracy probabilities", () => {
    const normal = attackProbabilities(15, 5, "normal", 20);
    expect(normal.normal).toBeCloseTo(0.5, 10);
    expect(normal.critical).toBeCloseTo(0.05, 10);
    expect(normal.hit).toBeCloseTo(0.55, 10);
    expect(attackProbabilities(15, 5, "advantage", 20).hit).toBeCloseTo(0.7975, 10);
    expect(attackProbabilities(15, 5, "advantage", 20).critical).toBeCloseTo(0.0975, 10);
    expect(attackProbabilities(15, 5, "disadvantage", 20).hit).toBeCloseTo(0.3025, 10);
    expect(attackProbabilities(15, 5, "disadvantage", 20).critical).toBeCloseTo(0.0025, 10);
    expect(attackProbabilities(15, 5, "elven_accuracy", 20).hit).toBeCloseTo(0.908875, 10);
    expect(attackProbabilities(15, 5, "elven_accuracy", 20).critical).toBeCloseTo(0.142625, 10);
  });

  it("honors automatic misses, expanded criticals and automatic critical hits", () => {
    const probabilities = attackProbabilities(99, -99, "normal", 19);
    expect(probabilities.normal).toBe(0);
    expect(probabilities.critical).toBeCloseTo(0.1, 10);
    expect(probabilities.hit).toBeCloseTo(0.1, 10);
  });

  it("calculates clipped damage exactly when a negative modifier can reduce damage to zero", () => {
    expect(expectedDamage(1, 4, -2)).toBeCloseTo(0.75, 10);
    expect(expectedDamage(0, 6, -2)).toBe(0);
  });

  it("includes critical dice, first-hit rider, power attack and guaranteed damage", () => {
    const build = {
      ...defaultBuild(), attack_bonus: "5", attacks_per_round: "2", damage_dice_count: "1",
      damage_die_sides: "8", damage_bonus: "4", rider_dice_count: "1", rider_die_sides: "6",
      rider_bonus: "0", guaranteed_damage: "2",
    };
    const result = analyzeBuild(build, 15);
    expect(result.damage_per_attack).toBeCloseTo(4.9, 10);
    // First-hit rider: (1 + miss) * (0.5 * 3.5 + 0.05 * 7) = 3.045.
    expect(result.rider_damage).toBeCloseTo(3.045, 10);
    expect(result.dpr).toBeCloseTo(14.845, 10);

    const power = analyzeBuild({ ...build, rider_dice_count: "0", guaranteed_damage: "0", power_attack: true }, 15);
    expect(power.hit_probability).toBeCloseTo(0.3, 10);
    expect(power.dpr).toBeCloseTo(11.55, 10);
  });

  it("turns party DPR into duration and reverse HP recommendations", () => {
    const result = analyzeEncounter(defaultAnalysis());
    expect(result.builds).toHaveLength(2);
    expect(result.builds[1].included_in_party).toBe(false);
    expect(result.raw_party_dpr).toBeCloseTo(11.5, 10);
    expect(result.adjusted_party_dpr).toBeCloseTo(9.775, 10);
    expect(result.estimated_rounds).toBeCloseTo(40 / 9.775, 10);
    expect(result.suggested_hp_each).toBeCloseTo(39.1, 10);
    expect(result.suggested_monster_count).toBeCloseTo(39.1 / 40, 10);
  });

  it("keeps comparison results but suppresses duration when no build joins the DM party", () => {
    const config = defaultAnalysis();
    config.builds = config.builds.map((build) => ({ ...build, enabled: false }));
    const result = analyzeEncounter(config);
    expect(result.builds).toHaveLength(2);
    expect(result.party_build_count).toBe(0);
    expect(result.raw_party_dpr).toBe(0);
    expect(result.estimated_rounds).toBe(Number.POSITIVE_INFINITY);
  });
});
