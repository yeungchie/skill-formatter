import { spawn } from "node:child_process";

export const MIN_CLI_VERSION = "0.1.0";
export const TOOL_NAME = "skfmt";
export const CONFIG_SECTION = TOOL_NAME;

export interface FormatOptions {
  executable?: string;
  configPath?: string;
  extraArgs: string[];
  stdinPath?: string;
  lines?: string;
  timeoutMs: number;
}

export type CommandSource = "configured" | "local" | "uvx" | "uv";

export interface ResolvedCommand {
  command: string;
  prefixArgs: string[];
  source: CommandSource;
}

export type CommandProbe = (command: string, args: string[]) => Promise<boolean>;

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

export interface Span {
  start: number;
  end: number;
}

export function parseVersion(output: string): string | null {
  const match = output.match(/\b(\d+)\.(\d+)\.(\d+)\b/);
  return match ? `${match[1]}.${match[2]}.${match[3]}` : null;
}

export function versionAtLeast(version: string, minimum: string): boolean {
  const found = parseVersion(version);
  const required = parseVersion(minimum);
  if (!found || !required) {
    return false;
  }
  const left = found.split(".").map(Number);
  const right = required.split(".").map(Number);
  for (let index = 0; index < 3; index += 1) {
    if (left[index] !== right[index]) {
      return left[index] > right[index];
    }
  }
  return true;
}

export function buildArgs(options: FormatOptions): string[] {
  const args: string[] = ["format"];
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

export function candidateCommands(configured?: string): ResolvedCommand[] {
  if (configured) {
    return [{ command: configured, prefixArgs: [], source: "configured" }];
  }
  return [
    { command: TOOL_NAME, prefixArgs: [], source: "local" },
    { command: "uvx", prefixArgs: [TOOL_NAME], source: "uvx" },
    { command: "uv", prefixArgs: ["tool", "run", TOOL_NAME], source: "uv" },
  ];
}

export function invocationArgs(resolved: ResolvedCommand, options: FormatOptions): string[] {
  return [...resolved.prefixArgs, ...buildArgs(options)];
}

export async function resolveCommand(
  options: FormatOptions,
  probe: CommandProbe,
): Promise<ResolvedCommand | null> {
  for (const candidate of candidateCommands(options.executable)) {
    if (candidate.source === "configured") {
      return candidate;
    }
    if (await probe(candidate.command, ["--version"])) {
      return candidate;
    }
  }
  return null;
}

export function describeCommand(resolved: ResolvedCommand): string {
  return [resolved.command, ...resolved.prefixArgs].join(" ");
}

export function runCommand(
  executable: string,
  args: string[],
  text: string,
  timeoutMs: number,
): Promise<RunResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, {
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
      reject(new Error(`${TOOL_NAME} timed out after ${timeoutMs} ms`));
    }, timeoutMs);
    child.stdin.end(text);
  });
}

export function runFormatter(
  resolved: ResolvedCommand,
  options: FormatOptions,
  text: string,
): Promise<RunResult> {
  return runCommand(
    resolved.command,
    invocationArgs(resolved, options),
    text,
    options.timeoutMs,
  );
}

export function minimalEdit(before: string, after: string): MinimalEdit | null {
  const span = changedSpan(before, after);
  if (!span) {
    return null;
  }
  const afterEnd = after.length - (before.length - span.end);
  return { start: span.start, end: span.end, text: after.slice(span.start, afterEnd) };
}

export function changedSpan(before: string, after: string): Span | null {
  if (before === after) {
    return null;
  }
  let start = 0;
  const max = Math.min(before.length, after.length);
  while (start < max && before[start] === after[start]) {
    start += 1;
  }
  let suffix = 0;
  const limit = max - start;
  while (suffix < limit && before[before.length - 1 - suffix] === after[after.length - 1 - suffix]) {
    suffix += 1;
  }
  return { start, end: before.length - suffix };
}

export function containsSpan(outer: Span, inner: Span): boolean {
  return inner.start >= outer.start && inner.end <= outer.end;
}
