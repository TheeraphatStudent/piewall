// Generates favicons, the Open Graph image, and brand-colored placeholder
// screenshots into public/. Run: npm run assets
// Placeholders are only written when the file is missing, so real screenshots
// dropped into public/images/ are never overwritten (pass --force to redo).
import { Resvg } from "@resvg/resvg-js";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const brand = resolve(root, "..", "brand");
const pub = resolve(root, "public");
const force = process.argv.includes("--force");
mkdirSync(resolve(pub, "images"), { recursive: true });

const FONT = "Segoe UI";
const render = (svg, width) =>
  new Resvg(svg, {
    fitTo: { mode: "width", value: width },
    font: { loadSystemFonts: true, defaultFontFamily: FONT },
  })
    .render()
    .asPng();

// The mark's geometry, lifted from brand/logo-mark.svg (512 box).
const PIE = "M256 256 L429.2 156 A200 200 0 1 1 256 56 Z";
const SLICE = "M270 231.75 L270 31.75 A200 200 0 0 1 443.2 131.75 Z";
const mark = (id) => `
  <defs><clipPath id="${id}"><path d="${PIE}"/></clipPath></defs>
  <path d="${PIE}" fill="#F27B1F"/>
  <g clip-path="url(#${id})" stroke="#C4520D" stroke-width="10" stroke-linecap="round" fill="none" opacity="0.55">
    <path d="M40 186 H472 M40 256 H472 M40 326 H472 M40 396 H472"/>
    <path d="M180 116 V186 M330 186 V256 M150 256 V326 M300 326 V396 M200 396 V466 M390 256 V326 M90 186 V256"/>
  </g>
  <path d="${SLICE}" fill="#FFC285"/>`;

// ---------- favicons ----------
const appIcon = readFileSync(resolve(brand, "app-icon.svg"), "utf8");
writeFileSync(resolve(pub, "favicon.svg"), appIcon);
writeFileSync(resolve(pub, "favicon-32.png"), render(appIcon, 32));
// Apple touch icon must be full-bleed (iOS applies its own mask).
const touch = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2C2C2E"/><stop offset="1" stop-color="#1C1C1E"/></linearGradient></defs>
  <rect width="512" height="512" fill="url(#bg)"/>
  <g transform="translate(256 262) scale(0.66) translate(-256 -256)">${mark("t")}</g>
</svg>`;
writeFileSync(resolve(pub, "apple-touch-icon.png"), render(touch, 180));
writeFileSync(resolve(pub, "logo-mark.svg"), readFileSync(resolve(brand, "logo-mark.svg"), "utf8"));

// ---------- Open Graph 1200x630 ----------
const og = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2C2C2E"/><stop offset="1" stop-color="#1C1C1E"/></linearGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <g transform="translate(96 135) scale(0.7)">${mark("o")}</g>
  <text x="500" y="300" font-family="${FONT}" font-weight="600" font-size="120" letter-spacing="-3" fill="#F5F5F7">piewall</text>
  <text x="504" y="378" font-family="${FONT}" font-size="44" letter-spacing="-0.5" fill="#A1A1A6">Your firewall, simple as pie.</text>
  <text x="504" y="470" font-family="${FONT}" font-size="26" fill="#A1A1A6">Windows Firewall rules, made clear. Free and open source.</text>
</svg>`;
writeFileSync(resolve(pub, "og.png"), render(og, 1200));

// ---------- placeholder screenshots ----------
const rules = [
  ["mp4toinc-ui", "Allow", "In", "TCP 8080", "Public", true],
  ["Block: python.exe", "Block", "In", "Any", "Public", true],
  ["Microsoft Teams", "Allow", "In", "UDP 50000-50059", "Private", true],
  ["Spotify Music", "Allow", "In", "TCP 57621", "All", true],
  ["Core Networking - DNS (UDP-Out)", "Allow", "Out", "UDP 53", "All", true],
  ["Remote Desktop - User Mode (TCP-In)", "Allow", "In", "TCP 3389", "Domain", false],
  ["File and Printer Sharing (SMB-In)", "Allow", "In", "TCP 445", "Private", false],
  ["Xbox Game Bar", "Allow", "Out", "Any", "All", true],
  ["Windows Media Player Network Sharing", "Block", "In", "TCP 10243", "Public", true],
  ["Node.js JavaScript Runtime", "Allow", "In", "Any", "Private", true],
  ["mDNS (UDP-In)", "Allow", "In", "UDP 5353", "Private", true],
  ["Delivery Optimization (TCP-In)", "Allow", "In", "TCP 7680", "All", true],
  ["Cast to Device streaming server", "Allow", "In", "TCP 10246", "Private", true],
];

function appShot(dark) {
  const c = dark
    ? { bg: "#1C1C1E", chrome: "#2C2C2E", text: "#F5F5F7", sub: "#A1A1A6", line: "#38383A", field: "#2C2C2E", sel: "#3A2A1E", allow: "#30D158", block: "#FF453A", banner: "#3A3218", bannerText: "#FFD60A", accent: "#FF9F52" }
    : { bg: "#FFFFFF", chrome: "#F5F5F7", text: "#1D1D1F", sub: "#6E6E73", line: "#E5E5EA", field: "#FFFFFF", sel: "#FFF1E5", allow: "#248A3D", block: "#D70015", banner: "#FFF4CC", bannerText: "#6B4E00", accent: "#C2410C" };
  const cols = [28, 470, 590, 680, 860, 1010];
  const head = ["Name", "Action", "Direction", "Port", "Profile", "Enabled"];
  let rows = "";
  rules.forEach((r, i) => {
    const y = 250 + i * 34;
    if (i === 1) rows += `<rect x="12" y="${y - 22}" width="1156" height="34" rx="6" fill="${c.sel}"/>`;
    const col = r[1] === "Allow" ? c.allow : c.block;
    rows += `<text x="${cols[0]}" y="${y}" fill="${c.text}">${r[0]}</text>
      <circle cx="${cols[1] + 6}" cy="${y - 5}" r="5" fill="${col}"/><text x="${cols[1] + 18}" y="${y}" fill="${col}" font-weight="600">${r[1]}</text>
      <text x="${cols[2]}" y="${y}" fill="${c.sub}">${r[2]}</text>
      <text x="${cols[3]}" y="${y}" fill="${c.text}" font-family="Cascadia Code, Consolas">${r[3]}</text>
      <text x="${cols[4]}" y="${y}" fill="${c.sub}">${r[4]}</text>
      <text x="${cols[5]}" y="${y}" fill="${r[5] ? c.text : c.sub}">${r[5] ? "Yes" : "No"}</text>
      <line x1="12" x2="1168" y1="${y + 12}" y2="${y + 12}" stroke="${c.line}"/>`;
  });
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="720" viewBox="0 0 1180 720" font-family="${FONT}" font-size="14">
  <rect width="1180" height="720" fill="${c.bg}"/>
  <rect width="1180" height="40" fill="${c.chrome}"/>
  <g transform="translate(14 8) scale(0.047)">${mark(dark ? "d" : "l")}</g>
  <text x="46" y="25" fill="${c.text}" font-size="13">piewall</text>
  <g stroke="${c.sub}" stroke-width="1.2" fill="none"><path d="M1040 20 h12"/><rect x="1088" y="14" width="11" height="11"/><path d="M1136 14 l11 11 M1147 14 l-11 11"/></g>
  <text x="14" y="66" fill="${c.sub}" font-size="13">File     View     Help</text>
  <rect x="14" y="84" width="360" height="34" rx="8" fill="${c.field}" stroke="${c.line}"/>
  <text x="40" y="106" fill="${c.sub}">Search 847 rules</text>
  <circle cx="28" cy="100" r="5.5" stroke="${c.sub}" stroke-width="1.5" fill="none"/>
  ${["Port", "Action", "Direction", "State"].map((t, i) => `<rect x="${392 + i * 104}" y="84" width="92" height="34" rx="8" fill="${c.field}" stroke="${c.line}"/><text x="${408 + i * 104}" y="106" fill="${c.text}">${t}  ▾</text>`).join("")}
  <rect x="890" y="84" width="276" height="34" rx="8" fill="${c.accent}"/><text x="1028" y="106" fill="${dark ? "#1C1C1E" : "#FFFFFF"}" text-anchor="middle" font-weight="600">Open a port…</text>
  <rect x="14" y="134" width="1152" height="44" rx="8" fill="${c.banner}"/>
  <text x="32" y="162" fill="${c.bannerText}" font-weight="600">1 Block rule overrides an Allow rule for TCP 8080.</text>
  <text x="1148" y="162" fill="${c.bannerText}" text-anchor="end" font-weight="600">Review ›</text>
  ${head.map((h, i) => `<text x="${cols[i]}" y="212" fill="${c.sub}" font-weight="600" font-size="13">${h}</text>`).join("")}
  <line x1="12" x2="1168" y1="224" y2="224" stroke="${c.line}"/>
  ${rows}
  <rect y="690" width="1180" height="30" fill="${c.chrome}"/>
  <text x="14" y="710" fill="${c.sub}" font-size="12">847 rules  ·  loaded in 0.48 s</text>
  <text x="1166" y="710" fill="${c.sub}" font-size="12" text-anchor="end">Placeholder image: replace with a real screenshot</text>
</svg>`;
}

const cliLines = [
  ["p", "piewall conflicts"],
  ["o", "BLOCK  Block: python.exe            In   Any        Public"],
  ["o", "  overrides  ALLOW  mp4toinc-ui     In   TCP 8080   Public"],
  ["o", "  created by a dismissed firewall popup"],
  ["o", ""],
  ["o", "1 conflict found."],
  ["o", ""],
  ["p", "piewall open 8080 --profile public"],
  ["o", "Opened TCP 8080 inbound on Public (rule group: piewall)."],
  ["o", ""],
  ["p", "piewall close 8080"],
  ["o", "Removed 1 rule piewall created for 8080."],
];
const cliShot = `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="560" viewBox="0 0 1000 560" font-family="Cascadia Code, Consolas" font-size="17">
  <rect width="1000" height="560" fill="#0C0C0C"/>
  <rect width="1000" height="40" fill="#1C1C1E"/>
  <text x="18" y="26" fill="#A1A1A6" font-family="${FONT}" font-size="13">Windows PowerShell</text>
  ${cliLines.map(([k, t], i) => {
    const y = 84 + i * 32;
    if (k === "p") return `<text x="24" y="${y}"><tspan fill="#A1A1A6">PS C:\\&gt; </tspan><tspan fill="#F5F5F7">${t}</tspan></text>`;
    const fill = t.startsWith("BLOCK") ? "#FF453A" : t.includes("ALLOW") ? "#30D158" : "#D1D1D6";
    return `<text x="24" y="${y}" fill="${fill}" xml:space="preserve">${t}</text>`;
  }).join("")}
  <text x="976" y="540" fill="#6E6E73" font-family="${FONT}" font-size="12" text-anchor="end">Placeholder image: replace with a real screenshot</text>
</svg>`;

const shots = [
  ["app-light.png", appShot(false), 2360],
  ["app-dark.png", appShot(true), 2360],
  ["cli.png", cliShot, 2000],
];
for (const [name, svg, w] of shots) {
  const out = resolve(pub, "images", name);
  if (existsSync(out) && !force) {
    console.log(`skip ${name} (exists)`);
    continue;
  }
  writeFileSync(out, render(svg, w));
  console.log(`wrote ${name}`);
}
console.log("favicons + og.png written");
