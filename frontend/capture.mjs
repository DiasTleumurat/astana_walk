import { chromium } from "@playwright/test";
import fs from "node:fs";
const out = "../.impeccable/review";
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
for (const [name, width, height] of [
  ["desktop", 1440, 1000],
  ["tablet", 768, 1024],
  ["mobile", 390, 844],
]) {
  const page = await browser.newPage({
    viewport: { width, height },
    reducedMotion: "reduce",
  });
  await page.goto("http://127.0.0.1:8000");
  await page.getByTestId("place-card").first().waitFor();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
  if (name === "desktop")
    await page.screenshot({ path: "../docs/demo.png", fullPage: false });
  if (name === "mobile") {
    await page.getByRole("button", { name: "Карта", exact: true }).click();
    await page.screenshot({ path: `${out}/mobile-map.png`, fullPage: true });
  }
  console.log(
    name,
    await page.evaluate(() => ({
      width: innerWidth,
      scroll: document.documentElement.scrollWidth,
    })),
  );
  await page.close();
}
await browser.close();
