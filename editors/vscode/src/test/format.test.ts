import assert from "node:assert/strict";
import { test } from "node:test";

import { buildArgs, minimalEdit, runCommand } from "../format";

test("buildArgs includes config, stdin path and range", () => {
  assert.deepEqual(
    buildArgs({
      executable: "skillfmt",
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
