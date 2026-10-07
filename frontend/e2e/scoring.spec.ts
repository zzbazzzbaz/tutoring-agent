import { expect, test } from "@playwright/test";

test.describe("平时分（AI 评分）", () => {
  test.setTimeout(240_000);

  test("保存提示词 → 生成 → 持久化 → 导出", async ({ page }) => {
    const marker = `e2e-${Date.now()}`;
    const rows = page.locator("table tbody tr");
    const scores = page.locator("table tbody tr td:nth-child(4)");

    await test.step("教师登录", async () => {
      await page.goto("/login");
      await page.locator("#username").fill("teacher1");
      await page.locator("#password").fill("teacher123");
      await page.getByRole("button", { name: "开始学习" }).click();
      await expect(page).toHaveURL(/\/teacher\/chat/);
    });

    await test.step("从学情分析进入平时分页面", async () => {
      await page.goto("/teacher/manage/analytics");
      await page.getByRole("link", { name: "平时分" }).click();
      await expect(page).toHaveURL(/\/teacher\/manage\/analytics\/scoring/);
      await expect(page.locator("textarea")).toBeVisible();
    });

    await test.step("保存提示词", async () => {
      await page
        .locator("textarea")
        .fill(`以系统标准为主，评语中包含标记 ${marker}`);
      await page.getByRole("button", { name: "保存提示词" }).click();
      await expect(page.getByText("提示词已保存")).toBeVisible();
    });

    await test.step("选择班级与起始日期并生成（真实模型）", async () => {
      const since = new Date(Date.now() - 365 * 24 * 3600 * 1000)
        .toISOString()
        .slice(0, 10);
      await page.getByRole("combobox").click();
      await page.getByRole("option", { name: /2025级 1班/ }).click();
      await page.locator('input[type="date"]').fill(since);
      await page.getByRole("button", { name: "生成平时分" }).click();
      await expect(page.getByText(/AI 评分中/)).toBeVisible();
      await expect(rows).toHaveCount(3, { timeout: 180_000 });
    });

    await test.step("校验分数范围与降序", async () => {
      const nums = (await scores.allTextContents()).map((s) =>
        Number(s.trim()),
      );
      expect(nums).toHaveLength(3);
      for (const n of nums) {
        expect(Number.isInteger(n)).toBeTruthy();
        expect(n).toBeGreaterThanOrEqual(0);
        expect(n).toBeLessThanOrEqual(100);
      }
      for (let i = 1; i < nums.length; i++) {
        expect(nums[i]).toBeLessThanOrEqual(nums[i - 1]);
      }
    });

    await test.step("刷新后结果与提示词持久化", async () => {
      await page.reload();
      await expect(page.locator("textarea")).toHaveValue(new RegExp(marker));
      await page.getByRole("combobox").click();
      await page.getByRole("option", { name: /2025级 1班/ }).click();
      await expect(rows).toHaveCount(3);
    });

    await test.step("重新生成覆盖（行数不翻倍）", async () => {
      const generatedAt = page.getByText(/生成时间：/);
      const before = (await generatedAt.textContent()) ?? "";
      await page.getByRole("button", { name: "生成平时分" }).click();
      await expect(page.getByText(/AI 评分中/)).toBeVisible();
      await expect(generatedAt).not.toHaveText(before, { timeout: 180_000 });
      await expect(rows).toHaveCount(3);
    });

    await test.step("导出 Word", async () => {
      const [download] = await Promise.all([
        page.waitForEvent("download"),
        page.getByRole("button", { name: "导出 Word" }).click(),
      ]);
      expect(download.suggestedFilename()).toContain("平时分成绩表");
    });
  });
});
