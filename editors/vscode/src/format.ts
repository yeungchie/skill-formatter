import { spawn } from "node:child_process";

export interface FormatOptions {
  executable: string;
  configPath?: string;
  extraArgs: string[];
  stdinPath?: string;
  lines?: string;
  timeoutMs: number;
}

export interface RunResult {
  code: number;
  stdout: string;
  stderr: string;
}

export interface MinimalEdit {
  start: number;
  end: number;
  text: string;
}

export function buildArgs(options: FormatOptions): string[] {
  const args: string[] = [];
  if (options.configPath) {
    args.push("--config", options.configPath);
  }
  if (options.stdinPath) {
    args.push("--stdin-path", options.stdinPath);
  }
  if (options.lines) {
    args.push("--lines", options.lines);
  }
  args.push(...options.extraArgs);
  return args;
}

export function runFormatter(options: FormatOptions, text: string): Promise<RunResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(options.executable, buildArgs(options), {
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    let timer: NodeJS.Timeout | undefined;
    const finish = (code: number): void => {
      if (timer) {
        clearTimeout(timer);
      }
      resolve({
        code,
        stdout: Buffer.concat(stdout).toString("utf8"),
        stderr: Buffer.concat(stderr).toString("utf8"),
      });
    };
    child.stdout.on("data", (chunk: Buffer) => stdout.push(chunk));
    child.stderr.on("data", (chunk: Buffer) => stderr.push(chunk));
    child.on("error", (error) => {
      if (timer) {
        clearTimeout(timer);
      }
      reject(error);
    });
    child.on("close", (code) => finish(code ?? 2));
    timer = setTimeout(() => {
      child.kill();
      reject(new Error(`skillfmt timed out after ${options.timeoutMs} ms`));
    }, options.timeoutMs);
    child.stdin.end(text);
  });
}

export function minimalEdit(before: string, after: string): MinimalEdit | null {
  if (before === after) {
    return null;
  }
  let start = 0;
  const max = Math.min(before.length, after.length);
  while (start < max && before[start] === after[start]) {
    start += 1;
  }
  let beforeEnd = before.length;
  let afterEnd = after.length;
  while (
    beforeEnd > start &&
    afterEnd > start &&
    before[beforeEnd - 1] === after[afterEnd - 1]
  ) {
    beforeEnd -= 1;
    afterEnd -= 1;
  }
  return { start, end: beforeEnd, text: after.slice(start, afterEnd) };
}
