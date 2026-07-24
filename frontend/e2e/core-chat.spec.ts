import { expect, test } from "@playwright/test";

test("角色、消息和备忘录核心流程", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "新建" }).click();
  await expect(page.getByRole("button", { name: "角色" })).toBeVisible();

  await page.getByRole("button", { name: "角色" }).click();
  await page.getByLabel("角色名称").fill("架构顾问");
  await page.getByLabel("专业领域").fill("软件架构");
  await page.getByRole("button", { name: "保存角色" }).click();
  await expect(page.getByText("当前版本 1")).toBeVisible();
  await page.getByRole("button", { name: "关闭助手角色" }).click();

  await page.getByLabel("消息内容").fill("请给我一个简短建议");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByText("Mock 回复：请给我一个简短建议")).toBeVisible();

  await page.getByRole("button", { name: "备忘录" }).click();
  await page.getByLabel("用户保护区").fill("始终使用中文回答");
  await page.getByRole("button", { name: "保存保护区" }).click();
  await expect(page.getByText(/版本 1 · 用户编辑/)).toBeVisible();
});

test("请求失败提示保持紧凑且不挤压输入区", async ({ page }) => {
  await page.route("**/api/v1/conversations/*/messages", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "TEST_FAILURE", message: "请求失败，请稍后重试" },
      }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "新建" }).click();
  await page.getByLabel("消息内容").fill("你好");
  await page.getByRole("button", { name: "发送" }).click();

  const error = page.getByText("请求失败，请稍后重试");
  await expect(error).toBeVisible();
  const errorBox = await error.boundingBox();
  expect(errorBox?.height).toBeLessThan(80);
  await expect(page.getByLabel("消息内容")).toBeVisible();
});
