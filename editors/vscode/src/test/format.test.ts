import assert from "node:assert/strict";
import { test } from "node:test";

import { buildArgs, minimalEdit, runFormatter } from "../format";

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
  const result = await runFormatter(
    {
      executable: process.execPath,
      extraArgs: ["-e", "process.stdin.pipe(process.stdout)"],
      timeoutMs: 5000,
    },
    "hello\n",
  );
  assert.equal(result.code, 0);
  assert.equal(result.stdout, "hello\n");
});
