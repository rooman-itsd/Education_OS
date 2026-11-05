// Renders the app icons in apps/frontend/public/icons from the brand emblem (apps/frontend/src/admin/assets/eos-emblem.png),
// with the Chromium that tests/e2e already installs (pnpm --filter e2e e2e:install). Run it again when the emblem changes:
//
//   node tools/scripts/make-pwa-icons.mjs
//
// icon-192 and icon-512 ("any"): the emblem at 80 % on white. icon-maskable-512 ("maskable"): at 56 %, inside the safe
// zone Android crops to. apple-touch-icon (180): iOS adds its own rounded corners.
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../..", import.meta.url));
const require = createRequire(`${root}tests/e2e/package.json`);
const { chromium } = require("@playwright/test");

const emblem = readFileSync(`${root}apps/frontend/src/admin/assets/eos-emblem.png`).toString("base64");
const out = `${root}apps/frontend/public/icons`;
const ICONS = [
  { file: "icon-192.png", size: 192, scale: 0.8 },
  { file: "icon-512.png", size: 512, scale: 0.8 },
  { file: "icon-maskable-512.png", size: 512, scale: 0.56 },
  { file: "apple-touch-icon.png", size: 180, scale: 0.78 },
];

const browser = await chromium.launch();
try {
  for (const { file, size, scale } of ICONS) {
    const page = await browser.newPage({ viewport: { width: size, height: size } });
    await page.setContent(
      `<html><body style="margin:0;width:${size}px;height:${size}px;background:#ffffff;display:flex;align-items:center;justify-content:center">` +
        `<img src="data:image/png;base64,${emblem}" style="max-width:${size * scale}px;max-height:${size * scale}px"></body></html>`,
    );
    await page.waitForFunction(() => document.images[0]?.complete);
    await page.screenshot({ path: `${out}/${file}`, omitBackground: false });
    await page.close();
    process.stdout.write(`${file} ${size}x${size}\n`);
  }
} finally {
  await browser.close();
}
