import { expect, test } from "@playwright/test";

test("quick calculation runs in the browser", async ({ page }) => {
  await page.goto("./");
  await expect(page.getByText(/规则引擎 v.+ 已就绪/)).toBeVisible({ timeout: 45_000 });
  await page.getByRole("button", { name: "立即结算" }).click();
  await expect(page.getByText("总伤害")).toBeVisible();
  await expect(page.locator(".summary-grid strong")).toHaveCount(3);
});

test("manual hits validate and persist after reload", async ({ page }) => {
  await page.goto("./");
  await expect(page.getByText(/规则引擎 v.+ 已就绪/)).toBeVisible({ timeout: 45_000 });
  await page.getByLabel("不知道 AC，手动指定命中").check();
  await page.getByLabel("命中次数").fill("1");
  await page.getByLabel("其中重击").fill("0");
  await page.getByRole("button", { name: "立即结算" }).click();
  await expect(page.locator(".summary-grid strong").first()).toContainText("1/1");
  await page.waitForTimeout(400);
  await page.reload();
  await expect(page.getByLabel("不知道 AC，手动指定命中")).toBeChecked();
});

test("advanced workspace is usable on narrow screens", async ({ page }) => {
  await page.goto("./");
  await page.getByRole("button", { name: "高级工作台" }).click();
  await expect(page.getByRole("heading", { name: "目标、攻击与法术" })).toBeVisible();
  await expect(page.getByLabel("目标名称")).toBeVisible();
  await expect(page.getByLabel("伤害名称")).toBeVisible();
});

test("cached PWA starts while offline", async ({ context, page }) => {
  await page.goto("./");
  await expect(page.getByText(/规则引擎 v.+ 已就绪/)).toBeVisible({ timeout: 45_000 });
  await page.reload();
  await expect(page.getByText(/规则引擎 v.+ 已就绪/)).toBeVisible({ timeout: 45_000 });
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByText(/规则引擎 v.+ 已就绪/)).toBeVisible({ timeout: 45_000 });
});
