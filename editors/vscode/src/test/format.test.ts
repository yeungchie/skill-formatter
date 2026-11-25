import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildArgs,
  candidateCommands,
  changedSpan,
  containsSpan,
  describeCommand,
  invocationArgs,
  minimalEdit,
  parseVersion,
  resolveCommand,
  runCommand,
  versionAtLeast,
} from "../format";

test("candidateCommands prefers local skfmt, then uvx, then uv", () => {
  assert.deepEqual(candidateCommands(), [
    { command: "skfmt", prefixArgs: [], source: "local" },
    { command: "uvx", prefixArgs: ["skfmt"], source: "uvx" },
    { command: "uv", prefixArgs: ["tool", "run", "skfmt"], source: "uv" },
  ]);
});

test("candidateCommands honors an explicit executable", () => {
  assert.deepEqual(candidateCommands("/opt/skfmt"), [
    { command: "/opt/skfmt", prefixArgs: [], source: "configured" },
  ]);
});

test("invocationArgs adds the uvx prefix", () => {
  assert.deepEqual(
    invocationArgs(
      { command: "uvx", prefixArgs: ["skfmt"], source: "uvx" },
      { extraArgs: [], stdinPath: "a.il", lines: "2:3", timeoutMs: 1000 },
    ),
    ["skfmt", "format", "--stdin-path", "a.il", "--lines", "2:3"],
  );
});

test("resolveCommand prefers a configured executable", async () => {
  let probed = false;
  const resolved = await resolveCommand(
    { executable: "/opt/skfmt", extraArgs: [], timeoutMs: 1000 },
    async () => {
      probed = true;
      return false;
    },
  );
  assert.deepEqual(resolved, {
    command: "/opt/skfmt",
    prefixArgs: [],
    source: "configured",
  });
  assert.equal(probed, false);
});

test("resolveCommand prefers local skfmt", async () => {
  const order: string[] = [];
  const resolved = await resolveCommand(
    { extraArgs: [], timeoutMs: 1000 },
    async (command) => {
      order.push(command);
      return command === "skfmt";
    },
  );
  assert.deepEqual(resolved, { command: "skfmt", prefixArgs: [], source: "local" });
  assert.deepEqual(order, ["skfmt"]);
});

test("resolveCommand falls back to uvx then uv", async () => {
  const uvx = await resolveCommand(
    { extraArgs: [], timeoutMs: 1000 },
    async (command) => command === "uvx",
  );
  assert.deepEqual(uvx, { command: "uvx", prefixArgs: ["skfmt"], source: "uvx" });
  const uv = await resolveCommand(
    { extraArgs: [], timeoutMs: 1000 },
    async (command) => command === "uv",
  );
  assert.deepEqual(uv, {
    command: "uv",
    prefixArgs: ["tool", "run", "skfmt"],
    source: "uv",
  });
});

test("resolveCommand returns null when nothing is available", async () => {
  assert.equal(
    await resolveCommand({ extraArgs: [], timeoutMs: 1000 }, async () => false),
    null,
  );
});

test("describeCommand joins the prefix args", () => {
  assert.equal(
    describeCommand({ command: "uvx", prefixArgs: ["skfmt"], source: "uvx" }),
    "uvx skfmt",
  );
});

test("buildArgs includes config, stdin path and range", () => {
  assert.deepEqual(
    buildArgs({
      executable: "skfmt",
      configPath: "cfg.toml",
      extraArgs: ["--cats", "eol"],
      stdinPath: "a.il",
      lines: "3:5",
      timeoutMs: 1000,
    }),
    [
      "format",
      "--config",
      "cfg.toml",
      "--stdin-path",
      "a.il",
      "--lines",
      "3:5",
      "--cats",
      "eol",
    ],
  );
});

test("minimalEdit returns null when unchanged", () => {
  assert.equal(minimalEdit("a\n", "a\n"), null);
});

test("minimalEdit finds the changed span", () => {
  assert.deepEqual(minimalEdit("foo(a)\n", "foo( a )\n"), {
    start: 4,
    end: 5,
    text: " a ",
  });
});

test("changedSpan stays inside the selected lines", () => {
  const inside = changedSpan("foo( 1 )\nbar( 3 )\n", "foo(1)\nbar( 3 )\n");
  assert.ok(inside);
  assert.equal(containsSpan({ start: 0, end: 9 }, inside), true);
});

test("changedSpan detects edits outside the selected lines", () => {
  const outside = changedSpan("foo( 1 )\nbar( 3 )\n", "foo(1)\nbar(3)\n");
  assert.ok(outside);
  assert.equal(containsSpan({ start: 0, end: 9 }, outside), false);
});

test("parseVersion reads skfmt --version output", () => {
  assert.equal(parseVersion("skfmt 0.2.0\n"), "0.2.0");
  assert.equal(parseVersion("no version here"), null);
});

test("versionAtLeast compares numeric components", () => {
  assert.equal(versionAtLeast("0.2.0", "0.2.0"), true);
  assert.equal(versionAtLeast("0.1.9", "0.2.0"), false);
  assert.equal(versionAtLeast("0.10.0", "0.2.0"), true);
  assert.equal(versionAtLeast("1.0.0", "0.2.0"), true);
});

test("runFormatter pipes stdin to stdout", async () => {
  const result = await runCommand(
    process.execPath,
    ["-e", "process.stdin.pipe(process.stdout)"],
    "hello\n",
    5000,
  );
  assert.equal(result.code, 0);
  assert.equal(result.stdout, "hello\n");
});
