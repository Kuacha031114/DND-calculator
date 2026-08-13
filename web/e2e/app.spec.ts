import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("./");
  const onboarding = page.getByRole("button", { name: "开始使用" });
  if (await onboarding.isVisible()) {
    await onboarding.click();
    await page.waitForTimeout(350);
  }
});

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
  await page.getByRole("button", { name: "选择一次", exact: true }).click();
  const damageEditor = page.locator(".dynamic-editor").last();
  await damageEditor.getByLabel("名称").fill("偷袭");
  await damageEditor.getByLabel("骰子数量").fill("1");
  await damageEditor.getByLabel("骰子面数").fill("6");
  await page.getByRole("button", { name: "① 投掷检定" }).click();
  await page.getByLabel(/攻击 1 · 第 1 次/).check();
  await page.getByRole("button", { name: "④ 结算攻击伤害" }).click();

  await expect(page.locator(".component-result strong").filter({ hasText: /^偷袭$/ })).toBeVisible();
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
  await page.getByRole("button", { name: "④ 结算攻击伤害" }).click();
  await expect(page.locator(".damage-breakdown")).toHaveCount(1);
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
  await expect(normal.locator(".damage-total strong")).not.toHaveText("0");
  await expect(immune.locator(".damage-total strong")).toHaveText("0");
  await expect(immune.locator(".defense-row")).toContainText("免疫");
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
  page.once("dialog", (dialog) => dialog.accept());
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

test("web onboarding and help use independent browser state", async ({ page }) => {
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.getByRole("dialog", { name: "从一次攻击，到整场遭遇" })).toBeVisible();
  await page.getByRole("button", { name: "开始使用" }).click();
  await page.getByRole("button", { name: "使用帮助" }).click();
  await expect(page.getByRole("dialog", { name: "使用帮助" })).toContainText("快速计算");
  await page.getByRole("button", { name: "知道了" }).click();
  await page.waitForTimeout(350);
  await page.reload();
  await expect(page.getByRole("dialog", { name: "从一次攻击，到整场遭遇" })).toBeHidden();
});

test("confirmed import can be undone in the same session", async ({ page }) => {
  await waitForEngine(page);
  const imported = {
    config_version: 2,
    targets: [{ id: "undo-target", name: "待撤销目标", ac: "17" }],
    entries: [{ id: "undo-entry", target_id: "undo-target", name: "待撤销攻击", damage_components: [] }],
    web: { active_view: "advanced", onboarding_seen: true },
  };
  page.once("dialog", (dialog) => dialog.accept());
  await page.locator('input[type="file"]').setInputFiles({
    name: "config-v3.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(imported)),
  });
  await expect(page.getByLabel("目标名称")).toHaveValue("待撤销目标");
  await page.getByRole("button", { name: "撤销本次导入" }).click();
  await expect(page.getByText(/已撤销本次导入/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "三步完成攻击结算" })).toBeVisible();
});

test("advanced workspace is usable without horizontal overflow", async ({ page }) => {
  await openAdvanced(page);
  await expect(page.getByRole("heading", { name: "目标、攻击与法术" })).toBeVisible();
  await expect(page.getByLabel("目标名称")).toBeVisible();
  await expect(page.getByRole("heading", { name: "伤害组件" })).toBeVisible();
  const overflows = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  expect(overflows).toBe(false);
});

test("selectable hit die can be assigned after the base d20", async ({ page }) => {
  await openAdvanced(page);
  await page.getByRole("button", { name: "选择一次 +1d4" }).click();
  const modifierEditor = page.locator(".dynamic-editor").first();
  await modifierEditor.getByLabel("名称").fill("勇气联结");
  await page.getByRole("button", { name: "① 投掷检定" }).click();
  const selection = page.getByLabel(/勇气联结/);
  await expect(selection).toBeVisible();
  await selection.selectOption({ index: 1 });
  await page.getByRole("button", { name: "提交命中修正" }).click();
  await expect(page.getByRole("button", { name: "④ 结算攻击伤害" })).toBeEnabled();
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

test("invalid DM inputs remain visible and recover without losing edits", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "强度与时长" }).click();
  await page.getByLabel("方案 1 名称").fill("保留的构筑名称");

  const cases = [
    { label: "怪物数量", valid: "2", error: "怪物数量 必须是整数" },
    { label: "每只怪物 HP", valid: "80", error: "每只怪物 HP 必须是数字" },
    { label: "队伍输出在线率", valid: "75", error: "队伍输出在线率 必须是数字" },
    { label: "希望战斗持续轮数", valid: "5", error: "目标战斗轮数 必须是数字" },
  ];
  for (const current of cases) {
    const field = page.locator(".dm-controls label.field").filter({ hasText: new RegExp(`^${current.label}`) }).locator("input");
    await field.fill("");
    await expect(page.getByRole("alert")).toContainText(current.error);
    await expect(field).toBeVisible();
    await expect(page.getByRole("heading", { name: "怪物与实战修正" })).toBeVisible();
    await expect(page.getByText("修正输入后，这里会自动恢复结果。")).toBeVisible();
    await expect(page.getByLabel("方案 1 名称")).toHaveValue("保留的构筑名称");
    await field.fill(current.valid);
    await expect(page.getByRole("alert")).toBeHidden();
    await expect(page.getByText("当前预计战斗时长")).toBeVisible();
  }
});

test("every editable build number remains available after validation errors", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "强度与时长" }).click();
  const card = page.locator(".build-card").first();
  const cases = [
    { label: "命中加值", valid: "8" },
    { label: "每轮攻击次数", valid: "3" },
    { label: "重击下限", valid: "19" },
    { label: "骰子数量", valid: "2" },
    { label: "骰子面数", valid: "6" },
    { label: "固定加值", valid: "5" },
    { label: "重击额外骰颗数", valid: "1" },
    { label: "首次命中附伤骰", valid: "2" },
    { label: "附伤骰面数", valid: "8" },
    { label: "附伤固定加值", valid: "1" },
    { label: "每轮固定伤害", valid: "2.5" },
  ];
  for (const current of cases) {
    const field = card.locator("label.field").filter({ hasText: new RegExp(`^${current.label}`) }).locator("input");
    await field.fill("");
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(field).toBeVisible();
    await expect(page.getByRole("heading", { name: "怪物与实战修正" })).toBeVisible();
    await field.fill(current.valid);
    await expect(page.getByRole("alert")).toBeHidden();
    await expect(card.locator(".dpr-result strong")).toBeVisible();
  }
});

test("target AC validation keeps both player and DM editors recoverable", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "强度与时长" }).click();
  const targetAc = page.getByLabel("分析目标 AC");
  await targetAc.fill("0");
  await expect(page.getByRole("alert")).toContainText("目标 AC 必须在 1 到 99 之间");
  await expect(page.getByLabel("方案 1 名称")).toBeVisible();
  await expect(page.getByLabel("怪物数量", { exact: true })).toBeVisible();
  await targetAc.fill("18");
  await expect(page.getByRole("alert")).toBeHidden();
  await expect(page.locator(".sensitivity-panel .selected-row td").first()).toHaveText("18");
});

test("build copy delete and party inclusion have predictable behavior", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "强度与时长" }).click();
  await page.locator(".build-card").first().getByRole("button", { name: "复制" }).click();
  await expect(page.locator(".build-card")).toHaveCount(3);
  const copy = page.locator(".build-card").nth(2);
  await expect(copy.getByLabel("方案 3 名称")).toHaveValue("常规攻击副本");
  await expect(copy.getByLabel("计入 DM 队伍")).not.toBeChecked();
  await copy.getByLabel("计入 DM 队伍").check();
  await expect(page.getByText(/队伍原始 DPR 23.0/)).toBeVisible();
  await copy.getByRole("button", { name: "删除" }).click();
  await expect(page.locator(".build-card")).toHaveCount(2);
  await page.locator(".build-card").first().getByLabel("计入 DM 队伍").uncheck();
  await expect(page.getByText(/请至少勾选一个/)).toBeVisible();
  await expect(page.getByLabel("怪物数量", { exact: true })).toBeVisible();
});

test("advantage critical rider and power attack controls recalculate results", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "强度与时长" }).click();
  const card = page.locator(".build-card").first();
  await card.getByLabel("投骰方式").selectOption("advantage");
  await card.getByLabel("重击下限").fill("19");
  await card.getByLabel("首次命中附伤骰").fill("2");
  await card.getByLabel("附伤骰面数").fill("6");
  await card.getByLabel("重击额外骰颗数").fill("1");
  await card.getByLabel("减 5 命中、命中后加 10 伤害").check();
  await expect(card.getByText(/其中重击 19.0%/)).toBeVisible();
  await expect(card.locator(".dpr-result strong")).not.toHaveText("11.5");
  await card.getByLabel("附伤骰在触发重击时翻倍").uncheck();
  await expect(card.locator(".dpr-result strong")).toBeVisible();
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

test("invalid analysis state fits a mobile viewport and keeps correction fields", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "强度与时长" }).click();
  await page.getByLabel("怪物数量", { exact: true }).fill("");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByLabel("怪物数量", { exact: true })).toBeVisible();
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
