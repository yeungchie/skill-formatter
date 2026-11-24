import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildArgs,
  changedSpan,
  containsSpan,
  minimalEdit,
  parseVersion,
  runCommand,
  versionAtLeast,
} from "../format";

test("buildArgs includes config, stdin path and range", () => {
  assert.deepEqual(
    buildArgs({
      executable: "skill-formatter",
      configPath: "cfg.toml",
      extraArgs: ["--skip", "comments"],
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
      "--skip",
      "comments",
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

test("parseVersion reads skill-formatter --version output", () => {
  assert.equal(parseVersion("skill-formatter 0.2.0\n"), "0.2.0");
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
