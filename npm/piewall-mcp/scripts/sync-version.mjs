#!/usr/bin/env node
// Copy `version` from the repo's pyproject.toml into npm/piewall-mcp/package.json.
// The launcher downloads piewall-mcp.exe from the GitHub release v<package version>, so the two
// must match. Run after bumping pyproject.toml:  node npm/piewall-mcp/scripts/sync-version.mjs
// --check exits 1 (without writing) when they differ; CI uses it.
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const pkgFile = fileURLToPath(new URL("../package.json", import.meta.url));
const pyproject = fileURLToPath(new URL("../../../pyproject.toml", import.meta.url));

const project = readFileSync(pyproject, "utf8").split(/^\[/m).find((s) => s.startsWith("project]"));
const match = project && /^version\s*=\s*"([^"]+)"/m.exec(project);
if (!match) {
  console.error(`could not read [project] version from ${pyproject}`);
  process.exit(2);
}
// PEP 440 pre-releases (0.2.0rc1) become semver (0.2.0-rc1).
const version = match[1].replace(/^(\d+\.\d+\.\d+)((?:a|b|rc)\d+)$/, "$1-$2");
if (!/^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$/.test(version)) {
  console.error(`pyproject version ${match[1]} has no npm (semver) equivalent`);
  process.exit(2);
}

const text = readFileSync(pkgFile, "utf8");
const pkg = JSON.parse(text);
if (pkg.version === version) {
  console.error(`package.json already at ${version}`);
  process.exit(0);
}
if (process.argv.includes("--check")) {
  console.error(`version mismatch: pyproject.toml ${match[1]} vs package.json ${pkg.version}`);
  process.exit(1);
}
pkg.version = version;
writeFileSync(pkgFile, JSON.stringify(pkg, null, 2) + "\n");
console.error(`package.json version ${text.match(/"version":\s*"([^"]+)"/)[1]} -> ${version}`);
