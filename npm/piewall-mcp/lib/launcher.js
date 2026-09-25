// piewall-mcp launcher: downloads the verified piewall-mcp.exe from the GitHub release
// and runs it. stdout belongs to the MCP stdio channel, so every log line goes to stderr.

import { spawn, spawnSync } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { createReadStream, createWriteStream, existsSync, readFileSync } from "node:fs";
import { mkdir, rename, rm, stat } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { Readable, Transform } from "node:stream";
import { pipeline } from "node:stream/promises";
import { fileURLToPath } from "node:url";

export const EXE_NAME = "piewall-mcp.exe";
export const SUMS_NAME = "SHA256SUMS.txt";
export const REPO = "TheeraphatStudent/piewall";
export const IMAGE = "docker.io/th33raphat/piewall";
const DOWNLOAD_TIMEOUT_MS = 5 * 60 * 1000;

export class LauncherError extends Error {}

export function log(message) {
  process.stderr.write(`piewall-mcp: ${message}\n`);
}

export function packageVersion() {
  const pkg = fileURLToPath(new URL("../package.json", import.meta.url));
  return JSON.parse(readFileSync(pkg, "utf8")).version;
}

/** The release version to use: PIEWALL_VERSION (with or without a leading "v") or ours. */
export function resolveVersion(env = process.env) {
  // npm needs semver (0.2.0-rc1); the release tag follows pyproject/PEP 440 (v0.2.0rc1).
  const raw = (env.PIEWALL_VERSION || packageVersion())
    .trim()
    .replace(/^v/i, "")
    .replace(/^(\d+\.\d+\.\d+)-((?:a|b|rc)\d+)$/, "$1$2");
  // Used in a URL and a folder name: keep it to plain version characters.
  if (!/^[0-9A-Za-z][0-9A-Za-z.+-]*$/.test(raw)) {
    throw new LauncherError(`invalid PIEWALL_VERSION ${JSON.stringify(raw)}`);
  }
  return raw;
}

export function releaseBaseUrl(version, env = process.env) {
  const base = env.PIEWALL_MCP_DOWNLOAD_BASE?.replace(/\/+$/, "");
  return base ? `${base}/v${version}/` : `https://github.com/${REPO}/releases/download/v${version}/`;
}

/** %LOCALAPPDATA%\piewall\mcp\<version>\piewall-mcp.exe (PIEWALL_MCP_CACHE_DIR replaces the root). */
export function cachePath(version, env = process.env) {
  const root =
    env.PIEWALL_MCP_CACHE_DIR ||
    path.join(env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"), "piewall", "mcp");
  return path.join(root, version, EXE_NAME);
}

/** Parse `sha256sum` output ("<hash>  <file>" or "<hash> *<file>") into Map<file, hash>. */
export function parseChecksums(text) {
  const sums = new Map();
  for (const line of text.split(/\r?\n/)) {
    const m = /^([0-9a-fA-F]{64}) [ *](.+?)\s*$/.exec(line);
    if (m) sums.set(m[2], m[1].toLowerCase());
  }
  return sums;
}

export async function sha256File(file) {
  const hash = createHash("sha256");
  await pipeline(createReadStream(file), hash);
  return hash.digest("hex");
}

/** Throws unless `actual` matches the checksum listed for `name`. */
export function verifyChecksum(sums, name, actual) {
  const expected = sums.get(name);
  if (!expected) throw new LauncherError(`${SUMS_NAME} has no entry for ${name}`);
  if (expected !== actual.toLowerCase()) {
    throw new LauncherError(`checksum mismatch for ${name}: expected ${expected}, got ${actual}`);
  }
}

async function get(url, fetchImpl) {
  let res;
  try {
    // fetch follows redirects (GitHub sends release assets to a CDN).
    res = await fetchImpl(url, {
      redirect: "follow",
      headers: { "user-agent": "piewall-mcp-launcher" },
      signal: AbortSignal.timeout(DOWNLOAD_TIMEOUT_MS),
    });
  } catch (err) {
    throw new LauncherError(`download failed: ${url}: ${err.cause?.message || err.message}`);
  }
  return res;
}

function notPublished(version, what) {
  return new LauncherError(
    `${what}.\n` +
      `  piewall-mcp.exe ships only with releases that include the MCP server (v0.1.0 does not). Options:\n` +
      `  - set PIEWALL_VERSION to a release that has it: https://github.com/${REPO}/releases\n` +
      `  - or set PIEWALL_MCP_EXE to a local piewall-mcp.exe`,
  );
}

/**
 * Download piewall-mcp.exe for `version` into `dest`, verify it against SHA256SUMS.txt and
 * move it into place atomically (temp file + rename). Returns `dest`.
 */
export async function download(version, dest, { env = process.env, fetchImpl = globalThis.fetch } = {}) {
  const base = releaseBaseUrl(version, env);

  const sumsRes = await get(base + SUMS_NAME, fetchImpl);
  if (sumsRes.status === 404) {
    throw notPublished(version, `piewall release v${version} not found (404 for ${base}${SUMS_NAME})`);
  }
  if (!sumsRes.ok) throw new LauncherError(`HTTP ${sumsRes.status} for ${base}${SUMS_NAME}`);
  const sums = parseChecksums(await sumsRes.text());
  if (!sums.has(EXE_NAME)) {
    throw notPublished(version, `piewall release v${version} has no ${EXE_NAME} (not listed in ${SUMS_NAME})`);
  }

  const exeRes = await get(base + EXE_NAME, fetchImpl);
  if (exeRes.status === 404) throw notPublished(version, `piewall release v${version} has no ${EXE_NAME} (404)`);
  if (!exeRes.ok || !exeRes.body) throw new LauncherError(`HTTP ${exeRes.status} for ${base}${EXE_NAME}`);

  const size = Number(exeRes.headers.get("content-length")) || 0;
  log(`downloading ${EXE_NAME} v${version}${size ? ` (${(size / 1048576).toFixed(1)} MB)` : ""}`);

  await mkdir(path.dirname(dest), { recursive: true });
  const tmp = `${dest}.${process.pid}.${randomBytes(4).toString("hex")}.tmp`;
  const hash = createHash("sha256");
  const tap = new Transform({
    transform(chunk, _enc, cb) {
      hash.update(chunk);
      cb(null, chunk);
    },
  });
  try {
    await pipeline(Readable.fromWeb(exeRes.body), tap, createWriteStream(tmp));
    verifyChecksum(sums, EXE_NAME, hash.digest("hex"));
    try {
      await rename(tmp, dest);
    } catch (err) {
      // Another launcher won the race and the exe is in use: theirs is the same verified file.
      if (!existsSync(dest)) throw err;
    }
  } finally {
    await rm(tmp, { force: true });
  }
  log(`verified SHA-256, cached at ${dest}`);
  return dest;
}

/** Path of the exe to run: PIEWALL_MCP_EXE, the cache, or a fresh download. */
export async function ensureExe({ env = process.env, fetchImpl } = {}) {
  if (env.PIEWALL_MCP_EXE) {
    const exe = path.resolve(env.PIEWALL_MCP_EXE);
    if (!existsSync(exe)) throw new LauncherError(`PIEWALL_MCP_EXE not found: ${exe}`);
    return exe;
  }
  const version = resolveVersion(env);
  const dest = cachePath(version, env);
  try {
    if ((await stat(dest)).size > 0) return dest; // verified when it was written
  } catch {
    // not cached yet
  }
  return download(version, dest, { env, fetchImpl });
}

/** Run `exe` with `args`, stdio inherited; resolves with the exit code or re-raises the signal. */
export function runChild(exe, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(exe, args, { stdio: "inherit", windowsHide: true });
    const signals = ["SIGINT", "SIGTERM", "SIGBREAK", "SIGHUP"];
    const forward = (sig) => {
      // Ctrl+C / Ctrl+Break already reach a Windows child sharing our console; let it shut down cleanly.
      if (process.platform === "win32" && (sig === "SIGINT" || sig === "SIGBREAK")) return;
      if (child.exitCode === null) child.kill(sig);
    };
    for (const sig of signals) process.on(sig, forward);
    const cleanup = () => {
      for (const sig of signals) process.off(sig, forward);
    };
    child.on("error", (err) => {
      cleanup();
      reject(new LauncherError(`could not start ${exe}: ${err.message}`));
    });
    child.on("exit", (code, signal) => {
      cleanup();
      resolve(signal ? { signal } : { code: code ?? 1 });
    });
  });
}

function findContainerRuntime() {
  for (const cmd of ["docker", "podman"]) {
    const probe = spawnSync(cmd, ["--version"], { stdio: "ignore", shell: false });
    if (probe.status === 0) return cmd;
  }
  return null;
}

/** Split our own flags off: --docker and --rules-file (only meaningful with --docker). */
export function parseLauncherArgs(argv) {
  const rest = [];
  let docker = false;
  let rulesFile = null;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--docker") docker = true;
    else if (a === "--rules-file" && i + 1 < argv.length) rulesFile = argv[++i];
    else if (a.startsWith("--rules-file=")) rulesFile = a.slice("--rules-file=".length);
    else rest.push(a);
  }
  return { docker, rulesFile, rest, argv };
}

export function dockerArgs(rulesFile, extra = []) {
  return ["run", "-i", "--rm", "-v", `${path.resolve(rulesFile)}:/data/rules.json:ro`, IMAGE, ...extra];
}

export const NON_WINDOWS_HELP = `piewall-mcp manages the Windows Firewall, so live mode needs Windows.

To analyse rules on this machine, export them on Windows first:
    piewall-cli export rules.json
then run the read-only server in a container:
    podman run -i --rm -v ./rules.json:/data/rules.json:ro ${IMAGE}
(docker works the same way), or let this launcher do it:
    npx -y piewall-mcp --docker --rules-file ./rules.json
`;

async function runDocker(opts, env) {
  const rulesFile = opts.rulesFile || env.PIEWALL_RULES_FILE || "rules.json";
  if (!existsSync(rulesFile)) {
    throw new LauncherError(`rules file not found: ${path.resolve(rulesFile)} (use --rules-file PATH)`);
  }
  const runtime = findContainerRuntime();
  if (!runtime) throw new LauncherError("--docker needs docker or podman on PATH");
  const args = dockerArgs(rulesFile, opts.rest);
  log(`${runtime} ${args.join(" ")}`);
  return runChild(runtime, args);
}

export async function main(argv = process.argv.slice(2), { env = process.env, platform = process.platform } = {}) {
  try {
    const opts = parseLauncherArgs(argv);
    let result;
    if (opts.docker) {
      result = await runDocker(opts, env);
    } else if (platform !== "win32") {
      process.stderr.write(NON_WINDOWS_HELP);
      return 1;
    } else {
      const exe = await ensureExe({ env });
      result = await runChild(exe, argv);
    }
    if (result.signal) {
      process.kill(process.pid, result.signal);
      return 1;
    }
    return result.code;
  } catch (err) {
    if (err instanceof LauncherError) {
      log(err.message);
      return 1;
    }
    throw err;
  }
}
