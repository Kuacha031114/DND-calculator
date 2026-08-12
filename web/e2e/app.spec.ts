import { expect, test } from "@playwright/test";

async function waitForEngine(page: import("@playwright/test").Page) {
  await expect(page.getByText(/规则引擎 v.+ 已就绪/)).toBeVisible({ timeout: 45_000 });
}

async function openAdvanced(page: import("@playwright/test").Page) {
  await page.goto("./");
  await waitForEngine(page);
  await page.getByRole("button", { name: "高级工作台" }).click();
}

test("quick calculation runs in the browser", async ({ page }) => {
  await page.goto("./");
  await waitForEngine(page);
  await page.getByRole("button", { name: "立即结算" }).click();
  await expect(page.getByText("总伤害")).toBeVisible();
  await expect(page.locator(".summary-grid strong")).toHaveCount(3);
});

test("manual hits validate and persist after reload", async ({ page }) => {
  await page.goto("./");
  await waitForEngine(page);
  await page.getByLabel("不知道 AC，手动指定命中").check();
  await page.getByLabel("命中次数").fill("1");
  await page.getByLabel("其中重击").fill("0");
  await page.getByRole("button", { name: "立即结算" }).click();
  await expect(page.locator(".summary-grid strong").first()).toContainText("1/1");
  await page.waitForTimeout(400);
  await page.reload();
  await expect(page.getByLabel("不知道 AC，手动指定命中")).toBeChecked();
});

test("advanced manual attack resolves a selected sneak attack and reroll", async ({ page }) => {
  await openAdvanced(page);
  await page.getByLabel("AC 未知，手动指定命中").check();
  await page.getByLabel("命中后附加").selectOption({ label: "偷袭" });
  await page.getByRole("button", { name: "① 投掷检定" }).click();
  await page.getByLabel(/攻击 1 · 第 1 次/).check();
  await page.getByRole("button", { name: "③ 结算攻击伤害" }).click();

  await expect(page.getByText(/偷袭（/)).toBeVisible();
  const firstDie = page.locator(".reroll-panel .check").first();
  await firstDie.getByRole("checkbox").check();
  await page.getByRole("button", { name: "重骰选中骰子" }).click();
  await expect(firstDie).toContainText("→");
});

test("advanced attack without riders resolves directly", async ({ page }) => {
  await openAdvanced(page);
  await page.getByLabel("AC 未知，手动指定命中").check();
  await page.getByRole("button", { name: "① 投掷检定" }).click();
  await expect(page.getByText(/没有需要选择的附加伤害/)).toBeVisible();
  await page.getByRole("button", { name: "③ 结算攻击伤害" }).click();
  await expect(page.locator(".damage-detail")).toHaveCount(1);
});

test("multi-target save applies defenses independently", async ({ page }) => {
  await openAdvanced(page);
  const targetActions = page.locator(".navigator .mini-actions").first();
  await targetActions.getByRole("button", { name: "新增" }).click();
  await page.getByLabel("目标名称").fill("免疫目标");
  await page.getByRole("textbox", { name: "免疫", exact: true }).fill("火焰");
  await page.getByLabel("结算方式").selectOption("save");
  await page.getByLabel("应用到全部目标").check();
  await page.getByRole("combobox", { name: /^伤害类型/ }).selectOption({ label: "火焰" });
  await page.getByRole("button", { name: "① 投掷检定" }).click();

  const normal = page.locator(".roll-row").filter({ hasText: "目标 1" });
  const immune = page.locator(".roll-row").filter({ hasText: "免疫目标" });
  await expect(normal.locator(".damage-detail strong")).not.toHaveText("= 0");
  await expect(immune.locator(".damage-detail strong")).toHaveText("= 0");
});

test("legacy desktop configuration imports and persists", async ({ page }) => {
  await page.goto("./");
  await waitForEngine(page);
  const legacy = {
    config_version: 1,
    window: { geometry: "1180x780" },
    targets: [{ id: "legacy-target", name: "旧版目标", ac: "18" }],
    entries: [{ id: "legacy-entry", target_id: "legacy-target", name: "旧版攻击" }],
    web: { active_view: "advanced" },
  };
  await page.locator('input[type="file"]').setInputFiles({
    name: "config-v3.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(legacy)),
  });
  await expect(page.getByText(/配置导入成功/)).toBeVisible();
  await expect(page.getByLabel("目标名称")).toHaveValue("旧版目标");
  await page.waitForTimeout(400);
  await page.reload();
  await expect(page.getByLabel("目标名称")).toHaveValue("旧版目标");
});

test("advanced workspace is usable without horizontal overflow", async ({ page }) => {
  await openAdvanced(page);
  await expect(page.getByRole("heading", { name: "目标、攻击与法术" })).toBeVisible();
  await expect(page.getByLabel("目标名称")).toBeVisible();
  await expect(page.getByLabel("伤害名称")).toBeVisible();
  const overflows = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflows).toBe(false);
});

test("build comparison updates DPR and DM duration in real time", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "强度与时长" }).click();
  await expect(page.getByRole("heading", { name: "命中率与期望伤害比较器" })).toBeVisible();
  await expect(page.getByText(/队伍原始 DPR 11.5/)).toBeVisible();
  await expect(page.getByText("当前预计战斗时长")).toBeVisible();

  await page.getByLabel("分析目标 AC").fill("20");
  await expect(page.getByText(/队伍原始 DPR 7.2/)).toBeVisible();
  await expect(page.locator(".sensitivity-panel .selected-row td").first()).toHaveText("20");

  await page.getByLabel("每只怪物 HP").fill("60");
  await expect(page.locator(".duration-card > strong")).toContainText("9.74");
  await expect(page.getByText(/每只约 25 HP/)).toBeVisible();
});

test("analysis profiles persist after reload", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "强度与时长" }).click();
  await page.getByLabel("方案 1 名称").fill("双持游侠");
  await page.locator(".build-card").first().getByLabel("每轮攻击次数").fill("3");
  await page.waitForTimeout(400);
  await page.reload();
  await expect(page.getByRole("heading", { name: "命中率与期望伤害比较器" })).toBeVisible();
  await expect(page.getByLabel("方案 1 名称")).toHaveValue("双持游侠");
  await expect(page.locator(".build-card").first().getByLabel("每轮攻击次数")).toHaveValue("3");
});

test("analysis workspace fits a mobile viewport", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "强度与时长" }).click();
  await expect(page.getByRole("heading", { name: "方案输出排名" })).toBeVisible();
  const overflows = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflows).toBe(false);
});

test("cached PWA starts while offline", async ({ context, page }) => {
  await page.goto("./");
  await waitForEngine(page);
  await page.reload();
  await waitForEngine(page);
  await context.setOffline(true);
  await page.reload();
  await waitForEngine(page);
});
