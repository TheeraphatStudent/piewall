import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { after, before, describe, test } from "node:test";

import {
  EXE_NAME,
  LauncherError,
  cachePath,
  dockerArgs,
  download,
  ensureExe,
  main,
  packageVersion,
  parseChecksums,
  parseLauncherArgs,
  resolveVersion,
  sha256File,
  verifyChecksum,
} from "../lib/launcher.js";

const sha = (buf) => createHash("sha256").update(buf).digest("hex");
const tmpdir = () => mkdtempSync(path.join(os.tmpdir(), "piewall-mcp-test-"));

describe("checksums", () => {
  const a = "a".repeat(64);
  const B = "B".repeat(64);

  test("parses sha256sum text and binary lines, CRLF, junk", () => {
    const sums = parseChecksums(`${a}  piewall-mcp.exe\r\n${B} *piewall.exe\n\n# comment\nnot a line\n`);
    assert.equal(sums.get("piewall-mcp.exe"), a);
    assert.equal(sums.get("piewall.exe"), "b".repeat(64));
    assert.equal(sums.size, 2);
  });

  test("verifyChecksum accepts a match, case-insensitively", () => {
    verifyChecksum(new Map([[EXE_NAME, a]]), EXE_NAME, a.toUpperCase());
  });

  test("verifyChecksum rejects a mismatch and a missing entry", () => {
    const sums = new Map([[EXE_NAME, a]]);
    assert.throws(() => verifyChecksum(sums, EXE_NAME, "c".repeat(64)), /checksum mismatch/);
    assert.throws(() => verifyChecksum(sums, "other.exe", a), /no entry for other.exe/);
  });

  test("sha256File hashes a file", async () => {
    const dir = tmpdir();
    const file = path.join(dir, "x.bin");
    writeFileSync(file, "hello");
    assert.equal(await sha256File(file), sha("hello"));
    rmSync(dir, { recursive: true, force: true });
  });
});

describe("version and cache path", () => {
  test("defaults to the package version", () => {
    assert.equal(resolveVersion({}), packageVersion());
  });

  test("PIEWALL_VERSION overrides, with or without v, semver prerelease -> PEP 440 tag", () => {
    assert.equal(resolveVersion({ PIEWALL_VERSION: "v1.2.3" }), "1.2.3");
    assert.equal(resolveVersion({ PIEWALL_VERSION: "0.2.0-rc1" }), "0.2.0rc1");
    assert.throws(() => resolveVersion({ PIEWALL_VERSION: "../../evil" }), LauncherError);
  });

  test("cache lives in %LOCALAPPDATA%\\piewall\\mcp\\<version>", () => {
    const p = cachePath("1.2.3", { LOCALAPPDATA: path.join("C:", "Users", "u", "AppData", "Local") });
    assert.equal(p, path.join("C:", "Users", "u", "AppData", "Local", "piewall", "mcp", "1.2.3", "piewall-mcp.exe"));
  });

  test("PIEWALL_MCP_CACHE_DIR replaces the cache root", () => {
    assert.equal(cachePath("1.2.3", { PIEWALL_MCP_CACHE_DIR: "/tmp/c" }), path.join("/tmp/c", "1.2.3", EXE_NAME));
  });
});

describe("download from a mock release server", () => {
  const exeBody = Buffer.from("MZ fake piewall-mcp.exe payload ".repeat(1000));
  let server;
  let base;
  let sumsFor; // version -> SHA256SUMS.txt body
  const hits = [];

  before(async () => {
    sumsFor = {
      "1.2.3": `${sha(exeBody)}  ${EXE_NAME}\n${"0".repeat(64)}  piewall.exe\n`,
      "6.6.6": `${"f".repeat(64)}  ${EXE_NAME}\n`, // wrong hash
      "0.1.0": `${"0".repeat(64)}  piewall.exe\n`, // release without piewall-mcp.exe
    };
    server = http.createServer((req, res) => {
      hits.push(req.url);
      const m = /^\/v([^/]+)\/(.+)$/.exec(req.url);
      if (req.url === "/cdn/blob") {
        res.writeHead(200, { "content-length": exeBody.length }).end(exeBody);
      } else if (m && m[2] === "SHA256SUMS.txt" && sumsFor[m[1]]) {
        res.writeHead(200).end(sumsFor[m[1]]);
      } else if (m && m[2] === EXE_NAME && m[1] !== "0.1.0") {
        // GitHub answers with a redirect to its CDN.
        res.writeHead(302, { location: "/cdn/blob" }).end();
      } else {
        res.writeHead(404).end("Not Found");
      }
    });
    await new Promise((r) => server.listen(0, "127.0.0.1", r));
    base = `http://127.0.0.1:${server.address().port}`;
  });
  after(() => server.close());

  test("downloads through a redirect, verifies and caches atomically", async () => {
    const dir = tmpdir();
    const env = { PIEWALL_MCP_DOWNLOAD_BASE: base, PIEWALL_MCP_CACHE_DIR: dir, PIEWALL_VERSION: "1.2.3" };
    const exe = await ensureExe({ env });
    assert.equal(exe, path.join(dir, "1.2.3", EXE_NAME));
    assert.deepEqual(readFileSync(exe), exeBody);
    assert.deepEqual(readdirSync(path.dirname(exe)), [EXE_NAME]); // no temp files left
    assert.ok(hits.includes("/cdn/blob"));

    // Second call is served from the cache, no network.
    const failing = () => Promise.reject(new Error("network used"));
    assert.equal(await ensureExe({ env, fetchImpl: failing }), exe);
    rmSync(dir, { recursive: true, force: true });
  });

  test("a checksum mismatch leaves nothing behind", async () => {
    const dir = tmpdir();
    const dest = path.join(dir, "6.6.6", EXE_NAME);
    await assert.rejects(
      download("6.6.6", dest, { env: { PIEWALL_MCP_DOWNLOAD_BASE: base } }),
      /checksum mismatch/,
    );
    assert.equal(existsSync(dest), false);
    assert.deepEqual(readdirSync(path.dirname(dest)), []);
    rmSync(dir, { recursive: true, force: true });
  });

  test("a release without piewall-mcp.exe gives a helpful error", async () => {
    const dir = tmpdir();
    await assert.rejects(
      download("0.1.0", path.join(dir, EXE_NAME), { env: { PIEWALL_MCP_DOWNLOAD_BASE: base } }),
      (err) => err instanceof LauncherError && /has no piewall-mcp.exe/.test(err.message) && /PIEWALL_VERSION/.test(err.message),
    );
    rmSync(dir, { recursive: true, force: true });
  });

  test("a missing release gives a helpful error", async () => {
    await assert.rejects(
      download("9.9.9", path.join(tmpdir(), EXE_NAME), { env: { PIEWALL_MCP_DOWNLOAD_BASE: base } }),
      (err) => err instanceof LauncherError && /release v9.9.9 not found/.test(err.message),
    );
  });

  test("a network failure is a LauncherError", async () => {
    await assert.rejects(
      download("1.2.3", path.join(tmpdir(), EXE_NAME), { env: { PIEWALL_MCP_DOWNLOAD_BASE: "http://127.0.0.1:1" } }),
      (err) => err instanceof LauncherError && /download failed/.test(err.message),
    );
  });
});

describe("main", () => {
  function capture(fn) {
    const out = [];
    const err = [];
    const o = process.stdout.write;
    const e = process.stderr.write;
    process.stdout.write = (c) => out.push(String(c)) || true;
    process.stderr.write = (c) => err.push(String(c)) || true;
    return fn().finally(() => {
      process.stdout.write = o;
      process.stderr.write = e;
    }).then((code) => ({ code, out: out.join(""), err: err.join("") }));
  }

  test("non-Windows prints container guidance to stderr only and exits 1", async () => {
    const r = await capture(() => main([], { env: {}, platform: "linux" }));
    assert.equal(r.code, 1);
    assert.equal(r.out, "");
    assert.match(r.err, /podman run -i --rm -v \.\/rules\.json:\/data\/rules\.json:ro docker\.io\/th33raphat\/piewall/);
  });

  test("a missing PIEWALL_MCP_EXE is reported on stderr", async () => {
    const r = await capture(() => main([], { env: { PIEWALL_MCP_EXE: "C:/nope/piewall-mcp.exe" }, platform: "win32" }));
    assert.equal(r.code, 1);
    assert.equal(r.out, "");
    assert.match(r.err, /PIEWALL_MCP_EXE not found/);
  });

  test("--docker argument handling", () => {
    const o = parseLauncherArgs(["--docker", "--rules-file", "r.json", "--transport", "stdio"]);
    assert.equal(o.docker, true);
    assert.equal(o.rulesFile, "r.json");
    assert.deepEqual(o.rest, ["--transport", "stdio"]);
    const args = dockerArgs("r.json");
    assert.deepEqual(args.slice(0, 4), ["run", "-i", "--rm", "-v"]);
    assert.equal(args[4], `${path.resolve("r.json")}:/data/rules.json:ro`);
    assert.equal(args[5], "docker.io/th33raphat/piewall");
  });
});
