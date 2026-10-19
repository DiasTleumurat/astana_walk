import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // Exercise the real map UI without depending on public tile servers in CI.
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#e9efe8"/></svg>',
    }),
  );
});

async function submitSearch(page: Page) {
  const [response] = await Promise.all([
    page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/recommendations" &&
        response.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Найти мою прогулку" }).click(),
  ]);
  await expect(
    page.getByRole("button", { name: "Найти мою прогулку" }),
  ).toBeEnabled();
  return response;
}

test("real recommendations, evidence and coffee filter", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Куда пойдём в Астане?" }),
  ).toBeVisible();
  await expect(page.getByTestId("place-card")).toHaveCount(3);
  await page.getByTestId("place-card").first().locator("summary").click();
  await expect(
    page
      .getByTestId("place-card")
      .first()
      .getByRole("link", { name: "OpenStreetMap" }),
  ).toHaveAttribute("href", /openstreetmap.org\/(node|way|relation)\//);
  await page.getByRole("button", { name: "Кофе рядом", exact: true }).click();
  const response = await submitSearch(page);
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  expect(result.recommendations.length).toBeGreaterThan(0);
  await expect(page.getByTestId("place-card")).toHaveCount(
    result.recommendations.length,
  );
  await expect(page.locator(".place-category")).toHaveText(
    result.recommendations.map(() => "Кафе"),
  );
  expect(errors).toEqual([]);
});

test("strict missing amenity gives honest empty state", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("place-card")).toHaveCount(3);
  await page.getByRole("button", { name: /Ещё пожелания/ }).click();
  await page.getByLabel("Подтверждённые розетки").check();
  await submitSearch(page);
  await expect(
    page.getByRole("heading", { name: "Не нашлось подходящих мест" }),
  ).toBeVisible();
  await expect(page.getByTestId("place-card")).toHaveCount(0);
});

test("geolocation denial and manual location", async ({ page, context }) => {
  await context.clearPermissions();
  await page.addInitScript(() => {
    navigator.geolocation.getCurrentPosition = (_success, error) =>
      error?.({
        code: 1,
        message: "Denied",
        PERMISSION_DENIED: 1,
        POSITION_UNAVAILABLE: 2,
        TIMEOUT: 3,
      });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Моё местоположение" }).click();
  await expect(page.getByText(/Доступ к геолокации запрещён/)).toBeVisible();
  await page.getByText("Координаты", { exact: true }).click();
  await page.getByLabel("Широта", { exact: true }).fill("43.2");
  await page.getByLabel("Долгота", { exact: true }).fill("76.9");
  await page.getByRole("button", { name: "Применить", exact: true }).click();
  await submitSearch(page);
  await expect(page.getByText(/Эта точка за пределами/)).toBeVisible();
});

test("map selection, mobile toggle, no overflow and detailed OSM tiles", async ({
  page,
}, testInfo) => {
  const external: string[] = [];
  page.on("request", (r) => {
    if (!r.url().startsWith("http://127.0.0.1") && !r.url().startsWith("data:"))
      external.push(r.url());
  });
  await page.goto("/");
  await expect(page.getByTestId("place-card")).toHaveCount(3);
  await page.getByRole("button", { name: "Выбрать на карте" }).click();
  await expect(
    page.getByText("Нажмите на карту, чтобы выбрать старт"),
  ).toBeVisible();
  await page
    .locator(".leaflet-container")
    .click({ position: { x: 150, y: 180 } });
  await expect(page.locator("#start")).toHaveValue("custom");
  await submitSearch(page);
  await expect(
    page.getByRole("button", { name: "Найти мою прогулку" }),
  ).toBeEnabled();
  if (testInfo.project.name === "mobile") {
    await page.getByRole("button", { name: "Карта", exact: true }).click();
    await expect(page.locator(".leaflet-container")).toBeVisible();
  }
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  expect(
    external.every((url) => url.startsWith("https://tile.openstreetmap.org/")),
  ).toBeTruthy();
});

test("map failure preserves list; API error has retry", async ({ page }) => {
  await page.route("https://tile.openstreetmap.org/**", (r) => r.abort());
  await page.goto("/");
  await expect(page.getByTestId("place-card")).toHaveCount(3);
  await page.route("**/api/recommendations", (r) =>
    r.fulfill({ status: 503, body: "{}" }),
  );
  await submitSearch(page);
  await expect(page.getByRole("alert")).toContainText("Не удалось");
  await expect(
    page.getByRole("button", { name: "Попробовать снова" }),
  ).toBeVisible();
});
