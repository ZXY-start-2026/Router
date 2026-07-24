import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8001",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command:
      "..\\backend\\.venv\\Scripts\\python.exe -m uvicorn tests.e2e_server:app --app-dir ..\\backend --host 127.0.0.1 --port 8001",
    url: "http://127.0.0.1:8001/api/v1/health",
    reuseExistingServer: false,
    env: {
      APP_ENV: "test",
      DATABASE_URL: "sqlite:///D:/codex/playwright-e2e.db",
      MOCK_PROVIDER_ENABLED: "true",
      MEMORY_MODEL_ID: "MODEL_A",
    },
  },
});
