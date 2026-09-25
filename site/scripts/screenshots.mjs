// Screenshots + checks against a running server.
// Usage: BASE=http://localhost:8787 node scripts/screenshots.mjs
//   (start one with `npx wrangler dev` or `npm run preview` first)
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.env.BASE ?? "http://localhost:8787";
const out = resolve(dirname(fileURLToPath(import.meta.url)), "..", "test-screenshots");
mkdirSync(out, { recursive: true });

const pages = [["home", "/"], ["thanks", "/thanks"], ["404", "/nope"]];
const widths = [1440, 390];
const schemes = ["light", "dark"];
let problems = 0;
const report = (msg) => { problems++; console.log("  ✗ " + msg); };

const browser = await chromium.launch();
for (const [name, path] of pages) {
  for (const width of widths) {
    for (const colorScheme of schemes) {
      const ctx = await browser.newContext({ viewport: { width, height: 900 }, colorScheme, deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      const errors = [];
      let jsBytes = 0;
      page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errors.push(m.text()); });
      page.on("pageerror", (e) => errors.push(String(e)));
      page.on("response", async (r) => {
        if (r.request().resourceType() === "script") {
          try { jsBytes += (await r.body()).length; } catch {}
        }
      });
      const res = await page.goto(BASE + path, { waitUntil: "networkidle" });
      await page.waitForTimeout(300);
      const tag = `${name}-${width}-${colorScheme}`;
      console.log(`${tag} (HTTP ${res?.status()})`);
      await page.screenshot({ path: resolve(out, `${tag}.png`), fullPage: true });
      await page.screenshot({ path: resolve(out, `${tag}-fold.png`) });
      if (name === "home") {
        for (const id of ["features", "slice", "cli", "showcase", "download", "coffee"]) {
          await page.locator("#" + id).screenshot({ path: resolve(out, `${tag}-${id}.png`) });
        }
      }

      const r = await page.evaluate(() => {
        const d = document.documentElement;
        const small = [...document.querySelectorAll("a, button")]
          .filter((el) => el.offsetParent !== null && !el.classList.contains("sr-only"))
          .map((el) => { const b = el.getBoundingClientRect(); return { t: (el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 40), h: b.height, w: b.width, inline: getComputedStyle(el).display === "inline" }; })
          .filter((b) => (b.h < 44 || b.w < 24) && !b.inline);
        const cavs = [...document.querySelectorAll("cav-img")];
        const noAlt = [...document.images].filter((i) => !i.hasAttribute("alt")).map((i) => i.src)
          .concat(cavs.filter((c) => !c.getAttribute("aria-label")).map((c) => "cav-img#" + cavs.indexOf(c)));
        const undrawn = cavs.filter((c) => c.offsetParent !== null).filter((c) => {
          const cv = c.shadowRoot && c.shadowRoot.querySelector("canvas");
          return !cv || cv.width < 50 || !c.style.aspectRatio;
        }).length;
        const cavStyled = cavs.every((c) => { const cv = c.shadowRoot && c.shadowRoot.querySelector("canvas"); return !cv || c.offsetParent === null || Math.abs(cv.getBoundingClientRect().width - c.getBoundingClientRect().width) < 2; });
        const hs = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6")].map((h) => +h.tagName[1]);
        const skips = hs.filter((l, i) => i > 0 && l > hs[i - 1] + 1);
        const onHome = location.pathname === "/";
        const hashes = [...document.querySelectorAll(onHome ? 'a[href^="#"], a[href^="/#"]' : 'a[href^="#"]')]
          .map((a) => a.getAttribute("href").replace(/^\//, ""))
          .filter((h) => h.length > 1 && !document.getElementById(h.slice(1)));
        const internal = [...new Set([...document.querySelectorAll("a[href^='/']")].map((a) => a.getAttribute("href").split("#")[0]).filter(Boolean))];
        const broken = [...document.images].filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.src);
        return { undrawn, cavStyled, overflow: d.scrollWidth - d.clientWidth, small, noAlt, h1: hs.filter((l) => l === 1).length, skips, hashes, internal, broken };
      });
      if (r.undrawn) report(`${r.undrawn} cav-img not drawn`);
      if (!r.cavStyled) report("cav-img shadow style blocked (canvas not full width)");
      if (r.overflow > 0) report(`horizontal overflow ${r.overflow}px`);
      if (r.small.length) report(`small targets: ${JSON.stringify(r.small)}`);
      if (r.noAlt.length) report(`images without alt: ${r.noAlt}`);
      if (r.h1 !== 1) report(`h1 count ${r.h1}`);
      if (r.skips.length) report(`heading level skips`);
      if (r.hashes.length) report(`missing anchors: ${r.hashes}`);
      if (r.broken.length) report(`broken images: ${r.broken}`);
      for (const href of r.internal) {
        const s = (await page.request.get(BASE + href)).status();
        if (s !== 200) report(`link ${href} -> ${s}`);
      }
      const wantedErrors = errors.filter((e) => !(name === "404" && /404/.test(e)));
      if (wantedErrors.length) report(`console: ${wantedErrors.join(" | ")}`);
      if (width === 1440 && colorScheme === "light") console.log(`  JS transferred: ${jsBytes} bytes`);
      await ctx.close();
    }
  }
}
await browser.close();
console.log(problems ? `${problems} problem(s)` : "all checks passed");
process.exitCode = problems ? 1 : 0;
